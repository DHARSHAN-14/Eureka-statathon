import csv
import io
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone

import numpy as np
import psycopg2
import psycopg2.extras
from psycopg2 import pool
from pgvector.psycopg2 import register_vector


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/statathon_nco",
)

_DB_POOL = None
_DB_POOL_MIN = int(os.getenv("DB_POOL_MIN", "1"))
_DB_POOL_MAX = int(os.getenv("DB_POOL_MAX", "8"))


def _get_pool():
    global _DB_POOL
    if _DB_POOL is None:
        _DB_POOL = pool.ThreadedConnectionPool(_DB_POOL_MIN, _DB_POOL_MAX, DATABASE_URL)
    return _DB_POOL

OCCUPATION_FIELDS = [
    "S No",
    "Occupational Title",
    "NCO 2015",
    "NCO 2004",
    "Division",
    "Sub Division",
    "Group",
    "Family",
    "Division Description",
    "Sub Division Description",
    "Group Description",
    "Family Description",
    "Occupation Description",
]


_pgvector_available = None  # tri-state: None = unknown, True/False = tested


@contextmanager
def get_conn():
    global _pgvector_available
    conn = _get_pool().getconn()
    try:
        # Register the pgvector type so numpy arrays can be passed as vector columns.
        # Gracefully skip if the extension is not installed — the main search uses
        # FAISS in-memory and does not require pgvector.
        if _pgvector_available is not False:
            try:
                register_vector(conn)
                _pgvector_available = True
            except Exception:
                if _pgvector_available is None:
                    print("Warning: pgvector extension not available — native vector search disabled.")
                    _pgvector_available = False
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _get_pool().putconn(conn)


def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS occupations (
                    id SERIAL PRIMARY KEY,
                    s_no TEXT,
                    occupation_title TEXT NOT NULL,
                    nco_2015 TEXT NOT NULL UNIQUE,
                    nco_2004 TEXT,
                    division TEXT NOT NULL,
                    sub_division TEXT NOT NULL,
                    occupation_group TEXT NOT NULL,
                    family TEXT NOT NULL,
                    division_description TEXT DEFAULT '',
                    sub_division_description TEXT DEFAULT '',
                    group_description TEXT DEFAULT '',
                    family_description TEXT DEFAULT '',
                    occupation_description TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                DROP INDEX IF EXISTS ux_occupations_nco_2004_present;

                CREATE TABLE IF NOT EXISTS prompt_history (
                    id BIGSERIAL PRIMARY KEY,
                    ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    query TEXT DEFAULT '',
                    translated_query TEXT DEFAULT '',
                    was_translated BOOLEAN DEFAULT FALSE,
                    occupation_title TEXT DEFAULT '',
                    nco_code TEXT DEFAULT '',
                    top_k INTEGER,
                    returned_count INTEGER,
                    client_ip TEXT DEFAULT '',
                    raw JSONB NOT NULL DEFAULT '{}'::jsonb
                );

                CREATE INDEX IF NOT EXISTS ix_prompt_history_ts
                    ON prompt_history (ts DESC);
                CREATE INDEX IF NOT EXISTS ix_prompt_history_occupation
                    ON prompt_history (occupation_title);

                CREATE TABLE IF NOT EXISTS search_documents (
                    row_id INTEGER PRIMARY KEY REFERENCES occupations(id) ON DELETE CASCADE,
                    document TEXT NOT NULL,
                    metadata JSONB NOT NULL
                );

                CREATE TABLE IF NOT EXISTS nco_graph (
                    nco_code TEXT PRIMARY KEY,
                    sector TEXT DEFAULT 'unknown',
                    keywords TEXT[] NOT NULL DEFAULT '{}',
                    payload JSONB NOT NULL DEFAULT '{}'::jsonb
                );

                CREATE TABLE IF NOT EXISTS search_assets (
                    name TEXT PRIMARY KEY,
                    data BYTEA NOT NULL,
                    content_type TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS admin_users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(64) NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )

    # Add geo columns to prompt_history if they don't exist yet (safe for existing databases)
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("ALTER TABLE prompt_history ADD COLUMN IF NOT EXISTS geo_city TEXT DEFAULT '';")
                cur.execute("ALTER TABLE prompt_history ADD COLUMN IF NOT EXISTS geo_state TEXT DEFAULT '';")
                cur.execute("ALTER TABLE prompt_history ADD COLUMN IF NOT EXISTS geo_country TEXT DEFAULT '';")
                cur.execute("CREATE INDEX IF NOT EXISTS ix_prompt_history_geo_state ON prompt_history (geo_state);")
    except Exception as e:
        print(f"Warning: Failed to add geo columns to prompt_history: {e}")

    # Try enabling pg_trgm and GIN index in a separate transaction so failures don't abort init_db
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
                cur.execute("CREATE INDEX IF NOT EXISTS ix_occupations_title_trgm ON occupations USING gin (occupation_title gin_trgm_ops);")
    except Exception as e:
        print(f"Warning: Failed to initialize PostgreSQL pg_trgm extension or GIN index. Fallback to in-memory matching will be used. Error: {e}")

    # Enable pgvector and add embedding columns if not present
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                cur.execute("ALTER TABLE occupations ADD COLUMN IF NOT EXISTS embedding vector(384);")
                cur.execute("ALTER TABLE occupations ADD COLUMN IF NOT EXISTS title_embedding vector(384);")
                cur.execute("DROP INDEX IF EXISTS ix_occupations_embedding;")
                cur.execute("DROP INDEX IF EXISTS ix_occupations_title_embedding;")
    except Exception as e:
        print(f"Warning: Failed to initialize pgvector extension or embedding columns: {e}")


def safe_text(value):
    if value is None:
        return ""
    return str(value).strip()


def row_to_csv_dict(row):
    return {
        "S No": safe_text(row.get("s_no")),
        "Occupational Title": safe_text(row.get("occupation_title")),
        "NCO 2015": safe_text(row.get("nco_2015")),
        "NCO 2004": safe_text(row.get("nco_2004")),
        "Division": safe_text(row.get("division")),
        "Sub Division": safe_text(row.get("sub_division")),
        "Group": safe_text(row.get("occupation_group")),
        "Family": safe_text(row.get("family")),
        "Division Description": safe_text(row.get("division_description")),
        "Sub Division Description": safe_text(row.get("sub_division_description")),
        "Group Description": safe_text(row.get("group_description")),
        "Family Description": safe_text(row.get("family_description")),
        "Occupation Description": safe_text(row.get("occupation_description")),
    }


def csv_dict_to_params(row):
    return {
        "s_no": safe_text(row.get("S No")),
        "occupation_title": safe_text(row.get("Occupational Title")),
        "nco_2015": safe_text(row.get("NCO 2015")),
        "nco_2004": safe_text(row.get("NCO 2004")),
        "division": safe_text(row.get("Division")),
        "sub_division": safe_text(row.get("Sub Division")),
        "occupation_group": safe_text(row.get("Group")),
        "family": safe_text(row.get("Family")),
        "division_description": safe_text(row.get("Division Description")),
        "sub_division_description": safe_text(row.get("Sub Division Description")),
        "group_description": safe_text(row.get("Group Description")),
        "family_description": safe_text(row.get("Family Description")),
        "occupation_description": safe_text(row.get("Occupation Description")),
    }


def get_admin_setting(key):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM admin_settings WHERE key = %s", (key,))
            row = cur.fetchone()
            return row[0] if row else None


def set_admin_setting(key, value):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO admin_settings (key, value)
                VALUES (%s, %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                """,
                (key, value),
            )


# ── Admin user helpers (admin_users table) ────────────────────────────────────

def admin_user_exists():
    """Return True if at least one row exists in admin_users."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM admin_users LIMIT 1")
            return cur.fetchone() is not None


def get_admin_password_hash(username: str):
    """Return the stored password hash for *username*, or None if not found."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT password_hash FROM admin_users WHERE username = %s",
                (username,),
            )
            row = cur.fetchone()
            return row[0] if row else None


def create_admin_user(username: str, password_hash: str):
    """Insert a new admin user.  Raises IntegrityError if username already exists."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO admin_users (username, password_hash) VALUES (%s, %s)",
                (username, password_hash),
            )


# ─────────────────────────────────────────────────────────────────────────────


def list_occupations():
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT *
                FROM occupations
                ORDER BY id
                """
            )
            return [dict(row) for row in cur.fetchall()]


def get_occupation(row_id):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM occupations WHERE id = %s", (row_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def insert_occupation(row):
    params = csv_dict_to_params(row)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO occupations (
                    s_no, occupation_title, nco_2015, nco_2004, division,
                    sub_division, occupation_group, family, division_description,
                    sub_division_description, group_description, family_description,
                    occupation_description
                )
                VALUES (
                    %(s_no)s, %(occupation_title)s, %(nco_2015)s, %(nco_2004)s,
                    %(division)s, %(sub_division)s, %(occupation_group)s,
                    %(family)s, %(division_description)s,
                    %(sub_division_description)s, %(group_description)s,
                    %(family_description)s, %(occupation_description)s
                )
                RETURNING id
                """,
                params,
            )
            return cur.fetchone()[0]


def update_occupation(row_id, row):
    params = csv_dict_to_params(row)
    params["id"] = row_id
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE occupations SET
                    s_no = %(s_no)s,
                    occupation_title = %(occupation_title)s,
                    nco_2015 = %(nco_2015)s,
                    nco_2004 = %(nco_2004)s,
                    division = %(division)s,
                    sub_division = %(sub_division)s,
                    occupation_group = %(occupation_group)s,
                    family = %(family)s,
                    division_description = %(division_description)s,
                    sub_division_description = %(sub_division_description)s,
                    group_description = %(group_description)s,
                    family_description = %(family_description)s,
                    occupation_description = %(occupation_description)s,
                    updated_at = NOW()
                WHERE id = %(id)s
                """,
                params,
            )


def delete_occupation(row_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM occupations WHERE id = %s", (row_id,))


def next_s_no():
    rows = list_occupations()
    values = []
    for row in rows:
        try:
            values.append(int(row.get("s_no") or 0))
        except (TypeError, ValueError):
            pass
    return str(max(values) + 1 if values else 1)


def load_csv_rows():
    return OCCUPATION_FIELDS[:], [row_to_csv_dict(row) | {"_row_id": row["id"]} for row in list_occupations()]


def replace_occupations_from_csv(csv_path):
    init_db()
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        skipped_duplicates = []
        seen_nco_2015 = set()
        seen_nco_2004 = set()
        for line_number, csv_row in enumerate(reader, start=2):
            row = csv_dict_to_params(csv_row)
            nco_2015 = row["nco_2015"]
            if nco_2015 in seen_nco_2015:
                skipped_duplicates.append((line_number, nco_2015, row["occupation_title"]))
                continue
            seen_nco_2015.add(nco_2015)
            nco_2004 = row.get("nco_2004") or ""
            if nco_2004:
                if nco_2004 in seen_nco_2004:
                    row["nco_2004"] = ""
                else:
                    seen_nco_2004.add(nco_2004)
            rows.append(row)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE occupations RESTART IDENTITY CASCADE")
            for row in rows:
                cur.execute(
                    """
                    INSERT INTO occupations (
                        s_no, occupation_title, nco_2015, nco_2004, division,
                        sub_division, occupation_group, family,
                        division_description, sub_division_description,
                        group_description, family_description,
                        occupation_description
                    )
                    VALUES (
                        %(s_no)s, %(occupation_title)s, %(nco_2015)s,
                        %(nco_2004)s, %(division)s, %(sub_division)s,
                        %(occupation_group)s, %(family)s,
                        %(division_description)s, %(sub_division_description)s,
                        %(group_description)s, %(family_description)s,
                        %(occupation_description)s
                    )
                    """,
                    row,
                )
    if skipped_duplicates:
        preview = ", ".join(
            f"line {line_number}: {code} ({title})"
            for line_number, code, title in skipped_duplicates[:5]
        )
        if len(skipped_duplicates) > 5:
            preview += f", ... and {len(skipped_duplicates) - 5} more"
        print(
            f"Skipped {len(skipped_duplicates)} duplicate NCO 2015 rows from CSV; "
            f"kept the first occurrence. {preview}"
        )


def append_prompt_history(entry):
    raw = dict(entry)
    ts_value = raw.get("ts")
    try:
        ts = datetime.fromisoformat(ts_value.replace("Z", "+00:00")) if ts_value else datetime.now(timezone.utc)
    except Exception:
        ts = datetime.now(timezone.utc)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO prompt_history (
                    ts, query, translated_query, was_translated, occupation_title,
                    nco_code, top_k, returned_count, client_ip,
                    geo_city, geo_state, geo_country, raw
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    ts,
                    safe_text(raw.get("query")),
                    safe_text(raw.get("translated_query")),
                    bool(raw.get("was_translated")),
                    safe_text(raw.get("occupation_title")),
                    safe_text(raw.get("nco_code")),
                    raw.get("top_k"),
                    raw.get("returned_count"),
                    safe_text(raw.get("client_ip")),
                    safe_text(raw.get("geo_city")),
                    safe_text(raw.get("geo_state")),
                    safe_text(raw.get("geo_country")),
                    psycopg2.extras.Json(raw),
                ),
            )


def read_prompt_history(limit=5000, occupation_title=""):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            params = []
            where = ""
            if occupation_title:
                where = "WHERE occupation_title = %s"
                params.append(occupation_title)
            params.append(limit)
            cur.execute(
                f"""
                SELECT ts, query, translated_query, was_translated,
                       occupation_title, nco_code, top_k, returned_count,
                       client_ip, raw
                FROM prompt_history
                {where}
                ORDER BY ts DESC
                LIMIT %s
                """,
                params,
            )
            history = []
            for row in cur.fetchall():
                raw = dict(row.get("raw") or {})
                raw.update({
                    "ts": row["ts"].isoformat(),
                    "query": row["query"],
                    "translated_query": row["translated_query"],
                    "was_translated": row["was_translated"],
                    "occupation_title": row["occupation_title"],
                    "nco_code": row["nco_code"],
                    "top_k": row["top_k"],
                    "returned_count": row["returned_count"],
                    "client_ip": row["client_ip"],
                    "geo_city": row.get("geo_city", ""),
                    "geo_state": row.get("geo_state", ""),
                    "geo_country": row.get("geo_country", ""),
                })
                history.append(raw)
            return history


def replace_prompt_history_from_json(json_path):
    if not os.path.exists(json_path):
        return
    with open(json_path, "r", encoding="utf-8") as f:
        history = json.load(f)
    if not isinstance(history, list):
        return
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE prompt_history RESTART IDENTITY")
    for entry in history:
        append_prompt_history(entry)


def save_search_documents(documents, metadata):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE search_documents")
            for doc, meta in zip(documents, metadata):
                cur.execute(
                    """
                    INSERT INTO search_documents (row_id, document, metadata)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (row_id) DO UPDATE
                    SET document = EXCLUDED.document,
                        metadata = EXCLUDED.metadata
                    """,
                    (meta["row_id"], doc, psycopg2.extras.Json(meta)),
                )


def load_search_documents():
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT row_id, document, metadata FROM search_documents ORDER BY row_id")
            rows = cur.fetchall()
            return [row["document"] for row in rows], [dict(row["metadata"]) for row in rows]


def save_graph(gn):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE nco_graph")
            for code, payload in gn.items():
                cur.execute(
                    """
                    INSERT INTO nco_graph (nco_code, sector, keywords, payload)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        code,
                        safe_text(payload.get("sector")) or "unknown",
                        list(payload.get("keywords") or []),
                        psycopg2.extras.Json(payload),
                    ),
                )


def load_graph():
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT nco_code, sector, keywords, payload FROM nco_graph")
            graph = {}
            for row in cur.fetchall():
                payload = dict(row.get("payload") or {})
                payload.setdefault("sector", row.get("sector") or "unknown")
                payload.setdefault("keywords", list(row.get("keywords") or []))
                graph[row["nco_code"]] = payload
            return graph


def save_asset(name, data, content_type):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO search_assets (name, data, content_type, updated_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (name) DO UPDATE
                SET data = EXCLUDED.data,
                    content_type = EXCLUDED.content_type,
                    updated_at = NOW()
                """,
                (name, psycopg2.Binary(data), content_type),
            )


def load_asset(name):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT data FROM search_assets WHERE name = %s", (name,))
            row = cur.fetchone()
            return bytes(row[0]) if row else None


def save_occupation_embeddings(occupation_id, embedding, title_embedding):
    """Write doc + title embeddings for a single occupation row."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE occupations
                SET embedding = %s, title_embedding = %s
                WHERE id = %s
                """,
                (embedding, title_embedding, occupation_id),
            )


def save_all_embeddings(id_embedding_pairs):
    """Bulk-write (occupation_id, embedding, title_embedding) tuples."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            for occ_id, emb, title_emb in id_embedding_pairs:
                cur.execute(
                    """
                    UPDATE occupations
                    SET embedding = %s, title_embedding = %s
                    WHERE id = %s
                    """,
                    (emb, title_emb, occ_id),
                )


def vector_search(query_vec, title_vec, top_k=10, filters=None):
    """
    Native pgvector ANN search with optional pre-filtered WHERE clauses.

    Args:
        query_vec: 1-D numpy array (384,) — full-document query embedding.
        title_vec:  1-D numpy array (384,) — title-only query embedding.
        top_k:      Number of results to return.
        filters:    Optional dict with keys division/sub_division/group/family.

    Returns:
        List of dicts with occupation metadata and cosine similarity scores.
    """
    # Build optional WHERE conditions
    conditions = ["embedding IS NOT NULL"]
    params = []
    filter_map = {
        "division":     "division",
        "sub_division": "sub_division",
        "group":        "occupation_group",
        "family":       "family",
    }
    if filters:
        for filter_key, col_name in filter_map.items():
            val = filters.get(filter_key)
            if val:
                if isinstance(val, (list, tuple, set)):
                    non_empty = [str(v) for v in val if v]
                    if non_empty:
                        placeholders = ",".join(["%s"] * len(non_empty))
                        conditions.append(f"{col_name} IN ({placeholders})")
                        params.extend(non_empty)
                else:
                    conditions.append(f"{col_name} = %s")
                    params.append(str(val))

    where_clause = "WHERE " + " AND ".join(conditions)

    # Fetch doc-similarity candidates
    doc_params = params + [query_vec, top_k * 4]
    title_params = params + [title_vec, top_k * 4]

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT id, nco_2015, occupation_title, nco_2004, division,
                       sub_division, occupation_group, family,
                       occupation_description, family_description, group_description,
                       1 - (embedding <=> %s::vector) AS doc_score
                FROM occupations
                {where_clause}
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                [query_vec] + params + [query_vec, top_k * 4],
            )
            doc_rows = {row["id"]: dict(row) for row in cur.fetchall()}

            # Fetch title-similarity candidates
            cur.execute(
                f"""
                SELECT id,
                       1 - (title_embedding <=> %s::vector) AS title_score
                FROM occupations
                {where_clause}
                ORDER BY title_embedding <=> %s::vector
                LIMIT %s
                """,
                [title_vec] + params + [title_vec, top_k * 4],
            )
            title_rows = {row["id"]: float(row["title_score"]) for row in cur.fetchall()}

    # Merge doc + title scores
    ALPHA, BETA = 0.7, 0.3
    merged = {}
    for occ_id, row in doc_rows.items():
        doc_score = float(row["doc_score"])
        merged[occ_id] = {"row": row, "doc_score": doc_score, "title_score": 0.0}
    for occ_id, ts in title_rows.items():
        if occ_id in merged:
            merged[occ_id]["title_score"] = ts
        else:
            # In title results but not doc results — need the full row
            merged[occ_id] = {"row": doc_rows.get(occ_id, {}), "doc_score": 0.0, "title_score": ts}

    results = []
    for occ_id, data in merged.items():
        row = data["row"]
        if not row:
            continue
        doc_s = data["doc_score"]
        title_s = data["title_score"]
        final = min(max(ALPHA * doc_s, title_s), 1.0)
        results.append({
            "id": occ_id,
            "nco_2015": row.get("nco_2015", ""),
            "occupation_title": row.get("occupation_title", ""),
            "nco_2004": row.get("nco_2004", ""),
            "division": row.get("division", ""),
            "sub_division": row.get("sub_division", ""),
            "occupation_group": row.get("occupation_group", ""),
            "family": row.get("family", ""),
            "occupation_description": row.get("occupation_description", ""),
            "family_description": row.get("family_description", ""),
            "group_description": row.get("group_description", ""),
            "doc_score": doc_s,
            "title_score": title_s,
            "final_score": final,
        })

    results.sort(key=lambda x: x["final_score"], reverse=True)
    return results[:top_k]


# Cached unique occupation titles for difflib fallback
_cached_titles = []

def get_cached_titles():
    global _cached_titles
    if not _cached_titles:
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT DISTINCT occupation_title FROM occupations;")
                    _cached_titles = [r[0] for r in cur.fetchall() if r[0]]
        except Exception as e:
            print(f"Failed to load cached titles for difflib: {e}")
            try:
                _, rows = load_csv_rows()
                _cached_titles = list(set(row["Occupational Title"] for row in rows if row.get("Occupational Title")))
            except Exception:
                pass
    return _cached_titles


def get_trigram_suggestions(query, limit=10):
    try:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT occupation_title, similarity(occupation_title, %s) as similarity
                    FROM occupations
                    WHERE similarity(occupation_title, %s) > 0.3
                    ORDER BY similarity DESC, occupation_title ASC
                    LIMIT %s;
                    """,
                    (query, query, limit)
                )
                return [row["occupation_title"] for row in cur.fetchall()]
    except Exception as e:
        print(f"Trigram suggestion failed: {e}")
        return None


def get_difflib_suggestions(query, limit=10):
    import difflib
    titles = get_cached_titles()
    if not titles:
        return []
    return difflib.get_close_matches(query, titles, n=limit, cutoff=0.5)


_cached_vocabulary_dict = {}

def get_cached_vocabulary_dict():
    global _cached_vocabulary_dict
    if not _cached_vocabulary_dict:
        import re
        from collections import Counter
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT occupation_title, occupation_description, 
                               family_description, group_description, 
                               division_description, sub_division_description 
                        FROM occupations;
                        """
                    )
                    rows = cur.fetchall()
                    
                    title_words = []
                    desc_words = []
                    for row in rows:
                        title_combined = (row[0] or "").lower()
                        t_words = re.findall(r"\b[a-zA-Z']+\b", title_combined)
                        title_words.extend(t_words)
                        
                        desc_combined = " ".join(filter(None, row[1:])).lower()
                        d_words = re.findall(r"\b[a-zA-Z']+\b", desc_combined)
                        desc_words.extend(d_words)

                    title_counts = Counter(title_words)
                    desc_counts = Counter(desc_words)

                    word_scores = {}
                    all_words = set(title_counts.keys()) | set(desc_counts.keys())
                    for w in all_words:
                        if len(w) <= 2:
                            continue
                        word_scores[w] = title_counts[w] * 30 + min(desc_counts[w], 3)

                    # Augment with simple singular forms and precompute character sets
                    augmented = {}
                    for w, score in word_scores.items():
                        augmented[w] = (set(w), max(augmented.get(w, (None, 0))[1], score))
                        if w.endswith("s") and len(w) > 3:
                            if w.endswith("ies") and len(w) > 4:
                                sing = w[:-3] + "y"
                            else:
                                sing = w[:-1]
                            augmented[sing] = (set(sing), max(augmented.get(sing, (None, 0))[1], score))
                            
                    # Load common English word list to bypass spelling corrections for normal words
                    common_words = set()
                    
                    # Add common English helpers and contractions directly
                    common_english_helpers = {
                        "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your", "yours", 
                        "yourself", "yourselves", "he", "him", "his", "himself", "she", "her", "hers", 
                        "herself", "it", "its", "itself", "they", "them", "their", "theirs", "themselves", 
                        "what", "which", "who", "whom", "this", "that", "these", "those", "am", "is", "are", 
                        "was", "were", "be", "been", "being", "have", "has", "had", "having", "do", "does", 
                        "did", "doing", "a", "an", "the", "and", "but", "if", "or", "because", "as", "until", 
                        "while", "of", "at", "by", "for", "with", "about", "against", "between", "into", 
                        "through", "during", "before", "after", "above", "below", "to", "from", "up", "down", 
                        "in", "out", "on", "off", "over", "under", "again", "further", "then", "once", "here", 
                        "there", "when", "where", "why", "how", "all", "any", "both", "each", "few", "more", 
                        "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same", "so", 
                        "than", "too", "very", "s", "t", "can", "will", "just", "don", "should", "now",
                        "im", "i'm", "ill", "i'll", "ive", "i've", "id", "i'd", "youre", "you're", "youll",
                        "you'll", "youve", "you've", "youd", "you'd", "hes", "he's", "hell", "he'll", "hed",
                        "he'd", "shes", "she's", "shell", "she'll", "shed", "she'd", "theyre", "they're",
                        "theyll", "they'll", "theyve", "they've", "theyd", "they'd", "we're", "were",
                        "we'll", "weve", "we've", "wed", "we'd", "cant", "can't", "wont", "won't", "dont",
                        "don't", "shouldnt", "shouldn't", "couldnt", "couldn't", "wouldnt", "wouldn't",
                        "cheer", "cheers", "course", "courses", "chair", "chairs"
                    }
                    common_words.update(common_english_helpers)
                    
                    # Read from google-10000-english.txt
                    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    words_file = os.path.join(project_dir, "data", "google-10000-english.txt")
                    if os.path.exists(words_file):
                        try:
                            with open(words_file, "r", encoding="utf-8") as f:
                                for line in f:
                                    word = line.strip().lower()
                                    if word and len(word) > 2:
                                        common_words.add(word)
                        except Exception as e:
                            print(f"Failed to read google-10000-english.txt: {e}")
                            
                    # Add comprehensive English dictionary from pyspellchecker
                    try:
                        from spellchecker import SpellChecker
                        spell = SpellChecker()
                        for w in spell.word_frequency.words():
                            if len(w) > 2:
                                common_words.add(w.lower())
                    except Exception as e:
                        print(f"Failed to load pyspellchecker vocabulary: {e}")
                            
                    # Add OOV vocabulary to protect from spell correction
                    try:
                        import sys
                        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                        if project_dir not in sys.path:
                            sys.path.append(project_dir)
                        from utils.oov_handler import oov_handler
                        for phrase in oov_handler.get_known_oov_words():
                            for token in phrase.split():
                                if len(token) > 2:
                                    common_words.add(token.lower())
                    except Exception as e:
                        print(f"Failed to load OOV vocabulary: {e}")

                    for cw in common_words:
                        if cw not in augmented:
                            augmented[cw] = (set(cw), 1.0)
                            
                    _cached_vocabulary_dict = augmented


        except Exception as e:
            print(f"Failed to load cached vocabulary for spellcheck: {e}")
            _cached_vocabulary_dict = {}
    return _cached_vocabulary_dict


def damerau_levenshtein_distance(s1, s2):
    len1 = len(s1)
    len2 = len(s2)
    dp = [[0] * (len2 + 1) for _ in range(len1 + 1)]
    for i in range(len1 + 1):
        dp[i][0] = i
    for j in range(len2 + 1):
        dp[0][j] = j
    for i in range(1, len1 + 1):
        for j in range(1, len2 + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,       # Deletion
                dp[i][j - 1] + 1,       # Insertion
                dp[i - 1][j - 1] + cost # Substitution
            )
            if i > 1 and j > 1 and s1[i - 1] == s2[j - 2] and s1[i - 2] == s2[j - 1]:
                dp[i][j] = min(dp[i][j], dp[i - 2][j - 2] + 1)
    return dp[len1][len2]


def get_spelling_suggestions(query, limit=10):
    """
    Perform word-level spelling correction on the query string using the database vocabulary.
    Returns a list containing the corrected query if any words were changed, or empty list otherwise.
    """
    import re
    import math
    import difflib
    
    vocab_dict = get_cached_vocabulary_dict()
    if not vocab_dict:
        return []
        
    SPELLING_HOTFIXES = {
        "chike": "chicken",
        "chai": "chair",
        "carpentre": "carpentry",
    }
    
    words_matches = list(re.finditer(r"\b[a-zA-Z']+\b", query))
    if not words_matches:
        return []
        
    corrected_query = query
    changed = False
    
    # Iterate backwards to keep spans correct after replacements
    for match in reversed(words_matches):
        w = match.group(0)
        wl = w.lower()
        
        # Check hotfixes first
        if wl in SPELLING_HOTFIXES:
            best_candidate = SPELLING_HOTFIXES[wl]
        else:
            # Keep short words or correct words as-is
            if len(wl) <= 2 or wl in vocab_dict:
                continue
                
            best_candidate = None
            best_score = -999999
            
            # Retrieve candidates using C-optimized difflib matching
            candidates = difflib.get_close_matches(wl, list(vocab_dict.keys()), n=15, cutoff=0.55)
            if not candidates:
                continue
                
            max_edit_dist = 2 if len(wl) <= 6 else 3
            wl_set = set(wl)
            
            for cand in candidates:
                cand_set, freq = vocab_dict[cand]
                if abs(len(wl) - len(cand)) > max_edit_dist:
                    continue
                    
                if len(wl_set - cand_set) > max_edit_dist:
                    continue
                    
                dist = damerau_levenshtein_distance(wl, cand)
                if dist > max_edit_dist:
                    continue
                    
                max_len = max(len(wl), len(cand))
                damerau_sim = 1.0 - (dist / max_len)
                gestalt_sim = difflib.SequenceMatcher(None, wl, cand).ratio()
                
                # Hybrid similarity: 80% Gestalt (character sequence) + 20% Damerau-Levenshtein (edit distance)
                sim = 0.8 * gestalt_sim + 0.2 * damerau_sim
                freq_bonus = 0.015 * math.log(freq + 1)
                len_penalty = 0.05 * abs(len(wl) - len(cand))
                score = sim + freq_bonus - len_penalty
                
                if cand[0] == wl[0]:
                    score += 0.03
                    
                if score > best_score:
                    best_score = score
                    best_candidate = cand
                    
        if best_candidate and best_candidate != wl:
            # Match casing of original word
            if w.istitle():
                corrected_word = best_candidate.title()
            elif w.isupper():
                corrected_word = best_candidate.upper()
            else:
                corrected_word = best_candidate
                
            start, end = match.span()
            corrected_query = corrected_query[:start] + corrected_word + corrected_query[end:]
            changed = True
            
    if changed:
        return [corrected_query]
    return []


def get_state_search_stats():
    """Return aggregated search counts per Indian state."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT geo_state, COUNT(*) AS search_count
                FROM prompt_history
                WHERE geo_state IS NOT NULL AND geo_state <> ''
                  AND geo_country = 'India'
                GROUP BY geo_state
                ORDER BY search_count DESC
                """
            )
            return [{"state": row["geo_state"], "count": row["search_count"]} for row in cur.fetchall()]


def get_international_search_stats():
    """Return search counts grouped by country, excluding India."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT geo_country, COUNT(*) AS search_count
                FROM prompt_history
                WHERE geo_country IS NOT NULL AND geo_country <> ''
                  AND geo_country <> 'India'
                GROUP BY geo_country
                ORDER BY search_count DESC
                """
            )
            return [{"country": row["geo_country"], "count": row["search_count"]} for row in cur.fetchall()]


def get_state_occupation_stats(state_name):
    """Return top occupations and division breakdown for a given state."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Total searches for this state
            cur.execute(
                "SELECT COUNT(*) AS total FROM prompt_history WHERE geo_state = %s AND geo_country = 'India'",
                (state_name,)
            )
            total_row = cur.fetchone()
            total = int(total_row["total"]) if total_row else 0

            # Top 10 occupations
            cur.execute(
                """
                SELECT occupation_title, COUNT(*) AS cnt
                FROM prompt_history
                WHERE geo_state = %s AND geo_country = 'India' AND occupation_title IS NOT NULL AND occupation_title <> ''
                GROUP BY occupation_title
                ORDER BY cnt DESC
                LIMIT 10
                """,
                (state_name,)
            )
            occupations = []
            for row in cur.fetchall():
                cnt = int(row["cnt"])
                pct = round(cnt / total * 100, 1) if total else 0
                occupations.append({
                    "title": row["occupation_title"],
                    "count": cnt,
                    "percentage": pct
                })

            # Division breakdown — join with occupations table to get division
            cur.execute(
                """
                SELECT o.division, COUNT(*) AS cnt
                FROM prompt_history ph
                LEFT JOIN occupations o ON ph.occupation_title = o.occupation_title
                WHERE ph.geo_state = %s AND ph.geo_country = 'India'
                  AND o.division IS NOT NULL AND o.division <> ''
                GROUP BY o.division
                ORDER BY cnt DESC
                LIMIT 10
                """,
                (state_name,)
            )
            divisions = [{
                "division": row["division"],
                "count": int(row["cnt"])
            } for row in cur.fetchall()]

            return {
                "state": state_name,
                "total": total,
                "occupations": occupations,
                "divisions": divisions
            }

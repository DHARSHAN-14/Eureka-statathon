import copy
import csv
import io
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone

import numpy as np
import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/statathon_nco",
)

_pool = None
_csv_rows_cache = None
_graph_cache = None


def _get_pool():
    global _pool
    if _pool is None:
        _pool = ThreadedConnectionPool(minconn=2, maxconn=20, dsn=DATABASE_URL)
    return _pool


def invalidate_caches():
    global _csv_rows_cache, _graph_cache
    _csv_rows_cache = None
    _graph_cache = None


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


@contextmanager
def get_conn():
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


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
                """
            )


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
            new_id = cur.fetchone()[0]
    invalidate_caches()
    return new_id


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
    invalidate_caches()


def delete_occupation(row_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM occupations WHERE id = %s", (row_id,))
    invalidate_caches()


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
    global _csv_rows_cache
    if _csv_rows_cache is not None:
        return copy.deepcopy(_csv_rows_cache)
    result = OCCUPATION_FIELDS[:], [row_to_csv_dict(row) | {"_row_id": row["id"]} for row in list_occupations()]
    _csv_rows_cache = result
    return copy.deepcopy(_csv_rows_cache)


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
    invalidate_caches()
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
                    nco_code, top_k, returned_count, client_ip, raw
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
    global _graph_cache
    if _graph_cache is not None:
        return copy.deepcopy(_graph_cache)
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT nco_code, sector, keywords, payload FROM nco_graph")
            graph = {}
            for row in cur.fetchall():
                payload = dict(row.get("payload") or {})
                payload.setdefault("sector", row.get("sector") or "unknown")
                payload.setdefault("keywords", list(row.get("keywords") or []))
                graph[row["nco_code"]] = payload
            _graph_cache = graph
            return copy.deepcopy(_graph_cache)


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


def save_embeddings(embeddings):
    buffer = io.BytesIO()
    np.save(buffer, embeddings)
    save_asset("nco_embeddings.npy", buffer.getvalue(), "application/x-numpy")


def load_embeddings():
    data = load_asset("nco_embeddings.npy")
    if data is None:
        return None
    return np.load(io.BytesIO(data))

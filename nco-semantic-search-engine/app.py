from dotenv import load_dotenv
load_dotenv()  # Load .env before anything else (must be first)

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
from flask_compress import Compress
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import sys
import os
import json
import threading
import time
import hashlib
from datetime import datetime, timezone
import csv
import re
import secrets
import io

# Add scripts directory to path to import searchapp
sys.path.append(os.path.join(os.path.dirname(__file__), 'scripts'))
# Add utils directory to path to import prompt system
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))
from database import db_store
db_store.init_db()

# Auto-arrange dataset file if present in the root folder
import shutil
import re
_root_csv = os.path.join(os.path.dirname(__file__), 'nco_dataset_v6_final.csv')
_target_csv = os.path.join(os.path.dirname(__file__), 'data', 'raw', 'nco_dataset_v6_final.csv')
if os.path.exists(_root_csv):
    os.makedirs(os.path.dirname(_target_csv), exist_ok=True)
    try:
        shutil.move(_root_csv, _target_csv)
        print(f"Automatically moved {_root_csv} to {_target_csv}")
    except Exception as e:
        print(f"Failed to move CSV automatically: {e}")



# Load search module once at startup for performance
import utils.searchapp as search_module

# Import PIGS — NCO-aware query guidance system
from utils.dynamic_prompts import pigs_v2_analyze
# Import translation service
from utils.translation_service import translation_service
# Import OOV handler
from utils.oov_handler import oov_handler
# Import IP geolocation utility
from utils.ip_location import resolve_ip_location


def _warm_search_path():
    """Pre-build the spellcheck vocabulary and warm SBERT/pgvector once at startup,
    so the first real user query doesn't pay the cold-start cost (~2s search +
    full vocab build)."""
    try:
        from database import db_store
        db_store.get_cached_vocabulary_dict()          # build + cache vocab once
        search_module.search("warmup", top_k=1)        # warm SBERT encode + pgvector
        print("[WARM] search path ready (vocab + SBERT + pgvector).", flush=True)
    except Exception as e:
        print(f"[WARM] search warm-up failed: {e}", flush=True)


threading.Thread(target=_warm_search_path, daemon=True).start()

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(32))
CORS(app)
Compress(app)   # gzip all text/json responses automatically

# ------------------------------------------------------------------
# In-memory search result cache
# Keyed on (translated_query, top_k, filters) — avoids re-running
# SBERT for identical queries within the TTL window.
# ------------------------------------------------------------------
_search_cache: dict = {}
_search_cache_lock = threading.Lock()
_SEARCH_CACHE_TTL  = 300   # seconds (5 min)
_SEARCH_CACHE_MAX  = 500   # max entries

def _search_cache_key(query: str, top_k: int, filters: dict) -> str:
    raw = f"{query.lower().strip()}|{top_k}|{json.dumps(filters or {}, sort_keys=True)}"
    return hashlib.md5(raw.encode()).hexdigest()

def _get_cached_search(key: str):
    with _search_cache_lock:
        entry = _search_cache.get(key)
        if entry and (time.monotonic() - entry["ts"]) < _SEARCH_CACHE_TTL:
            return entry["data"]
    return None

def _set_cached_search(key: str, data: list):
    with _search_cache_lock:
        if len(_search_cache) >= _SEARCH_CACHE_MAX:
            oldest = min(_search_cache, key=lambda k: _search_cache[k]["ts"])
            del _search_cache[oldest]
        _search_cache[key] = {"ts": time.monotonic(), "data": data}

CSV_PATH = os.path.join(os.path.dirname(__file__), 'data', 'raw', 'nco_dataset_v6_final.csv')
ASSET_VERSION = os.getenv("ASSET_VERSION", "8")
STATIC_CACHE_SECONDS = int(os.getenv("STATIC_CACHE_SECONDS", "86400"))


@app.context_processor
def inject_asset_version():
    return {"asset_version": ASSET_VERSION}


@app.after_request
def add_performance_headers(response):
    # Security headers
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.pop("X-XSS-Protection", None)

    # Cache static assets — versioned files get immutable/1-year, others use configured TTL
    if request.path.startswith("/static/"):
        if request.args.get("v"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = f"public, max-age={STATIC_CACHE_SECONDS}"
    return response


@app.route('/favicon.ico')
def favicon():
    return '', 204


@app.route('/.well-known/appspecific/com.chrome.devtools.json')
def chrome_devtools_json():
    """Suppress Chrome DevTools discovery probe — harmless 204 instead of noisy 404."""
    return '', 204


def _get_admin_setting(key):
    return db_store.get_admin_setting(key)


def _set_admin_setting(key, value):
    db_store.set_admin_setting(key, value)


_ADMIN_USERNAME = "admin"


def _hash_password(password: str) -> str:
    """Hash a password using Werkzeug PBKDF2-SHA256. Never log the return value."""
    return generate_password_hash(password)


def _verify_password(password: str, stored_hash: str) -> bool:
    """
    Timing-safe password verification via Werkzeug.
    check_password_hash uses hmac.compare_digest internally.
    """
    if not stored_hash:
        return False
    return check_password_hash(stored_hash, password)


def _require_admin_password(password: str):
    """
    Fetch the hash for the single admin account from admin_users and verify.
    Returns (True, None) on success, (False, error_message) on failure.
    """
    if not password or not str(password).strip():
        return False, "Password is required"
    stored = db_store.get_admin_password_hash(_ADMIN_USERNAME)
    if not stored:
        return False, "Admin account not found"
    if _verify_password(password, stored):
        return True, None
    return False, "Invalid password"


def _ensure_admin_account():
    """
    Guarantee exactly one admin account exists in admin_users.
    If the table is empty (first deploy), a cryptographically random password
    is generated, its hash stored in PostgreSQL, and the plaintext printed
    ONCE to stdout so the operator can capture it.
    No password is ever written to source code, config files, or env vars.
    """
    if db_store.admin_user_exists():
        return
    raw_password = secrets.token_urlsafe(16)
    db_store.create_admin_user(_ADMIN_USERNAME, _hash_password(raw_password))
    print("\n" + "=" * 62)
    print("  ADMIN ACCOUNT CREATED (first-run setup)")
    print(f"  Username : {_ADMIN_USERNAME}")
    print(f"  Password : {raw_password}")
    print("  Save this password — it will NOT be shown again.")
    print("=" * 62 + "\n")

_ensure_admin_account()


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_authenticated"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated


def admin_api_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_authenticated"):
            return jsonify({"error": "Authentication required", "redirect": "/admin/login"}), 401
        return f(*args, **kwargs)
    return decorated


def _read_prompt_history():
    return list(reversed(db_store.read_prompt_history(limit=5000)))


def _write_prompt_history(history):
    # Prompt history is append-only in PostgreSQL. This function remains for
    # compatibility with older call sites.
    return None


def _append_prompt_history_entry(entry):
    db_store.append_prompt_history(entry)


def _safe_text(value):
    if value is None:
        return ""
    return str(value).strip()


def _normalize_nco_code(value):
    raw = _safe_text(value)
    if not raw:
        return ""
    raw = raw.replace(" ", "")
    parts = raw.split(".")

    def _digits(s):
        return re.sub(r"\D", "", s or "")

    if len(parts) == 1:
        digits = _digits(parts[0])
        if len(digits) == 8:
            return f"{digits[:4]}.{digits[4:8]}"
        if len(digits) == 4:
            return f"{digits}.0000"
        if 4 < len(digits) < 8:
            return f"{digits[:4]}.{digits[4:].ljust(4, '0')[:4]}"
        if len(digits) > 8:
            return f"{digits[:4]}.{digits[4:8]}"
        return raw

    left = _digits(parts[0])
    right = _digits(parts[1] if len(parts) > 1 else "")
    left = left[:4].ljust(4, "0")
    right = right[:4].ljust(4, "0")
    return f"{left}.{right}"


def _format_nco_2004(value):
    raw = _safe_text(value)
    if not raw:
        return ""
    raw = raw.replace(" ", "")
    parts = raw.split(".")

    def _digits(s):
        return re.sub(r"\D", "", s or "")

    if len(parts) == 1:
        digits = _digits(parts[0])
        if len(digits) == 6:
            return f"{digits[:4]}.{digits[4:6]}"
        if len(digits) == 4:
            return f"{digits}.00"
        if 4 < len(digits) < 6:
            return f"{digits[:4]}.{digits[4:].ljust(2, '0')[:2]}"
        if len(digits) > 6:
            return f"{digits[:4]}.{digits[4:6]}"
        return raw

    left = _digits(parts[0])
    right = _digits(parts[1] if len(parts) > 1 else "")
    left = left[:4].ljust(4, "0")
    right = right[:2].ljust(2, "0")
    return f"{left}.{right}"


def _parse_nco_2015(value):
    raw = _safe_text(value).replace(" ", "")
    if not raw:
        return "", "NCO 2015 code is required"
    m = re.fullmatch(r"(\d{4})\.(\d{4})", raw)
    if not m:
        return "", "Invalid NCO 2015 format. Use XXXX.XXXX"
    return f"{m.group(1)}.{m.group(2)}", None


def _parse_nco_2004(value, required=False):
    raw = _safe_text(value).replace(" ", "")
    if not raw:
        if required:
            return "", "NCO 2004 code is required"
        return "", None
    m = re.fullmatch(r"(\d{4})\.(\d{2})", raw)
    if not m:
        return "", "Invalid NCO 2004 format. Use XXXX.XX"
    return f"{m.group(1)}.{m.group(2)}", None


def _load_csv_rows():
    return db_store.load_csv_rows()


def _write_csv_rows(fieldnames, rows):
    # Occupations are now stored directly in PostgreSQL through insert/update/delete helpers.
    return None


def _build_document_for_row(row):
    """Construct the text document used for full-document embedding from a single occupation row."""
    return f"""
Occupation Title: {_safe_text(row.get('Occupational Title'))}
NCO 2015 Code: {_safe_text(row.get('NCO 2015'))}

Hierarchy:
Division: {_safe_text(row.get('Division'))}
Sub Division: {_safe_text(row.get('Sub Division'))}
Group: {_safe_text(row.get('Group'))}
Family: {_safe_text(row.get('Family'))}

Occupation Description:
{_safe_text(row.get('Occupation Description'))}

Family Description:
{_safe_text(row.get('Family Description'))}

Group Description:
{_safe_text(row.get('Group Description'))}
""".strip()


def _rebuild_search_assets(rows, changed_row_ids=None):
    """
    Rebuild graph keyword data and pgvector embeddings.

    Args:
        rows: All occupation rows (used to rebuild the graph).
        changed_row_ids: Optional set of _row_id values to limit embedding updates.
                         Pass None to re-encode every row (e.g. after a full migration).
    """
    from sentence_transformers import SentenceTransformer
    import numpy as np

    # --- Rebuild nco_graph (keyword signals) ---
    gn = {}
    for row in rows:
        code = _safe_text(row.get("NCO 2015"))
        if not code:
            continue
        doc = _build_document_for_row(row).lower()
        words = re.findall(r"\b[a-z]{3,}\b", doc)
        keywords = list(set(words))
        sector = "unknown"
        for line in doc.split("\n"):
            if line.strip().startswith("division:"):
                sector = line.split(":", 1)[1].strip().title()
                break
        gn[code] = {"sector": sector, "keywords": keywords}
    db_store.save_graph(gn)

    # --- Encode and store embeddings for changed (or all) rows ---
    model = SentenceTransformer("BAAI/bge-small-en-v1.5")

    rows_to_encode = rows
    if changed_row_ids is not None:
        rows_to_encode = [r for r in rows if int(r.get("_row_id") or -1) in changed_row_ids]

    id_embedding_pairs = []
    for row in rows_to_encode:
        row_id = int(row.get("_row_id") or -1)
        if row_id < 0:
            continue
        doc = _build_document_for_row(row)
        title = _safe_text(row.get("Occupational Title"))
        emb = model.encode([doc], convert_to_numpy=True, normalize_embeddings=True)[0]
        title_emb = model.encode([title], convert_to_numpy=True, normalize_embeddings=True)[0]
        id_embedding_pairs.append((row_id, emb, title_emb))

    if id_embedding_pairs:
        db_store.save_all_embeddings(id_embedding_pairs)

    if hasattr(search_module, "reload_from_db"):
        search_module.reload_from_db()


def _build_result_from_row(row, row_id):
    return {
        "occupation_title": _safe_text(row.get("Occupational Title")),
        "row_id": row_id,
        "nco_code": _normalize_nco_code(row.get("NCO 2015")),
        "semantic_score": 1.0,
        "gn_score": 0.0,
        "final_score": 1.0,
        "details": {
            "nco_2004_code": _format_nco_2004(row.get("NCO 2004")),
            "division": _safe_text(row.get("Division")),
            "sub_division": _safe_text(row.get("Sub Division")),
            "group": _safe_text(row.get("Group")),
            "family": _safe_text(row.get("Family")),
            "occupation_description": _safe_text(row.get("Occupation Description")),
            "family_description": _safe_text(row.get("Family Description")),
            "group_description": _safe_text(row.get("Group Description")),
        },
    }


def _search_by_nco_code(nco_query):
    code = _normalize_nco_code(nco_query)
    if not code:
        return []
    _, rows = _load_csv_rows()
    results = []
    for idx, row in enumerate(rows):
        if _normalize_nco_code(row.get("NCO 2015")) == code:
            results.append(_build_result_from_row(row, int(row.get("_row_id") or idx)))
    return results

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if session.get("admin_authenticated"):
        return redirect(url_for("admin_dashboard"))
    error = None
    if request.method == 'POST':
        password = request.form.get('password', '').strip()
        ok, err = _require_admin_password(password)
        if ok:
            session['admin_authenticated'] = True
            return redirect(url_for("admin_dashboard"))
        error = "Invalid password. Please try again."
    return render_template('admin/login.html', error=error)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_authenticated', None)
    return redirect(url_for("admin_login"))

@app.route('/admin')
@admin_required
def admin_dashboard():
    return render_template('admin/dashboard.html')

@app.route('/api/search', methods=['POST'])
def search_jobs():
    data = request.get_json()
    if data is None:
        return jsonify({"error": "Invalid JSON"}), 400
    query = data.get('query', '').strip()
    user_language = data.get('user_language', None)  # User's confirmed language
    search_mode = data.get('search_mode', 'general')
    filters = data.get('filters', {})
    try:
        top_k = int(data.get('top_k', request.args.get('top_k', 5)))
    except (TypeError, ValueError):
        top_k = 5
    top_k = max(1, min(top_k, 100))
    
    try:
        if query:
            import time as _t
            _phase = _t.perf_counter()
            def _lap(label):
                nonlocal _phase
                _now = _t.perf_counter()
                print(f"[PERF] {label}: {(_now - _phase)*1000:.0f}ms", flush=True)
                _phase = _now
            spelling_correction = None
            was_transliterated = False
            original_query = query
            translation_notice = None
            transliteration_notice = None
            language_ambiguity = None
            translated_query = query

            # Determine source language code (only if selected in dropdown and not English)
            lang_code = None
            if user_language and not user_language.startswith("en"):
                lang_code = user_language.split("-")[0]

            # 1. Transliteration (for Indic languages with Roman script input)
            if lang_code:
                if translation_service.is_roman_script(query):
                    try:
                        transliteration_result = translation_service.transliterate(query, lang_code)
                        if transliteration_result and transliteration_result.strip().lower() != query.strip().lower():
                            query = transliteration_result
                            was_transliterated = True
                            transliteration_notice = {
                                "original": original_query,
                                "transliterated": query
                            }
                    except Exception as ex:
                        print(f"Transliteration failed: {ex}")

            if search_mode == "nco":
                results = _search_by_nco_code(query)[:top_k]
                return jsonify({
                    "results": results,
                    "suggestion": None,
                    "translation_notice": None,
                    "language_ambiguity": None,
                    "top_k": top_k,
                    "spelling_correction": None,
                    "transliteration_notice": transliteration_notice
                })

            # 2. Translation (to English)
            if lang_code:
                try:
                    translated_query = translation_service.translate(query, source_lang=lang_code, target_lang="en")
                    if translated_query.lower() != query.lower():
                        translation_notice = {
                            "original": query,
                            "translated": translated_query,
                            "message": f"Query translated from original text"
                        }
                except Exception as ex:
                    print(f"Translation failed: {ex}")

            _lap("translate+translit")
            # 2.5 OOV Expansion
            translated_query = oov_handler.process_query(translated_query)
            _lap("oov")

            # 3. Spell Correction (English target vocabulary spell check)
            if search_mode == "general":
                close_matches = db_store.get_spelling_suggestions(translated_query, limit=1)
                if close_matches and close_matches[0].lower() != translated_query.lower():
                    import difflib
                    ratio = difflib.SequenceMatcher(None, translated_query.lower(), close_matches[0].lower()).ratio()
                    if ratio >= 0.7:  # high confidence match
                        spelling_correction = {
                            "original": translated_query,
                            "corrected": close_matches[0]
                        }
                        translated_query = close_matches[0]
            _lap("spelling")

            # Use the search function — cached to avoid re-running SBERT
            _ck = _search_cache_key(translated_query, top_k, filters)
            results = _get_cached_search(_ck)
            if results is None:
                results = search_module.search(translated_query, top_k=top_k, filters=filters)
                _set_cached_search(_ck, results)
            for r in results:
                if "nco_code" in r:
                    r["nco_code"] = _normalize_nco_code(r.get("nco_code"))
                if "details" in r and "nco_2004" in r["details"]:
                    r["details"]["nco_2004"] = _format_nco_2004(r["details"]["nco_2004"])
            _lap("search")

            # ------------------ PIGS v2 ANALYSIS ------------------
            pigs_output = None
            if pigs_v2_analyze and results:
                try:
                    pigs_output = pigs_v2_analyze(translated_query, results)
                except Exception as e:
                    print(f"PIGS analysis error: {e}")
                    pigs_output = None
            _lap("pigs")

            try:
                detected_lang = "English"
                if translated_query.lower() != query.lower():
                    lang_code = (user_language or "en").split("-")[0].lower()
                    supported_langs = translation_service.get_supported_languages()
                    detected_lang = supported_langs.get(lang_code, "Other")

                top = results[0] if results else {}
                top_details = top.get("details") or {}
                client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
                if client_ip:
                    client_ip = client_ip.split(',')[0].strip()
                geo = {}
                try:
                    geo = resolve_ip_location(client_ip)
                except Exception:
                    pass
                _append_prompt_history_entry({
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "query": query,
                    "translated_query": translated_query,
                    "was_translated": translated_query.lower() != query.lower(),
                    "detected_language": detected_lang,
                    "occupation_title": top.get('occupation_title', ''),
                    "nco_code": top.get('nco_2015', top.get('nco_code', '')),
                    "division": top_details.get("division", ""),
                    "sub_division": top_details.get("sub_division", ""),
                    "group": top_details.get("group", ""),
                    "family": top_details.get("family", ""),
                    "top_k": top_k,
                    "returned_count": len(results),
                    "client_ip": client_ip,
                    "geo_city": geo.get("city", ""),
                    "geo_state": geo.get("state", ""),
                    "geo_country": geo.get("country", ""),
                })
            except Exception:
                pass
            _lap("history+geo")

            return jsonify({
                "results": results,
                "translation_notice": translation_notice,
                "language_ambiguity": language_ambiguity,
                "pigs": pigs_output,
                "top_k": top_k,
                "returned_count": len(results),
                "spelling_correction": spelling_correction,
                "transliteration_notice": transliteration_notice
            })
        else:
            # Use the get_all_jobs function for empty queries
            results = search_module.get_all_jobs(filters=filters) if search_module else []
            return jsonify({
                "results": results,
                "directory_mode": True,
                "returned_count": len(results),
                "spelling_correction": None
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/suggest', methods=['GET', 'POST'])
def suggest_completions():
    if request.method == 'POST':
        data = request.get_json() or {}
        query = data.get('query', '').strip()
    else:
        query = request.args.get('query', '').strip()
        
    if not query or len(query) < 2:
        return jsonify({"suggestions": []})
        
    try:
        suggestions = db_store.get_spelling_suggestions(query, limit=10)
        return jsonify({"suggestions": suggestions})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/translate', methods=['POST'])
def translate_text():
    data = request.get_json()
    if data is None:
        return jsonify({"error": "Invalid JSON"}), 400
    
    text = data.get('text', '').strip()
    source_lang = data.get('source_lang', 'auto')
    target_lang = data.get('target_lang', 'en')
    preferred_service = data.get('preferred_service', 'lingua')
    
    if not text:
        return jsonify({"error": "Text is required"}), 400
    
    try:
        was_transliterated = False
        original_text = text
        
        # If source_lang is an Indic language and text is in Roman script, transliterate it first
        if source_lang != "en" and source_lang != "auto":
            if translation_service.is_roman_script(text):
                transliterated = translation_service.transliterate(text, source_lang)
                if transliterated and transliterated.strip() != text.strip():
                    text = transliterated
                    was_transliterated = True
                    
        translated_text = translation_service.translate(
            text, source_lang, target_lang, preferred_service
        )
        return jsonify({
            "original_text": original_text,
            "transliterated_text": text if was_transliterated else None,
            "was_transliterated": was_transliterated,
            "translated_text": translated_text,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "service_used": preferred_service
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/languages', methods=['GET'])
def get_supported_languages():
    try:
        languages = translation_service.get_supported_languages()
        return jsonify({"languages": languages})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/admin/api/prompt-history', methods=['GET'])
@admin_api_required
def get_prompt_history():
    try:
        occupation_title = request.args.get('occupation_title', '').strip()
        try:
            limit = int(request.args.get('limit', '100'))
        except ValueError:
            limit = 100
        limit = max(1, min(limit, 5000))

        history = db_store.read_prompt_history(limit=limit, occupation_title=occupation_title)
        return jsonify(history)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin/api/occupations', methods=['GET'])
@admin_api_required
def get_occupations():
    try:
        fieldnames, rows = _load_csv_rows()
        occupations = []
        for idx, row in enumerate(rows):
            occupations.append({
                "row_id": int(row.get("_row_id") or idx),
                "id": _safe_text(row.get("S No")),
                "occupation_title": _safe_text(row.get("Occupational Title")),
                "nco_code": _normalize_nco_code(row.get("NCO 2015")),
                "nco_2004_code": _format_nco_2004(row.get("NCO 2004")),
                "division": _safe_text(row.get("Division")),
                "sub_division": _safe_text(row.get("Sub Division")),
                "group": _safe_text(row.get("Group")),
                "family": _safe_text(row.get("Family")),
                "division_description": _safe_text(row.get("Division Description")),
                "sub_division_description": _safe_text(row.get("Sub Division Description")),
                "group_description": _safe_text(row.get("Group Description")),
                "family_description": _safe_text(row.get("Family Description")),
                "description": _safe_text(row.get("Occupation Description")),
            })

        return jsonify(occupations)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin/api/occupations/<int:row_id>', methods=['PUT'])
@admin_api_required
def update_occupation(row_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        fieldnames, rows = _load_csv_rows()
        existing_row = next((r for r in rows if int(r.get("_row_id") or -1) == row_id), None)
        if not existing_row:
            return jsonify({"success": False, "error": "Occupation not found"}), 404

        ok, err = _require_admin_password(data.get("admin_password"))
        if not ok:
            return jsonify({"success": False, "error": err}), 403

        occupation_title = _safe_text(data.get("occupation_title"))
        division = _safe_text(data.get("division"))
        sub_division = _safe_text(data.get("sub_division"))
        group = _safe_text(data.get("group"))
        family = _safe_text(data.get("family"))
        description = _safe_text(data.get("description"))

        if not occupation_title:
            return jsonify({"success": False, "error": "Occupation title is required"}), 400
        if not division:
            return jsonify({"success": False, "error": "Division is required"}), 400
        if not sub_division:
            return jsonify({"success": False, "error": "Sub Division is required"}), 400
        if not group:
            return jsonify({"success": False, "error": "Group is required"}), 400
        if not family:
            return jsonify({"success": False, "error": "Family is required"}), 400
        if not description:
            return jsonify({"success": False, "error": "Occupation description is required"}), 400

        new_nco, nco_2015_err = _parse_nco_2015(data.get("nco_code"))
        if nco_2015_err:
            return jsonify({"success": False, "error": nco_2015_err}), 400

        existing_nco2004 = _safe_text(existing_row.get("NCO 2004"))
        incoming_nco2004 = data.get("nco_2004_code", existing_nco2004)
        required_2004 = bool(existing_nco2004)
        new_nco_2004, nco_2004_err = _parse_nco_2004(incoming_nco2004, required=required_2004)
        if nco_2004_err:
            return jsonify({"success": False, "error": nco_2004_err}), 400

        for r in rows:
            if int(r.get("_row_id") or -1) == row_id:
                continue
            if _normalize_nco_code(r.get("NCO 2015")) == new_nco:
                return jsonify({
                    "success": False,
                    "error": f"NCO 2015 code already exists: {new_nco}"
                }), 400
            row_nco_2004 = _safe_text(r.get("NCO 2004"))
            if new_nco_2004 and row_nco_2004 and row_nco_2004 == new_nco_2004:
                return jsonify({
                    "success": False,
                    "error": f"NCO 2004 code already exists: {new_nco_2004}"
                }), 400

        row = dict(existing_row)
        row["Occupational Title"] = occupation_title
        row["NCO 2015"] = new_nco
        row["NCO 2004"] = new_nco_2004 if required_2004 else _safe_text(row.get("NCO 2004", ""))
        row["Division"] = division
        row["Sub Division"] = sub_division
        row["Group"] = group
        row["Family"] = family
        row["Occupation Description"] = description
        row["Family Description"] = _safe_text(data.get("family_description", row.get("Family Description", "")))
        row["Group Description"] = _safe_text(data.get("group_description", row.get("Group Description", "")))
        row["Division Description"] = _safe_text(data.get("division_description", row.get("Division Description", "")))
        row["Sub Division Description"] = _safe_text(data.get("sub_division_description", row.get("Sub Division Description", "")))

        db_store.update_occupation(row_id, row)
        _, rebuilt_rows = _load_csv_rows()
        _rebuild_search_assets(rebuilt_rows, changed_row_ids={row_id})

        return jsonify({"success": True, "message": "Occupation updated successfully"})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/admin/api/occupations', methods=['POST'])
@admin_api_required
def add_occupation():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        ok, err = _require_admin_password(data.get("admin_password"))
        if not ok:
            return jsonify({"success": False, "error": err}), 403

        fieldnames, rows = _load_csv_rows()

        occupation_title = _safe_text(data.get("occupation_title"))
        division = _safe_text(data.get("division"))
        sub_division = _safe_text(data.get("sub_division"))
        group = _safe_text(data.get("group"))
        family = _safe_text(data.get("family"))
        description = _safe_text(data.get("description"))

        if not occupation_title:
            return jsonify({"success": False, "error": "Occupation title is required"}), 400
        if not division:
            return jsonify({"success": False, "error": "Division is required"}), 400
        if not sub_division:
            return jsonify({"success": False, "error": "Sub Division is required"}), 400
        if not group:
            return jsonify({"success": False, "error": "Group is required"}), 400
        if not family:
            return jsonify({"success": False, "error": "Family is required"}), 400
        if not description:
            return jsonify({"success": False, "error": "Occupation description is required"}), 400

        new_nco, nco_2015_err = _parse_nco_2015(data.get("nco_code"))
        if nco_2015_err:
            return jsonify({"success": False, "error": nco_2015_err}), 400

        new_nco_2004, nco_2004_err = _parse_nco_2004(data.get("nco_2004_code"), required=False)
        if nco_2004_err:
            return jsonify({"success": False, "error": nco_2004_err}), 400

        for r in rows:
            if _normalize_nco_code(r.get("NCO 2015")) == new_nco:
                return jsonify({
                    "success": False,
                    "error": f"NCO 2015 code already exists: {new_nco}"
                }), 400
            row_nco_2004 = _safe_text(r.get("NCO 2004"))
            if new_nco_2004 and row_nco_2004 and row_nco_2004 == new_nco_2004:
                return jsonify({
                    "success": False,
                    "error": f"NCO 2004 code already exists: {new_nco_2004}"
                }), 400

        new_row = {
            "S No": db_store.next_s_no(),
            "Occupational Title": occupation_title,
            "NCO 2015": new_nco,
            "NCO 2004": new_nco_2004,
            "Division": division,
            "Sub Division": sub_division,
            "Group": group,
            "Family": family,
            "Division Description": _safe_text(data.get("division_description", "")),
            "Sub Division Description": _safe_text(data.get("sub_division_description", "")),
            "Group Description": _safe_text(data.get("group_description", "")),
            "Family Description": _safe_text(data.get("family_description", "")),
            "Occupation Description": description,
        }

        new_row_id = db_store.insert_occupation(new_row)
        _, rebuilt_rows = _load_csv_rows()
        _rebuild_search_assets(rebuilt_rows, changed_row_ids={new_row_id})

        return jsonify({"success": True, "message": "Occupation added successfully", "row_id": new_row_id})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/admin/api/occupations/<int:row_id>', methods=['DELETE'])
@admin_api_required
def delete_occupation(row_id):
    try:
        data = request.get_json(silent=True) or {}
        ok, err = _require_admin_password(data.get("admin_password"))
        if not ok:
            return jsonify({"success": False, "error": err}), 403

        fieldnames, rows = _load_csv_rows()
        if not any(int(r.get("_row_id") or -1) == row_id for r in rows):
            return jsonify({"success": False, "error": "Occupation not found"}), 404

        db_store.delete_occupation(row_id)
        _, rebuilt_rows = _load_csv_rows()
        # Deleted row has no embedding to update; just rebuild the graph and reload runtime.
        _rebuild_search_assets(rebuilt_rows, changed_row_ids=set())

        return jsonify({"success": True, "message": "Occupation deleted successfully"})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# Analytics API endpoints
@app.route('/admin/api/analytics/divisions')
@admin_api_required
def analytics_divisions():
    try:
        fieldnames, rows = _load_csv_rows()
        division_counts = {}
        
        for row in rows:
            division = row.get("Division", "")
            if division:
                division_counts[division] = division_counts.get(division, 0) + 1
        
        # Get top 10 divisions
        sorted_divisions = sorted(division_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return jsonify({
            "labels": [item[0] for item in sorted_divisions],
            "values": [item[1] for item in sorted_divisions]
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/admin/api/analytics/confidence')
@admin_api_required
def analytics_confidence():
    try:
        history = db_store.read_prompt_history(limit=5000)
        confidence_groups = {"High": 0, "Medium": 0, "Low": 0}
        
        for entry in history:
            confidence = entry.get("confidence", 0)
            if confidence > 85:
                confidence_groups["High"] += 1
            elif confidence >= 60:
                confidence_groups["Medium"] += 1
            else:
                confidence_groups["Low"] += 1
        
        return jsonify({
            "labels": list(confidence_groups.keys()),
            "values": list(confidence_groups.values())
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/admin/api/analytics/top-occupations')
@admin_api_required
def analytics_top_occupations():
    try:
        history = db_store.read_prompt_history(limit=5000)
        occupation_counts = {}
        
        for entry in history:
            if entry.get("nco_code"):
                occupation_counts[entry["nco_code"]] = occupation_counts.get(entry["nco_code"], 0) + 1
        
        # Get top 10 occupations
        sorted_occupations = sorted(occupation_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return jsonify({
            "labels": [item[0] for item in sorted_occupations],
            "values": [item[1] for item in sorted_occupations]
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/admin/api/analytics/search-trend')
@admin_api_required
def analytics_search_trend():
    try:
        history = db_store.read_prompt_history(limit=5000)
        # Group by last 7 days
        from datetime import datetime, timedelta
        trend_data = {}
        
        for i in range(7):
            date = datetime.now() - timedelta(days=i)
            date_key = date.strftime("%Y-%m-%d")
            trend_data[date_key] = 0
        
        for entry in history:
            if "ts" in entry:
                entry_date = datetime.fromisoformat(entry["ts"].replace('Z', '+00:00'))
                date_key = entry_date.strftime("%Y-%m-%d")
                if date_key in trend_data:
                    trend_data[date_key] += 1
        
        # Get last 7 days in order
        labels = []
        values = []
        for i in range(6, -1, -1):
            date = datetime.now() - timedelta(days=i)
            date_key = date.strftime("%Y-%m-%d")
            labels.append(date.strftime("%a"))
            values.append(trend_data.get(date_key, 0))
        
        return jsonify({
            "labels": labels,
            "values": values
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/admin/api/analytics/languages')
@admin_api_required
def analytics_languages():
    try:
        history = db_store.read_prompt_history(limit=5000)
        language_counts = {}
        
        for entry in history:
            lang = entry.get("detected_language")
            if not lang:
                if entry.get("was_translated"):
                    lang = "Tamil"
                else:
                    lang = "English"
            if lang in ["en", "English"]:
                lang = "English"
            language_counts[lang] = language_counts.get(lang, 0) + 1
        
        return jsonify({
            "labels": list(language_counts.keys()),
            "values": list(language_counts.values())
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/admin/api/analytics/low-confidence')
@admin_api_required
def analytics_low_confidence():
    try:
        history = db_store.read_prompt_history(limit=5000)
        low_confidence = []
        
        for entry in history:
            confidence = entry.get("confidence", 0)
            if confidence < 60:
                low_confidence.append({
                    "query": entry.get("query", ""),
                    "count": 1,
                    "avg_confidence": confidence
                })
        
        # Group by query and count
        query_counts = {}
        for item in low_confidence:
            query = item["query"]
            if query not in query_counts:
                query_counts[query] = {"count": 0, "total_confidence": 0}
            query_counts[query]["count"] += 1
            query_counts[query]["total_confidence"] += item["avg_confidence"]
        
        # Calculate average confidence and sort
        result = []
        for query, data in query_counts.items():
            avg_conf = data["total_confidence"] / data["count"]
            result.append({
                "query": query,
                "count": data["count"],
                "avg_confidence": round(avg_conf, 2)
            })
        
        # Sort by count and take top 10
        result.sort(key=lambda x: x["count"], reverse=True)
        
        return jsonify(result[:10])
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/admin/api/analytics/states')
@admin_api_required
def analytics_states():
    """Return aggregated search counts per Indian state for the India map."""
    try:
        stats = db_store.get_state_search_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/admin/api/analytics/states/<state_name>')
@admin_api_required
def analytics_state_detail(state_name):
    """Return top occupations and division breakdown for a specific state."""
    try:
        stats = db_store.get_state_occupation_stats(state_name)
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin/api/analytics/countries')
@admin_api_required
def analytics_countries():
    """Return search counts per country, excluding India."""
    try:
        stats = db_store.get_international_search_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    debug_mode = os.getenv("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")
    app.run(host=os.getenv("HOST", "0.0.0.0"), debug=debug_mode, port=int(os.getenv("PORT", "5000")), threaded=True)

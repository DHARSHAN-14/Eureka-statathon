#!/usr/bin/env python3
"""
NCO Intelligence Engine - Main Entry Point
Run this file to start the FastAPI server: python app.py
"""
import uvicorn
import sys
import os

# Ensure the project root is in the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print("🚀 Starting NCO Intelligence Engine API Server...")
    print("📝 API Documentation: http://localhost:8000/docs")
    print("🔍 Alternative Docs: http://localhost:8000/redoc")
    print("⏹️  Press Ctrl+C to stop the server\n")
    
    uvicorn.run(
        "src.app.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

PROMPT_HISTORY_PATH = os.path.join(os.path.dirname(__file__), 'data', 'processed', 'prompt_history.json')
CSV_PATH = os.path.join(os.path.dirname(__file__), 'data', 'raw', 'nco_dataset_v3.csv')
DOCUMENTS_PATH = os.path.join(os.path.dirname(__file__), 'data', 'processed', 'nco_documents.json')
METADATA_PATH = os.path.join(os.path.dirname(__file__), 'data', 'processed', 'nco_metadata.json')
GN_PATH = os.path.join(os.path.dirname(__file__), 'data', 'processed', 'nco_graph.json')
EMBEDDINGS_PATH = os.path.join(os.path.dirname(__file__), 'models', 'nco_embeddings.npy')
INDEX_PATH = os.path.join(os.path.dirname(__file__), 'models', 'nco_faiss.index')
ADMIN_DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'admin.db')


def _get_admin_db_conn():
    os.makedirs(os.path.dirname(ADMIN_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(ADMIN_DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS admin_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    return conn


def _get_admin_setting(key):
    conn = _get_admin_db_conn()
    try:
        cur = conn.execute("SELECT value FROM admin_settings WHERE key = ?", (key,))
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _set_admin_setting(key, value):
    conn = _get_admin_db_conn()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO admin_settings (key, value) VALUES (?, ?)",
            (key, value),
        )
        conn.commit()
    finally:
        conn.close()


def _hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    pwd = password.encode("utf-8")
    salt_bytes = salt.encode("utf-8")
    digest = hashlib.pbkdf2_hmac("sha256", pwd, salt_bytes, 200_000).hex()
    return f"{salt}${digest}"


def _verify_password(password, stored):
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    candidate = _hash_password(password, salt)
    return secrets.compare_digest(candidate, stored)


def _require_admin_password(password):
    if not password or not str(password).strip():
        return False, "Password is required"

    stored = _get_admin_setting("admin_password_hash")
    if not stored:
        # First-time setup: store password and lock it.
        _set_admin_setting("admin_password_hash", _hash_password(password))
        return True, None

    if _verify_password(password, stored):
        return True, None

    return False, "Invalid password"


def _ensure_prompt_history_file():
    os.makedirs(os.path.dirname(PROMPT_HISTORY_PATH), exist_ok=True)
    if not os.path.exists(PROMPT_HISTORY_PATH):
        with open(PROMPT_HISTORY_PATH, 'w', encoding='utf-8') as f:
            f.write('[]')


def _read_prompt_history():
    _ensure_prompt_history_file()
    try:
        with open(PROMPT_HISTORY_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _write_prompt_history(history):
    os.makedirs(os.path.dirname(PROMPT_HISTORY_PATH), exist_ok=True)
    tmp_path = PROMPT_HISTORY_PATH + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, PROMPT_HISTORY_PATH)


def _append_prompt_history_entry(entry):
    history = _read_prompt_history()
    history.append(entry)
    if len(history) > 5000:
        history = history[-5000:]
    _write_prompt_history(history)


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
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(f"Missing CSV: {CSV_PATH}")
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    required_fields = [
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
    for field in required_fields:
        if field not in fieldnames:
            fieldnames.append(field)
    return fieldnames, rows


def _write_csv_rows(fieldnames, rows):
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    tmp_path = CSV_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp_path, CSV_PATH)


def _build_documents_and_metadata(rows):
    documents = []
    metadata = []
    for idx, row in enumerate(rows):
        doc = f"""
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
        documents.append(doc)
        metadata.append({
            "row_id": idx,
            "nco_2015": _safe_text(row.get("NCO 2015")),
            "occupation_title": _safe_text(row.get("Occupational Title")),
        })
    return documents, metadata


def _rebuild_search_assets(rows):
    # Rebuild processed JSON files
    documents, metadata = _build_documents_and_metadata(rows)
    os.makedirs(os.path.dirname(DOCUMENTS_PATH), exist_ok=True)
    with open(DOCUMENTS_PATH, "w", encoding="utf-8") as f:
        json.dump(documents, f, indent=2, ensure_ascii=False)
    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    # Rebuild graph keywords
    gn = {}
    for idx, item in enumerate(metadata):
        code = item["nco_2015"]
        desc = documents[idx].lower() if idx < len(documents) else ""
        words = re.findall(r"\b[a-z]{3,}\b", desc)
        keywords = list(set(words))
        sector = "unknown"
        if "division:" in desc:
            lines = desc.split("\n")
            for line in lines:
                if line.strip().startswith("division:"):
                    sector = line.split(":", 1)[1].strip().title()
                    break
        gn[code] = {"sector": sector, "keywords": keywords}
    with open(GN_PATH, "w", encoding="utf-8") as f:
        json.dump(gn, f, indent=2, ensure_ascii=False)

    # Rebuild embeddings and FAISS index
    from sentence_transformers import SentenceTransformer
    import numpy as np
    import faiss

    model = SentenceTransformer("BAAI/bge-small-en-v1.5")
    embeddings = model.encode(
        documents,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    os.makedirs(os.path.dirname(EMBEDDINGS_PATH), exist_ok=True)
    np.save(EMBEDDINGS_PATH, embeddings)

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
    faiss.write_index(index, INDEX_PATH)


def _build_result_from_row(row, row_id):
    return {
        "occupation_title": _safe_text(row.get("Occupational Title")),
        "row_id": row_id,
        "nco_code": _normalize_nco_code(row.get("NCO 2015")),
        "semantic_score": 1.0,
        "gn_score": 0.0,
        "final_score": 1.0,
        "details": {
            "nco_2004_code": _safe_text(row.get("NCO 2004")),
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
            results.append(_build_result_from_row(row, idx))
    return results

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
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
    try:
        top_k = int(data.get('top_k', request.args.get('top_k', 5)))
    except (TypeError, ValueError):
        top_k = 5
    top_k = max(1, min(top_k, 100))
    
    try:
        if query:
            if search_mode == "nco":
                results = _search_by_nco_code(query)[:top_k]
                return jsonify({
                    "results": results,
                    "suggestion": None,
                    "translation_notice": None,
                    "language_ambiguity": None,
                    "top_k": top_k
                })

            # Check for language ambiguity
            detected_lang, is_ambiguous, alternative_lang = translation_service.detect_language_with_confidence(query)
            language_ambiguity = None
            
            if is_ambiguous and not user_language:
                # If ambiguous and user hasn't confirmed, ask user to select
                language_ambiguity = {
                    "is_ambiguous": True,
                    "primary_lang": detected_lang,
                    "alternative_lang": alternative_lang,
                    "message": f"Is this {detected_lang.upper()} or {alternative_lang.upper()}?"
                }
                # Return search with English results first as preview
                translated_query = translation_service.translate_with_lingua(query, source_lang="auto", target_lang="en")
            elif user_language:
                # User confirmed language, use it
                detected_lang = user_language
                translated_query = translation_service.translate_with_lingua(query, source_lang=user_language, target_lang="en")
            else:
                # No ambiguity, proceed normally
                translated_query = translation_service.translate_with_lingua(query, source_lang="auto", target_lang="en")
            
            # Check if translation occurred
            translation_notice = None
            if translated_query.lower() != query.lower():
                translation_notice = {
                    "original": query,
                    "translated": translated_query,
                    "message": f"Query translated from original text"
                }
            
            # Use the search function for specific queries
            results = search_module.search(translated_query, top_k=top_k)
            for r in results:
                if "nco_code" in r:
                    r["nco_code"] = _normalize_nco_code(r.get("nco_code"))

            # ------------------ PIGS ANALYSIS ------------------
            pigs_output = None

            if pigs_analyze_prompt and results:
                try:
                    level_scores, pigs_suggestions = pigs_analyze_prompt(translated_query, results)
                    prompt_examples = generate_dynamic_prompts(
                        results[0].get('occupation_title', 'professional')
                    )
                    pigs_output = {
                        "level_scores": level_scores,
                        "suggestions": pigs_suggestions,
                        "prompt_examples": prompt_examples
                    }
                except Exception:
                    pigs_output = None

            try:
                top = results[0] if results else {}
                _append_prompt_history_entry({
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "query": query,
                    "translated_query": translated_query,
                    "was_translated": translated_query.lower() != query.lower(),
                    "occupation_title": top.get('occupation_title', ''),
                    "nco_code": top.get('nco_2015', top.get('nco_code', '')),
                    "top_k": top_k,
                    "returned_count": len(results),
                    "client_ip": request.remote_addr
                })
            except Exception:
                pass

            # Generate contextual suggestion examples
            suggestion = None
            if len(results) >= 2:
                top_score = results[0].get('final_score', 0)
                next_score = results[1].get('final_score', 0)
                q_lower = translated_query.lower()
                # Check if query directly mentions a job title from top results
                top_title = results[0].get('occupation_title', '').lower()
                is_direct_job_mention = any(word in top_title for word in q_lower.split()) if top_title else False
                
                # Skip suggestions if query directly mentions a job title
                if not is_direct_job_mention:
                    # For any ambiguous or low-confidence query, use dynamic prompt generation
                    if (top_score < 0.6 and abs(top_score - next_score) < 0.05) or top_score < 0.5:
                        occupation_title = results[0].get('occupation_title', 'professional')
                        prompts = generate_dynamic_prompts(occupation_title)
                        suggestion = "Try searching like this:<br>" + "<br>".join([f"&bull; \"{prompt}\"" for prompt in prompts])
            return jsonify({
                "results": results, 
                "suggestion": suggestion, 
                "translation_notice": translation_notice,
                "language_ambiguity": language_ambiguity,
                "pigs": pigs_output,
                "top_k": top_k,
                "returned_count": len(results)
            })
        else:
            # Use the get_all_jobs function for empty queries
            _, rows = _load_csv_rows()
            results = [_build_result_from_row(row, idx) for idx, row in enumerate(rows)]
            return jsonify({
                "results": results,
                "directory_mode": True,
                "returned_count": len(results)
            })
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
        translated_text = translation_service.translate(
            text, source_lang, target_lang, preferred_service
        )
        return jsonify({
            "original_text": text,
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
def get_prompt_history():
    try:
        occupation_title = request.args.get('occupation_title', '').strip()
        try:
            limit = int(request.args.get('limit', '100'))
        except ValueError:
            limit = 100
        limit = max(1, min(limit, 500))

        history = _read_prompt_history()
        history = list(reversed(history))
        if occupation_title:
            history = [h for h in history if h.get('occupation_title') == occupation_title]
        return jsonify(history[:limit])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin/api/occupations', methods=['GET'])
def get_occupations():
    try:
        fieldnames, rows = _load_csv_rows()
        occupations = []
        for idx, row in enumerate(rows):
            occupations.append({
                "row_id": idx,
                "s_no": _safe_text(row.get("S No")),
                "occupation_title": _safe_text(row.get("Occupational Title")),
                "nco_code": _safe_text(row.get("NCO 2015")),
                "nco_2004_code": _safe_text(row.get("NCO 2004")),
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
def update_occupation(row_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        fieldnames, rows = _load_csv_rows()
        if row_id < 0 or row_id >= len(rows):
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

        existing_nco2004 = _safe_text(rows[row_id].get("NCO 2004"))
        incoming_nco2004 = data.get("nco_2004_code", existing_nco2004)
        required_2004 = bool(existing_nco2004)
        new_nco_2004, nco_2004_err = _parse_nco_2004(incoming_nco2004, required=required_2004)
        if nco_2004_err:
            return jsonify({"success": False, "error": nco_2004_err}), 400

        for i, r in enumerate(rows):
            if i == row_id:
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

        row = rows[row_id]
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

        rows[row_id] = row
        _write_csv_rows(fieldnames, rows)
        _rebuild_search_assets(rows)

        return jsonify({"success": True, "message": "Occupation updated successfully"})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/admin/api/occupations', methods=['POST'])
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

        # Compute next S No
        s_no = len(rows) + 1
        try:
            existing = [int(r.get("S No", "0") or 0) for r in rows]
            s_no = max(existing) + 1 if existing else 1
        except Exception:
            s_no = len(rows) + 1

        new_row = {
            "S No": str(s_no),
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

        rows.append(new_row)
        _write_csv_rows(fieldnames, rows)
        _rebuild_search_assets(rows)

        new_row_id = len(rows) - 1
        return jsonify({"success": True, "message": "Occupation added successfully", "row_id": new_row_id})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/admin/api/occupations/<int:row_id>', methods=['DELETE'])
def delete_occupation(row_id):
    try:
        data = request.get_json(silent=True) or {}
        ok, err = _require_admin_password(data.get("admin_password"))
        if not ok:
            return jsonify({"success": False, "error": err}), 403

        fieldnames, rows = _load_csv_rows()
        if row_id < 0 or row_id >= len(rows):
            return jsonify({"success": False, "error": "Occupation not found"}), 404

        rows.pop(row_id)
        _write_csv_rows(fieldnames, rows)
        _rebuild_search_assets(rows)

        return jsonify({"success": True, "message": "Occupation deleted successfully"})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# Analytics API endpoints
@app.route('/admin/api/analytics/divisions')
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
def analytics_confidence():
    try:
        history_file = os.path.join(os.path.dirname(__file__), 'data', 'processed', 'prompt_history.json')
        if not os.path.exists(history_file):
            return jsonify({"labels": [], "values": []})
        
        with open(history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
        
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
def analytics_top_occupations():
    try:
        history_file = os.path.join(os.path.dirname(__file__), 'data', 'processed', 'prompt_history.json')
        if not os.path.exists(history_file):
            return jsonify({"labels": [], "values": []})
        
        with open(history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
        
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
def analytics_search_trend():
    try:
        history_file = os.path.join(os.path.dirname(__file__), 'data', 'processed', 'prompt_history.json')
        if not os.path.exists(history_file):
            return jsonify({"labels": [], "values": []})
        
        with open(history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
        
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
def analytics_languages():
    try:
        history_file = os.path.join(os.path.dirname(__file__), 'data', 'processed', 'prompt_history.json')
        if not os.path.exists(history_file):
            return jsonify({"labels": [], "values": []})
        
        with open(history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
        
        language_counts = {}
        
        for entry in history:
            lang = entry.get("detected_language", "Unknown")
            language_counts[lang] = language_counts.get(lang, 0) + 1
        
        return jsonify({
            "labels": list(language_counts.keys()),
            "values": list(language_counts.values())
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/admin/api/analytics/low-confidence')
def analytics_low_confidence():
    try:
        history_file = os.path.join(os.path.dirname(__file__), 'data', 'processed', 'prompt_history.json')
        if not os.path.exists(history_file):
            return jsonify([])
        
        with open(history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
        
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

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, port=port)

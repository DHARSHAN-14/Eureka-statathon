"""Standalone NCO Search Engine API."""

import csv
import importlib.util
import os
import re
import sys

from flask import Flask, jsonify, request
from flask_cors import CORS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")
UTILS_DIR = os.path.join(BASE_DIR, "utils")

sys.path.insert(0, SCRIPTS_DIR)
sys.path.insert(0, UTILS_DIR)

SEARCH_MODULE_PATH = os.path.join(SCRIPTS_DIR, "06_searchapp.py")
spec = importlib.util.spec_from_file_location("searchapp", SEARCH_MODULE_PATH)
if not spec or not spec.loader:
    raise RuntimeError("Failed to load search module")

search_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(search_module)

from dynamic_prompts import generate_dynamic_prompts
from translation_service import translation_service

pigs_analyze_prompt = getattr(search_module, "pigs_analyze_prompt", None)

app = Flask(__name__)
CORS(app)

CSV_PATH = os.path.join(BASE_DIR, "data", "raw", "nco_dataset_v3.csv")


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


def _load_csv_rows():
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(f"Missing CSV: {CSV_PATH}")
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    return rows


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
    rows = _load_csv_rows()
    results = []
    for idx, row in enumerate(rows):
        if _normalize_nco_code(row.get("NCO 2015")) == code:
            results.append(_build_result_from_row(row, idx))
    return results


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "nco-search-engine",
        "model": "BAAI/bge-small-en-v1.5",
    })


@app.route("/api/search", methods=["POST"])
def search_jobs():
    data = request.get_json()
    if data is None:
        return jsonify({"error": "Invalid JSON"}), 400

    query = data.get("query", "").strip()
    user_language = data.get("user_language")
    search_mode = data.get("search_mode", "general")

    try:
        top_k = int(data.get("top_k", request.args.get("top_k", 5)))
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
                    "top_k": top_k,
                    "returned_count": len(results),
                })

            detected_lang, is_ambiguous, alternative_lang = translation_service.detect_language_with_confidence(query)
            language_ambiguity = None

            if is_ambiguous and not user_language:
                language_ambiguity = {
                    "is_ambiguous": True,
                    "primary_lang": detected_lang,
                    "alternative_lang": alternative_lang,
                    "message": f"Is this {detected_lang.upper()} or {alternative_lang.upper()}?",
                }
                translated_query = translation_service.translate_with_lingua(
                    query, source_lang="auto", target_lang="en"
                )
            elif user_language:
                translated_query = translation_service.translate_with_lingua(
                    query, source_lang=user_language, target_lang="en"
                )
            else:
                translated_query = translation_service.translate_with_lingua(
                    query, source_lang="auto", target_lang="en"
                )

            translation_notice = None
            if translated_query.lower() != query.lower():
                translation_notice = {
                    "original": query,
                    "translated": translated_query,
                    "message": "Query translated from original text",
                }

            results = search_module.search(translated_query, top_k=top_k)
            for result in results:
                if "nco_code" in result:
                    result["nco_code"] = _normalize_nco_code(result.get("nco_code"))

            pigs_output = None
            if pigs_analyze_prompt and results:
                try:
                    level_scores, pigs_suggestions = pigs_analyze_prompt(translated_query, results)
                    prompt_examples = generate_dynamic_prompts(
                        results[0].get("occupation_title", "professional")
                    )
                    pigs_output = {
                        "level_scores": level_scores,
                        "suggestions": pigs_suggestions,
                        "prompt_examples": prompt_examples,
                    }
                except Exception:
                    pigs_output = None

            suggestion = None
            if len(results) >= 2:
                top_score = results[0].get("final_score", 0)
                next_score = results[1].get("final_score", 0)
                q_lower = translated_query.lower()
                top_title = results[0].get("occupation_title", "").lower()
                is_direct_job_mention = any(
                    word in top_title for word in q_lower.split()
                ) if top_title else False

                if not is_direct_job_mention:
                    if (top_score < 0.6 and abs(top_score - next_score) < 0.05) or top_score < 0.5:
                        occupation_title = results[0].get("occupation_title", "professional")
                        prompts = generate_dynamic_prompts(occupation_title)
                        suggestion = "Try searching like this:<br>" + "<br>".join(
                            [f"&bull; \"{prompt}\"" for prompt in prompts]
                        )

            return jsonify({
                "results": results,
                "suggestion": suggestion,
                "translation_notice": translation_notice,
                "language_ambiguity": language_ambiguity,
                "pigs": pigs_output,
                "top_k": top_k,
                "returned_count": len(results),
            })

        rows = _load_csv_rows()
        results = [_build_result_from_row(row, idx) for idx, row in enumerate(rows)]
        return jsonify({
            "results": results,
            "directory_mode": True,
            "returned_count": len(results),
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/translate", methods=["POST"])
def translate_text():
    data = request.get_json()
    if data is None:
        return jsonify({"error": "Invalid JSON"}), 400

    text = data.get("text", "").strip()
    source_lang = data.get("source_lang", "auto")
    target_lang = data.get("target_lang", "en")
    preferred_service = data.get("preferred_service", "lingua")

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
            "service_used": preferred_service,
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/languages", methods=["GET"])
def get_supported_languages():
    try:
        languages = translation_service.get_supported_languages()
        return jsonify({"languages": languages})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")

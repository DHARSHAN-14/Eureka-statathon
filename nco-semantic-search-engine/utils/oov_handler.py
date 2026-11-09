"""
utils/oov_handler.py
━━━━━━━━━━━━━━━━━━━━━
Layer 2 — Out-Of-Vocabulary expansion.

Source of truth: the `oov_dictionary` table in PostgreSQL (populated by
scripts/generate_oov_dictionary.py). If the database is unavailable or empty,
it falls back to the editable CSV at data/processed/oov_dictionary.csv.

Expands recognised OOV terms in a query by appending standard-English concepts:

  "i traveled in rapido"  → "i traveled in rapido driver rider taxi transportation"
  "i work as a ward boy"  → "i work as a ward boy hospital attendant orderly healthcare"

Greedy longest-match n-gram scan so multi-word keys ("ward boy", "asha worker")
fire correctly. The original wording is always preserved.

This layer handles ONLY true OOV (brands, vernacular, abbreviations). Ordinary
occupational understanding comes from the dataset-derived synonym bank (Layer 1)
and SBERT — not from this file.
"""

import csv
import logging
import os
from typing import List

logger = logging.getLogger(__name__)

# Max concepts appended per OOV hit — keeps the query vector focused
_MAX_EXPAND = 4


class OOVHandler:
    def __init__(self, json_path: str = None):
        if json_path is None:
            _base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            json_path = os.path.join(_base, "data", "processed", "oov_dictionary.json")
        self.json_path = json_path
        self._oov: dict = {}
        self._max_ngram: int = 1
        self._load()

    def _load_from_json(self) -> dict:
        """Fallback: parse the OOV JSON (term -> list of concepts)."""
        if not os.path.exists(self.json_path):
            return {}
        import json
        try:
            with open(self.json_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load OOV JSON fallback: {e}")
            return {}

    def _load(self):
        """Load from PostgreSQL, falling back to the editable JSON."""
        data = {}
        try:
            from database import db_store
            data = db_store.load_oov_dictionary()
        except Exception as e:
            logger.warning(f"OOV: PostgreSQL load failed ({e}); trying JSON.")
        if not data:
            data = self._load_from_json()

        self._oov = data
        self._max_ngram = max((len(k.split()) for k in self._oov), default=1)
        logger.info(
            f"OOV Handler loaded {len(self._oov)} entries "
            f"(max phrase length {self._max_ngram})."
        )

    def get_known_oov_words(self) -> List[str]:
        """Return all OOV keys — used to protect these terms from spell correction."""
        return list(self._oov.keys())

    def process_query(self, query: str) -> str:
        """
        Greedy longest-match n-gram expansion. At each position the longest
        phrase (up to _max_ngram tokens) present in the dictionary wins; its
        original tokens are kept and up to _MAX_EXPAND concepts are appended.
        """
        if not query:
            return query

        tokens = query.lower().split()
        n = len(tokens)
        out: list = []
        i = 0
        while i < n:
            matched = False
            for size in range(min(self._max_ngram, n - i), 0, -1):
                phrase = " ".join(tokens[i:i + size])
                concepts = self._oov.get(phrase)
                if concepts:
                    out.extend(tokens[i:i + size])
                    out.extend(concepts[:_MAX_EXPAND])
                    logger.info(f"OOV hit: '{phrase}' -> {concepts[:_MAX_EXPAND]}")
                    i += size
                    matched = True
                    break
            if not matched:
                out.append(tokens[i])
                i += 1
        return " ".join(out)

    def reload(self):
        """Hot-reload after regenerating the dictionary."""
        self._load()


# Singleton — imported by searchapp.py
oov_handler = OOVHandler()

import requests
import json
import logging
import os
import threading
import re
from typing import Optional, Dict, Any
from langdetect import detect, detect_langs, LangDetectException

# Monkeypatch dataclasses to allow mutable defaults of custom objects (e.g. dataclass instances),
# which is required for fairseq and hydra to work on Python 3.11+ without throwing ValueErrors.
import dataclasses
orig_get_field = dataclasses._get_field

def patched_get_field(cls, a_name, a_type, default_kw_only):
    default = getattr(cls, a_name, dataclasses.MISSING)
    default_val = default.default if isinstance(default, dataclasses.Field) else default
    if default_val is not dataclasses.MISSING and default_val is not None:
        cls_type = default_val.__class__
        if cls_type not in (list, dict, set) and getattr(cls_type, '__hash__', None) is None:
            orig_hash = cls_type.__hash__
            try:
                cls_type.__hash__ = lambda self: 0
                return orig_get_field(cls, a_name, a_type, default_kw_only)
            except TypeError:
                pass
            finally:
                cls_type.__hash__ = orig_hash
    return orig_get_field(cls, a_name, a_type, default_kw_only)

dataclasses._get_field = patched_get_field

# Monkeypatch importlib.machinery.FileFinder to restore find_module in Python 3.12+ for hydra-core 1.0.7
import importlib.machinery
if not hasattr(importlib.machinery.FileFinder, 'find_module'):
    def filefinder_find_module(self, fullname, path=None):
        spec = self.find_spec(fullname, path)
        return spec.loader if spec is not None else None
    importlib.machinery.FileFinder.find_module = filefinder_find_module

# Backfill OmegaConf.update(merge=) which was added in omegaconf 2.1.
# hydra-core 1.0.7 calls this kwarg; omegaconf 2.0.x doesn't have it.
try:
    import inspect as _ins, omegaconf as _oc
    if 'merge' not in _ins.signature(_oc.OmegaConf.update).parameters:
        _orig_oc_update = _oc.OmegaConf.update.__func__
        @staticmethod
        def _patched_oc_update(cfg, key, value=None, merge=False):
            return _orig_oc_update(cfg, key, value)
        _oc.OmegaConf.update = _patched_oc_update
except Exception:
    pass  # omegaconf not installed — will be patched in-place during package setup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# IndicTrans2 Flores-101 BCP-47 language codes — covers all 22 scheduled Indian languages + English
INDICTRANS_LANG_MAP = {
    "en":  "eng_Latn",
    "hi":  "hin_Deva",
    "ta":  "tam_Taml",
    "te":  "tel_Telu",
    "bn":  "ben_Beng",
    "mr":  "mar_Deva",
    "gu":  "guj_Gujr",
    "kn":  "kan_Knda",
    "ml":  "mal_Mlym",
    "pa":  "pan_Guru",
    "ur":  "urd_Arab",
    "as":  "asm_Beng",   # Assamese
    "or":  "ory_Orya",   # Odia
    "ne":  "npi_Deva",   # Nepali
    "sa":  "san_Deva",   # Sanskrit
    "sd":  "snd_Arab",   # Sindhi
    "mai": "mai_Deva",   # Maithili
    "kok": "kok_Deva",   # Konkani
    "mni": "mni_Mtei",   # Meitei / Manipuri
    "doi": "doi_Deva",   # Dogri
    "ks":  "kas_Arab",   # Kashmiri
    "brx": "brx_Deva",   # Bodo
    "sat": "sat_Olck",   # Santali
}


class TranslationService:
    """Offline translation using IndicTrans2 (CTranslate2 int8) + AI4Bharat transliteration."""

    def __init__(self):
        _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # IndicTrans2 CT2 model directory
        _it2_env = os.getenv(
            "INDICTRANS2_CT2_DIR",
            os.path.join(_project_root, "models", "indictrans2-ct2"),
        )
        if not os.path.isabs(_it2_env):
            _it2_env = os.path.join(_project_root, _it2_env)
        self.indictrans2_ct2_dir = os.path.normpath(_it2_env)

        self._it2_translator = None   # ctranslate2.Translator
        self._it2_src_sp     = None   # sentencepiece source model (vocab/model.SRC)
        self._it2_tgt_sp     = None   # sentencepiece target model (vocab/model.TGT)
        self._it2_ip         = None   # IndicProcessor
        self._it2_lock       = threading.Lock()

        # Transliteration — a SINGLE shared multilingual XlitEngine handles all
        # languages. (A separate engine per language would load a full ~2GB model
        # copy each time and exhaust RAM, causing multi-minute swap-thrashing.)
        self._xlit_engine   = None
        self._xlit_lock     = threading.Lock()
        self._xlit_patched  = False

        # Spellchecker for selective transliteration
        self._spell = None
        try:
            from spellchecker import SpellChecker
            self._spell = SpellChecker()
            hinglish_stop = [
                "mai", "tu", "hai", "tha", "thi", "the", "hu", "ho", "me", "to",
                "in", "is", "par", "pe", "se", "ko", "ka", "ki", "ke", "wo", "woh",
                "yeh", "ye", "kya", "kyu", "kaha", "kab", "kon", "mera", "meri",
                "mere", "tera", "teri", "tere", "uska", "uski", "uske", "unka",
                "unki", "unke", "humar", "humari", "humare", "aap", "aapka",
                "aapki", "aapke", "naukri",
            ]
            self._spell.word_frequency.remove_words(hinglish_stop)
            logger.info("pyspellchecker loaded for selective transliteration.")
        except ImportError:
            logger.warning("pyspellchecker not found. Selective transliteration will fall back to default behavior.")

        # Pre-warm models in the background so the first user search isn't slow.
        # IndicTrans2 and XlitEngine both take ~10-20s to load; doing it at startup
        # means the user never waits on their first query.
        _warm_thread = threading.Thread(target=self._prewarm_models, daemon=True)
        _warm_thread.start()

    def _prewarm_models(self):
        """Background thread: load IndicTrans2 + the shared XlitEngine after startup."""
        import time
        time.sleep(5)  # let Flask finish binding before burning CPU on model loads

        try:
            logger.info("Pre-warming IndicTrans2 CT2 model...")
            self._init_indictrans2()
            logger.info("IndicTrans2 CT2 ready.")
        except Exception as e:
            logger.warning(f"IndicTrans2 pre-warm failed: {e}")

        # One shared multilingual XlitEngine covers every language.
        try:
            logger.info("Pre-warming shared XlitEngine...")
            self._init_xlit_engine()
            logger.info("XlitEngine ready.")
        except Exception as e:
            logger.warning(f"XlitEngine pre-warm failed: {e}")

    # ------------------------------------------------------------------
    # IndicTrans2 CT2 — lazy init (thread-safe)
    # ------------------------------------------------------------------

    def _init_indictrans2(self) -> bool:
        """Load IndicTrans2 CT2 model, SPM tokenizers, and IndicProcessor on first use."""
        if self._it2_translator is not None:
            return True

        with self._it2_lock:
            if self._it2_translator is not None:
                return True

            ct2_dir  = self.indictrans2_ct2_dir
            src_spm  = os.path.join(ct2_dir, "vocab", "model.SRC")
            tgt_spm  = os.path.join(ct2_dir, "vocab", "model.TGT")

            if not os.path.isfile(os.path.join(ct2_dir, "model.bin")):
                logger.warning(
                    f"IndicTrans2 CT2 model not found at {ct2_dir}. "
                    "Run: python scripts/download_indictrans2_model.py"
                )
                return False

            try:
                import ctranslate2
                import sentencepiece
                from IndicTransToolkit import IndicProcessor

                logger.info(f"Loading IndicTrans2 CT2 model from {ct2_dir} ...")

                self._it2_ip     = IndicProcessor(inference=True)
                self._it2_src_sp = sentencepiece.SentencePieceProcessor(src_spm)
                self._it2_tgt_sp = sentencepiece.SentencePieceProcessor(tgt_spm)

                # inter_threads=4 keeps single-query inference fast on CPU
                self._it2_translator = ctranslate2.Translator(
                    ct2_dir,
                    device="cpu",
                    inter_threads=4,
                )

                logger.info("IndicTrans2 CT2 loaded successfully.")
                return True

            except Exception as e:
                logger.error(f"Failed to load IndicTrans2 CT2: {e}")
                return False

    # ------------------------------------------------------------------
    # Core translation
    # ------------------------------------------------------------------

    def translate_with_indictrans2(
        self,
        text: str,
        source_lang: str = "auto",
        target_lang: str = "en",
    ) -> str:
        """
        Translate text using the offline IndicTrans2 CT2 model (Indic → English).

        Model: adalat-ai/ct2-rotary-indictrans2-indic-en-dist-200M
        Tokenization: sentencepiece (vocab/model.SRC + vocab/model.TGT)
        Input format: [src_lang_tag] + spm_tokens  (CT2 auto-appends </s> per config)
        Target: English-only decoder — no target prefix required
        """
        if not self._init_indictrans2():
            return text

        try:
            if source_lang == "auto":
                source_lang = self.detect_language(text)

            if source_lang == target_lang or source_lang[:2] == target_lang[:2]:
                return text

            src_tag = INDICTRANS_LANG_MAP.get(source_lang) or INDICTRANS_LANG_MAP.get(source_lang[:2])

            if not src_tag:
                logger.warning(f"Unsupported source language: {source_lang}")
                return text

            logger.info(f"Translating {src_tag} -> eng_Latn via IndicTrans2 CT2 ...")

            # IndicProcessor: Unicode normalisation + script-specific preprocessing.
            # preprocess_batch embeds language tags as plain text, e.g.:
            #   'नौकरी' → 'hin_Deva eng_Latn नौकरी'
            # The SPM model does NOT know these tags as single tokens (id=0 for both),
            # so we strip the embedded prefix and inject src_tag directly as a CT2
            # vocabulary token, which the CT2 source_vocabulary.json does know.
            preprocessed = self._it2_ip.preprocess_batch(
                [text], src_lang=src_tag, tgt_lang="eng_Latn"
            )[0]
            tag_prefix = f"{src_tag} eng_Latn "
            clean_text = preprocessed[len(tag_prefix):] if preprocessed.startswith(tag_prefix) else preprocessed

            # Tokenise with source SPM, then prepend the language tag as a raw CT2 token.
            # add_source_eos=true in config.json → CT2 appends </s> automatically.
            spm_tokens   = self._it2_src_sp.encode(clean_text, out_type=str)
            input_tokens = [src_tag] + spm_tokens

            # CT2 beam search — fast int8 inference, no torch involved.
            # English-only target decoder: no target_prefix needed.
            results = self._it2_translator.translate_batch(
                [input_tokens],
                beam_size=4,
                max_decoding_length=256,
                no_repeat_ngram_size=4,
            )

            # Decode with target SPM
            output_tokens  = results[0].hypotheses[0]
            raw_translated = self._it2_tgt_sp.decode(output_tokens)

            # IndicProcessor: cleanup / denormalisation
            translations = self._it2_ip.postprocess_batch([raw_translated], lang="eng_Latn")
            result = translations[0].strip() if translations else ""

            if result:
                # Normalize to lowercase — model sometimes outputs ALL-CAPS for single words;
                # SBERT is case-insensitive so this has no effect on search quality.
                result = result.lower()
                logger.info(f"IndicTrans2: '{text[:40]}' -> '{result[:40]}'")
                return result

            return text

        except Exception as e:
            logger.error(f"IndicTrans2 translation error: {e}")
            return text

    def translate(
        self,
        text: str,
        source_lang: str = "auto",
        target_lang: str = "en",
        preferred_service: str = None,  # kept for API compat — ignored
    ) -> str:
        """Translate text using the offline IndicTrans2 CT2 model."""
        if not text or not text.strip():
            return text

        text = text.strip()

        if os.path.isfile(os.path.join(self.indictrans2_ct2_dir, "model.bin")):
            result = self.translate_with_indictrans2(text, source_lang, target_lang)
            if result and result.strip().lower() != text.strip().lower():
                return result

        return text

    # ------------------------------------------------------------------
    # Transliteration (XlitEngine — unchanged from original)
    # ------------------------------------------------------------------

    def _init_xlit_engine(self, lang_code: str = None):
        """Lazily load and cache ONE shared multilingual XlitEngine for all languages.

        The underlying model is multilingual regardless of language, so a single
        instance serves every language; the target language is selected per-call
        via the lang_code argument to translit_sentence/translit_word.
        """
        if self._xlit_engine is not None:
            return self._xlit_engine

        with self._xlit_lock:
            if self._xlit_engine is not None:
                return self._xlit_engine

            try:
                # urduhack (pulled in by ai4bharat-transliteration) imports tf2crf,
                # which uses keras.src.engine — removed in Keras 3.x / TF 2.16+.
                # urduhack is only needed for Urdu/Shahmukhi script normalization;
                # a no-op mock is safe for all other Indic scripts.
                import sys as _sys, types as _types
                if "urduhack" not in _sys.modules:
                    _mock_urduhack = _types.ModuleType("urduhack")
                    _mock_urduhack.normalize = lambda x: x
                    _sys.modules["urduhack"] = _mock_urduhack
                    logger.info("Mocked urduhack (Keras 3.x compat)")

                if not self._xlit_patched:
                    import torch
                    orig_load = torch.load
                    def patched_load(*args, **kwargs):
                        kwargs['weights_only'] = False
                        return orig_load(*args, **kwargs)
                    torch.load = patched_load

                    # fairseq registers dataclass configs with hydra's ConfigStore at import
                    # time via class decorators. omegaconf 2.0.x doesn't support Tuple[...]
                    # type annotations in some scheduler dataclasses. Wrap store() to swallow
                    # only those ValidationErrors so hydra's own plugin configs still register.
                    import hydra.core.config_store as _hcs
                    from omegaconf.errors import ValidationError as _OmegaValidationError
                    _orig_cs_store = _hcs.ConfigStore.store
                    def _safe_cs_store(self, *args, **kwargs):
                        try:
                            return _orig_cs_store(self, *args, **kwargs)
                        except (_OmegaValidationError, TypeError):
                            pass
                    _hcs.ConfigStore.store = _safe_cs_store

                    self._xlit_patched = True
                    logger.info("Applied torch.load + hydra ConfigStore monkeypatches for XlitEngine")

                from ai4bharat.transliteration import XlitEngine

                logger.info("Loading shared multilingual XlitEngine ...")
                # lang2use="all" loads the multilingual model once for every language.
                # rescore=False skips the ~56s "Loading dicts into RAM" language-model
                # load; transliteration quality is unaffected for our short queries.
                engine = XlitEngine("all", beam_width=4, rescore=False)
                self._xlit_engine = engine
                logger.info("Shared XlitEngine loaded successfully.")
                return engine
            except Exception as e:
                logger.exception("Failed to load shared XlitEngine")
                return None

    def is_roman_script(self, text: str) -> bool:
        """Return True if the text is primarily written in Roman/Latin script."""
        if not text:
            return False
        cleaned = re.sub(r'[^a-zA-Z\s]', '', text)
        if not cleaned.strip():
            return False
        total_letters = len(re.sub(r'[^a-zA-Z]', '', text))
        total_chars   = len(text.replace(" ", ""))
        if total_chars == 0:
            return False
        return (total_letters / total_chars) > 0.7

    def transliterate(self, text: str, lang_code: str) -> str:
        """Transliterate from Roman script to native Indic script (selective — preserves English words)."""
        if not text or not text.strip():
            return text

        engine = self._init_xlit_engine(lang_code)
        if not engine:
            return text

        try:
            if self._spell:
                tokens = re.split(r'(\s+)', text)
                result_tokens = []
                hindi_buffer  = []

                def flush_buffer():
                    if not hindi_buffer:
                        return
                    chunk_str = "".join(hindi_buffer)
                    stripped  = chunk_str.strip()
                    if not stripped:
                        result_tokens.append(chunk_str)
                        hindi_buffer.clear()
                        return
                    try:
                        # Pass lang_code so the shared engine transliterates ONLY
                        # this language (returns a str) instead of all 22 (a dict).
                        res = engine.translit_sentence(stripped, lang_code=lang_code)
                        if isinstance(res, dict):
                            transliterated = res.get(lang_code, stripped) or stripped
                        else:
                            transliterated = res if res else stripped
                    except Exception:
                        transliterated = stripped
                    leading_space  = chunk_str[: len(chunk_str) - len(chunk_str.lstrip())]
                    trailing_space = chunk_str[len(chunk_str.rstrip()) :]
                    result_tokens.append(leading_space + transliterated + trailing_space)
                    hindi_buffer.clear()

                for token in tokens:
                    if not token:
                        continue
                    if token.isspace():
                        hindi_buffer.append(token)
                        continue
                    clean_token = re.sub(r'[^a-zA-Z]', '', token).lower()
                    is_english  = False
                    if len(clean_token) >= 3 and clean_token in self._spell:
                        if clean_token not in {"mai", "hai", "hu", "tha", "karo", "kare", "bhi"}:
                            is_english = True
                    if is_english:
                        flush_buffer()
                        result_tokens.append(token)
                    else:
                        hindi_buffer.append(token)

                flush_buffer()
                result = "".join(result_tokens)
            else:
                res = engine.translit_sentence(text, lang_code=lang_code)
                if isinstance(res, dict):
                    result = res.get(lang_code, text) if res else text
                else:
                    result = res if res else text

            # Clean up ai4bharat debug artifacts
            try:
                import glob as _glob
                for f in _glob.glob("test_xlit*.json"):
                    try:
                        os.remove(f)
                    except OSError:
                        pass
            except Exception:
                pass

            return result

        except Exception as e:
            logger.error(f"Transliteration error for {lang_code}: {e}")
            return text

    # ------------------------------------------------------------------
    # Language detection
    # ------------------------------------------------------------------

    def detect_language_with_confidence(self, text: str) -> tuple:
        """Return (lang_code, is_ambiguous, alternative_lang)."""
        try:
            if len(text.strip()) < 3:
                return ("en", False, None)

            probabilities = detect_langs(text)
            if not probabilities:
                return ("en", False, None)

            primary_lang = probabilities[0].lang
            primary_prob = probabilities[0].prob

            is_ambiguous   = False
            alternative_lang = None

            if (
                len(probabilities) > 1
                and probabilities[1].prob > 0.3
                and (primary_prob - probabilities[1].prob) < 0.15
            ):
                is_ambiguous     = True
                alternative_lang = probabilities[1].lang
                logger.info(
                    f"Language ambiguity: {primary_lang}({primary_prob:.2f}) "
                    f"vs {alternative_lang}({probabilities[1].prob:.2f})"
                )

            logger.info(f"Detected: {primary_lang} (conf: {primary_prob:.2f}, ambiguous: {is_ambiguous})")
            return (primary_lang, is_ambiguous, alternative_lang)

        except Exception as e:
            logger.warning(f"Language detection failed for '{text[:50]}': {e}")
            return ("en", False, None)

    def detect_language(self, text: str) -> str:
        lang, _, _ = self.detect_language_with_confidence(text)
        return lang

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def get_supported_languages(self) -> Dict[str, str]:
        """Return all 22 scheduled Indian languages supported by IndicTrans2."""
        return {
            "en":  "English",
            "hi":  "Hindi",
            "ta":  "Tamil",
            "te":  "Telugu",
            "bn":  "Bengali",
            "mr":  "Marathi",
            "gu":  "Gujarati",
            "kn":  "Kannada",
            "ml":  "Malayalam",
            "pa":  "Punjabi",
            "ur":  "Urdu",
            "as":  "Assamese",
            "or":  "Odia",
            "ne":  "Nepali",
            "sa":  "Sanskrit",
            "sd":  "Sindhi",
            "mai": "Maithili",
            "kok": "Konkani",
            "mni": "Manipuri",
            "doi": "Dogri",
            "ks":  "Kashmiri",
            "brx": "Bodo",
            "sat": "Santali",
        }


# Global singleton
translation_service = TranslationService()

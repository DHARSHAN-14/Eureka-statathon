import os
import sys
import unittest

# Force UTF-8 output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add project root to sys.path
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_DIR not in sys.path:
    sys.path.append(PROJECT_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_DIR, ".env"))

from utils.translation_service import translation_service


class TestTranslationMerge(unittest.TestCase):
    """
    Tests for the IndicTrans2-backed TranslationService.
    Translation tests require the CT2 model to be downloaded first:
        python scripts/download_indictrans2_model.py
    """

    def test_roman_script_detection(self):
        print("\nTesting Roman script detection...")
        self.assertTrue(translation_service.is_roman_script("naukri chahiye"))
        self.assertTrue(translation_service.is_roman_script("computer operator"))
        self.assertTrue(translation_service.is_roman_script("kisani"))

        self.assertFalse(translation_service.is_roman_script("नौकरी चाहिए"))
        self.assertFalse(translation_service.is_roman_script("வணக்கம்"))
        self.assertFalse(translation_service.is_roman_script("హలో"))

    def test_transliteration_hindi(self):
        print("\nTesting Hindi transliteration (XlitEngine)...")
        transliterated = translation_service.transliterate("naukri", "hi")
        print(f"  'naukri' -> '{transliterated}'")
        self.assertEqual(transliterated, "नौकरी")

        transliterated_phrase = translation_service.transliterate("kisani", "hi")
        print(f"  'kisani' -> '{transliterated_phrase}'")
        self.assertEqual(transliterated_phrase, "किसानी")

    def test_translation_hindi(self):
        print("\nTesting Hindi -> English translation (IndicTrans2 CT2)...")
        translated = translation_service.translate("नौकरी", source_lang="hi", target_lang="en")
        print(f"  'नौकरी' -> '{translated}'")
        self.assertTrue(
            any(w in translated.lower() for w in ("job", "employment", "work", "occupation")),
            f"Unexpected translation: '{translated}'"
        )

    def test_english_query_with_hindi_dropdown(self):
        print("\nTesting English query with Hindi dropdown (roundtrip) ...")
        query     = "doctor"
        lang_code = "hi"

        self.assertTrue(translation_service.is_roman_script(query))

        # Step 1 — transliterate Roman → Devanagari
        transliterated = translation_service.transliterate(query, lang_code)
        print(f"  Transliterated: '{query}' -> '{transliterated}'")

        # Step 2 — translate Devanagari → English (IndicTrans2)
        translated_query = translation_service.translate(
            transliterated, source_lang=lang_code, target_lang="en"
        )
        print(f"  Translated: '{transliterated}' -> '{translated_query}'")
        self.assertEqual(translated_query.lower(), "doctor")

    def test_supported_languages_coverage(self):
        print("\nTesting supported languages coverage ...")
        langs = translation_service.get_supported_languages()
        self.assertGreaterEqual(len(langs), 22, "Expected all 22 scheduled Indian languages")
        for code in ("hi", "ta", "te", "bn", "mr", "gu", "kn", "ml", "pa", "ur"):
            self.assertIn(code, langs, f"Missing language: {code}")


if __name__ == '__main__':
    unittest.main()

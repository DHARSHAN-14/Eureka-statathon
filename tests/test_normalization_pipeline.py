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
from utils.spell_service import spell_service

class TestNormalizationPipeline(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing Test Suite ===")
        # Force initialization of spell service
        print("Training Spello...")
        spell_service.initialize()
        
    def test_roman_script_detection(self):
        print("\nTesting Roman script detection...")
        # Valid Roman script queries
        self.assertTrue(translation_service.is_roman_script("naukri chahiye"))
        self.assertTrue(translation_service.is_roman_script("computer operator"))
        self.assertTrue(translation_service.is_roman_script("kisani"))
        
        # Non-Roman script queries (native script)
        self.assertFalse(translation_service.is_roman_script("नौकरी चाहिए"))
        self.assertFalse(translation_service.is_roman_script("வணக்கம்"))
        self.assertFalse(translation_service.is_roman_script("హలో"))
        
    def test_transliteration_hindi(self):
        print("\nTesting Hindi transliteration...")
        # Test word level transliteration
        transliterated = translation_service.transliterate("naukri", "hi")
        print(f"  'naukri' -> '{transliterated}'")
        self.assertEqual(transliterated, "नौकरी")
        
        transliterated_phrase = translation_service.transliterate("kisani", "hi")
        print(f"  'kisani' -> '{transliterated_phrase}'")
        self.assertEqual(transliterated_phrase, "किसानी")
        
    def test_spell_correction(self):
        print("\nTesting English spell correction...")
        # Typos in occupational titles
        self.assertEqual(spell_service.correct("accounting clrk"), "accounting clerk")
        self.assertEqual(spell_service.correct("computer operater"), "computer operator")
        
    def test_spell_correction_bypass(self):
        print("\nTesting English vocabulary bypass...")
        # Correctly spelled occupational words should not be modified
        self.assertEqual(spell_service.correct("software developer"), "software developer")
        self.assertEqual(spell_service.correct("accounting clerk"), "accounting clerk")
        self.assertEqual(spell_service.correct("computer operator"), "computer operator")

if __name__ == '__main__':
    unittest.main()

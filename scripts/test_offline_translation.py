import os
import sys

# Force UTF-8 encoding for stdout on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add project root to sys.path so we can import utils
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_DIR not in sys.path:
    sys.path.append(PROJECT_DIR)

from utils.translation_service import translation_service

def main():
    print("=== Testing Local Offline NLLB-200 Translation ===")
    
    # Check if NLLB files exist
    model_dir = translation_service.nllb_model_dir
    print(f"Model directory: {model_dir}")
    if not os.path.exists(model_dir):
        print("Error: NLLB model directory does not exist.")
        sys.exit(1)
        
    # Test translations from different languages to English
    test_cases = [
        # (text, source_lang, target_lang)
        ("नमस्ते, आप कैसे हैं?", "hi", "en"),             # Hindi
        ("வணக்கம், நீங்கள் எப்படி இருக்கிறீர்கள்?", "ta", "en"),  # Tamil
        ("హలో, మీరు ఎలా ఉన్నారు?", "te", "en"),           # Telugu
        ("नमस्कार, तुम्ही कसे आहात?", "mr", "en"),          # Marathi
        ("કેમ છો, તમે કેમ છો?", "gu", "en"),              # Gujarati
        ("ನಮಸ್ಕಾರ, ನೀವು ಹೇಗಿದ್ದೀರಾ?", "kn", "en"),          # Kannada
        ("ഹലോ, സുഖമാണോ?", "ml", "en"),                 # Malayalam
        ("ਹੈਲੋ, ਤੁਸੀਂ ਕਿਵੇਂ ਹੋ?", "pa", "en"),             # Punjabi
        ("ہیلو، آپ کیسے ہیں؟", "ur", "en"),               # Urdu
        ("Hello, how are you?", "en", "hi")              # English to Hindi
    ]
    
    # Force use of local/nllb service
    print("\nRunning translations using NLLB-200...")
    for text, src, tgt in test_cases:
        try:
            translated = translation_service.translate(
                text, source_lang=src, target_lang=tgt, preferred_service="nllb"
            )
            print(f"[{src} -> {tgt}]")
            print(f"  Original  : {text}")
            print(f"  Translated: {translated}")
            print("-" * 40)
        except Exception as e:
            print(f"Error translating '{text}': {e}")

if __name__ == "__main__":
    main()

import requests
import json
import logging
import os
import threading
import re
from typing import Optional, Dict, Any
from langdetect import detect, detect_langs, LangDetectException

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# NLLB-200 Language code mapping for standard 2-letter codes to NLLB tags
NLLB_LANG_MAP = {
    "en": "eng_Latn",
    "hi": "hin_Deva",
    "ta": "tam_Taml",
    "te": "tel_Telu",
    "bn": "ben_Beng",
    "mr": "mar_Deva",
    "gu": "guj_Gujr",
    "kn": "kan_Knda",
    "ml": "mal_Mlym",
    "pa": "pan_Guru",
    "ur": "urd_Arab"
}

class TranslationService:
    """Translation service that uses Bhashini, Google Translate, and local NLLB APIs"""
    
    def __init__(self):
        # Removed libretranslate urls
        
        # Bhashini API configuration
        self.bhashini_base_url = "https://meity-auth.ulcacontrib.org/ulca/apis/v0"
        self.bhashini_api_key = os.getenv("BHASHINI_API_KEY")
        self.bhashini_user_id = os.getenv("BHASHINI_USER_ID")
        
        # NLLB configuration
        self.nllb_model_dir = os.getenv(
            "NLLB_MODEL_DIR",
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "nllb-ct2")
        )
        self._nllb_translator = None
        self._nllb_sp = None
        self._nllb_lock = threading.Lock()
        self.preferred_service = os.getenv("PREFERRED_TRANSLATION_SERVICE", "bhashini")
        
        # Transliteration configuration
        self._xlit_engines = {}
        self._xlit_lock = threading.Lock()
        self._xlit_patched = False
        
    def _init_xlit_engine(self, lang_code: str):
        """Initialize and cache the XlitEngine for a given language code lazily"""
        if lang_code in self._xlit_engines:
            return self._xlit_engines[lang_code]
            
        with self._xlit_lock:
            # Double-checked locking
            if lang_code in self._xlit_engines:
                return self._xlit_engines[lang_code]
                
            try:
                # Monkeypatch torch.load to bypass weights_only=True restriction in newer PyTorch versions
                if not self._xlit_patched:
                    import torch
                    orig_load = torch.load
                    def patched_load(*args, **kwargs):
                        kwargs['weights_only'] = False
                        return orig_load(*args, **kwargs)
                    torch.load = patched_load
                    self._xlit_patched = True
                    logger.info("Applied torch.load monkeypatch for XlitEngine")
                
                from ai4bharat.transliteration import XlitEngine
                
                logger.info(f"Loading XlitEngine for language '{lang_code}'...")
                # Initialize engine for the specific language
                engine = XlitEngine(lang_code, beam_width=4, rescore=True)
                self._xlit_engines[lang_code] = engine
                logger.info(f"XlitEngine for '{lang_code}' loaded successfully.")
                return engine
            except Exception as e:
                logger.error(f"Failed to load XlitEngine for language '{lang_code}': {e}")
                return None
                
    def is_roman_script(self, text: str) -> bool:
        """
        Check if the text is primarily written in Roman/Latin script (e.g., ASCII characters).
        This is used to detect Hinglish, Tanglish, etc.
        """
        if not text:
            return False
            
        # Clean text of numbers and punctuation for detection
        cleaned = re.sub(r'[^a-zA-Z\s]', '', text)
        if not cleaned.strip():
            # If there are no alphabetic characters, it's not Roman script
            return False
            
        # Check ratio of English letters to total characters
        total_letters = len(re.sub(r'[^a-zA-Z]', '', text))
        # Total non-whitespace characters
        total_chars = len(text.replace(" ", ""))
        if total_chars == 0:
            return False
            
        # If more than 70% of characters are Latin/ASCII letters, we consider it Roman script
        return (total_letters / total_chars) > 0.7
        
    def transliterate(self, text: str, lang_code: str) -> str:
        """
        Transliterate a sentence from Roman script to native Indic script.
        """
        if not text or not text.strip():
            return text
            
        engine = self._init_xlit_engine(lang_code)
        if not engine:
            return text
            
        try:
            # Run built-in translit_sentence
            res = engine.translit_sentence(text)
            # res is a dict like: {'hi': 'नमस्ते दुनिया'}
            if res and lang_code in res:
                return res[lang_code]
            return text
        except Exception as e:
            logger.error(f"Error during transliteration for {lang_code}: {e}")
            return text
            
    def set_bhashini_credentials(self, api_key: str, user_id: str):
        """Set Bhashini API credentials"""
        self.bhashini_api_key = api_key
        self.bhashini_user_id = user_id
    
    def detect_language_with_confidence(self, text: str) -> tuple:
        """
        Detect language with confidence information
        Args:
            text: Text to detect language for
        Returns:
            Tuple of (language_code, is_ambiguous, alternative_language)
        """
        try:
            # For very short text, default to English to avoid misdetection
            if len(text.strip()) < 3:
                logger.info(f"Text too short ({len(text.strip())} chars), assuming English")
                return ("en", False, None)
            
            # Use langdetect to get probabilities
            probabilities = detect_langs(text)
            
            if not probabilities:
                return ("en", False, None)
            
            primary_lang = probabilities[0].lang
            primary_prob = probabilities[0].prob
            
            # Check for ambiguity - if top 2 languages are too close
            # OR if primary is non-English but contains English words
            is_ambiguous = False
            alternative_lang = None
            
            if len(probabilities) > 1 and probabilities[1].prob > 0.3 and (primary_prob - probabilities[1].prob) < 0.15:
                # High ambiguity between top 2 languages
                is_ambiguous = True
                alternative_lang = probabilities[1].lang
                logger.info(f"Language ambiguity detected: {primary_lang}({primary_prob:.2f}) vs {alternative_lang}({probabilities[1].prob:.2f})")
            
            logger.info(f"Detected language: {primary_lang} (confidence: {primary_prob:.2f}), ambiguous: {is_ambiguous}")
            return (primary_lang, is_ambiguous, alternative_lang)
            
        except Exception as e:
            logger.warning(f"Could not detect language for text: {text[:50]}, error: {str(e)}")
            return ("en", False, None)
    
    def detect_language(self, text: str) -> str:
        """
        Detect the language of the text with confidence checking
        Args:
            text: Text to detect language for
        Returns:
            Language code (e.g., 'en', 'hi', 'es') or 'en' if detection fails
        """
        lang, _, _ = self.detect_language_with_confidence(text)
        return lang
    
    def translate_with_google(self, text: str, source_lang: str = "auto", target_lang: str = "en") -> str:
        """
        Translate using Google Translate (via deep-translator package)
        """
        if source_lang == "auto":
            detected_lang = self.detect_language(text)
            if detected_lang == target_lang or detected_lang == target_lang[:2]:
                logger.info(f"Text is already in {target_lang}, skipping translation")
                return text
            source_lang = detected_lang
        
        if source_lang == "en" or source_lang.startswith("en"):
            logger.info(f"Source language is English, skipping translation")
            return text
            
        logger.info(f"Translating from {source_lang} to {target_lang} using Google Translate...")
        try:
            from deep_translator import GoogleTranslator
            google_source = source_lang if source_lang != "auto" else "auto"
            translator = GoogleTranslator(source=google_source, target=target_lang)
            translated = translator.translate(text)
            
            if translated and translated.strip().lower() != text.strip().lower():
                logger.info(f"Google translation successful: '{text[:40]}' -> '{translated[:40]}'")
                return translated
            else:
                logger.warning(f"Google translation returned unchanged text")
                return text
        except ImportError:
            logger.error("deep-translator is not installed. Please run: pip install deep-translator")
            return text
        except Exception as e:
            logger.error(f"Google translation error: {str(e)}")
            return text
    
    def translate_with_bhashini(self, text: str, source_lang: str = "auto", target_lang: str = "en") -> str:
        """
        Translate text using Bhashini API
        Args:
            text: Text to translate
            source_lang: Source language code (default: "auto")
            target_lang: Target language code (default: "en")
        Returns:
            Translated text or original text if translation fails
        """
        if not self.bhashini_api_key or not self.bhashini_user_id:
            logger.warning("Bhashini credentials not set")
            return text
        
        try:
            # Language code mapping for Bhashini
            lang_mapping = {
                "en": "en",
                "hi": "hi",
                "ta": "ta",
                "te": "te",
                "bn": "bn",
                "mr": "mr",
                "gu": "gu",
                "kn": "kn",
                "ml": "ml",
                "pa": "pa",
                "ur": "ur",
                "auto": "en"  # Default to English for auto detection
            }
            
            source = lang_mapping.get(source_lang, source_lang)
            target = lang_mapping.get(target_lang, target_lang)
            
            # Get pipeline configuration
            pipeline_url = f"{self.bhashini_base_url}/model/compute"
            headers = {
                "Authorization": f"{self.bhashini_user_id} {self.bhashini_api_key}",
                "Content-Type": "application/json"
            }
            
            # Translation pipeline request
            pipeline_data = {
                "pipelineTasks": [
                    {
                        "taskType": "translation",
                        "config": {
                            "language": {
                                "sourceLanguage": source,
                                "targetLanguage": target
                            }
                        }
                    }
                ],
                "inputData": [
                    {
                        "source": text
                    }
                ]
            }
            
            response = requests.post(pipeline_url, headers=headers, json=pipeline_data, timeout=15)
            
            if response.status_code == 200:
                result = response.json()
                pipeline_response = result.get('pipelineResponse', [])
                
                if pipeline_response:
                    output = pipeline_response[0].get('output', [])
                    if output:
                        translated_text = output[0].get('target', text)
                        return translated_text
            
            logger.warning(f"Bhashini API error: {response.status_code}")
            return text
            
        except Exception as e:
            logger.error(f"Bhashini translation error: {str(e)}")
            return text
    
    def _init_nllb(self) -> bool:
        """Initialize NLLB model lazily with a thread lock"""
        if self._nllb_translator is not None:
            return True
            
        with self._nllb_lock:
            # Double-checked locking
            if self._nllb_translator is not None:
                return True
                
            if not os.path.exists(self.nllb_model_dir):
                logger.warning(f"NLLB model directory not found at {self.nllb_model_dir}")
                return False
                
            try:
                import ctranslate2
                import sentencepiece
                
                logger.info(f"Loading NLLB-200 model from {self.nllb_model_dir}...")
                sp_model_path = os.path.join(self.nllb_model_dir, "sentencepiece.bpe.model")
                if not os.path.exists(sp_model_path):
                    logger.error(f"NLLB sentencepiece model not found at {sp_model_path}")
                    return False
                    
                self._nllb_sp = sentencepiece.SentencePieceProcessor(sp_model_path)
                self._nllb_translator = ctranslate2.Translator(self.nllb_model_dir, device="cpu")
                logger.info("NLLB-200 model loaded successfully.")
                return True
            except Exception as e:
                logger.error(f"Failed to load NLLB-200 model: {str(e)}")
                return False

    def translate_with_nllb(self, text: str, source_lang: str = "auto", target_lang: str = "en") -> str:
        """
        Translate text using offline NLLB model
        """
        if not self._init_nllb():
            return text
            
        try:
            if source_lang == "auto":
                source_lang = self.detect_language(text)
                
            if source_lang == target_lang or source_lang[:2] == target_lang[:2]:
                return text
                
            src_nllb = NLLB_LANG_MAP.get(source_lang, NLLB_LANG_MAP.get(source_lang[:2]))
            tgt_nllb = NLLB_LANG_MAP.get(target_lang, NLLB_LANG_MAP.get(target_lang[:2]))
            
            if not src_nllb or not tgt_nllb:
                logger.warning(f"Unsupported NLLB language mapping: {source_lang} -> {target_lang}")
                return text
                
            logger.info(f"Translating from {src_nllb} to {tgt_nllb} using NLLB-200...")
            
            tokens = self._nllb_sp.encode(text, out_type=str)
            input_tokens = [src_nllb] + tokens + ["</s>"]
            
            results = self._nllb_translator.translate_batch([input_tokens], target_prefix=[[tgt_nllb]])
            
            output_tokens = results[0].hypotheses[0]
            translated = self._nllb_sp.decode(output_tokens[1:])
            
            if translated and translated.strip():
                logger.info(f"NLLB translation successful: '{text[:40]}' -> '{translated[:40]}'")
                return translated.strip()
            
            return text
        except Exception as e:
            logger.error(f"NLLB translation error: {str(e)}")
            return text

    def translate(self, text: str, source_lang: str = "auto", target_lang: str = "en", 
                  preferred_service: str = None) -> str:
        """
        Translate text with fallback chain.
        Preferred service can be: "bhashini", "google", "nllb", or "local".
        """
        if not text or not text.strip():
            return text
        
        text = text.strip()
        
        if preferred_service is None:
            preferred_service = self.preferred_service
            
        # Determine the order of services to try
        services = []
        if preferred_service in ("nllb", "local"):
            services = ["nllb", "bhashini", "google"]
        elif preferred_service == "google":
            services = ["google", "bhashini", "nllb"]
        else:  # default or "bhashini"
            services = ["bhashini", "google", "nllb"]
            
        for service in services:
            if service == "bhashini":
                if self.bhashini_api_key and self.bhashini_user_id:
                    result = self.translate_with_bhashini(text, source_lang, target_lang)
                    if result and result.strip().lower() != text.strip().lower():
                        return result
            elif service == "google":
                result = self.translate_with_google(text, source_lang, target_lang)
                if result and result.strip().lower() != text.strip().lower():
                    return result
            elif service == "nllb":
                if os.path.exists(self.nllb_model_dir):
                    result = self.translate_with_nllb(text, source_lang, target_lang)
                    if result and result.strip().lower() != text.strip().lower():
                        return result
                        
        # If all fail or unchanged, return original text
        return text
    
    def get_supported_languages(self) -> Dict[str, str]:
        """
        Get supported languages for translation
        Returns:
            Dictionary of language codes and names
        """
        return {
            "en": "English",
            "hi": "Hindi",
            "ta": "Tamil",
            "te": "Telugu",
            "bn": "Bengali",
            "mr": "Marathi",
            "gu": "Gujarati",
            "kn": "Kannada",
            "ml": "Malayalam",
            "pa": "Punjabi",
            "ur": "Urdu"
        }

# Global translation service instance
translation_service = TranslationService()

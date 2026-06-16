import requests
import json
import logging
from typing import Optional, Dict, Any
from langdetect import detect, detect_langs, LangDetectException

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TranslationService:
    """Translation service that uses LibreTranslate and Bhashini APIs"""
    
    def __init__(self):
        # LibreTranslate API configuration
        self.libretranslate_urls = [
            "https://libretranslate.de/translate",  # Primary
            "https://lt.vern.cc/translate",  # Fallback 1
            "https://libretranslate.com/translate",  # Fallback 2
        ]
        
        # Bhashini API configuration
        self.bhashini_base_url = "https://meity-auth.ulcacontrib.org/ulca/apis/v0"
        self.bhashini_api_key = None  # Set your Bhashini API key here
        self.bhashini_user_id = None  # Set your Bhashini user ID here
    
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
    
    def translate_with_lingua(self, text: str, source_lang: str = "auto", target_lang: str = "en") -> str:
        """
        Fast translation using MyMemory first, then LibreTranslate as fallback
        Skips translation if text is already in target language
        Args:
            text: Text to translate
            source_lang: Source language code (default: "auto")
            target_lang: Target language code (default: "en")
        Returns:
            Translated text or original text if translation fails
        """
        # Detect language if source is auto
        if source_lang == "auto":
            detected_lang = self.detect_language(text)
            
            # If already in target language, skip translation
            if detected_lang == target_lang or detected_lang == target_lang[:2]:  # Handle 'en' vs 'en-US'
                logger.info(f"Text is already in {target_lang}, skipping translation")
                return text
            
            source_lang = detected_lang
        
        # Also check if source_lang is already English
        if source_lang == "en" or source_lang.startswith("en"):
            logger.info(f"Source language is English, skipping translation")
            return text
        
        # Try MyMemory API first (fastest)
        logger.info(f"Translating from {source_lang} to {target_lang} using MyMemory...")
        translated = self._try_mymemory_translation(text, source_lang, target_lang)
        if translated:
            # Stop here even if text unchanged - MyMemory is the fastest
            logger.info(f"MyMemory returned result (even if unchanged), skipping fallbacks")
            return translated
        
        # Try LibreTranslate instances as fallback only if MyMemory failed/timed out
        logger.warning(f"MyMemory failed, trying LibreTranslate fallbacks...")
        for i, url in enumerate(self.libretranslate_urls):
            logger.info(f"Trying LibreTranslate instance {i+1}: {url}")
            translated = self._try_libretranslate_translation(text, source_lang, target_lang, url)
            if translated:
                return translated
        
        # If all translation attempts fail, return original text
        logger.warning(f"All translation services failed, returning original text")
        return text
    
    def _try_libretranslate_translation(self, text: str, source_lang: str, target_lang: str, url: str) -> Optional[str]:
        """
        Try to translate using LibreTranslate API
        Args:
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
            url: LibreTranslate endpoint URL
        Returns:
            Translated text or None if failed
        """
        try:
            payload = {
                "q": text,
                "source": source_lang if source_lang != "auto" else "auto",
                "target": target_lang
            }
            response = requests.post(url, json=payload, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                translated = data.get('translatedText', text)
                logger.info(f"LibreTranslate translation successful: '{text[:50]}' -> '{translated[:50]}'")
                return translated
            else:
                logger.warning(f"LibreTranslate API error: {response.status_code} from {url}")
                return None
                
        except requests.exceptions.Timeout:
            logger.warning(f"LibreTranslate API timeout from {url}")
            return None
        except Exception as e:
            logger.warning(f"LibreTranslate translation error from {url}: {str(e)}")
            return None
    
    def _try_mymemory_translation(self, text: str, source_lang: str, target_lang: str) -> Optional[str]:
        """
        Try to translate using MyMemory API (free translation service) - FAST
        Args:
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
        Returns:
            Translated text or None if failed
        """
        # Map language codes to MyMemory format if needed
        mymemory_source = source_lang if source_lang != "auto" else "auto"
        mymemory_target = target_lang
        
        try:
            url = "https://api.mymemory.translated.net/get"
            params = {
                "q": text,
                "langpair": f"{mymemory_source}|{mymemory_target}"
            }
            # Reduced timeout from 5 to 3 seconds for faster failure detection
            response = requests.get(url, params=params, timeout=3)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("responseStatus") == 200:
                    translated = data.get("responseData", {}).get("translatedText", text)
                    logger.info(f"MyMemory translation successful: '{text[:40]}' -> '{translated[:40]}'")
                    return translated
                else:
                    logger.warning(f"MyMemory API error: {data.get('responseStatus')}")
                    return None
            else:
                logger.warning(f"MyMemory API error: HTTP {response.status_code}")
                return None
                
        except requests.exceptions.Timeout:
            logger.warning(f"MyMemory API timeout (>3s)")
            return None
        except Exception as e:
            logger.warning(f"MyMemory translation error: {str(e)}")
            return None
    
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
    
    def translate(self, text: str, source_lang: str = "auto", target_lang: str = "en", 
                  preferred_service: str = "lingua") -> str:
        """
        Translate text using preferred service with fallback
        Args:
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
            preferred_service: Preferred service ("lingua" or "bhashini")
        Returns:
            Translated text or original text if all services fail
        """
        if not text or not text.strip():
            return text
        
        text = text.strip()
        
        # Try preferred service first
        if preferred_service == "bhashini":
            result = self.translate_with_bhashini(text, source_lang, target_lang)
            if result != text:  # Translation successful
                return result
            # Fallback to Lingua
            return self.translate_with_lingua(text, source_lang, target_lang)
        else:
            result = self.translate_with_lingua(text, source_lang, target_lang)
            if result != text:  # Translation successful
                return result
            # Fallback to Bhashini
            return self.translate_with_bhashini(text, source_lang, target_lang)
    
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

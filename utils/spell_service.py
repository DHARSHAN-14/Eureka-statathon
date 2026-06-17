import os
import re
import logging
import threading
from spello.model import SpellCorrectionModel
from database.db_store import get_cached_titles, load_csv_rows

logger = logging.getLogger(__name__)

# List of common English pronouns, contractions, helping verbs, prepositions, etc.
COMMON_ENGLISH_HELPERS = {
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your", "yours", 
    "yourself", "yourselves", "he", "him", "his", "himself", "she", "her", "hers", 
    "herself", "it", "its", "itself", "they", "them", "their", "theirs", "themselves", 
    "what", "which", "who", "whom", "this", "that", "these", "those", "am", "is", "are", 
    "was", "were", "be", "been", "being", "have", "has", "had", "having", "do", "does", 
    "did", "doing", "a", "an", "the", "and", "but", "if", "or", "because", "as", "until", 
    "while", "of", "at", "by", "for", "with", "about", "against", "between", "into", 
    "through", "during", "before", "after", "above", "below", "to", "from", "up", "down", 
    "in", "out", "on", "off", "over", "under", "again", "further", "then", "once", "here", 
    "there", "when", "where", "why", "how", "all", "any", "both", "each", "few", "more", 
    "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same", "so", 
    "than", "too", "very", "s", "t", "can", "will", "just", "don", "should", "now",
    "im", "i'm", "ill", "i'll", "ive", "i've", "id", "i'd", "youre", "you're", "youll",
    "you'll", "youve", "you've", "youd", "you'd", "hes", "he's", "hell", "he'll", "hed",
    "he'd", "shes", "she's", "shell", "she'll", "shed", "she'd", "theyre", "they're",
    "theyll", "they'll", "theyve", "they've", "theyd", "they'd", "we're", "were",
    "we'll", "weve", "we've", "wed", "we'd", "cant", "can't", "wont", "won't", "dont",
    "don't", "shouldnt", "shouldn't", "couldnt", "couldn't", "wouldnt", "wouldn't"
}

class SpellService:
    """Spell correction service using HelloHaptik's Spello model trained on occupational titles"""
    
    def __init__(self):
        self._model = None
        self._vocab = set()
        self._lock = threading.Lock()
        self._initialized = False
        
    def initialize(self):
        """Initialize and train the model dynamically if not already initialized"""
        if self._initialized:
            return True
            
        with self._lock:
            if self._initialized:
                return True
                
            try:
                logger.info("Initializing SpellService...")
                
                # 1. Load titles from database/CSV for training
                titles = get_cached_titles()
                if not titles:
                    logger.warning("No occupational titles found for training Spello model.")
                    return False
                
                # 2. Build complete offline vocabulary set for correction bypass
                vocab = set()
                
                # Add English helper words
                vocab.update(COMMON_ENGLISH_HELPERS)
                
                # Add all unique words from NCO database records/CSV
                try:
                    _, rows = load_csv_rows()
                    for row in rows:
                        for val in row.values():
                            if val:
                                words = re.findall(r'\b\w+\b', str(val).lower())
                                for w in words:
                                    vocab.add(w)
                except Exception as e:
                    logger.warning(f"Failed to load NCO CSV for vocabulary: {e}")
                    
                # Add unique words from titles directly just in case
                for title in titles:
                    words = re.findall(r'\b\w+\b', title.lower())
                    for w in words:
                        vocab.add(w)

                # Load Google 10k English words file (offline)
                project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                words_file = os.path.join(project_dir, "data", "google-10000-english.txt")
                if os.path.exists(words_file):
                    try:
                        with open(words_file, "r", encoding="utf-8") as f:
                            for line in f:
                                word = line.strip().lower()
                                if word:
                                    vocab.add(word)
                        logger.info("Loaded Google 10k common English words into spelling bypass list.")
                    except Exception as e:
                        logger.warning(f"Failed to read Google 10k wordlist: {e}")
                
                self._vocab = vocab
                logger.info(f"Built spelling correction vocabulary with {len(vocab)} unique words.")
                
                # 3. Train Spello on NCO occupational titles
                logger.info("Training Spello model...")
                self._model = SpellCorrectionModel(language='en')
                self._model.train(titles)
                self._initialized = True
                logger.info("SpellService initialized and trained successfully.")
                return True
            except Exception as e:
                logger.error(f"Failed to initialize SpellService: {e}")
                return False
                
    def correct(self, text: str) -> str:
        """
        Correct spelling of English queries.
        Uses a fast vocabulary check: if all words in the text are already valid vocabulary words,
        bypasses Spello to avoid unwanted corrections.
        """
        if not text or not text.strip():
            return text
            
        text = text.strip()
        
        # Ensure model is initialized
        if not self._initialized:
            success = self.initialize()
            if not success or not self._model:
                return text
                
        # Tokenize query words
        query_words = re.findall(r'\b\w+\b', text.lower())
        if not query_words:
            return text
            
        # Vocabulary Bypass Check
        # If every word in the query is already in our valid vocabulary set,
        # skip spell correction to avoid false positives.
        all_valid = True
        for word in query_words:
            if word not in self._vocab:
                all_valid = False
                break
                
        if all_valid:
            logger.info(f"Spell correction bypassed: '{text}' consists entirely of valid vocabulary words.")
            return text
            
        try:
            # Run Spello correction
            result = self._model.spell_correct(text)
            corrected_text = result.get('spell_corrected_text', text)
            if corrected_text != text:
                logger.info(f"Spello corrected spelling: '{text}' -> '{corrected_text}'")
            return corrected_text
        except Exception as e:
            logger.error(f"Error during spell correction: {e}")
            return text

# Global singleton instance
spell_service = SpellService()

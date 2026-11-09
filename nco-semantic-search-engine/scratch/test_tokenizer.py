import os
import sys
from transformers import AutoTokenizer
from IndicTransToolkit.processor import IndicProcessor

def main():
    model_name = "ai4bharat/indictrans2-indic-en-dist-200M"
    print(f"Loading tokenizer {model_name}...")
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    
    # Initialize processor
    ip = IndicProcessor(inference=True)
    
    src_lang, tgt_lang = "hin_Deva", "eng_Latn"
    sentences = ["नौकरी"]
    
    # Preprocess
    preprocessed = ip.preprocess_batch(sentences, src_lang=src_lang, tgt_lang=tgt_lang)
    print(f"Preprocessed: {preprocessed}")
    
    # Tokenize
    inputs = tokenizer(preprocessed, padding=True, truncation=True)
    print(f"Input IDs: {inputs['input_ids']}")
    
    # Decode back to show tokens
    for input_id_seq in inputs['input_ids']:
        tokens = tokenizer.convert_ids_to_tokens(input_id_seq)
        print(f"Tokens: {tokens}")

if __name__ == "__main__":
    main()

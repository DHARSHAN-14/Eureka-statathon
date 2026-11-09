import os
import sys
import re

# Add project root to sys.path to allow imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv()

from database import db_store
import utils.searchapp as search_module

# Define our test cases
# Each test case has a query, an expected spelling correction word,
# and expected keywords that should appear in the top search results.
TEST_CASES = [
    {
        "query": "i am chike",
        "expected_correction": "chicken",
        "expected_result_keywords": ["poultry", "chick"]
    },
    {
        "query": "i am chai",
        "expected_correction": "chair",
        "expected_result_keywords": ["furniture", "restorer", "wood"]
    },
    {
        "query": "i work with carpentre",
        "expected_correction": "carpentry",
        "expected_result_keywords": ["carpenter", "carpentry"]
    },
    {
        "query": "i build houze",
        "expected_correction": "house",
        "expected_result_keywords": ["mason", "carpenter", "builder", "house"]
    },
    {
        "query": "i am techer",
        "expected_correction": "teacher",
        "expected_result_keywords": ["teacher", "instructor", "professor"]
    },
    {
        "query": "elecrician work",
        "expected_correction": "electrician",
        "expected_result_keywords": ["electrician", "electrical"]
    },
    {
        "query": "i am docter",
        "expected_correction": "doctor",
        "expected_result_keywords": ["doctor", "medical", "physician", "veterinarian"]
    },
    {
        "query": "shop supervisar",
        "expected_correction": "supervisor",
        "expected_result_keywords": ["shop", "supervisor"]
    },
    {
        "query": "i driv taxi",
        "expected_correction": "drive",
        "expected_result_keywords": ["driver", "chauffeur", "taxi"]
    },
    {
        "query": "i paint buildin",
        "expected_correction": "building",
        "expected_result_keywords": ["painter", "building"]
    }
]

def run_tests():
    print("=" * 80)
    print("RUNNING AUTOMATED SPELLING CORRECTION & SEMANTIC SEARCH TESTS")
    print("=" * 80)
    
    # Initialize DB (needed to populate spelling vocab cache)
    db_store.init_db()
    
    passed_cases = 0
    total_cases = len(TEST_CASES)
    
    for idx, case in enumerate(TEST_CASES, start=1):
        query = case["query"]
        expected_corr = case["expected_correction"]
        expected_keywords = case["expected_result_keywords"]
        
        print(f"\n[Test {idx}/{total_cases}] Query: '{query}'")
        
        # 1. Spelling Correction
        suggestions = db_store.get_spelling_suggestions(query, limit=1)
        corrected_query = suggestions[0] if suggestions else query
        
        # Check if the expected spelling correction was applied
        spelling_passed = expected_corr.lower() in corrected_query.lower()
        spelling_status = "PASS" if spelling_passed else "FAIL"
        print(f"  [-] Spelling Correction: '{query}' -> '{corrected_query}' ({spelling_status})")
        if not spelling_passed:
            print(f"     Expected correction to contain: '{expected_corr}'")
            
        # 2. Search Execution
        results = search_module.search(corrected_query, top_k=5)
        
        # Check if any top returned occupation title or description contains the expected keywords
        found_keywords = []
        for r in results:
            title = r.get("occupation_title", "").lower()
            details = r.get("details", {})
            desc = details.get("occupation_description", "").lower()
            
            for kw in expected_keywords:
                if kw in title or kw in desc:
                    if kw not in found_keywords:
                        found_keywords.append(kw)
                        
        search_passed = len(found_keywords) > 0
        search_status = "PASS" if search_passed else "FAIL"
        print(f"  [-] Search Results: Found keywords {found_keywords} of expected {expected_keywords} ({search_status})")
        if results:
            print("     Top retrieved occupation titles:")
            for i, r in enumerate(results[:3], start=1):
                print(f"       {i}. {r['occupation_title']} (score: {r['final_score']:.3f})")
        else:
            print("     No results retrieved.")
            
        # Case passes if both spelling and search retrieve correct domains
        if spelling_passed and search_passed:
            passed_cases += 1
            print("  TEST CASE RESULT: PASSED")
        else:
            print("  TEST CASE RESULT: FAILED")
            
    print("\n" + "=" * 80)
    print(f"SUMMARY: {passed_cases}/{total_cases} test cases PASSED.")
    print("=" * 80)
    
    if passed_cases == total_cases:
        print("All spelling and semantic query tests passed successfully!")
        sys.exit(0)
    else:
        print("Some tests failed. Please inspect the log output above.")
        sys.exit(1)

if __name__ == "__main__":
    run_tests()

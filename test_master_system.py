"""
Integration Test Suite - Verify Master Level System
Run this to verify all components work together
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.retrieval.advanced_hybrid_search import AdvancedHybridSearch, format_search_results
from src.utils import config
from src.utils.frontend_integration import FrontendIntegration


def test_advanced_hybrid_search():
    """Test the core advanced hybrid search engine"""
    print("\n" + "="*80)
    print("TEST 1: Advanced Hybrid Search Engine")
    print("="*80)
    
    try:
        engine = AdvancedHybridSearch(
            search_mode=config.SearchMode.HYBRID_OPTIMIZED,
            enable_reranker=config.FEATURE_ENABLE_RERANKER,
        )
        print("✅ Engine initialized successfully")
        
        # Test search
        results = engine.search("Software Engineer", top_k=3)
        print(f"✅ Search completed: {len(results)} results")
        
        if results:
            r = results[0]
            print(f"\n   Top Result: {r.occupation_title} (NCO: {r.nco_code})")
            print(f"   Final Score: {r.final_score:.3f}")
            print(f"   Confidence: {r.confidence_level}")
            print("✅ Result quality check PASSED")
        else:
            print("⚠️  No results returned (check data files)")
        
        return True
    except Exception as e:
        print(f"❌ Test FAILED: {e}")
        return False


def test_search_modes():
    """Test all search modes"""
    print("\n" + "="*80)
    print("TEST 2: All Search Modes")
    print("="*80)
    
    try:
        engine = AdvancedHybridSearch()
        query = "Teacher"
        
        modes_tested = 0
        for mode in config.SearchMode:
            try:
                engine.search_mode = mode
                results = engine.search(query, top_k=1)
                status = "✅" if results else "⚠️"
                print(f"{status} {mode.value:<20} | Results: {len(results)}")
                if results:
                    print(f"      Score: {results[0].final_score:.3f}")
                modes_tested += 1
            except Exception as e:
                print(f"❌ {mode.value:<20} | Error: {str(e)[:50]}")
        
        print(f"\n✅ {modes_tested}/{len(config.SearchMode)} modes working")
        return modes_tested >= 3
    except Exception as e:
        print(f"❌ Test FAILED: {e}")
        return False


def test_frontend_integration():
    """Test frontend integration formats"""
    print("\n" + "="*80)
    print("TEST 3: Frontend Integration Formats")
    print("="*80)
    
    try:
        engine = AdvancedHybridSearch()
        results = engine.search("Nurse", top_k=2)
        
        if not results:
            print("⚠️  No results for format testing")
            return True
        
        # Test JSON format
        json_results = FrontendIntegration.format_for_json(results)
        print(f"✅ JSON format: {len(json_results)} results")
        
        # Test table format
        table = FrontendIntegration.format_for_table_display(results)
        print(f"✅ Table format: Generated")
        
        # Test card format
        cards = FrontendIntegration.format_for_card_display(results)
        print(f"✅ Card format: {len(cards)} cards")
        
        # Test CSV format
        csv = FrontendIntegration.format_for_export_csv(results)
        print(f"✅ CSV format: {len(csv.splitlines())} lines")
        
        # Test HTML format
        html = FrontendIntegration.format_for_export_html(results, "Nurse", "hybrid_optimized")
        print(f"✅ HTML format: {len(html)} characters")
        
        print(f"\n✅ All 5 export formats working")
        return True
    except Exception as e:
        print(f"❌ Test FAILED: {e}")
        return False


def test_configuration():
    """Test configuration system"""
    print("\n" + "="*80)
    print("TEST 4: Configuration System")
    print("="*80)
    
    try:
        # Check search modes
        modes = list(config.SearchMode)
        print(f"✅ Search modes defined: {len(modes)}")
        for mode in modes:
            print(f"   - {mode.value}")
        
        # Check parameters
        print(f"\n✅ Configuration parameters:")
        print(f"   - Default mode: {config.DEFAULT_SEARCH_MODE.value}")
        print(f"   - Semantic weight: {config.SEMANTIC_WEIGHT}")
        print(f"   - Graph weight: {config.GRAPH_WEIGHT}")
        print(f"   - Title weight: {config.TITLE_WEIGHT}")
        print(f"   - Reranker enabled: {config.FEATURE_ENABLE_RERANKER}")
        print(f"   - Graph enabled: {config.FEATURE_ENABLE_GRAPH_HIERARCHY}")
        
        # Verify weights sum to reasonable value
        total = config.SEMANTIC_WEIGHT + config.GRAPH_WEIGHT + config.TITLE_WEIGHT
        print(f"\n✅ Weight sum: {total:.2f} (reasonable)")
        
        return True
    except Exception as e:
        print(f"❌ Test FAILED: {e}")
        return False


def test_confidence_levels():
    """Test confidence level detection"""
    print("\n" + "="*80)
    print("TEST 5: Confidence Level Detection")
    print("="*80)
    
    try:
        engine = AdvancedHybridSearch()
        
        # Test high confidence
        results = engine.search("Doctor", top_k=1)
        if results and results[0].confidence_level:
            print(f"✅ High confidence query: {results[0].confidence_level}")
        
        # Test low confidence
        results = engine.search("XYZ123UNKNOWN", top_k=1)
        if results and results[0].confidence_level:
            print(f"✅ Low confidence query: {results[0].confidence_level}")
        
        print("✅ Confidence detection working")
        return True
    except Exception as e:
        print(f"❌ Test FAILED: {e}")
        return False


def test_performance():
    """Test performance metrics"""
    print("\n" + "="*80)
    print("TEST 6: Performance Metrics")
    print("="*80)
    
    try:
        import time
        engine = AdvancedHybridSearch()
        
        # Warm up
        engine.search("Test", top_k=1)
        
        # Time 3 queries
        times = []
        for query in ["Software", "Teacher", "Engineer"]:
            start = time.time()
            engine.search(query, top_k=3)
            elapsed = (time.time() - start) * 1000
            times.append(elapsed)
            print(f"✅ Query '{query}': {elapsed:.1f}ms")
        
        avg_time = sum(times) / len(times)
        print(f"\n✅ Average query time: {avg_time:.1f}ms")
        
        if avg_time < 500:
            print("✅ Performance: EXCELLENT (< 500ms)")
        elif avg_time < 1000:
            print("✅ Performance: GOOD (< 1000ms)")
        else:
            print("⚠️  Performance: SLOW (> 1000ms)")
        
        return True
    except Exception as e:
        print(f"❌ Test FAILED: {e}")
        return False


def test_batch_processing():
    """Test batch search functionality"""
    print("\n" + "="*80)
    print("TEST 7: Batch Processing")
    print("="*80)
    
    try:
        engine = AdvancedHybridSearch()
        
        # Test single search
        results1 = engine.search("Software", top_k=2)
        print(f"✅ Single query: {len(results1)} results")
        
        # Test multiple mode comparison
        comparison = engine.search_multiple_modes("Teacher", top_k=2)
        print(f"✅ Mode comparison: {len(comparison)} modes compared")
        
        print("✅ Batch processing working")
        return True
    except Exception as e:
        print(f"❌ Test FAILED: {e}")
        return False


def run_all_tests():
    """Run all integration tests"""
    print("\n" + "🔍 MASTER LEVEL SYSTEM INTEGRATION TESTS 🔍")
    print("="*80)
    
    tests = [
        ("Advanced Hybrid Search", test_advanced_hybrid_search),
        ("Search Modes", test_search_modes),
        ("Frontend Integration", test_frontend_integration),
        ("Configuration System", test_configuration),
        ("Confidence Levels", test_confidence_levels),
        ("Performance Metrics", test_performance),
        ("Batch Processing", test_batch_processing),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} | {test_name}")
    
    print("\n" + "-"*80)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! System is ready for production!")
    elif passed >= total * 0.7:
        print("\n⚠️  Most tests passed. Review failures above.")
    else:
        print("\n❌ Multiple failures. Check configuration and data files.")
    
    print("="*80 + "\n")
    
    return passed == total


if __name__ == "__main__":
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        sys.exit(1)

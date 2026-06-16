#!/usr/bin/env python3
"""
Quick implementation check for the NCO search system
"""
import json
import numpy as np
import faiss
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_file_paths():
    """Check if all required files exist"""
    print("=" * 60)
    print("1. CHECKING FILE PATHS")
    print("=" * 60)
    
    files = {
        "Metadata": "data/processed/nco_metadata.json",
        "Documents": "data/processed/nco_documents.json",
        "Graph": "data/processed/nco_graph.json",
        "Embeddings": "models/nco_embeddings.npy",
        "FAISS Index": "models/nco_faiss.index"
    }
    
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    all_exist = True
    
    for name, path in files.items():
        full_path = os.path.join(base_path, path)
        exists = os.path.exists(full_path)
        status = "✅" if exists else "❌"
        size = os.path.getsize(full_path) if exists else 0
        print(f"{status} {name:20} {path:35} ({size:,} bytes)")
        if not exists:
            all_exist = False
    
    return all_exist

def check_data_consistency():
    """Check data consistency across files"""
    print("\n" + "=" * 60)
    print("2. CHECKING DATA CONSISTENCY")
    print("=" * 60)
    
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Load data
    with open(os.path.join(base_path, "data/processed/nco_metadata.json"), "r") as f:
        metadata = json.load(f)
    
    with open(os.path.join(base_path, "data/processed/nco_documents.json"), "r") as f:
        documents = json.load(f)
    
    with open(os.path.join(base_path, "data/processed/nco_graph.json"), "r") as f:
        graph = json.load(f)
    
    embeddings = np.load(os.path.join(base_path, "models/nco_embeddings.npy"))
    index = faiss.read_index(os.path.join(base_path, "models/nco_faiss.index"))
    
    # Checks
    checks = []
    
    # Check 1: Metadata and documents count match
    meta_count = len(metadata)
    doc_count = len(documents)
    checks.append(("Metadata vs Documents count", meta_count == doc_count, 
                   f"{meta_count} == {doc_count}"))
    
    # Check 2: Embeddings shape matches document count
    emb_count = embeddings.shape[0]
    checks.append(("Documents vs Embeddings count", doc_count == emb_count,
                   f"{doc_count} == {emb_count}"))
    
    # Check 3: FAISS index count matches
    index_count = index.ntotal
    checks.append(("Embeddings vs Index count", emb_count == index_count,
                   f"{emb_count} == {index_count}"))
    
    # Check 4: Graph node count (should be <= metadata count due to unique codes)
    graph_count = len(graph)
    checks.append(("Graph nodes count", graph_count <= meta_count,
                   f"{graph_count} <= {meta_count}"))
    
    # Check 5: Graph structure consistency
    sample_code = list(graph.keys())[0]
    sample_node = graph[sample_code]
    has_sector = "sector" in sample_node
    has_keywords = "keywords" in sample_node
    checks.append(("Graph node structure", has_sector and has_keywords,
                   f"Has sector: {has_sector}, Has keywords: {has_keywords}"))
    
    # Check 6: Embedding dimensions
    emb_dim = embeddings.shape[1]
    expected_dim = 384  # all-MiniLM-L6-v2 produces 384-dim embeddings
    checks.append(("Embedding dimensions", emb_dim == expected_dim,
                   f"{emb_dim} == {expected_dim}"))
    
    # Check 7: Metadata structure
    sample_meta = metadata[0]
    required_keys = ["row_id", "nco_2015", "occupation_title"]
    has_all_keys = all(k in sample_meta for k in required_keys)
    checks.append(("Metadata structure", has_all_keys,
                   f"Has all keys: {required_keys}"))
    
    # Print results
    all_pass = True
    for name, passed, details in checks:
        status = "✅" if passed else "❌"
        print(f"{status} {name:40} {details}")
        if not passed:
            all_pass = False
    
    return all_pass

def check_potential_issues():
    """Check for potential bugs or issues"""
    print("\n" + "=" * 60)
    print("3. CHECKING FOR POTENTIAL ISSUES")
    print("=" * 60)
    
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    issues = []
    
    # Load graph for analysis
    with open(os.path.join(base_path, "data/processed/nco_graph.json"), "r") as f:
        graph = json.load(f)
    
    # Issue 1: Check for empty keywords
    empty_keywords = sum(1 for node in graph.values() if not node.get("keywords", []))
    if empty_keywords > 0:
        issues.append(f"⚠️  {empty_keywords} nodes have empty keywords list")
    else:
        print("✅ No nodes with empty keywords")
    
    # Issue 2: Check graph score division by zero (already handled in code)
    # The code checks `if not keywords: return 0.0` - this is correct
    
    # Issue 3: Check for duplicate NCO codes in metadata
    with open(os.path.join(base_path, "data/processed/nco_metadata.json"), "r") as f:
        metadata = json.load(f)
    
    codes = [item["nco_2015"] for item in metadata]
    unique_codes = len(set(codes))
    if len(codes) != unique_codes:
        duplicates = len(codes) - unique_codes
        issues.append(f"⚠️  {duplicates} duplicate NCO codes in metadata")
    else:
        print(f"✅ All {len(codes)} NCO codes are unique")
    
    # Issue 4: Check index alignment
    # Metadata row_id should match array index
    mismatches = sum(1 for i, item in enumerate(metadata) if item["row_id"] != i)
    if mismatches > 0:
        issues.append(f"⚠️  {mismatches} metadata row_id/index mismatches")
    else:
        print("✅ Metadata row_id aligns with array index")
    
    # Issue 5: Check graph score normalization
    # The score is: len(overlap) / len(keywords)
    # This normalizes by keyword count, which can bias towards nodes with fewer keywords
    # This is a design choice, but worth noting
    print("⚠️  Graph score divides by keyword count (may favor nodes with fewer keywords)")
    
    if issues:
        for issue in issues:
            print(issue)
        return False
    else:
        return True

def test_search_functionality():
    """Test basic search functionality"""
    print("\n" + "=" * 60)
    print("4. TESTING SEARCH FUNCTIONALITY")
    print("=" * 60)
    
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    try:
        from sentence_transformers import SentenceTransformer
        
        # Load index and metadata
        index = faiss.read_index(os.path.join(base_path, "models/nco_faiss.index"))
        with open(os.path.join(base_path, "data/processed/nco_metadata.json"), "r") as f:
            metadata = json.load(f)
        
        # Load model
        model = SentenceTransformer("all-MiniLM-L6-v2")
        
        # Test query
        test_query = "software developer"
        query_vec = model.encode([test_query], convert_to_numpy=True, normalize_embeddings=True)
        scores, indices = index.search(query_vec, 5)
        
        print(f"✅ Search test query: '{test_query}'")
        print(f"   Found {len(indices[0])} results")
        print(f"   Top result: {metadata[indices[0][0]]['occupation_title']}")
        print(f"   Score: {scores[0][0]:.4f}")
        
        # Test graph scoring
        with open(os.path.join(base_path, "data/processed/nco_graph.json"), "r") as f:
            graph = json.load(f)
        
        import re
        def clean_text(text):
            return re.sub(r"[^a-z0-9\s]", "", text.lower())
        
        def compute_graph_score(query, occupation_code):
            query_words = set(clean_text(query).split())
            keywords = set(graph.get(occupation_code, {}).get("keywords", []))
            if not keywords:
                return 0.0
            overlap = query_words & keywords
            return len(overlap) / len(keywords)
        
        test_code = metadata[indices[0][0]]["nco_2015"]
        gn_score = compute_graph_score(test_query, test_code)
        print(f"✅ Graph score test: {gn_score:.4f} for code {test_code}")
        
        return True
    except Exception as e:
        print(f"❌ Search functionality test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all checks"""
    print("\n" + "=" * 60)
    print("NCO SEARCH SYSTEM - IMPLEMENTATION CHECK")
    print("=" * 60 + "\n")
    
    results = []
    
    results.append(("File Paths", check_file_paths()))
    results.append(("Data Consistency", check_data_consistency()))
    results.append(("Potential Issues", check_potential_issues()))
    results.append(("Search Functionality", test_search_functionality()))
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {name}")
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        print("\n✅ All checks passed!")
    else:
        print("\n⚠️  Some checks failed. Please review above.")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())


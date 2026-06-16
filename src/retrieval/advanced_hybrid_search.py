"""
Advanced Hybrid Search Engine - Combines OLD's domain optimization with NEW's architecture.

Features:
- Sophisticated hybrid scoring (semantic + graph + title)
- Multiple search modes
- Result reranking with CrossEncoder
- Confidence scoring
- Performance metrics
"""

import sys
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict

project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.retrieval.semantic_search import SemanticSearch
from src.graph.graph_search import GraphSearch
from src.models.embedding_model import EmbeddingModel
from src.models.reranker import Reranker
from src.utils import config
from src.utils.logger import get_logger


logger = get_logger(__name__)


@dataclass
class SearchResult:
    """Represents a single search result with detailed scoring"""
    rank: int
    occupation_title: str
    nco_code: str
    nco_2004_code: Optional[str] = None
    
    # Scoring components
    semantic_score: float = 0.0
    title_score: float = 0.0
    graph_score: float = 0.0
    rerank_score: float = 0.0
    
    # Final score
    final_score: float = 0.0
    confidence_level: str = "low"  # low, medium, high
    
    # Hierarchy and context
    hierarchy: List[str] = None
    siblings: List[Dict] = None
    
    # Metadata
    document: Optional[str] = None
    metadata: Optional[Dict] = None
    details: Optional[Dict] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, handling nested dataclasses"""
        return asdict(self)


class AdvancedHybridSearch:
    """
    Production-grade hybrid search engine combining:
    1. Semantic search (FAISS) for initial candidates
    2. Graph hierarchy scoring for context relevance
    3. Title-based scoring for query-title alignment
    4. CrossEncoder reranking for result refinement
    5. Configurable weighting for domain optimization
    """
    
    def __init__(
        self,
        search_mode: config.SearchMode = config.DEFAULT_SEARCH_MODE,
        enable_reranker: bool = config.FEATURE_ENABLE_RERANKER,
        enable_logging: bool = config.ENABLE_QUERY_LOGGING,
    ):
        """Initialize the advanced search engine"""
        self.search_mode = search_mode
        self.enable_reranker = enable_reranker
        self.enable_logging = enable_logging
        
        # Initialize components
        logger.info(f"Initializing AdvancedHybridSearch in {search_mode} mode")
        self.semantic = SemanticSearch()
        self.graph = GraphSearch()
        self.embedding_model = EmbeddingModel()
        
        # Initialize reranker if enabled
        self.reranker = None
        if self.enable_reranker and config.FEATURE_ENABLE_RERANKER:
            try:
                self.reranker = Reranker()
                logger.info("Reranker initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize reranker: {e}")
                self.reranker = None
        
        # Load old-style graph for keyword scoring
        self._load_old_graph()
        self._query_cache = {}
        
        logger.info("AdvancedHybridSearch initialization complete")
    
    def _load_old_graph(self):
        """Load OLD implementation's keyword graph for compatibility"""
        try:
            import json
            if config.OLD_GN_PATH.exists():
                with open(config.OLD_GN_PATH, 'r', encoding='utf-8') as f:
                    self.old_graph = json.load(f)
                logger.info("OLD graph loaded for keyword scoring")
            else:
                self.old_graph = {}
                logger.warning("OLD graph not found")
        except Exception as e:
            logger.error(f"Failed to load OLD graph: {e}")
            self.old_graph = {}
    
    def _clean_text(self, text: str) -> str:
        """Clean text for keyword matching"""
        return re.sub(r"[^a-z0-9\s]", "", text.lower())
    
    def _compute_graph_score(self, query: str, nco_code: str) -> float:
        """
        Compute keyword overlap score between query and occupation keywords
        (OLD implementation's graph scoring)
        """
        query_words = set(self._clean_text(query).split())
        keywords = set(self.old_graph.get(nco_code, {}).get("keywords", []))
        
        if not keywords:
            return 0.0
        
        overlap = query_words & keywords
        return len(overlap) / len(keywords) if keywords else 0.0
    
    def _compute_title_score_with_boost(
        self,
        query: str,
        title: str,
        title_score: float,
    ) -> Tuple[float, float]:
        """
        Compute title score with boosting logic (OLD implementation)
        
        Returns:
            Tuple of (boosted_semantic_score, title_final_score)
        """
        query_clean = self._clean_text(query)
        title_clean = self._clean_text(title)
        query_words = set(query_clean.split())
        title_words = set(title_clean.split())
        
        # Determine boost factor
        boost_factor = 1.0
        if title_clean == query_clean or title_words.issubset(query_words):
            boost_factor = config.TITLE_EXACT_BOOST
        elif len(query_words & title_words) > 0:
            boost_factor = config.TITLE_PARTIAL_BOOST
        
        title_final = title_score * config.TITLE_INDEX_BOOST
        
        return boost_factor, title_final
    
    def _compute_hierarchy_score(self, hierarchy: List[str]) -> float:
        """Compute score based on hierarchy depth"""
        if not hierarchy:
            return 0.0
        
        depth = len(hierarchy)
        return config.HIERARCHY_DEPTH_SCORES.get(depth, 1.0)
    
    def _compute_final_score(
        self,
        semantic_score: float,
        graph_score: float,
        title_score: float,
        hierarchy_depth: int,
        title_boost: float = 1.0,
        rerank_score: float = 0.0,
    ) -> float:
        """
        Compute final combined score based on search mode
        """
        if self.search_mode == config.SearchMode.SEMANTIC:
            # Pure semantic search
            return semantic_score
        
        elif self.search_mode == config.SearchMode.HYBRID_BALANCED:
            # NEW implementation's balanced approach
            base_score = (
                config.SEMANTIC_WEIGHT * semantic_score +
                config.GRAPH_WEIGHT * graph_score +
                config.TITLE_WEIGHT * title_score
            )
            if self.reranker and rerank_score > 0:
                final = (1 - config.RERANK_WEIGHT) * base_score + config.RERANK_WEIGHT * rerank_score
                return min(max(final, 0.0), 1.0)
            return min(max(base_score, 0.0), 1.0)
        
        elif self.search_mode == config.SearchMode.HYBRID_OPTIMIZED:
            # OLD implementation's domain-tuned approach
            base_score = (
                config.SEMANTIC_WEIGHT * semantic_score +
                config.GRAPH_WEIGHT * graph_score
            )
            
            # Apply global multiplier
            boosted = base_score * config.GLOBAL_BOOST_MULTIPLIER
            
            # Apply title boost
            semantic_final = boosted * title_boost
            title_final = title_score * config.TITLE_INDEX_BOOST
            
            # Take maximum and cap at 1.0
            final_score = min(max(semantic_final, title_final), 1.0)
            
            # Apply reranker if available
            if self.reranker and rerank_score > 0:
                final_score = (
                    (1 - config.RERANK_WEIGHT) * final_score +
                    config.RERANK_WEIGHT * rerank_score
                )
            
            return min(max(final_score, 0.0), 1.0)
        
        elif self.search_mode == config.SearchMode.HYBRID_GRAPH_FOCUSED:
            # Graph-focused approach
            hierarchy_score = config.HIERARCHY_DEPTH_SCORES.get(hierarchy_depth, 0.5)
            
            base_score = (
                0.5 * semantic_score +
                0.35 * graph_score +
                0.15 * hierarchy_score
            )
            
            if self.reranker and rerank_score > 0:
                final = (1 - config.RERANK_WEIGHT) * base_score + config.RERANK_WEIGHT * rerank_score
                return min(max(final, 0.0), 1.0)
            
            return min(max(base_score, 0.0), 1.0)
        
        elif self.search_mode == config.SearchMode.RERANKED:
            # Reranker-focused (requires reranker)
            if self.reranker and rerank_score > 0:
                return rerank_score
            else:
                # Fallback to hybrid balanced
                base_score = (
                    config.SEMANTIC_WEIGHT * semantic_score +
                    config.GRAPH_WEIGHT * graph_score +
                    config.TITLE_WEIGHT * title_score
                )
                return min(max(base_score, 0.0), 1.0)
        
        else:
            # Default to hybrid balanced
            base_score = (
                config.SEMANTIC_WEIGHT * semantic_score +
                config.GRAPH_WEIGHT * graph_score +
                config.TITLE_WEIGHT * title_score
            )
            return min(max(base_score, 0.0), 1.0)
    
    def _determine_confidence_level(self, score: float) -> str:
        """Determine confidence level based on score"""
        if score >= config.CONFIDENCE_HIGH_THRESHOLD:
            return "high"
        elif score >= config.CONFIDENCE_THRESHOLD:
            return "medium"
        else:
            return "low"
    
    def search(
        self,
        query: str,
        top_k: int = config.TOP_K_RESULTS,
        return_scores: bool = True,
    ) -> List[SearchResult]:
        """
        Perform advanced hybrid search
        
        Args:
            query: Search query
            top_k: Number of results to return
            return_scores: Whether to include detailed scores
        
        Returns:
            List of SearchResult objects
        """
        if not query or not query.strip():
            logger.warning("Empty query provided")
            return []
        
        # Normalize top_k
        top_k = max(1, min(int(top_k), config.MAX_TOP_K))
        candidate_k = max(config.CANDIDATE_K, top_k)
        
        try:
            # Step 1: Semantic search to get initial candidates
            logger.debug(f"Performing semantic search for query: {query}")
            semantic_results = self.semantic.search(
                query=query,
                top_k=candidate_k
            )
            
            if not semantic_results:
                logger.warning(f"No semantic results found for query: {query}")
                return []
            
            # Step 2: Compute scores for each candidate
            candidates = []
            for result in semantic_results:
                nco_code = result['nco_code']
                semantic_score = result['score']
                title = result['occupation_title']
                
                # Compute individual scores
                graph_score = self._compute_graph_score(query, nco_code)
                
                # Get title score (embedding-based)
                title_embedding = self.embedding_model.encode_query(title)
                query_embedding = self.embedding_model.encode_query(query)
                title_score = float(
                    (query_embedding @ title_embedding.T).flatten()[0]
                )
                title_score = min(max(title_score, 0.0), 1.0)
                
                # Compute title boost
                title_boost, title_final = self._compute_title_score_with_boost(
                    query, title, title_score
                )
                
                # Get hierarchy for depth scoring
                hierarchy = []
                try:
                    occupation_id = f"Occupation:{nco_code}"
                    hierarchy = self.graph.get_full_hierarchy(occupation_id)
                except Exception as e:
                    logger.debug(f"Failed to get hierarchy for {nco_code}: {e}")
                
                hierarchy_depth = len(hierarchy) if hierarchy else 1
                
                # Compute final score (without reranking yet)
                final_score = self._compute_final_score(
                    semantic_score=semantic_score,
                    graph_score=graph_score,
                    title_score=title_score,
                    hierarchy_depth=hierarchy_depth,
                    title_boost=title_boost,
                    rerank_score=0.0,
                )
                
                candidates.append({
                    'rank': 0,  # Will be updated after sorting
                    'occupation_title': title,
                    'nco_code': nco_code,
                    'nco_2004_code': result['metadata'].get('nco_2004_code'),
                    'semantic_score': semantic_score,
                    'title_score': title_score,
                    'graph_score': graph_score,
                    'rerank_score': 0.0,
                    'final_score': final_score,
                    'confidence_level': self._determine_confidence_level(final_score),
                    'hierarchy': hierarchy,
                    'document': result['document'],
                    'metadata': result['metadata'],
                    'title_boost': title_boost,
                })
            
            # Step 3: Sort by final score
            candidates = sorted(candidates, key=lambda x: x['final_score'], reverse=True)
            
            # Step 4: Apply reranking if enabled
            if self.reranker and self.enable_reranker:
                logger.debug("Applying CrossEncoder reranking")
                try:
                    reranked_candidates = self._apply_reranking(query, candidates, top_k)
                    candidates = reranked_candidates
                except Exception as e:
                    logger.error(f"Reranking failed: {e}. Using previous ranking.")
            
            # Step 5: Select top-k and prepare results
            top_candidates = candidates[:top_k]
            
            # Get additional hierarchy info
            results = []
            for rank, candidate in enumerate(top_candidates, start=1):
                # Get siblings
                siblings = []
                try:
                    occupation_id = f"Occupation:{candidate['nco_code']}"
                    siblings = self.graph.get_siblings(occupation_id)
                except Exception as e:
                    logger.debug(f"Failed to get siblings for {candidate['nco_code']}: {e}")
                
                # Get job details
                details = {}
                try:
                    details = self._get_job_details(candidate['nco_code'])
                except Exception as e:
                    logger.debug(f"Failed to get job details for {candidate['nco_code']}: {e}")
                
                result = SearchResult(
                    rank=rank,
                    occupation_title=candidate['occupation_title'],
                    nco_code=candidate['nco_code'],
                    nco_2004_code=candidate.get('nco_2004_code'),
                    semantic_score=candidate['semantic_score'],
                    title_score=candidate['title_score'],
                    graph_score=candidate['graph_score'],
                    rerank_score=candidate['rerank_score'],
                    final_score=candidate['final_score'],
                    confidence_level=candidate['confidence_level'],
                    hierarchy=candidate['hierarchy'],
                    siblings=siblings,
                    document=candidate['document'],
                    metadata=candidate['metadata'],
                    details=details,
                )
                results.append(result)
            
            # Log results
            if self.enable_logging:
                logger.info(
                    f"Query: {query} | Results: {len(results)} | "
                    f"Mode: {self.search_mode} | Top score: {results[0].final_score:.3f}"
                )
            
            return results
        
        except Exception as e:
            logger.error(f"Search failed for query '{query}': {e}", exc_info=True)
            return []
    
    def _apply_reranking(
        self,
        query: str,
        candidates: List[Dict],
        top_k: int,
    ) -> List[Dict]:
        """Apply CrossEncoder reranking to candidates"""
        if not self.reranker or not candidates:
            return candidates
        
        # Prepare pairs for reranking
        pairs = [
            [query, candidate['occupation_title']]
            for candidate in candidates[:top_k * 2]  # Rerank more than needed
        ]
        
        # Get rerank scores
        rerank_scores = self.reranker.rerank(query, pairs, top_k)
        
        # Update scores in candidates
        for i, score in enumerate(rerank_scores):
            if i < len(candidates):
                candidates[i]['rerank_score'] = score
                
                # Recompute final score with reranking
                candidates[i]['final_score'] = self._compute_final_score(
                    semantic_score=candidates[i]['semantic_score'],
                    graph_score=candidates[i]['graph_score'],
                    title_score=candidates[i]['title_score'],
                    hierarchy_depth=len(candidates[i].get('hierarchy', [])) or 1,
                    title_boost=candidates[i].get('title_boost', 1.0),
                    rerank_score=score,
                )
                candidates[i]['confidence_level'] = self._determine_confidence_level(
                    candidates[i]['final_score']
                )
        
        # Re-sort after reranking
        return sorted(candidates, key=lambda x: x['final_score'], reverse=True)
    
    def _get_job_details(self, nco_code: str) -> Dict[str, Any]:
        """Get detailed job information from metadata"""
        try:
            # This would be loaded from the CSV/metadata
            # For now, return empty dict - implement with actual data source
            return {}
        except Exception as e:
            logger.debug(f"Failed to get job details: {e}")
            return {}
    
    def search_multiple_modes(
        self,
        query: str,
        top_k: int = config.TOP_K_RESULTS,
    ) -> Dict[str, List[SearchResult]]:
        """
        Perform search with all modes and compare results
        Useful for analysis and benchmarking
        """
        results = {}
        current_mode = self.search_mode
        
        try:
            for mode in config.SearchMode:
                self.search_mode = mode
                try:
                    results[mode.value] = self.search(query, top_k)
                except Exception as e:
                    logger.error(f"Search failed in mode {mode}: {e}")
                    results[mode.value] = []
        finally:
            self.search_mode = current_mode
        
        return results


def format_search_results(results: List[SearchResult], verbose: bool = False) -> str:
    """Format search results for display"""
    if not results:
        return "No results found."
    
    output = []
    output.append("\n" + "=" * 100)
    
    for result in results:
        output.append(
            f"\n[RANK #{result.rank}] {result.occupation_title} (NCO: {result.nco_code})"
        )
        output.append(f"Final Score: {result.final_score:.3f} | Confidence: {result.confidence_level.upper()}")
        
        if verbose and config.FEATURE_ENABLE_SCORE_DETAILS:
            output.append(
                f"  Semantic: {result.semantic_score:.3f} | "
                f"Graph: {result.graph_score:.3f} | "
                f"Title: {result.title_score:.3f}"
            )
            if result.rerank_score > 0:
                output.append(f"  Rerank: {result.rerank_score:.3f}")
        
        if result.hierarchy:
            hierarchy_str = " → ".join(result.hierarchy[-3:])  # Show last 3 levels
            output.append(f"  Hierarchy: {hierarchy_str}")
        
        if verbose and result.details:
            if 'division' in result.details:
                output.append(f"  Division: {result.details.get('division', 'N/A')}")
        
        output.append("-" * 100)
    
    output.append("=" * 100)
    return "\n".join(output)


if __name__ == "__main__":
    # Example usage
    search_engine = AdvancedHybridSearch(
        search_mode=config.SearchMode.HYBRID_OPTIMIZED
    )
    
    test_queries = [
        "Software Developer",
        "teacher",
        "nurse"
    ]
    
    for query in test_queries:
        results = search_engine.search(query, top_k=3)
        print(format_search_results(results, verbose=True))

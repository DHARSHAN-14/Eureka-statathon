"""
Professional Production-Grade API for NCO Intelligence Engine
Built with FastAPI following best practices
"""

import sys
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from fastapi import (
    FastAPI, HTTPException, Query, BackgroundTasks, 
    status, Request
)
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from enum import Enum

from src.retrieval.advanced_hybrid_search import (
    AdvancedHybridSearch, SearchResult, format_search_results
)
from src.utils import config
from src.utils.logger import get_logger


logger = get_logger(__name__)


# ==========================================
# Pydantic Models
# ==========================================

class SearchModeEnum(str, Enum):
    """Available search modes"""
    SEMANTIC = "semantic"
    HYBRID_BALANCED = "hybrid_balanced"
    HYBRID_OPTIMIZED = "hybrid_optimized"
    HYBRID_GRAPH = "hybrid_graph"
    RERANKED = "reranked"


class SearchRequest(BaseModel):
    """Request model for search"""
    query: str = Field(..., min_length=1, max_length=500, description="Search query")
    top_k: int = Field(
        default=config.TOP_K_RESULTS,
        ge=1,
        le=config.MAX_TOP_K,
        description="Number of results to return"
    )
    search_mode: SearchModeEnum = Field(
        default=SearchModeEnum.HYBRID_OPTIMIZED,
        description="Search mode to use"
    )
    include_scores: bool = Field(
        default=True,
        description="Include detailed scoring breakdown"
    )
    include_hierarchy: bool = Field(
        default=True,
        description="Include occupation hierarchy"
    )
    include_siblings: bool = Field(
        default=True,
        description="Include sibling occupations"
    )
    
    @validator('query')
    def query_not_empty(cls, v):
        if not v.strip():
            raise ValueError('Query cannot be empty or whitespace only')
        return v.strip()


class ScoreBreakdown(BaseModel):
    """Detailed score breakdown"""
    semantic_score: float = Field(description="Semantic similarity score")
    title_score: float = Field(description="Title matching score")
    graph_score: float = Field(description="Graph hierarchy score")
    rerank_score: float = Field(default=0.0, description="CrossEncoder rerank score")
    final_score: float = Field(description="Final combined score")
    confidence_level: str = Field(description="Confidence level: low, medium, high")


class HierarchyInfo(BaseModel):
    """Hierarchy information"""
    levels: List[str] = Field(description="Hierarchy levels from root to occupation")
    depth: int = Field(description="Number of levels in hierarchy")


class OccupationResult(BaseModel):
    """Individual occupation search result"""
    rank: int = Field(description="Rank in results")
    occupation_title: str = Field(description="Occupation title")
    nco_code: str = Field(description="NCO 2015 code")
    nco_2004_code: Optional[str] = Field(default=None, description="NCO 2004 code")
    scores: Optional[ScoreBreakdown] = Field(default=None, description="Score breakdown")
    hierarchy: Optional[HierarchyInfo] = Field(default=None, description="Hierarchy information")
    siblings: List[str] = Field(default_factory=list, description="Sibling occupation titles")
    document_excerpt: Optional[str] = Field(default=None, description="Document excerpt")


class SearchResponse(BaseModel):
    """Response model for search"""
    success: bool = Field(description="Whether search was successful")
    query: str = Field(description="Original query")
    search_mode: str = Field(description="Search mode used")
    results_count: int = Field(description="Number of results returned")
    total_time_ms: float = Field(description="Total execution time in milliseconds")
    results: List[OccupationResult] = Field(description="Search results")
    warnings: List[str] = Field(default_factory=list, description="Any warnings from search")


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(description="Service status")
    timestamp: str = Field(description="Timestamp")
    version: str = Field(description="API version")
    search_modes: List[str] = Field(description="Available search modes")


# ==========================================
# FastAPI Application
# ==========================================

app = FastAPI(
    title=config.API_TITLE,
    version=config.API_VERSION,
    description="Advanced NCO Intelligence Engine with hybrid search capabilities",
    docs_url="/docs" if config.DOCS_ENABLED else None,
    redoc_url="/redoc" if config.DOCS_ENABLED else None,
)


# Add CORS middleware
if config.ENABLE_CORS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# ==========================================
# Global Search Engine Instance
# ==========================================

search_engine: Optional[AdvancedHybridSearch] = None


@app.on_event("startup")
async def startup_event():
    """Initialize search engine on startup"""
    global search_engine
    try:
        logger.info("Starting up NCO Intelligence Engine...")
        search_engine = AdvancedHybridSearch(
            search_mode=config.DEFAULT_SEARCH_MODE,
            enable_reranker=config.FEATURE_ENABLE_RERANKER,
            enable_logging=config.ENABLE_QUERY_LOGGING,
        )
        logger.info("Search engine initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize search engine: {e}", exc_info=True)
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down NCO Intelligence Engine")


# ==========================================
# Middleware
# ==========================================

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add response time header"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# ==========================================
# Route Handlers
# ==========================================

@app.get(
    "/",
    response_model=Dict[str, Any],
    summary="Root endpoint",
    tags=["General"]
)
def root():
    """Root endpoint with API information"""
    return {
        "service": config.API_TITLE,
        "version": config.API_VERSION,
        "status": "operational",
        "docs": "/docs",
        "endpoints": {
            "health": "/health",
            "search": "/search",
            "search_batch": "/search/batch",
            "compare_modes": "/search/compare",
        }
    }


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    tags=["General"]
)
def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        version=config.API_VERSION,
        search_modes=[mode.value for mode in config.SearchMode]
    )


@app.post(
    "/search",
    response_model=SearchResponse,
    summary="Search for occupations",
    tags=["Search"],
    status_code=status.HTTP_200_OK,
)
async def search(
    request: SearchRequest,
):
    """
    Perform an advanced hybrid search for occupations
    
    ## Query Parameters
    - **query**: The occupation search query (required)
    - **top_k**: Number of results to return (1-100, default 10)
    - **search_mode**: Search algorithm mode
    - **include_scores**: Include detailed score breakdown
    - **include_hierarchy**: Include occupation hierarchy
    - **include_siblings**: Include related occupations
    
    ## Search Modes
    - `semantic`: Pure semantic similarity
    - `hybrid_balanced`: Balanced semantic + graph
    - `hybrid_optimized`: Domain-tuned scoring (recommended)
    - `hybrid_graph`: Graph-focused
    - `reranked`: With CrossEncoder reranking
    
    ## Response
    Returns detailed results with scores, hierarchy, and siblings
    """
    if not search_engine:
        logger.error("Search engine not initialized")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search engine not initialized"
        )
    
    start_time = time.time()
    warnings = []
    
    try:
        # Set search mode
        search_engine.search_mode = config.SearchMode(request.search_mode)
        
        # Perform search
        results = search_engine.search(
            query=request.query,
            top_k=request.top_k,
        )
        
        # Check for low confidence
        if results and results[0].final_score < config.CONFIDENCE_LOW_THRESHOLD:
            warnings.append(
                f"Low confidence in results (score: {results[0].final_score:.2f}). "
                "Consider refining your query."
            )
        
        # Format results
        formatted_results = []
        for result in results:
            # Build score breakdown
            scores = None
            if request.include_scores:
                scores = ScoreBreakdown(
                    semantic_score=result.semantic_score,
                    title_score=result.title_score,
                    graph_score=result.graph_score,
                    rerank_score=result.rerank_score,
                    final_score=result.final_score,
                    confidence_level=result.confidence_level,
                )
            
            # Build hierarchy
            hierarchy_info = None
            if request.include_hierarchy and result.hierarchy:
                hierarchy_info = HierarchyInfo(
                    levels=result.hierarchy,
                    depth=len(result.hierarchy)
                )
            
            # Build siblings list
            siblings = []
            if request.include_siblings and result.siblings:
                try:
                    siblings = [s.get('label', s) for s in result.siblings[:5]]
                except:
                    siblings = []
            
            # Get document excerpt
            document_excerpt = None
            if result.document:
                document_excerpt = result.document[:200] + "..." if len(result.document) > 200 else result.document
            
            formatted_results.append(
                OccupationResult(
                    rank=result.rank,
                    occupation_title=result.occupation_title,
                    nco_code=result.nco_code,
                    nco_2004_code=result.nco_2004_code,
                    scores=scores,
                    hierarchy=hierarchy_info,
                    siblings=siblings,
                    document_excerpt=document_excerpt,
                )
            )
        
        elapsed_time = (time.time() - start_time) * 1000  # Convert to ms
        
        logger.info(
            f"Search successful: query='{request.query}' "
            f"mode={request.search_mode} results={len(formatted_results)} "
            f"time={elapsed_time:.1f}ms"
        )
        
        return SearchResponse(
            success=True,
            query=request.query,
            search_mode=request.search_mode,
            results_count=len(formatted_results),
            total_time_ms=elapsed_time,
            results=formatted_results,
            warnings=warnings,
        )
    
    except Exception as e:
        elapsed_time = (time.time() - start_time) * 1000
        logger.error(f"Search failed: {e}", exc_info=True)
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


@app.post(
    "/search/batch",
    summary="Batch search multiple queries",
    tags=["Search"],
)
async def search_batch(
    queries: List[str] = Query(..., description="List of queries to search"),
    top_k: int = Query(config.TOP_K_RESULTS, ge=1, le=config.MAX_TOP_K),
    search_mode: SearchModeEnum = Query(SearchModeEnum.HYBRID_OPTIMIZED),
):
    """
    Search for multiple queries in one request
    
    Useful for batch processing multiple occupations
    """
    if not search_engine:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search engine not initialized"
        )
    
    results = {}
    
    for query in queries[:20]:  # Limit to 20 queries
        try:
            search_engine.search_mode = config.SearchMode(search_mode)
            search_results = search_engine.search(query, top_k)
            results[query] = [
                {
                    "rank": r.rank,
                    "title": r.occupation_title,
                    "nco_code": r.nco_code,
                    "score": r.final_score,
                }
                for r in search_results
            ]
        except Exception as e:
            logger.error(f"Batch search failed for query '{query}': {e}")
            results[query] = []
    
    return {
        "success": True,
        "queries_processed": len(results),
        "results": results
    }


@app.post(
    "/search/compare",
    summary="Compare search results across all modes",
    tags=["Analysis"],
)
async def compare_modes(
    request: SearchRequest,
):
    """
    Compare search results across all search modes
    
    Useful for analysis, benchmarking, and understanding
    how different algorithms rank the same query
    """
    if not search_engine:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search engine not initialized"
        )
    
    try:
        comparison_results = search_engine.search_multiple_modes(
            query=request.query,
            top_k=request.top_k,
        )
        
        # Format comparison results
        comparison = {}
        for mode, results in comparison_results.items():
            comparison[mode] = [
                {
                    "rank": r.rank,
                    "title": r.occupation_title,
                    "nco_code": r.nco_code,
                    "score": r.final_score,
                    "confidence": r.confidence_level,
                }
                for r in results
            ]
        
        return {
            "success": True,
            "query": request.query,
            "modes_compared": len(comparison),
            "comparison": comparison,
        }
    
    except Exception as e:
        logger.error(f"Mode comparison failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Comparison failed: {str(e)}"
        )


# ==========================================
# Error Handlers
# ==========================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """General exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "Internal server error",
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host=config.API_HOST,
        port=config.API_PORT,
        log_level="info",
    )

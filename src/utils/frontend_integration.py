"""
Professional Frontend Integration Module
Provides utilities for seamless frontend-backend communication
"""

import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.retrieval.advanced_hybrid_search import SearchResult, format_search_results
from src.utils import config


class FrontendIntegration:
    """
    Utilities for professional frontend integration
    Formats results for JSON, HTML, CSV export, etc.
    """
    
    @staticmethod
    def format_for_json(results: List[SearchResult]) -> List[Dict[str, Any]]:
        """Format results for JSON API response"""
        return [
            {
                "rank": r.rank,
                "title": r.occupation_title,
                "nco_code": r.nco_code,
                "nco_2004_code": r.nco_2004_code,
                "scores": {
                    "semantic": round(r.semantic_score, 4),
                    "graph": round(r.graph_score, 4),
                    "title": round(r.title_score, 4),
                    "rerank": round(r.rerank_score, 4) if r.rerank_score > 0 else None,
                    "final": round(r.final_score, 4),
                    "confidence": r.confidence_level,
                },
                "hierarchy": r.hierarchy,
                "siblings": r.siblings,
            }
            for r in results
        ]
    
    @staticmethod
    def format_for_table_display(results: List[SearchResult]) -> str:
        """Format results as ASCII table"""
        if not results:
            return "No results found"
        
        lines = [
            "\n" + "=" * 140,
            f"{'Rank':<5} {'Occupation Title':<50} {'NCO Code':<10} "
            f"{'Semantic':<12} {'Graph':<12} {'Final':<12} {'Confidence':<12}",
            "-" * 140,
        ]
        
        for r in results:
            lines.append(
                f"{r.rank:<5} {r.occupation_title[:50]:<50} {r.nco_code:<10} "
                f"{r.semantic_score:<12.3f} {r.graph_score:<12.3f} "
                f"{r.final_score:<12.3f} {r.confidence_level:<12}"
            )
        
        lines.append("=" * 140)
        return "\n".join(lines)
    
    @staticmethod
    def format_for_card_display(results: List[SearchResult]) -> List[Dict]:
        """Format results as card-style objects for UI"""
        cards = []
        for r in results:
            card = {
                "id": f"{r.nco_code}-{r.rank}",
                "rank": r.rank,
                "title": r.occupation_title,
                "nco_code": r.nco_code,
                "badge_color": FrontendIntegration._get_confidence_color(r.confidence_level),
                "score_percentage": int(r.final_score * 100),
                "confidence_text": r.confidence_level.upper(),
                "hierarchy": " > ".join(r.hierarchy[-3:]) if r.hierarchy else "N/A",
                "sibling_count": len(r.siblings) if r.siblings else 0,
                "related_titles": [s.get('label', s) for s in r.siblings[:3]] if r.siblings else [],
            }
            cards.append(card)
        return cards
    
    @staticmethod
    def format_for_export_csv(results: List[SearchResult]) -> str:
        """Format results for CSV export"""
        if not results:
            return "No results to export"
        
        lines = [
            "Rank,Occupation Title,NCO 2015,NCO 2004,Semantic Score,Graph Score,Title Score,"
            "Rerank Score,Final Score,Confidence,Hierarchy Depth,Sibling Count"
        ]
        
        for r in results:
            hierarchy_depth = len(r.hierarchy) if r.hierarchy else 0
            sibling_count = len(r.siblings) if r.siblings else 0
            
            lines.append(
                f'{r.rank},'
                f'"{r.occupation_title}",'
                f'{r.nco_code},'
                f'{r.nco_2004_code or ""},'
                f'{r.semantic_score:.4f},'
                f'{r.graph_score:.4f},'
                f'{r.title_score:.4f},'
                f'{r.rerank_score:.4f},'
                f'{r.final_score:.4f},'
                f'{r.confidence_level},'
                f'{hierarchy_depth},'
                f'{sibling_count}'
            )
        
        return "\n".join(lines)
    
    @staticmethod
    def format_for_export_html(
        results: List[SearchResult],
        query: str,
        search_mode: str
    ) -> str:
        """Format results as professional HTML"""
        cards_html = []
        
        for r in results:
            confidence_class = FrontendIntegration._get_confidence_class(r.confidence_level)
            hierarchy_html = ""
            
            if r.hierarchy:
                hierarchy_parts = " &raquo; ".join(r.hierarchy[-3:])
                hierarchy_html = f'<div class="hierarchy">{hierarchy_parts}</div>'
            
            siblings_html = ""
            if r.siblings:
                sibling_titles = ", ".join([s.get('label', s)[:30] for s in r.siblings[:3]])
                siblings_html = f'<div class="siblings"><strong>Related:</strong> {sibling_titles}...</div>'
            
            card = f"""
            <div class="result-card">
                <div class="result-header">
                    <span class="rank">#{r.rank}</span>
                    <h3>{r.occupation_title}</h3>
                    <span class="nco-code">NCO: {r.nco_code}</span>
                </div>
                <div class="result-scores">
                    <div class="score-item">
                        <label>Overall</label>
                        <div class="score-bar">
                            <div class="score-fill {confidence_class}" style="width: {int(r.final_score * 100)}%"></div>
                        </div>
                        <span class="score-text">{r.final_score:.1%}</span>
                    </div>
                </div>
                <div class="result-meta">
                    <span class="confidence {confidence_class}">{r.confidence_level.upper()}</span>
                    {hierarchy_html}
                    {siblings_html}
                </div>
            </div>
            """
            cards_html.append(card)
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>NCO Search Results - {query}</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background: #f5f7fa;
                    padding: 20px;
                    margin: 0;
                }}
                .container {{
                    max-width: 1000px;
                    margin: 0 auto;
                }}
                .header {{
                    background: white;
                    padding: 20px;
                    border-radius: 8px;
                    margin-bottom: 20px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .header h1 {{
                    margin: 0 0 10px 0;
                    color: #1a73e8;
                }}
                .header .meta {{
                    color: #666;
                    font-size: 14px;
                }}
                .results {{
                    display: grid;
                    gap: 16px;
                }}
                .result-card {{
                    background: white;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    border-left: 4px solid #1a73e8;
                }}
                .result-header {{
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    margin-bottom: 16px;
                }}
                .rank {{
                    background: #1a73e8;
                    color: white;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 12px;
                }}
                .result-header h3 {{
                    margin: 0;
                    flex: 1;
                    color: #202124;
                }}
                .nco-code {{
                    background: #f0f0f0;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 12px;
                    font-weight: 500;
                }}
                .score-bar {{
                    background: #e0e0e0;
                    height: 8px;
                    border-radius: 4px;
                    overflow: hidden;
                    margin: 6px 0;
                }}
                .score-fill {{
                    height: 100%;
                    transition: width 0.3s ease;
                }}
                .score-fill.high {{
                    background: #34a853;
                }}
                .score-fill.medium {{
                    background: #fbbc04;
                }}
                .score-fill.low {{
                    background: #ea4335;
                }}
                .confidence {{
                    display: inline-block;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 12px;
                    font-weight: 500;
                    margin-right: 8px;
                }}
                .confidence.high {{
                    background: #d4edda;
                    color: #155724;
                }}
                .confidence.medium {{
                    background: #fff3cd;
                    color: #856404;
                }}
                .confidence.low {{
                    background: #f8d7da;
                    color: #721c24;
                }}
                .hierarchy {{
                    font-size: 13px;
                    color: #666;
                    margin-top: 8px;
                    padding-top: 8px;
                    border-top: 1px solid #eee;
                }}
                .siblings {{
                    font-size: 13px;
                    color: #666;
                    margin-top: 8px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>NCO Search Results</h1>
                    <div class="meta">
                        <strong>Query:</strong> {query}<br>
                        <strong>Mode:</strong> {search_mode}<br>
                        <strong>Results:</strong> {len(results)}
                    </div>
                </div>
                <div class="results">
                    {"".join(cards_html)}
                </div>
            </div>
        </body>
        </html>
        """
        return html
    
    @staticmethod
    def _get_confidence_color(confidence_level: str) -> str:
        """Get color for confidence level"""
        colors = {
            "high": "#34a853",
            "medium": "#fbbc04",
            "low": "#ea4335",
        }
        return colors.get(confidence_level, "#999")
    
    @staticmethod
    def _get_confidence_class(confidence_level: str) -> str:
        """Get CSS class for confidence level"""
        return confidence_level.lower()


# Example usage for frontend
if __name__ == "__main__":
    from src.retrieval.advanced_hybrid_search import AdvancedHybridSearch
    
    # Search
    engine = AdvancedHybridSearch()
    results = engine.search("Software Engineer", top_k=3)
    
    # Format for different outputs
    print("JSON Format:")
    print(FrontendIntegration.format_for_json(results))
    
    print("\n\nTable Format:")
    print(FrontendIntegration.format_for_table_display(results))
    
    print("\n\nCard Format:")
    print(FrontendIntegration.format_for_card_display(results))

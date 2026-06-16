import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import json
from dataclasses import dataclass
from typing import Dict, List

import faiss
import numpy as np

from src.models.embedding_model import EmbeddingModel
from src.utils.config import (
    FAISS_INDEX_PATH,
    METADATA_PATH,
    TOP_K_RESULTS,
)


@dataclass(frozen=True)
class SemanticSearchResult:
    score: float
    row_id: int
    nco_code: str
    occupation_title: str
    document: str
    metadata: Dict


class SemanticSearch:
    """
    FAISS-based semantic search over NCO occupation documents.
    """

    def __init__(
        self,
        index_path: Path = FAISS_INDEX_PATH,
        metadata_path: Path = METADATA_PATH,
    ):
        self.index_path = Path(index_path)
        self.metadata_path = Path(metadata_path)

        self.embedding_model = EmbeddingModel()

        self.index = self.load_index()
        self.metadata = self.load_metadata()

        self.validate_index_metadata_alignment()

        print(
            f"Semantic Search Ready | "
            f"Vectors={self.index.ntotal} | Metadata={len(self.metadata)}"
        )

    def load_index(self):
        if not self.index_path.exists():
            raise FileNotFoundError(
                f"FAISS index not found: {self.index_path}. "
                "Run faiss_builder.py first."
            )

        return faiss.read_index(
            str(self.index_path)
        )

    def load_metadata(self) -> List[Dict]:
        if not self.metadata_path.exists():
            raise FileNotFoundError(
                f"Metadata file not found: {self.metadata_path}. "
                "Run preparation.py first."
            )

        with open(self.metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        if not isinstance(metadata, list):
            raise ValueError(
                "Invalid metadata format. Expected list of dictionaries."
            )

        if not metadata:
            raise ValueError(
                "Metadata is empty."
            )

        return metadata

    def validate_index_metadata_alignment(self) -> None:
        if self.index.ntotal != len(self.metadata):
            raise ValueError(
                "FAISS index and metadata count mismatch. "
                f"Index={self.index.ntotal}, Metadata={len(self.metadata)}"
            )

    def embed_query(self, query: str) -> np.ndarray:
        if not query or not query.strip():
            raise ValueError(
                "Query cannot be empty."
            )

        embedding = self.embedding_model.encode(
            query,
            normalize=True
        )

        return embedding.astype(np.float32)

    def build_candidate_document(
        self,
        item: Dict
    ) -> str:
        return f"""
Occupation Title: {item.get("occupation_title", "")}
NCO 2015 Code: {item.get("nco_2015", "")}
NCO 2004 Code: {item.get("nco_2004", "")}

Hierarchy:
Division: {item.get("division", "")}
Sub Division: {item.get("sub_division", "")}
Group: {item.get("group", "")}
Family: {item.get("family", "")}

Occupation Description:
{item.get("occupation_description", "")}

Family Description:
{item.get("family_description", "")}

Group Description:
{item.get("group_description", "")}
""".strip()

    def search(
        self,
        query: str,
        top_k: int = TOP_K_RESULTS,
    ) -> List[Dict]:
        top_k = max(
            1,
            min(
                int(top_k),
                self.index.ntotal
            )
        )

        query_embedding = self.embed_query(
            query
        )

        scores, indices = self.index.search(
            query_embedding,
            top_k
        )

        results = []

        for score, idx in zip(
            scores[0],
            indices[0]
        ):
            if idx < 0:
                continue

            item = self.metadata[int(idx)]

            results.append(
                {
                    "score": float(score),
                    "row_id": int(item.get("row_id", idx)),
                    "nco_code": item.get("nco_2015", ""),
                    "occupation_title": item.get("occupation_title", ""),
                    "document": self.build_candidate_document(item),
                    "metadata": item,
                }
            )

        return results


if __name__ == "__main__":
    semantic = SemanticSearch()

    while True:
        query = input("\nEnter Query (exit to quit): ").strip()

        if query.lower() == "exit":
            break

        results = semantic.search(
            query=query,
            top_k=10
        )

        print("\nTop Matches:\n")

        for rank, result in enumerate(results, start=1):
            print(
                f"{rank}. {result['occupation_title']} "
                f"({result['nco_code']}) "
                f"| Score={result['score']:.4f}"
            )
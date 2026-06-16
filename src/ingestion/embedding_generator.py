import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import json
from dataclasses import dataclass
from typing import List

import numpy as np

from src.models.embedding_model import EmbeddingModel
from src.utils.config import (
    DOCUMENTS_PATH,
    EMBEDDINGS_PATH,
)


DEFAULT_BATCH_SIZE = 32


@dataclass(frozen=True)
class EmbeddingStats:
    documents_loaded: int
    embeddings_created: int
    embedding_dimension: int
    output_path: str


class EmbeddingGenerationService:
    """
    Generates dense vector embeddings for prepared NCO documents.

    Input:
        data/processed/nco_documents.json

    Output:
        models/nco_embeddings.npy
    """

    def __init__(
        self,
        documents_path: Path = DOCUMENTS_PATH,
        embeddings_path: Path = EMBEDDINGS_PATH,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ):
        self.documents_path = Path(documents_path)
        self.embeddings_path = Path(embeddings_path)
        self.batch_size = batch_size
        self.embedding_model = EmbeddingModel()

    def load_documents(self) -> List[str]:
        if not self.documents_path.exists():
            raise FileNotFoundError(
                f"Documents file not found: {self.documents_path}. "
                "Run preparation.py first."
            )

        with open(self.documents_path, "r", encoding="utf-8") as f:
            documents = json.load(f)

        if not isinstance(documents, list):
            raise ValueError(
                "Invalid documents format. Expected a list of strings."
            )

        if not documents:
            raise ValueError(
                "No documents found. Cannot generate embeddings."
            )

        invalid_items = [
            index for index, item in enumerate(documents)
            if not isinstance(item, str) or not item.strip()
        ]

        if invalid_items:
            raise ValueError(
                f"Invalid/empty documents found at indices: {invalid_items[:10]}"
            )

        return documents

    def generate_embeddings(self, documents: List[str]) -> np.ndarray:
        print(
            f"Generating embeddings for {len(documents)} documents "
            f"with batch_size={self.batch_size}..."
        )

        embeddings = self.embedding_model.model.encode(
            documents,
            batch_size=self.batch_size,
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

        embeddings = embeddings.astype(np.float32)

        return embeddings

    def validate_embeddings(
        self,
        documents: List[str],
        embeddings: np.ndarray
    ) -> None:
        if not isinstance(embeddings, np.ndarray):
            raise TypeError(
                "Embeddings must be a NumPy ndarray."
            )

        if embeddings.ndim != 2:
            raise ValueError(
                f"Embeddings must be 2D. Got shape: {embeddings.shape}"
            )

        if embeddings.shape[0] != len(documents):
            raise ValueError(
                "Embedding/document count mismatch. "
                f"Documents={len(documents)}, Embeddings={embeddings.shape[0]}"
            )

        if embeddings.shape[1] <= 0:
            raise ValueError(
                "Invalid embedding dimension."
            )

        if np.isnan(embeddings).any():
            raise ValueError(
                "Embeddings contain NaN values."
            )

        if np.isinf(embeddings).any():
            raise ValueError(
                "Embeddings contain infinite values."
            )

    def save_embeddings(self, embeddings: np.ndarray) -> None:
        self.embeddings_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        np.save(
            self.embeddings_path,
            embeddings
        )

    def verify_saved_embeddings(
        self,
        expected_shape
    ) -> None:
        if not self.embeddings_path.exists():
            raise FileNotFoundError(
                f"Embedding file was not created: {self.embeddings_path}"
            )

        loaded = np.load(
            self.embeddings_path
        )

        if loaded.shape != expected_shape:
            raise ValueError(
                "Saved embedding shape mismatch. "
                f"Expected={expected_shape}, Got={loaded.shape}"
            )

    def process(self) -> EmbeddingStats:
        print("Loading prepared documents...")
        documents = self.load_documents()

        embeddings = self.generate_embeddings(
            documents
        )

        print("Validating embeddings...")
        self.validate_embeddings(
            documents,
            embeddings
        )

        print("Saving embeddings...")
        self.save_embeddings(
            embeddings
        )

        print("Verifying saved embeddings...")
        self.verify_saved_embeddings(
            expected_shape=embeddings.shape
        )

        stats = EmbeddingStats(
            documents_loaded=len(documents),
            embeddings_created=embeddings.shape[0],
            embedding_dimension=embeddings.shape[1],
            output_path=str(self.embeddings_path),
        )

        print("\nEmbedding Generation Complete")
        print("-" * 50)
        print(f"Documents Loaded     : {stats.documents_loaded}")
        print(f"Embeddings Created   : {stats.embeddings_created}")
        print(f"Embedding Dimension  : {stats.embedding_dimension}")
        print(f"Embeddings Path      : {stats.output_path}")

        return stats


if __name__ == "__main__":
    service = EmbeddingGenerationService()
    service.process()
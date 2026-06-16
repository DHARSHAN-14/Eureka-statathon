import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import numpy as np
from sentence_transformers import SentenceTransformer

from src.utils.config import EMBEDDING_MODEL_NAME


class EmbeddingModel:

    _instance = None

    def __new__(cls):

        if cls._instance is None:

            cls._instance = super().__new__(cls)

            print(
                f"Loading Embedding Model: "
                f"{EMBEDDING_MODEL_NAME}"
            )

            cls._instance.model = (
                SentenceTransformer(
                    EMBEDDING_MODEL_NAME
                )
            )

        return cls._instance

    def encode(
        self,
        texts,
        normalize=True
    ):

        if isinstance(texts, str):
            texts = [texts]

        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=normalize,
            show_progress_bar=False
        )

        return embeddings.astype(
            np.float32
        )

    def encode_query(
        self,
        query
    ):

        return self.encode(
            query
        )[0]

    def encode_documents(
        self,
        documents
    ):

        return self.encode(
            documents
        )
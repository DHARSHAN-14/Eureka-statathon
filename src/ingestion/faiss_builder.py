import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from dataclasses import dataclass

import faiss
import numpy as np

from src.utils.config import (
    EMBEDDINGS_PATH,
    FAISS_INDEX_PATH
)


@dataclass(frozen=True)
class FaissStats:
    vectors_indexed: int
    embedding_dimension: int
    index_path: str


class FaissIndexBuilder:
    """
    Builds a FAISS index from generated embeddings.

    Input:
        models/nco_embeddings.npy

    Output:
        models/nco_faiss.index
    """

    def __init__(
        self,
        embeddings_path: Path = EMBEDDINGS_PATH,
        index_path: Path = FAISS_INDEX_PATH,
    ):
        self.embeddings_path = Path(
            embeddings_path
        )

        self.index_path = Path(
            index_path
        )

    def load_embeddings(self):

        if not self.embeddings_path.exists():

            raise FileNotFoundError(
                f"Embeddings file not found: "
                f"{self.embeddings_path}"
            )

        embeddings = np.load(
            self.embeddings_path
        )

        return embeddings

    def validate_embeddings(
        self,
        embeddings
    ):

        if not isinstance(
            embeddings,
            np.ndarray
        ):

            raise TypeError(
                "Embeddings must be numpy array."
            )

        if embeddings.ndim != 2:

            raise ValueError(
                f"Embeddings must be 2D. "
                f"Got shape={embeddings.shape}"
            )

        if embeddings.shape[0] == 0:

            raise ValueError(
                "No embeddings found."
            )

        if embeddings.shape[1] == 0:

            raise ValueError(
                "Embedding dimension cannot be zero."
            )

        if np.isnan(
            embeddings
        ).any():

            raise ValueError(
                "Embeddings contain NaN values."
            )

        if np.isinf(
            embeddings
        ).any():

            raise ValueError(
                "Embeddings contain infinite values."
            )

    def build_index(
        self,
        embeddings
    ):

        dimension = embeddings.shape[1]

        index = faiss.IndexFlatIP(
            dimension
        )

        index.add(
            embeddings.astype(
                np.float32
            )
        )

        return index

    def save_index(
        self,
        index
    ):

        self.index_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        faiss.write_index(
            index,
            str(self.index_path)
        )

    def verify_saved_index(
        self,
        expected_total
    ):

        if not self.index_path.exists():

            raise FileNotFoundError(
                f"Index file missing: "
                f"{self.index_path}"
            )

        loaded_index = faiss.read_index(
            str(self.index_path)
        )

        if loaded_index.ntotal != expected_total:

            raise ValueError(
                "Index verification failed. "
                f"Expected={expected_total}, "
                f"Got={loaded_index.ntotal}"
            )

        return loaded_index

    def run_self_test(
        self,
        index,
        embeddings
    ):

        query = embeddings[0:1]

        scores, indices = index.search(
            query,
            5
        )

        if indices[0][0] != 0:

            raise ValueError(
                "FAISS self-test failed."
            )

        return {
            "top_score":
                float(scores[0][0]),

            "top_index":
                int(indices[0][0])
        }

    def process(self):

        print(
            "Loading embeddings..."
        )

        embeddings = (
            self.load_embeddings()
        )

        print(
            "Validating embeddings..."
        )

        self.validate_embeddings(
            embeddings
        )

        print(
            "Building FAISS index..."
        )

        index = self.build_index(
            embeddings
        )

        print(
            "Saving FAISS index..."
        )

        self.save_index(
            index
        )

        print(
            "Verifying saved index..."
        )

        verified_index = (
            self.verify_saved_index(
                expected_total=
                embeddings.shape[0]
            )
        )

        print(
            "Running FAISS self-test..."
        )

        test_result = (
            self.run_self_test(
                verified_index,
                embeddings
            )
        )

        stats = FaissStats(
            vectors_indexed=
            verified_index.ntotal,

            embedding_dimension=
            embeddings.shape[1],

            index_path=
            str(self.index_path)
        )

        print(
            "\nFAISS Index Creation Complete"
        )

        print("-" * 50)

        print(
            f"Vectors Indexed     : "
            f"{stats.vectors_indexed}"
        )

        print(
            f"Embedding Dimension : "
            f"{stats.embedding_dimension}"
        )

        print(
            f"Index Path          : "
            f"{stats.index_path}"
        )

        print(
            f"Self Test Score     : "
            f"{test_result['top_score']:.4f}"
        )

        return stats


if __name__ == "__main__":

    builder = FaissIndexBuilder()

    builder.process()
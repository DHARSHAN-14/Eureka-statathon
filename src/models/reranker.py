import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from sentence_transformers import CrossEncoder


class Reranker:

    def __init__(self):

        print(
            "Loading Cross Encoder..."
        )

        self.model = CrossEncoder(
            "cross-encoder/ms-marco-MiniLM-L-6-v2"
        )

    def rerank(
        self,
        query,
        candidates,
        top_k=10
    ):

        if not candidates:
            return []

        pairs = []

        for item in candidates:

            document_text = ""

            if "document" in item:
                document_text = item["document"]

            elif "occupation_title" in item:
                document_text = (
                    item["occupation_title"]
                )

            pairs.append(
                (
                    query,
                    document_text
                )
            )

        scores = self.model.predict(
            pairs
        )

        for item, score in zip(
            candidates,
            scores
        ):

            item["rerank_score"] = (
                float(score)
            )

        candidates.sort(
            key=lambda x:
            x["rerank_score"],
            reverse=True
        )

        return candidates[:top_k]
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.retrieval.semantic_search import SemanticSearch
from src.graph.graph_search import GraphSearch


class HybridSearch:

    def __init__(self):

        self.semantic = SemanticSearch()

        self.graph = GraphSearch()

    def get_hierarchy(
        self,
        occupation_id
    ):

        try:

            return self.graph.get_full_hierarchy(
                occupation_id
            )

        except Exception:

            return []

    def get_siblings(
        self,
        occupation_id
    ):

        try:

            return self.graph.get_siblings(
                occupation_id
            )

        except Exception:

            return []

    def search(
        self,
        query,
        top_k=10
    ):

        semantic_results = (
            self.semantic.search(
                query=query,
                top_k=top_k
            )
        )

        enriched_results = []

        for result in semantic_results:

            occupation_id = (
                f"Occupation:{result['nco_code']}"
            )

            hierarchy = self.get_hierarchy(
                occupation_id
            )

            siblings = self.get_siblings(
                occupation_id
            )

            enriched_results.append(
                {
                    "occupation_title":
                        result["occupation_title"],

                    "nco_code":
                        result["nco_code"],

                    "semantic_score":
                        result["score"],

                    "document":
                        result["document"],

                    "metadata":
                        result["metadata"],

                    "hierarchy":
                        hierarchy,

                    "siblings":
                        siblings
                }
            )

        return enriched_results


if __name__ == "__main__":

    hybrid = HybridSearch()

    while True:

        query = input(
            "\nEnter Query (exit to quit): "
        ).strip()

        if query.lower() == "exit":
            break

        results = hybrid.search(
            query=query,
            top_k=5
        )

        print("\n")

        for rank, result in enumerate(
            results,
            start=1
        ):

            print("=" * 80)

            print(
                f"Rank #{rank}"
            )

            print(
                f"Occupation : "
                f"{result['occupation_title']}"
            )

            print(
                f"NCO Code   : "
                f"{result['nco_code']}"
            )

            print(
                f"Score      : "
                f"{result['semantic_score']:.4f}"
            )

            print("\nHierarchy:")

            for node in result[
                "hierarchy"
            ]:

                print(
                    f"   -> {node}"
                )

            print(
                f"\nSibling Count: "
                f"{len(result['siblings'])}"
            )

            print()
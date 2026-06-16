import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.retrieval.hybrid_search import HybridSearch


class QueryEngine:

    def __init__(self):

        self.hybrid = HybridSearch()

    def search(
        self,
        query,
        top_k=5
    ):

        results = self.hybrid.search(
            query=query,
            top_k=top_k
        )

        formatted_results = []

        for result in results:

            formatted_results.append(
                {
                    "occupation_title":
                        result["occupation_title"],

                    "nco_code":
                        result["nco_code"],

                    "confidence":
                        round(
                            result["semantic_score"],
                            4
                        ),

                    "hierarchy":
                        result["hierarchy"]
                }
            )

        return formatted_results

    def display(
        self,
        query,
        top_k=5
    ):

        results = self.search(
            query=query,
            top_k=top_k
        )

        print("\n")
        print("=" * 80)
        print(f"QUERY: {query}")
        print("=" * 80)

        for rank, result in enumerate(
            results,
            start=1
        ):

            print("\n")
            print("-" * 80)

            print(
                f"Rank #{rank}"
            )

            print(
                f"Occupation : {result['occupation_title']}"
            )

            print(
                f"NCO Code   : {result['nco_code']}"
            )

            print(
                f"Confidence : {result['confidence']}"
            )

            print("\nHierarchy:")

            for level in result["hierarchy"]:

                print(
                    f"   -> {level}"
                )

        print("\n")
        print("=" * 80)


if __name__ == "__main__":

    engine = QueryEngine()

    while True:

        query = input(
            "\nEnter Query (exit to quit): "
        )

        if query.lower() == "exit":
            break

        engine.display(
            query=query,
            top_k=5
        )
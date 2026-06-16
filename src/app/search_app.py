import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.retrieval.query_engine import QueryEngine


class SearchApplication:

    def __init__(self):

        self.engine = QueryEngine()

    def banner(self):

        print("\n")
        print("=" * 80)
        print("NCO OCCUPATION INTELLIGENCE ENGINE")
        print("=" * 80)

    def run(self):

        self.banner()

        while True:

            query = input(
                "\nEnter Query (exit to quit): "
            )

            if query.lower() == "exit":
                break

            self.engine.display(
                query=query,
                top_k=5
            )


if __name__ == "__main__":

    app = SearchApplication()

    app.run()
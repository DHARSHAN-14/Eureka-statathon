import json
import sys
from pathlib import Path

import networkx as nx

# Add parent directories to path to handle module imports
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils.config import GRAPH_JSON_PATH


class GraphSearch:

    def __init__(self, graph_path=GRAPH_JSON_PATH):
        self.graph = nx.DiGraph()
        self.load_graph(graph_path)

    def load_graph(self, graph_path):

        with open(graph_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for node in data["nodes"]:
            node_id = node.pop("id")

            self.graph.add_node(
                node_id,
                **node
            )

        for edge in data["edges"]:
            self.graph.add_edge(
                edge["source"],
                edge["target"],
                relationship=edge.get("relationship")
            )

        print(
            f"Graph Loaded | Nodes={self.graph.number_of_nodes()} | Edges={self.graph.number_of_edges()}"
        )

    # ---------------------------------------------------
    # Node Search
    # ---------------------------------------------------

    def find_node(self, keyword):

        keyword = keyword.lower()

        matches = []

        for node_id, attrs in self.graph.nodes(data=True):

            label = attrs.get(
                "label",
                ""
            ).lower()

            if keyword in label:
                matches.append(
                    {
                        "id": node_id,
                        "label": attrs.get("label"),
                        "type": attrs.get("node_type")
                    }
                )

        return matches

    # ---------------------------------------------------
    # Parent Lookup
    # ---------------------------------------------------

    def get_parent(self, node_id):

        parents = list(
            self.graph.predecessors(node_id)
        )

        return parents

    # ---------------------------------------------------
    # Child Lookup
    # ---------------------------------------------------

    def get_children(self, node_id):

        children = list(
            self.graph.successors(node_id)
        )

        return children

    # ---------------------------------------------------
    # Full Hierarchy
    # ---------------------------------------------------

    def get_full_hierarchy(self, node_id):

        hierarchy = []

        current = node_id

        while True:

            hierarchy.append(current)

            parents = list(
                self.graph.predecessors(current)
            )

            if not parents:
                break

            current = parents[0]

        hierarchy.reverse()

        return hierarchy

    # ---------------------------------------------------
    # Ancestors
    # ---------------------------------------------------

    def get_ancestors(self, node_id):

        return list(
            nx.ancestors(
                self.graph,
                node_id
            )
        )

    # ---------------------------------------------------
    # Descendants
    # ---------------------------------------------------

    def get_descendants(self, node_id):

        return list(
            nx.descendants(
                self.graph,
                node_id
            )
        )

    # ---------------------------------------------------
    # Siblings
    # ---------------------------------------------------

    def get_siblings(self, node_id):

        parents = list(
            self.graph.predecessors(node_id)
        )

        if not parents:
            return []

        parent = parents[0]

        siblings = list(
            self.graph.successors(parent)
        )

        return [
            node
            for node in siblings
            if node != node_id
        ]

    # ---------------------------------------------------
    # Family Occupations
    # ---------------------------------------------------

    def get_family_occupations(
        self,
        family_node_id
    ):

        occupations = []

        for child in self.graph.successors(
            family_node_id
        ):

            attrs = self.graph.nodes[child]

            if attrs.get(
                "node_type"
            ) == "Occupation":

                occupations.append(
                    {
                        "id": child,
                        "label": attrs.get("label"),
                        "nco_code": attrs.get("nco_code")
                    }
                )

        return occupations

    # ---------------------------------------------------
    # Division Occupations
    # ---------------------------------------------------

    def get_all_occupations_in_division(
        self,
        division_node_id
    ):

        occupations = []

        descendants = nx.descendants(
            self.graph,
            division_node_id
        )

        for node in descendants:

            attrs = self.graph.nodes[node]

            if attrs.get(
                "node_type"
            ) == "Occupation":

                occupations.append(
                    {
                        "id": node,
                        "label": attrs.get("label"),
                        "nco_code": attrs.get("nco_code")
                    }
                )

        return occupations


if __name__ == "__main__":

    search = GraphSearch()

    results = search.find_node(
        "software"
    )

    print(
        "\nMatching Nodes:\n"
    )

    for item in results:

        print(item)
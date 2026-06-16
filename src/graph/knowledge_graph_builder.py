import json
import sys
from pathlib import Path

import networkx as nx
import pandas as pd

# Add parent directories to path to handle module imports
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils.config import (
    NCO_CSV_PATH,
    GRAPH_DIR,
    GRAPH_JSON_PATH,
    NODE_DIVISION,
    NODE_SUBDIVISION,
    NODE_GROUP,
    NODE_FAMILY,
    NODE_OCCUPATION,
    REL_HAS_SUBDIVISION,
    REL_HAS_GROUP,
    REL_HAS_FAMILY,
    REL_HAS_OCCUPATION
)

from src.graph.graph_schema import (
    create_node,
    clean_text
)


class NCOKnowledgeGraphBuilder:

    def __init__(self):
        self.graph = nx.DiGraph()

    def add_node(
        self,
        node_id,
        label,
        node_type,
        **attributes
    ):

        if not self.graph.has_node(node_id):

            self.graph.add_node(
                node_id,
                label=label,
                node_type=node_type,
                **attributes
            )

    def add_relationship(
        self,
        source,
        target,
        relationship
    ):

        self.graph.add_edge(
            source,
            target,
            relationship=relationship
        )

    def build_from_dataframe(self, df):

        for _, row in df.iterrows():

            division_name = clean_text(
                row["Division"]
            )

            subdivision_name = clean_text(
                row["Sub Division"]
            )

            group_name = clean_text(
                row["Group"]
            )

            family_name = clean_text(
                row["Family"]
            )

            occupation_name = clean_text(
                row["Occupational Title"]
            )

            occupation_code = clean_text(
                row["NCO 2015"]
            )

            division_node = create_node(
                NODE_DIVISION,
                division_name
            )

            subdivision_node = create_node(
                NODE_SUBDIVISION,
                subdivision_name
            )

            group_node = create_node(
                NODE_GROUP,
                group_name
            )

            family_node = create_node(
                NODE_FAMILY,
                family_name
            )

            occupation_node_id = (
                f"Occupation:{occupation_code}"
            )

            self.add_node(
                division_node.node_id,
                division_node.label,
                division_node.node_type
            )

            self.add_node(
                subdivision_node.node_id,
                subdivision_node.label,
                subdivision_node.node_type
            )

            self.add_node(
                group_node.node_id,
                group_node.label,
                group_node.node_type
            )

            self.add_node(
                family_node.node_id,
                family_node.label,
                family_node.node_type
            )

            self.add_node(
                occupation_node_id,
                occupation_name,
                NODE_OCCUPATION,
                nco_code=occupation_code
            )

            self.add_relationship(
                division_node.node_id,
                subdivision_node.node_id,
                REL_HAS_SUBDIVISION
            )

            self.add_relationship(
                subdivision_node.node_id,
                group_node.node_id,
                REL_HAS_GROUP
            )

            self.add_relationship(
                group_node.node_id,
                family_node.node_id,
                REL_HAS_FAMILY
            )

            self.add_relationship(
                family_node.node_id,
                occupation_node_id,
                REL_HAS_OCCUPATION
            )

    def save_graph_json(self):

        data = {
            "nodes": [],
            "edges": []
        }

        for node_id, attrs in self.graph.nodes(
            data=True
        ):

            data["nodes"].append(
                {
                    "id": node_id,
                    **attrs
                }
            )

        for source, target, attrs in self.graph.edges(
            data=True
        ):

            data["edges"].append(
                {
                    "source": source,
                    "target": target,
                    **attrs
                }
            )

        GRAPH_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        with open(
            GRAPH_JSON_PATH,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                indent=2,
                ensure_ascii=False
            )

    def get_graph(self):
        return self.graph


def build_knowledge_graph():

    print("Loading NCO dataset...")

    df = pd.read_csv(
        NCO_CSV_PATH
    )

    builder = NCOKnowledgeGraphBuilder()

    print("Building knowledge graph...")

    builder.build_from_dataframe(df)

    print("Saving graph JSON...")

    builder.save_graph_json()

    graph = builder.get_graph()

    print("\nKnowledge Graph Statistics")
    print("-" * 50)

    print(
        f"Nodes: {graph.number_of_nodes()}"
    )

    print(
        f"Edges: {graph.number_of_edges()}"
    )

    print(
        f"Occupations Processed: {len(df)}"
    )

    return graph


if __name__ == "__main__":
    build_knowledge_graph()
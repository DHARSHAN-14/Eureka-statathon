import networkx as nx

from src.utils.config import (
    GRAPH_DIR,
    GRAPHML_PATH,
    GEXF_PATH
)


class GraphExporter:

    def __init__(self, graph: nx.DiGraph):
        self.graph = graph

    def export_graphml(self):

        GRAPH_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        nx.write_graphml(
            self.graph,
            GRAPHML_PATH
        )

        print(
            f"✅ GraphML exported -> {GRAPHML_PATH}"
        )

    def export_gexf(self):

        GRAPH_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        nx.write_gexf(
            self.graph,
            GEXF_PATH
        )

        print(
            f"✅ GEXF exported -> {GEXF_PATH}"
        )

    def export_all(self):

        self.export_graphml()

        self.export_gexf()
import json
import sys
from pathlib import Path

from pyvis.network import Network

# Add parent directories to path to handle module imports
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils.config import (
    GRAPH_JSON_PATH,
    HTML_VISUALIZATION_PATH
)


class GraphVisualizer:

    def __init__(self):

        self.net = Network(
            height="900px",
            width="100%",
            directed=True,
            bgcolor="#111111",
            font_color="white"
        )

    def node_color(self, node_type):

        colors = {
            "Division": "#ff4d4d",
            "SubDivision": "#ff944d",
            "Group": "#ffd24d",
            "Family": "#4dff88",
            "Occupation": "#4da6ff"
        }

        return colors.get(
            node_type,
            "#cccccc"
        )

    def node_size(self, node_type):

        sizes = {
            "Division": 40,
            "SubDivision": 30,
            "Group": 25,
            "Family": 20,
            "Occupation": 10
        }

        return sizes.get(
            node_type,
            10
        )

    def load_graph(self):

        with open(
            GRAPH_JSON_PATH,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    def build(self):

        graph_data = self.load_graph()

        for node in graph_data["nodes"]:

            node_type = node["node_type"]

            self.net.add_node(
                node["id"],
                label=node["label"],
                title=f"""
                Type: {node_type}
                """,
                color=self.node_color(node_type),
                size=self.node_size(node_type)
            )

        for edge in graph_data["edges"]:

            self.net.add_edge(
                edge["source"],
                edge["target"]
            )

        self.net.set_options("""
        {
          "physics": {
            "enabled": false
          },
          "layout": {
            "hierarchical": {
              "enabled": true,
              "direction": "UD",
              "sortMethod": "directed"
            }
          }
        }
        """)

    def save(self):

        self.net.write_html(
            str(HTML_VISUALIZATION_PATH)
        )

        print(
            f"Visualization saved: {HTML_VISUALIZATION_PATH}"
        )


def create_visualization():

    visualizer = GraphVisualizer()

    visualizer.build()

    visualizer.save()


if __name__ == "__main__":
    create_visualization()
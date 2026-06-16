from dataclasses import dataclass


@dataclass(frozen=True)
class GraphNode:
    """
    Generic graph node representation.
    """

    node_id: str
    node_type: str
    label: str


def clean_text(value) -> str:
    """
    Normalize text values before graph insertion.
    """

    if value is None:
        return ""

    value = str(value).strip()

    value = " ".join(value.split())

    return value


def build_node_id(node_type: str, value: str) -> str:
    """
    Generate globally unique node id.
    """

    value = clean_text(value)

    return f"{node_type}:{value}"


def create_node(node_type: str, label: str) -> GraphNode:
    """
    Factory for graph nodes.
    """

    label = clean_text(label)

    return GraphNode(
        node_id=build_node_id(node_type, label),
        node_type=node_type,
        label=label
    )
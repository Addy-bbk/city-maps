"""Read and Write the City Maps Plain-Text Graph Format.

The format is simple:

# Nodes
0 -20 400
1 10 250
...

# Edges
0 1
0 2
...

Rules:
* The node IDs will be the consecutive numbers 0 through n-1.
* The coordinates are measured in meters in a projected (Cartesian) coordinate system.
* Each edge will be represented only once, and will use the smaller ID.
* There are no loops (edges going from a vertex to itself) and there are no multiple edges.
* There are no other attributes.

Since this module depends only on the Standard Library and NetworkX, it does not depend on OSMnx. Therefore the format can be tested without contacting the OpenStreetMap servers.
"""

from __future__ import annotations

from pathlib import Path

import networkx as nx

NODE_HEADER = "# Nodes"
EDGE_HEADER = "# Edges"

# FORMAT COORDINATE. If value is an integer, then it prints as just that number. Otherwise, drop off a '.0'.
def _format_coord(value: float, precision: int) -> str:
    """Print out a coordinate. Drop a .0 when printing a number like '400.0'. Print it instead as '400'. """
    return f"{round(float(value), precision):g}"


def write_graph(G: nx.Graph, path: str | Path, precision: int = 1) -> Path:
    """Write an undirected graph to the City Maps text format.

    Every node must carry 'x' and 'y' attributes and be labelled with a
    consecutive integer from 0. Raises ValueError otherwise, rather than
    writing a file that silently violates the specification.
    """
    path = Path(path)
    nodes = sorted(G.nodes())

    if nodes != list(range(len(nodes))):
        raise ValueError(
            "nodes must be labelled 0..n-1; call relabel_consecutive() first"
        )

    lines = [NODE_HEADER]
    for n in nodes:
        attrs = G.nodes[n]
        if "x" not in attrs or "y" not in attrs:
            raise ValueError(f"node {n} is missing an 'x' or 'y' attribute")
        x = _format_coord(attrs["x"], precision)
        y = _format_coord(attrs["y"], precision)
        lines.append(f"{n} {x} {y}")

    # Canonicalise: undirected, deduplicated, self-loops dropped, sorted.
    edges = sorted({(min(u, v), max(u, v)) for u, v in G.edges() if u != v})

    lines.append("")
    lines.append(EDGE_HEADER)
    lines.extend(f"{u} {v}" for u, v in edges)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def read_graph(path: str | Path) -> nx.Graph:
    """This is a function to read a City Maps Text File into a NetworkX Graph.
    This allows to test round trips and parse data. """
    path = Path(path)
    G = nx.Graph()
    section = None

    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if line == NODE_HEADER:
            section = "nodes"
            continue
        if line == EDGE_HEADER:
            section = "edges"
            continue
        if line.startswith("#"):
            continue

        parts = line.split()
        try:
            if section == "nodes":
                node_id, x, y = int(parts[0]), float(parts[1]), float(parts[2])
                G.add_node(node_id, x=x, y=y)
            elif section == "edges":
                G.add_edge(int(parts[0]), int(parts[1]))
            else:
                raise ValueError("data appears before any section header")
        except (ValueError, IndexError) as exc:
            raise ValueError(f"{path.name}, line {lineno}: malformed -> {raw!r}") from exc

    return G


def relabel_consecutive(G: nx.Graph) -> nx.Graph:
    """Relabel the nodes in a NetworkX Graph so they are labeled 0..n-1.
    Sorting the original labels first ensures that the same input always generates the same output file, 
    which is important for reproducibility and for comparing the dataset after running different pipelines. """
    mapping = {old: new for new, old in enumerate(sorted(G.nodes(), key=str))}
    return nx.relabel_nodes(G, mapping, copy=True)

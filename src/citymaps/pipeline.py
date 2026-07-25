"""
A five stage extraction pipeline from open street map to text file. 
1. Download - obtain the drivable network for a place (OSMnx).
2. Project - convert lat/lon to local UTM zone (metres).
3. Consolidate - combine clusters of nodes into single intersections.
4. Reduce - transform to an undirected simple graph with only x and y coordinates.
5. Export - write the text file (delegated to formats.write_graph).
Everything down stream of this module operates on plain networkx graphs.
This is also the only module that needs to be connected to internet because it imports OSMnx. 
"""

from __future__ import annotations

import logging
from pathlib import Path

import networkx as nx
import osmnx as ox

from . import config
from .formats import relabel_consecutive, write_graph

log = logging.getLogger(__name__)


def download(query: str) -> nx.MultiDiGraph:
    """get the road network within a place boundary where cars can drive."""
    log.info("downloading %s", query)
    return ox.graph_from_place(
        query,
        network_type=config.NETWORK_TYPE,
        simplify=True,
        retain_all=False,
    )


def project(G: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """Project on the UTM zone containing the centroid of the graph."""
    return ox.project_graph(G, to_crs=None)


def consolidate(G: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """merge each set of nodes lying inside tolerance to one intersection. """
    return ox.consolidate_intersections(
        G,
        tolerance=config.CONSOLIDATION_TOLERANCE_M,
        rebuild_graph=True,
        dead_ends=config.CONSOLIDATE_DEAD_ENDS,
        reconnect_edges=True,
    )


def reduce_to_simple(G: nx.MultiDiGraph) -> nx.Graph:
    """collapse to an undirected simple graph carrying only x,y.
    one way streets, parallel carriageways and road classifications disappear here;
    The dataset contains topology and geometry data, nothing else.
    """
    U = nx.Graph()
    for node, attrs in G.nodes(data=True):
        U.add_node(node, x=float(attrs["x"]), y=float(attrs["y"]))
    for u, v in G.edges():
        if u != v:  # drop self-loops (e.g. roundabouts collapsed to a point)
            U.add_edge(u, v)

    if config.KEEP_LARGEST_COMPONENT and U.number_of_nodes():
        largest = max(nx.connected_components(U), key=len)
        discarded = U.number_of_nodes() - len(largest)
        if discarded:
            log.info("discarding %d nodes outside largest component", discarded)
        U = U.subgraph(largest).copy()

    U = relabel_consecutive(U)

    if config.RECENTRE_ON_CENTROID and U.number_of_nodes():
        U = recentre(U)

    return U


def recentre(G: nx.Graph) -> nx.Graph:
    """move all coordinates so mean node position sits at origin.
    Only pure translation therefore distances, angles and topology unchanged,
    Just numbers smaller & readable.
    Eastings in UTM are otherwise six digit values which would dominate size of files for no benefit.
    """
    n = G.number_of_nodes()
    cx = sum(G.nodes[i]["x"] for i in G.nodes()) / n
    cy = sum(G.nodes[i]["y"] for i in G.nodes()) / n
    for i in G.nodes():
        G.nodes[i]["x"] -= cx
        G.nodes[i]["y"] -= cy
    return G


def process_city(name: str, query: str, output_dir: Path | None = None) -> dict:
    """return evidence record for that city: turns 'pipeline ran' into something tabulatable in report."""
    output_dir = Path(output_dir or config.GRAPH_DIR)
    slug = name.lower().replace(" ", "_").replace(",", "")

    raw = download(query)
    raw_nodes = raw.number_of_nodes()

    projected = project(raw)
    crs = str(projected.graph.get("crs"))

    consolidated = consolidate(projected)
    simple = reduce_to_simple(consolidated)

    path = write_graph(simple, output_dir / f"{slug}.txt", config.COORD_PRECISION)

    return {
        "city": name,
        "query": query,
        "crs": crs,
        "raw_nodes": raw_nodes,
        "final_nodes": simple.number_of_nodes(),
        "final_edges": simple.number_of_edges(),
        "reduction_pct": round(100 * (1 - simple.number_of_nodes() / raw_nodes), 1)
        if raw_nodes
        else 0.0,
        "file": str(path.relative_to(config.PROJECT_ROOT)),
    }

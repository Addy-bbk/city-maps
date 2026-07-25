"""
Offline validation and formatting unit-tests for CityMaps. These tests do not interact with OpenStreetMap; 
instead, they generate "mini-lattices." The characteristics of these lattices have been predetermined (i.e., all lattices are well-characterized), 
so if the tests fail, then there is something wrong with the code itself (and not the result of a connection issue or an OSM update). To run these tests, type:
pytest -q
"""


import sys
from pathlib import Path

import networkx as nx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from citymaps.formats import read_graph, relabel_consecutive, write_graph
from citymaps.validate import check_planarity, check_structure


def grid(rows: int, cols: int) -> nx.Graph:
    """Creates a lattice (rows x cols) with 10m spacting.
    A 10 x 10 grid has 180 edges and 100 nodes. So this checks against arithmetic instead of the previous output
    """
    G = nx.grid_2d_graph(rows, cols)
    G = nx.convert_node_labels_to_integers(G, ordering="sorted")
    for i, (r, c) in enumerate(sorted((r, c) for r in range(rows) for c in range(cols))):
        G.nodes[i]["x"] = float(c * 10)
        G.nodes[i]["y"] = float(r * 10)
    return G


def test_written_file_matches_specification(tmp_path):
    G = grid(2, 2)
    path = write_graph(G, tmp_path / "toy.txt")
    lines = path.read_text().splitlines()

    assert lines[0] == "# Nodes"
    assert lines[1] == "0 0 0"          
    assert "" in lines                   
    assert "# Edges" in lines


def test_round_trip_preserves_topology_and_geometry(tmp_path):
    G = grid(4, 5)
    H = read_graph(write_graph(G, tmp_path / "rt.txt"))

    assert H.number_of_nodes() == G.number_of_nodes()
    assert H.number_of_edges() == G.number_of_edges()
    assert nx.is_isomorphic(G, H)
    for n in G.nodes():
        assert H.nodes[n]["x"] == pytest.approx(G.nodes[n]["x"])
        assert H.nodes[n]["y"] == pytest.approx(G.nodes[n]["y"])


def test_negative_coordinates_survive_round_trip(tmp_path):
    """Negative coordinates were created through recentring; therefore, the parser must be able to interpret them. 
    For example, see the specification’s own example (“0 -20 400”) contains one. That is why negative values are used by this round-trip test"""
    G = nx.Graph()
    G.add_node(0, x=-20.0, y=400.0)
    G.add_node(1, x=10.0, y=250.0)
    G.add_edge(0, 1)

    H = read_graph(write_graph(G, tmp_path / "neg.txt"))
    assert H.nodes[0]["x"] == pytest.approx(-20.0)


def test_self_loops_and_parallel_edges_are_dropped(tmp_path):
    G = nx.MultiGraph()
    G.add_node(0, x=0.0, y=0.0)
    G.add_node(1, x=1.0, y=1.0)
    G.add_edge(0, 0)      # self-loop
    G.add_edge(0, 1)
    G.add_edge(0, 1)      # parallel edge
    H = read_graph(write_graph(nx.Graph(G), tmp_path / "clean.txt"))
    assert H.number_of_edges() == 1
    assert nx.number_of_selfloops(H) == 0


def test_edges_are_canonically_ordered(tmp_path):
    G = nx.Graph()
    G.add_node(0, x=0.0, y=0.0)
    G.add_node(1, x=1.0, y=0.0)
    G.add_edge(1, 0)      # added in reverse
    text = write_graph(G, tmp_path / "ord.txt").read_text()
    edge_lines = text.split("# Edges")[1].split()
    assert edge_lines == ["0", "1"]


def test_non_consecutive_labels_are_rejected(tmp_path):
    G = nx.Graph()
    G.add_node(7, x=0.0, y=0.0)
    G.add_node(9, x=1.0, y=1.0)
    G.add_edge(7, 9)
    with pytest.raises(ValueError, match="0..n-1"):
        write_graph(G, tmp_path / "bad.txt")


def test_missing_coordinates_are_rejected(tmp_path):
    G = nx.Graph()
    G.add_node(0, x=0.0)  # no 'y'
    with pytest.raises(ValueError, match="'x' or 'y'"):
        write_graph(G, tmp_path / "bad.txt")


def test_relabel_is_deterministic():
    G = nx.Graph()
    G.add_edges_from([("b", "a"), ("a", "c")])
    for n in G.nodes():
        G.nodes[n]["x"] = G.nodes[n]["y"] = 0.0
    first = sorted(relabel_consecutive(G).edges())
    second = sorted(relabel_consecutive(G).edges())
    assert first == second


def test_malformed_line_reports_line_number(tmp_path):
    p = tmp_path / "broken.txt"
    p.write_text("# Nodes\n0 0 0\n1 oops 3\n")
    with pytest.raises(ValueError, match="line 3"):
        read_graph(p)


def test_structure_report_on_known_grid():
    G = grid(10, 10)
    r = check_structure(G)
    # A 10x10 grid contains 100 nodes and 180 edges.
    assert r["n_nodes"] == 100
    assert r["n_edges"] == 180
    assert r["mean_degree"] == pytest.approx(3.6)
    assert r["connected"] and r["within_planar_bound"] and r["passed"]


def test_grid_is_planar_and_k5_is_not():
    assert check_planarity(grid(6, 6))["is_planar"] is True
    k5 = check_planarity(nx.complete_graph(5))
    assert k5["is_planar"] is False
    # K5 is small enough to compute its witness and therefore the witness is K5 (5 nodes).
    assert k5["witness_computed"] is True
    assert k5["kuratowski_size"] == 5


def test_large_nonplanar_graph_skips_witness():
    """Witness search is skipped for larger than the node limit graphs so that a large non-planar 
    city doesn't hang while returning quickly after determining if the graph is planar. 
    Since K5 is non-planar regardless of how many isolating nodes are added to it, we build a graph greater 
    than the test size limit that is also known to be non-planar. """
    G = nx.complete_graph(5)          # non-planar core
    G.add_nodes_from(range(5, 30))    # padding to exceed the tiny test limit
    r = check_planarity(G, witness_limit=10)
    assert r["is_planar"] is False
    assert r["witness_computed"] is False
    assert "kuratowski_size" not in r

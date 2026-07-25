"""
Validation checks for city graphs created by drawing city graphs out of existing data sets:
Structural validation of the graph structure, and planarity. Visual verification for correct-ness (superimposition over a base map) 
will be done in a jupyter-notebook where humans can judge whether the graph is correct or not instead of using an assert-statement. 
This file follows the same pattern as formats.py. It uses only NetworkX, and thus the complete set of checks can be executed 
without having to connect to any remote service."""

from __future__ import annotations

import networkx as nx


def check_structure(G: nx.Graph) -> dict:
    """perform structural sanity checks and return a dictionary containing a report.
    This function does not raise exceptions; A city that fails a test will produce findings,
    but should not cause the program to crash. The caller will decide how to proceed."""
    n = G.number_of_nodes()
    m = G.number_of_edges()

    report = {
        "n_nodes": n,
        "n_edges": m,
        "connected": nx.is_connected(G) if n else False,
        "n_components": nx.number_connected_components(G) if n else 0,
        "n_self_loops": nx.number_of_selfloops(G),
        "n_isolated": len(list(nx.isolates(G))),
        "mean_degree": (2 * m / n) if n else 0.0,
        "edge_node_ratio": (m / n) if n else 0.0,
    }

    # According to Euler's formula, every simple planar graph with n>=3 is bound by m<=3n-6. 
    # Most road networks have values well below this, so if a value exceeds this, 
    # it is likely due to an error during processing rather than some uncommon property of a city.
    report["planar_edge_bound"] = (3 * n - 6) if n >= 3 else None
    report["within_planar_bound"] = (m <= 3 * n - 6) if n >= 3 else True

    # Road networks are sparsely connected. Mean degree for typical values is generally between 2 and 4.
    # Thus, values outside these bounds may indicate an error during simplification.
    report["plausible_mean_degree"] = 1.5 <= report["mean_degree"] <= 5.0

    report["passed"] = all(
        [
            n > 0,
            m > 0,
            report["n_self_loops"] == 0,
            report["n_isolated"] == 0,
            report["within_planar_bound"],
            report["plausible_mean_degree"],
        ]
    )
    return report


# Above this number of nodes the Kuratowski subgraph search example is not attempted.
# The planarity test itself is linear time and will be executed for any city; 
# only the extraction of the witness (true counter-example =) is expensive because networkx 
# repeatedly builds and re-tests subgraphs until it finds a minimal obstruction.
# On very large, non-planar road networks the search can take several minutes, 
# so the extraction of the witness is reserved for graphs that are sufficiently small so as to keep the search cheap.
WITNESS_NODE_LIMIT = 2000


def check_planarity(G: nx.Graph, witness_limit: int = WITNESS_NODE_LIMIT) -> dict:
    """Test planarity using networkx's Boyer Myrvold implementation.

As mentioned previously, road networks are only approximate planar. Bridges, tunnels, etc., create real crossings; 
therefore, a non-planar result is to be expected for many cities and would also represent a finding.
The planarity test is always performed. However, the Kuratowski subgraph — a minimal witness that locates a crossing for visualization purposes — 
is only extracted when the graph has at most `witness_limit` nodes since the extraction cost increases rapidly with increasing size of the graph. 
Therefore, larger graphs only receive the boolean results from the previous step and `witness_computed` is set to False. 
Hence, the report can provide honest reasons why there were no witnesses provided."""

# Fast path: Only perform the boolean planarity test, O(n+m), safe on all sizes.
    is_planar = nx.check_planarity(G, counterexample=False)[0]
    result = {"is_planar": bool(is_planar), "witness_computed": False}

    if not is_planar and G.number_of_nodes() <= witness_limit:
        _, witness = nx.check_planarity(G, counterexample=True)
        if witness is not None:
            result["witness_computed"] = True
            result["kuratowski_nodes"] = sorted(witness.nodes())
            result["kuratowski_size"] = witness.number_of_nodes()

    return result


def validate(G: nx.Graph) -> dict:
    """Run the full offline check suite for one city."""
    report = check_structure(G)
    report.update(check_planarity(G))
    return report

from dataclasses import asdict

from repairgraph.topology.schema import TopologyGraph


def topology_to_dict(topology: TopologyGraph) -> dict:
    """Convert a TopologyGraph to a JSON-serializable dictionary."""
    return asdict(topology)

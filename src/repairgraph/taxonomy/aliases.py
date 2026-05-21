ALIASES = {
    "rear_wheel_arch_separator": "wheel_arch_separator",
}


def resolve_alias(node_id: str) -> str:
    return ALIASES.get(node_id, node_id)

ALIASES = {
    "rear_wheel_arch_separator": "wheel_arch_separator",
    "rear_quarter_separator": "rear_pillar_separator",
    "2_plate_spot_weld": "spot_weld",
    "3_plate_spot_weld": "spot_weld",
    "4_plate_spot_weld": "spot_weld",
    "double_hole_mig_brazing": "mig_brazing",
    "single_hole_mig_brazing": "mig_brazing",
    "mag_weld": "mag_plug_weld",
}


def resolve_alias(node_id: str) -> str:
    return ALIASES.get(node_id, node_id)

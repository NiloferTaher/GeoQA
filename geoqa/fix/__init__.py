"""Fix-function wrappers for GeoQA cleanup helpers."""

from geoqa.fixes import (
    RepairProfile,
    apply_basic_geometry_fixes,
    apply_repair_plan,
    clear_custom_repairs,
    drop_null_geometries,
    list_custom_repairs,
    make_geometries_valid,
    register_custom_repair,
    remove_duplicate_vertices,
)

__all__ = [
    "RepairProfile",
    "apply_basic_geometry_fixes",
    "apply_repair_plan",
    "clear_custom_repairs",
    "drop_null_geometries",
    "list_custom_repairs",
    "make_geometries_valid",
    "register_custom_repair",
    "remove_duplicate_vertices",
]

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True, frozen=True)
class WaterNetworkSchemaHints:
    asset_id_field: str | None
    diameter_field: str | None
    material_field: str | None
    status_field: str | None
    role_field: str | None
    present_fields: tuple[str, ...]
    missing_fields: tuple[str, ...]
    schema_strength: str

    @property
    def required_fields(self) -> tuple[str, ...]:
        return tuple(field for field in (self.asset_id_field, self.status_field) if field)

    @property
    def unique_field(self) -> str | None:
        return self.asset_id_field


def _first_existing(columns: set[str], candidates: tuple[str, ...]) -> str | None:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def detect_water_network_schema(layer: Any) -> WaterNetworkSchemaHints:
    columns = {str(column) for column in getattr(layer, "columns", [])}
    asset_id_field = _first_existing(columns, ("asset_id", "pipe_id", "assetid", "assetid_1", "globalid"))
    diameter_field = _first_existing(columns, ("pipe_diameter", "diameter", "diam_mm", "diameter_mm", "nominal_diameter"))
    material_field = _first_existing(columns, ("material", "pipe_material", "matl", "pipe_mat"))
    status_field = _first_existing(columns, ("status", "asset_status", "lifecycle_status", "operational_status"))
    role_field = _first_existing(columns, ("asset_type", "asset_class", "network_role", "service_type", "pipe_role"))

    present_fields = tuple(
        field
        for field in (asset_id_field, diameter_field, material_field, status_field, role_field)
        if field is not None
    )
    missing_fields = tuple(
        label
        for label, field in (
            ("asset_id", asset_id_field),
            ("diameter", diameter_field),
            ("material", material_field),
            ("status", status_field),
            ("role", role_field),
        )
        if field is None
    )
    strength_score = len(present_fields)
    schema_strength = "strong" if strength_score >= 4 else "moderate" if strength_score >= 2 else "weak"

    return WaterNetworkSchemaHints(
        asset_id_field=asset_id_field,
        diameter_field=diameter_field,
        material_field=material_field,
        status_field=status_field,
        role_field=role_field,
        present_fields=present_fields,
        missing_fields=missing_fields,
        schema_strength=schema_strength,
    )


__all__ = ["WaterNetworkSchemaHints", "detect_water_network_schema"]

"""Pure validation utilities for zone-based layout constraints."""

from __future__ import annotations

from typing import Any


class ZoneError(Exception):
    """Base exception for zone constraint violations."""

    pass


class ZoneOverflowError(ZoneError):
    """Raised when a zone exceeds its max_objects limit."""

    pass


class ZoneTypeError(ZoneError):
    """Raised when an object type is not allowed in a zone."""

    pass


class ZoneNotFoundError(ZoneError):
    """Raised when a referenced zone does not exist in the layout."""

    pass


class PrimaryZoneEmptyError(ZoneError):
    """Raised when the primary zone lacks a non-text visual object."""

    pass


def validate_zone(
    zone_name: str,
    mobj: Any,
    zone: dict[str, Any],
    zone_objects: dict[str, list[Any]],
) -> None:
    """Enforce max_objects and allowed_types constraints."""
    max_obj = zone.get("max_objects")
    if max_obj is not None:
        current = len(zone_objects.get(zone_name, []))
        if current >= max_obj:
            raise ZoneOverflowError(
                f"Zone '{zone_name}' is full (max_objects={max_obj}). "
                f"Attempted to add {type(mobj).__name__}."
            )

    allowed = zone.get("allowed_types")
    if allowed is not None:
        type_name = type(mobj).__name__
        mro_names = {cls.__name__ for cls in type(mobj).__mro__}
        if not mro_names.intersection(set(allowed)):
            raise ZoneTypeError(
                f"Zone '{zone_name}' does not allow type '{type_name}'. Allowed: {allowed}"
            )


def validate_primary_zone(
    zones: dict[str, dict[str, Any]],
    zone_objects: dict[str, list[Any]],
    text_types: tuple[str, ...] = ("Text", "Tex", "TexText", "MathTex"),
) -> None:
    """Check that the primary zone contains at least one non-text visual."""
    primary_zone = None
    for name, meta in zones.items():
        if meta.get("importance") == "primary":
            primary_zone = name
            break

    if primary_zone is None:
        return

    visual_found = False
    for mobj in zone_objects.get(primary_zone, []):
        if type(mobj).__name__ not in text_types:
            visual_found = True
            break

    if not visual_found:
        raise PrimaryZoneEmptyError(
            f"Primary zone '{primary_zone}' must contain at least one "
            f"non-text visual mobject (e.g. Circle, Axes, NumberLine)."
        )

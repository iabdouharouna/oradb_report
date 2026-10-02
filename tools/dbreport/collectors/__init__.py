"""Collecteurs du rapport standard (une section par domaine)."""

from __future__ import annotations

from .backup import collect_backup
from .capacity import collect_capacity
from .dataguard import collect_dataguard
from .health import collect_health
from .identity import collect_identity
from .objects import collect_objects
from .security import collect_security

# Ordre d'execution et d'affichage des sections.
COLLECTORS: tuple[tuple[str, object], ...] = (
    ("identity", collect_identity),
    ("capacity", collect_capacity),
    ("objects", collect_objects),
    ("health", collect_health),
    ("security", collect_security),
    ("backup", collect_backup),
    ("dataguard", collect_dataguard),
)

SECTION_NAMES = tuple(name for name, _ in COLLECTORS)

__all__ = ["COLLECTORS", "SECTION_NAMES"]

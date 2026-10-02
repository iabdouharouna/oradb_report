"""Orchestration de la collecte et persistance des snapshots."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from .collectors import COLLECTORS, SECTION_NAMES
from .config import InventoryEntry, Settings
from .db import one_line, session
from .model import DatabaseSnapshot

LOGGER = logging.getLogger("dbreport")

SNAPSHOT_NAME = "snapshot.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def collect_database(
    entry: InventoryEntry,
    settings: Settings,
    sections: tuple[str, ...] | None = None,
) -> DatabaseSnapshot:
    """Collecte toutes les sections d'une base ; une erreur de connexion est capturee."""

    snapshot = DatabaseSnapshot(
        name=entry.name,
        dsn=entry.dsn,
        environment=entry.environment,
        service=entry.service,
        tags=list(entry.tags),
        collected_at=_utc_now(),
    )

    selected = [
        (name, func)
        for name, func in COLLECTORS
        if sections is None or name in sections
    ]

    try:
        with session(entry, settings) as connection:
            for name, func in selected:
                LOGGER.info("  section %s", name)
                snapshot.sections.append(func(connection, entry))
    except Exception as exc:  # noqa: BLE001 - on isole l'echec par base
        snapshot.ok = False
        snapshot.error = one_line(exc)
        LOGGER.error("  base %s : echec : %s", entry.name, snapshot.error)
    return snapshot


def collect_all(
    settings: Settings,
    names: list[str] | None = None,
    tags: list[str] | None = None,
    sections: tuple[str, ...] | None = None,
) -> list[DatabaseSnapshot]:
    """Collecte l'ensemble des bases selectionnees de l'inventaire."""

    targets = settings.select(names=names, tags=tags)
    if not targets:
        LOGGER.warning("aucune base selectionnee dans l'inventaire")
    snapshots: list[DatabaseSnapshot] = []
    for entry in targets:
        LOGGER.info("base %s (%s)", entry.name, entry.dsn)
        snapshots.append(collect_database(entry, settings, sections))
    return snapshots


def resolve_sections(value: str | None) -> tuple[str, ...] | None:
    """Convertit une liste de sections (texte) en tuple valide ; None = toutes."""

    raw = value or os.environ.get("ORAREPORT_SECTIONS") or ""
    names = [item.strip().lower() for item in raw.split(",") if item.strip()]
    if not names:
        return None
    unknown = [name for name in names if name not in SECTION_NAMES]
    if unknown:
        raise ValueError(
            "Section(s) inconnue(s) : "
            + ", ".join(unknown)
            + " ; disponibles : "
            + ", ".join(SECTION_NAMES)
        )
    return tuple(names)


def save_snapshots(
    snapshots: list[DatabaseSnapshot], settings: Settings, directory: Path
) -> Path:
    """Ecrit le snapshot (JSON) dans le dossier fourni et retourne le chemin."""

    directory.mkdir(parents=True, exist_ok=True)
    filename = os.environ.get("ORAREPORT_SNAPSHOT_NAME") or SNAPSHOT_NAME
    path = directory / filename
    payload = {
        "generated_at": _utc_now(),
        "inventory": str(settings.inventory_file),
        "databases": [snapshot.to_dict() for snapshot in snapshots],
    }
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return path


def new_snapshot_dir(settings: Settings) -> Path:
    return settings.output_dir / _stamp()


def load_snapshot_file(path: Path) -> tuple[dict, list[DatabaseSnapshot]]:
    """Lit un fichier snapshot et retourne (payload, snapshots)."""

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    snapshots = [
        DatabaseSnapshot.from_dict(item) for item in data.get("databases", [])
    ]
    return data, snapshots


def latest_snapshot_file(settings: Settings) -> Path | None:
    """Retourne le snapshot JSON le plus recent du repertoire de sortie."""

    if not settings.output_dir.is_dir():
        return None
    candidates = sorted(
        (
            path / SNAPSHOT_NAME
            for path in settings.output_dir.iterdir()
            if path.is_dir() and (path / SNAPSHOT_NAME).is_file()
        ),
        key=lambda item: item.parent.name,
    )
    return candidates[-1] if candidates else None

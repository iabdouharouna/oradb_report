"""Auto-test hors base : valide l'inventaire, le modele et les rendus de rapport.

Utilisation (dans le venv cree par setup_project.py) :

    python tools/selftest.py

Ne se connecte a aucune base : construit un snapshot en memoire et verifie que
les rapports Markdown / HTML / CSV sont bien produits.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from dbreport.collect import load_snapshot_file, save_snapshots  # noqa: E402
from dbreport.config import from_env  # noqa: E402
from dbreport.model import CollectorResult, DatabaseSnapshot  # noqa: E402
from dbreport.report import write_reports  # noqa: E402


def _sample_snapshot() -> DatabaseSnapshot:
    snapshot = DatabaseSnapshot(
        name="DEMO",
        dsn="demo:1521/PDB1",
        environment="test",
        service="primary",
        tags=["demo"],
        collected_at="2026-01-01 00:00:00 UTC",
    )
    snapshot.sections.append(
        CollectorResult(
            "identity",
            "OK",
            facts={"name": "DEMO", "version": "19.0.0.0.0", "database_role": "PRIMARY"},
            tables={"pdbs": [{"name": "PDB1", "open_mode": "READ WRITE"}]},
        )
    )
    snapshot.sections.append(
        CollectorResult(
            "capacity",
            "OK",
            facts={"database_mb": 1234.5, "tablespace_max_pct": 87.3},
            tables={"tablespaces": [{"tablespace_name": "USERS", "used_pct": 87.3}]},
        )
    )
    snapshot.sections.append(
        CollectorResult(
            "objects",
            "PARTIEL",
            facts={"invalid_total": 3},
            tables={
                "invalid_objects": [
                    {"owner": "APP", "object_name": "PKG_X", "status": "INVALID"}
                ]
            },
            messages=["stale_stats: ORA-00942: table or view does not exist"],
        )
    )
    snapshot.sections.append(
        CollectorResult(
            "security",
            "OK",
            facts={"account_locked": 2},
            tables={"accounts": [{"username": "SCOTT", "account_status": "OPEN"}]},
        )
    )
    snapshot.sections.append(
        CollectorResult("backup", "OK", facts={"last_backup_age_days": 0.5}, tables={})
    )
    snapshot.sections.append(
        CollectorResult(
            "dataguard",
            "OK",
            facts={
                "dg_protection_mode": "MAXIMUM AVAILABILITY",
                "dg_protection_level": "MAXIMUM AVAILABILITY",
                "dg_standby_count": 2,
                "dg_synced_count": 2,
                "dg_gap_count": 0,
                "dg_sync_status": "2/2 SYNC",
                "dg_seq_gap_STANDBY1": 1,
                "dg_transport_gap_STANDBY1": 0,
                "dg_seq_gap_STANDBY2": 1,
                "dg_transport_gap_STANDBY2": 0,
            },
            tables={
                "dataguard_config": [
                    {"db_unique_name": "STANDBY1", "role": "PHYSICAL STANDBY", "parent_dbun": "DEMO"},
                    {"db_unique_name": "STANDBY2", "role": "PHYSICAL STANDBY", "parent_dbun": "DEMO"},
                ],
                "dataguard_standby_sync": [
                    {
                        "dest_id": 2,
                        "db_unique_name": "STANDBY1",
                        "dest_role": "PHYSICAL STANDBY",
                        "synchronized": "YES",
                        "synchronization_status": "OK",
                        "recovery_mode": "MANAGED REAL TIME APPLY",
                        "gap_status": "NO",
                        "applied_seq#": 100,
                        "archived_seq#": 101,
                        "error": 0,
                        "estimated_startup_time": "2026-01-01 00:00:00",
                    },
                    {
                        "dest_id": 3,
                        "db_unique_name": "STANDBY2",
                        "dest_role": "PHYSICAL STANDBY",
                        "synchronized": "YES",
                        "synchronization_status": "OK",
                        "recovery_mode": "MANAGED REAL TIME APPLY",
                        "gap_status": "NO",
                        "applied_seq#": 100,
                        "archived_seq#": 101,
                        "error": 0,
                        "estimated_startup_time": "2026-01-01 00:00:00",
                    },
                ],
                "dataguard_stats": [
                    {"name": "apply lag", "value": "0", "unit": "seconds", "time_computed": "2026-01-01 00:00:00"},
                    {"name": "transport lag", "value": "0", "unit": "seconds", "time_computed": "2026-01-01 00:00:00"},
                ],
                "dataguard_status": [],
            },
        )
    )
    return snapshot


def main() -> int:
    settings = from_env()
    print(f"Inventaire : {settings.inventory_file}")
    print(f"Bases      : {len(settings.databases)}")
    for entry in settings.databases:
        print(
            f"  - {entry.name} env={entry.environment!r} service={entry.service!r} "
            f"tags={list(entry.tags)} user={entry.user!r} defined={entry.defined}"
        )

    snapshot = _sample_snapshot()
    out_dir = settings.output_dir / "selftest"
    payload = {
        "generated_at": "2026-01-01 00:00:00 UTC",
        "inventory": str(settings.inventory_file),
        "databases": [snapshot.to_dict()],
    }

    snapshot_path = save_snapshots([snapshot], settings, out_dir)
    _payload, loaded = load_snapshot_file(snapshot_path)
    assert loaded and loaded[0].name == "DEMO", "round-trip snapshot invalide"
    print(f"Snapshot     : {snapshot_path}")

    written = write_reports(payload, [snapshot], out_dir, ["all"])
    for path in written:
        print(f"Rapport ecrit : {path}")

    markdown = (out_dir / "rapport.md").read_text(encoding="utf-8")
    html = (out_dir / "rapport.html").read_text(encoding="utf-8")
    assert "Rapport standard du parc Oracle" in markdown
    assert "Synthese du parc" in markdown
    assert "dataguard" in markdown.lower()
    assert "DG Sync" in markdown
    assert "<!DOCTYPE html>" in html
    assert "Synthèse du parc" in html
    assert 'id="db-0"' in html, "panneau par base absent"
    assert 'data-target="db-0"' in html, "onglet par base absent"
    assert "Rechercher une base" in html, "filtre de recherche absent"
    assert "Standby DG" in html
    assert "Synchronisés" in html
    assert "Avec GAP" in html

    workbook_path = out_dir / "rapport.xlsx"
    assert workbook_path.is_file(), "classeur Excel absent"
    from openpyxl import load_workbook

    workbook = load_workbook(workbook_path)
    titles = workbook.sheetnames
    assert "Synthese" in titles, f"feuille Synthese absente : {titles}"
    assert "DEMO" in titles, f"feuille par base absente : {titles}"
    # Should have Synthese + DEMO + dataguard section content in DEMO sheet
    print(f"Classeur Excel : {workbook_path} (feuilles: {titles})")

    print("SELFTEST OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Section - Data Guard (configuration, sync status, protection mode)."""

from __future__ import annotations

from ..model import CollectorResult
from ._base import Section


DG_CONFIG_SQL = """
SELECT db_unique_name, dest_role, parent_dbun
FROM v$dataguard_config
WHERE dest_role != 'PRIMARY DATABASE'
ORDER BY db_unique_name
"""

DG_STANDBY_SYNC_SQL = """
SELECT dest_id, db_unique_name, dest_role,
       synchronized, synchronization_status,
       recovery_mode, gap_status,
       TO_CHAR(estimated_startup_time, 'YYYY-MM-DD HH24:MI:SS') AS estimated_startup_time
FROM v$archive_dest_status
WHERE db_unique_name IS NOT NULL
  AND dest_role IN ('PHYSICAL STANDBY', 'LOGICAL STANDBY', 'FAR SYNC STANDBY', 'SNAPSHOT STANDBY')
ORDER BY dest_id
"""

DG_PROTECTION_SQL = """
SELECT protection_mode, protection_level
FROM v$database
"""

DG_STATS_SQL = """
SELECT name, value, unit,
       TO_CHAR(time_computed, 'YYYY-MM-DD HH24:MI:SS') AS time_computed
FROM v$dataguard_stats
ORDER BY name
"""

DG_STATUS_SQL = """
SELECT facility, severity, dest_id, message_num,
       TO_CHAR(timestamp, 'YYYY-MM-DD HH24:MI:SS') AS timestamp,
       message
FROM v$dataguard_status
WHERE severity IN ('Error', 'Warning')
ORDER BY timestamp DESC
FETCH FIRST 20 ROWS ONLY
"""


def collect_dataguard(connection, entry) -> CollectorResult:
    section = Section("dataguard")

    config = section.store(connection, "dataguard_config", DG_CONFIG_SQL, optional=True)

    sync = section.store(connection, "dataguard_standby_sync", DG_STANDBY_SYNC_SQL, optional=True)

    protection = section.first(connection, DG_PROTECTION_SQL, optional=True)
    if protection:
        section.fact("dg_protection_mode", protection.get("protection_mode"))
        section.fact("dg_protection_level", protection.get("protection_level"))

    section.store(connection, "dataguard_stats", DG_STATS_SQL, optional=True)

    section.store(connection, "dataguard_status", DG_STATUS_SQL, optional=True)

    if sync:
        total = len(sync)
        synced = sum(1 for row in sync if str(row.get("synchronized") or "").upper() == "YES")
        gaps = sum(1 for row in sync if str(row.get("gap_status") or "").upper() == "YES")
        section.fact("dg_standby_count", total)
        section.fact("dg_synced_count", synced)
        section.fact("dg_gap_count", gaps)
        section.fact("dg_sync_status", f"{synced}/{total} SYNC" + (f", {gaps} GAP" if gaps else ""))

    return section.result()
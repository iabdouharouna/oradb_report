"""Section - Data Guard (configuration, sync status, protection mode, gap analysis)."""

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
SELECT ads.dest_id,
       ads.db_unique_name,
       dgc.dest_role,
       ads.synchronized,
       ads.gap_status,
       ads.applied_seq#,
       ads.archived_seq#,
       ads.error,
       ads.recovery_mode
FROM v$archive_dest_status ads
JOIN v$dataguard_config dgc ON ads.db_unique_name = dgc.db_unique_name
WHERE ads.db_unique_name IS NOT NULL
  AND dgc.dest_role IN ('PHYSICAL STANDBY', 'LOGICAL STANDBY', 'FAR SYNC STANDBY', 'SNAPSHOT STANDBY')
ORDER BY ads.dest_id
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
SELECT facility, severity, dest_id, message_num, error_code,
       TO_CHAR(timestamp, 'YYYY-MM-DD HH24:MI:SS') AS timestamp,
       message
FROM v$dataguard_status
WHERE severity IN ('Error', 'Warning')
ORDER BY timestamp DESC
FETCH FIRST 20 ROWS ONLY
"""

PRIMARY_SEQ_SQL = """
SELECT MAX(sequence#) AS current_seq
FROM v$archived_log
WHERE resetlogs_id = (SELECT resetlogs_id FROM v$database)
  AND standby_dest = 'NO'
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

    primary_seq = section.first(connection, PRIMARY_SEQ_SQL, optional=True)
    primary_current_seq = primary_seq.get("current_seq") if primary_seq else None

    if sync:
        total = len(sync)
        synced = sum(1 for row in sync if str(row.get("synchronized") or "").upper() == "YES")
        gaps = sum(1 for row in sync if str(row.get("gap_status") or "").upper() == "YES")
        section.fact("dg_standby_count", total)
        section.fact("dg_synced_count", synced)
        section.fact("dg_gap_count", gaps)
        section.fact("dg_sync_status", f"{synced}/{total} SYNC" + (f", {gaps} GAP" if gaps else ""))

        if primary_current_seq is not None:
            for row in sync:
                # Les colonnes Oracle 19c sont en majuscules: APPLIED_SEQ#, ARCHIVED_SEQ#
                applied = row.get("applied_seq#") or row.get("APPLIED_SEQ#")
                archived = row.get("archived_seq#") or row.get("ARCHIVED_SEQ#")
                db_name = row.get("db_unique_name")
                if applied is not None:
                    gap = primary_current_seq - applied
                    if gap < 0:
                        gap = 0
                    section.fact(f"dg_seq_gap_{db_name}", gap)
                if archived is not None:
                    transport_gap = primary_current_seq - archived
                    if transport_gap < 0:
                        transport_gap = 0
                    section.fact(f"dg_transport_gap_{db_name}", transport_gap)

    return section.result()
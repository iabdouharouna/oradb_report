"""Section 4 - Sante et performance (memoire, parametres, attentes, licences)."""

from __future__ import annotations

from ..model import CollectorResult
from ._base import Section

MB = 1048576

PARAMETERS = (
    "'db_name'",
    "'db_unique_name'",
    "'db_block_size'",
    "'compatible'",
    "'memory_target'",
    "'memory_max_target'",
    "'sga_target'",
    "'sga_max_size'",
    "'pga_aggregate_target'",
    "'pga_aggregate_limit'",
    "'processes'",
    "'sessions'",
    "'db_files'",
    "'open_cursors'",
    "'filesystemio_options'",
    "'audit_trail'",
)

SGA_SQL = "SELECT ROUND(SUM(value) / 1048576, 1) AS sga_mb FROM v$sga"

SGA_COMPONENTS_SQL = """
SELECT name, ROUND(bytes / 1048576, 1) AS size_mb, resizeable
FROM v$sgainfo
ORDER BY bytes DESC NULLS LAST
"""

PGA_SQL = """
SELECT name, ROUND(value / 1048576, 1) AS size_mb
FROM v$pgastat
WHERE name IN ('aggregate PGA target parameter', 'total PGA allocated',
               'total PGA inuse', 'aggregate PGA auto target')
ORDER BY name
"""

PARAMETERS_SQL = (
    "SELECT name, value, isdefault, ismodified FROM v$parameter "
    "WHERE name IN (" + ", ".join(PARAMETERS) + ") ORDER BY name"
)

TOP_EVENTS_SQL = """
SELECT event, wait_class, total_waits,
       ROUND(time_waited / 100, 1) AS time_waited_s,
       ROUND(average_wait, 2) AS avg_wait_cs
FROM v$system_event
WHERE wait_class <> 'Idle'
ORDER BY time_waited DESC
FETCH FIRST 10 ROWS ONLY
"""

OPTIONS_SQL = "SELECT parameter, value FROM v$option ORDER BY parameter"

AWR_SQL = """
SELECT COUNT(*) AS snapshot_count,
       TO_CHAR(MAX(end_interval_time), 'YYYY-MM-DD HH24:MI:SS') AS last_snapshot
FROM dba_hist_snapshot
"""


def collect_health(connection, entry) -> CollectorResult:
    section = Section("health")

    sga = section.first(connection, SGA_SQL, optional=True)
    if sga:
        section.fact("sga_mb", sga.get("sga_mb"))
    section.store(connection, "sga_components", SGA_COMPONENTS_SQL, optional=True)

    pga = section.store(connection, "pga_stats", PGA_SQL, optional=True)
    if pga:
        for row in pga:
            if row.get("name") == "total PGA allocated":
                section.fact("pga_allocated_mb", row.get("size_mb"))

    section.store(connection, "parameters", PARAMETERS_SQL)
    section.store(connection, "top_wait_events", TOP_EVENTS_SQL, optional=True)

    options = section.store(connection, "options", OPTIONS_SQL, optional=True)
    if options:
        flags = {str(row.get("parameter")): str(row.get("value")) for row in options}
        section.fact("diagnostics_pack", flags.get("Diagnostics Pack", "?"))
        section.fact("tuning_pack", flags.get("Tuning Pack", "?"))
        section.fact("partitioning", flags.get("Partitioning", "?"))
        section.fact("rac", flags.get("Real Application Clusters", "?"))

    awr = section.first(connection, AWR_SQL, optional=True)
    if awr:
        section.fact("awr_snapshot_count", awr.get("snapshot_count"))
        section.fact("awr_last_snapshot", awr.get("last_snapshot"))

    return section.result()

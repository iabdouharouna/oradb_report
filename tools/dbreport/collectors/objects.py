"""Section 3 - Objets, integrite et volumetrie (invalides, stats, segments, jobs)."""

from __future__ import annotations

from ..model import CollectorResult
from ._base import Section

OBJECT_COUNTS_SQL = """
SELECT object_type, COUNT(*) AS object_count
FROM dba_objects
GROUP BY object_type
ORDER BY object_count DESC
"""

INVALID_COUNT_SQL = (
    "SELECT COUNT(*) AS invalid_count FROM dba_objects WHERE status <> 'VALID'"
)

INVALID_SQL = """
SELECT owner, object_name, object_type, status,
       TO_CHAR(last_ddl_time, 'YYYY-MM-DD HH24:MI:SS') AS last_ddl_time
FROM dba_objects
WHERE status <> 'VALID' AND object_type <> 'SYNONYM'
ORDER BY owner, object_type, object_name
FETCH FIRST 100 ROWS ONLY
"""

STALE_STATS_SQL = """
SELECT owner, table_name, num_rows,
       TO_CHAR(last_analyzed, 'YYYY-MM-DD') AS last_analyzed, stale_stats
FROM dba_tab_statistics
WHERE partition_name IS NULL
  AND (last_analyzed IS NULL OR last_analyzed < SYSDATE - 30 OR stale_stats = 'YES')
ORDER BY last_analyzed NULLS FIRST
FETCH FIRST 50 ROWS ONLY
"""

TOP_SEGMENTS_SQL = """
SELECT owner, segment_name, segment_type, tablespace_name,
       ROUND(bytes / 1048576, 1) AS size_mb
FROM dba_segments
ORDER BY bytes DESC
FETCH FIRST 20 ROWS ONLY
"""

SCHEDULER_ERRORS_SQL = """
SELECT owner, job_name, status,
       TO_CHAR(actual_start_date, 'YYYY-MM-DD HH24:MI:SS') AS start_time, run_duration
FROM dba_scheduler_job_run_details
WHERE status = 'FAILED'
ORDER BY actual_start_date DESC
FETCH FIRST 20 ROWS ONLY
"""


def collect_objects(connection, entry) -> CollectorResult:
    section = Section("objects")

    counts = section.store(connection, "object_counts", OBJECT_COUNTS_SQL)
    if counts:
        section.fact(
            "object_total", sum(int(row.get("object_count") or 0) for row in counts)
        )

    invalid_count = section.first(connection, INVALID_COUNT_SQL)
    if invalid_count:
        section.fact("invalid_total", invalid_count.get("invalid_count"))

    section.store(connection, "invalid_objects", INVALID_SQL)
    section.store(connection, "stale_stats", STALE_STATS_SQL, optional=True)
    section.store(connection, "top_segments", TOP_SEGMENTS_SQL, optional=True)
    section.store(
        connection, "scheduler_failures", SCHEDULER_ERRORS_SQL, optional=True
    )

    return section.result()

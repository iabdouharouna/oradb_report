"""Section 6 - Sauvegarde et reprise (RMAN, Datapump)."""

from __future__ import annotations

from ..model import CollectorResult
from ._base import Section


RMAN_JOBS_SQL = """
SELECT status,
       TO_CHAR(start_time, 'YYYY-MM-DD HH24:MI:SS') AS start_time,
       TO_CHAR(end_time, 'YYYY-MM-DD HH24:MI:SS') AS end_time,
       input_type,
       ROUND(input_bytes / 1048576, 1) AS input_mb,
       ROUND(output_bytes / 1048576, 1) AS output_mb,
       time_taken_display
FROM v$rman_backup_job_details
ORDER BY start_time DESC
FETCH FIRST 10 ROWS ONLY
"""

RMAN_LAST_SQL = """
SELECT TO_CHAR(MAX(end_time), 'YYYY-MM-DD HH24:MI:SS') AS last_end,
       ROUND(SYSDATE - MAX(end_time), 1) AS age_days
FROM v$rman_backup_job_details
WHERE status = 'COMPLETED'
"""

DATAPUMP_SQL = """
SELECT owner_name, job_name, operation, job_mode, state
FROM dba_datapump_jobs
ORDER BY job_name
"""


def collect_backup(connection, entry) -> CollectorResult:
    section = Section("backup")

    section.store(connection, "rman_jobs", RMAN_JOBS_SQL, optional=True)

    last = section.first(connection, RMAN_LAST_SQL, optional=True)
    if last:
        section.fact("last_backup_time", last.get("last_end"))
        section.fact("last_backup_age_days", last.get("age_days"))

    section.store(connection, "datapump_jobs", DATAPUMP_SQL, optional=True)

    return section.result()
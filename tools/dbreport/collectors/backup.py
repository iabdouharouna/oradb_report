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
ARCHIVE_LOG_VOLUME_7D_SQL = """
SELECT TO_CHAR(d.jour,'DD/MM') AS day,
       ROUND(SUM(CASE WHEN d.hh='00' THEN d.gb ELSE 0 END), 2) AS h00,
       ROUND(SUM(CASE WHEN d.hh='01' THEN d.gb ELSE 0 END), 2) AS h01,
       ROUND(SUM(CASE WHEN d.hh='02' THEN d.gb ELSE 0 END), 2) AS h02,
       ROUND(SUM(CASE WHEN d.hh='03' THEN d.gb ELSE 0 END), 2) AS h03,
       ROUND(SUM(CASE WHEN d.hh='04' THEN d.gb ELSE 0 END), 2) AS h04,
       ROUND(SUM(CASE WHEN d.hh='05' THEN d.gb ELSE 0 END), 2) AS h05,
       ROUND(SUM(CASE WHEN d.hh='06' THEN d.gb ELSE 0 END), 2) AS h06,
       ROUND(SUM(CASE WHEN d.hh='07' THEN d.gb ELSE 0 END), 2) AS h07,
       ROUND(SUM(CASE WHEN d.hh='08' THEN d.gb ELSE 0 END), 2) AS h08,
       ROUND(SUM(CASE WHEN d.hh='09' THEN d.gb ELSE 0 END), 2) AS h09,
       ROUND(SUM(CASE WHEN d.hh='10' THEN d.gb ELSE 0 END), 2) AS h10,
       ROUND(SUM(CASE WHEN d.hh='11' THEN d.gb ELSE 0 END), 2) AS h11,
       ROUND(SUM(CASE WHEN d.hh='12' THEN d.gb ELSE 0 END), 2) AS h12,
       ROUND(SUM(CASE WHEN d.hh='13' THEN d.gb ELSE 0 END), 2) AS h13,
       ROUND(SUM(CASE WHEN d.hh='14' THEN d.gb ELSE 0 END), 2) AS h14,
       ROUND(SUM(CASE WHEN d.hh='15' THEN d.gb ELSE 0 END), 2) AS h15,
       ROUND(SUM(CASE WHEN d.hh='16' THEN d.gb ELSE 0 END), 2) AS h16,
       ROUND(SUM(CASE WHEN d.hh='17' THEN d.gb ELSE 0 END), 2) AS h17,
       ROUND(SUM(CASE WHEN d.hh='18' THEN d.gb ELSE 0 END), 2) AS h18,
       ROUND(SUM(CASE WHEN d.hh='19' THEN d.gb ELSE 0 END), 2) AS h19,
       ROUND(SUM(CASE WHEN d.hh='20' THEN d.gb ELSE 0 END), 2) AS h20,
       ROUND(SUM(CASE WHEN d.hh='21' THEN d.gb ELSE 0 END), 2) AS h21,
       ROUND(SUM(CASE WHEN d.hh='22' THEN d.gb ELSE 0 END), 2) AS h22,
       ROUND(SUM(CASE WHEN d.hh='23' THEN d.gb ELSE 0 END), 2) AS h23,
       ROUND(SUM(d.gb), 2) AS total_gb
FROM (
  SELECT TRUNC(a.first_time) jour,
         TO_CHAR(a.first_time,'HH24') hh,
         a.bytes/1024/1024/1024 gb
  FROM (
    SELECT thread#, sequence#, resetlogs_change#,
           MIN(first_time) AS first_time,
           MAX(blocks * block_size) AS bytes
    FROM v$archived_log
    WHERE first_time >= TRUNC(SYSDATE) - 6
      AND standby_dest = 'NO'
    GROUP BY thread#, sequence#, resetlogs_change#
  ) a
) d
GROUP BY d.jour
ORDER BY d.jour DESC
"""


def collect_backup(connection, entry) -> CollectorResult:
    section = Section("backup")

    section.store(connection, "rman_jobs", RMAN_JOBS_SQL, optional=True)

    last = section.first(connection, RMAN_LAST_SQL, optional=True)
    if last:
        section.fact("last_backup_time", last.get("last_end"))
        section.fact("last_backup_age_days", last.get("age_days"))

    section.store(connection, "datapump_jobs", DATAPUMP_SQL, optional=True)

    vol = section.store(connection, "archive_log_volume_7d_hourly_gb", ARCHIVE_LOG_VOLUME_7D_SQL, optional=True)
    if vol:
        section.fact("archivelog_total_7d_gb", round(sum((r.get("total_gb") or 0) for r in vol), 2))
        max_gb = 0
        for r in vol:
            for h in range(24):
                key = f"h{h:02d}"
                v = r.get(key) or 0
                if isinstance(v, (int, float)) and v > max_gb:
                    max_gb = v
        section.fact("archivelog_max_hourly_gb", round(max_gb, 2))

    return section.result()

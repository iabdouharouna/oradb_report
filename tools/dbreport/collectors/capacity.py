"""Section 2 - Capacite et stockage (tablespaces, fichiers, redo, FRA, ASM)."""

from __future__ import annotations

from ..model import CollectorResult
from ._base import Section

MB = 1048576

TABLESPACE_SQL = """
SELECT df.tablespace_name,
       ROUND(df.total_bytes / 1048576, 1) AS total_mb,
       ROUND(NVL(fs.free_bytes, 0) / 1048576, 1) AS free_mb,
       ROUND((df.total_bytes - NVL(fs.free_bytes, 0)) / 1048576, 1) AS used_mb,
       ROUND((df.total_bytes - NVL(fs.free_bytes, 0)) * 100
             / NULLIF(df.total_bytes, 0), 1) AS used_pct,
       df.autoextensible,
       ROUND(df.max_bytes / 1048576, 1) AS max_mb
FROM (SELECT tablespace_name,
             SUM(bytes) AS total_bytes,
             CASE WHEN SUM(CASE WHEN autoextensible = 'YES' THEN 1 ELSE 0 END) > 0
                  THEN 'YES' ELSE 'NO' END AS autoextensible,
             SUM(CASE WHEN autoextensible = 'YES'
                      THEN GREATEST(maxbytes, bytes) ELSE bytes END) AS max_bytes
      FROM dba_data_files
      GROUP BY tablespace_name) df
LEFT JOIN (SELECT tablespace_name, SUM(bytes) AS free_bytes
           FROM dba_free_space GROUP BY tablespace_name) fs
  ON df.tablespace_name = fs.tablespace_name
ORDER BY used_pct DESC NULLS LAST
"""

TEMP_SQL = """
SELECT tablespace_name,
       ROUND(NVL(tablespace_size, 0) / 1048576, 1) AS total_mb,
       ROUND(NVL(free_space, 0) / 1048576, 1) AS free_mb,
       ROUND((NVL(tablespace_size, 0) - NVL(free_space, 0)) * 100
             / NULLIF(tablespace_size, 0), 1) AS used_pct
FROM dba_temp_free_space
ORDER BY tablespace_name
"""

DATAFILE_SQL = """
SELECT tablespace_name, file_name, ROUND(bytes / 1048576, 1) AS size_mb,
       autoextensible, ROUND(maxbytes / 1048576, 1) AS max_mb, status, online_status
FROM dba_data_files
ORDER BY tablespace_name, file_name
"""

TEMPFILE_SQL = """
SELECT tablespace_name, file_name, ROUND(bytes / 1048576, 1) AS size_mb,
       autoextensible, ROUND(maxbytes / 1048576, 1) AS max_mb, status
FROM dba_temp_files
ORDER BY tablespace_name, file_name
"""

REDO_SQL = """
SELECT group#, thread#, ROUND(bytes / 1048576, 1) AS size_mb, members, status, archived
FROM v$log
ORDER BY group#
"""

CONTROLFILE_SQL = "SELECT status, name FROM v$controlfile ORDER BY name"

FRA_SQL = """
SELECT name, ROUND(space_limit / 1048576, 1) AS limit_mb,
       ROUND(space_used / 1048576, 1) AS used_mb,
       ROUND(space_used * 100 / NULLIF(space_limit, 0), 1) AS used_pct
FROM v$recovery_file_dest
"""

FRA_USAGE_SQL = """
SELECT file_type, percent_space_used, number_of_files
FROM v$flash_recovery_area_usage
ORDER BY file_type
"""

ASM_SQL = """
SELECT name, type, state, ROUND(total_mb, 1) AS total_mb,
       ROUND(free_mb, 1) AS free_mb, ROUND(usable_file_mb, 1) AS usable_file_mb
FROM v$asm_diskgroup
ORDER BY name
"""


def collect_capacity(connection, entry) -> CollectorResult:
    section = Section("capacity")

    totals = section.first(
        connection,
        "SELECT (SELECT NVL(SUM(bytes), 0) FROM dba_data_files) AS df_bytes, "
        "(SELECT NVL(SUM(bytes), 0) FROM dba_temp_files) AS tf_bytes, "
        "(SELECT NVL(SUM(bytes), 0) FROM v$log) AS redo_bytes FROM dual",
    )
    if totals:
        df_mb = round((totals.get("df_bytes") or 0) / MB, 1)
        tf_mb = round((totals.get("tf_bytes") or 0) / MB, 1)
        redo_mb = round((totals.get("redo_bytes") or 0) / MB, 1)
        section.fact("datafile_mb", df_mb)
        section.fact("tempfile_mb", tf_mb)
        section.fact("redo_mb", redo_mb)
        section.fact("database_mb", round(df_mb + tf_mb, 1))

    tablespaces = section.store(connection, "tablespaces", TABLESPACE_SQL)
    if tablespaces:
        section.fact("tablespace_count", len(tablespaces))
        section.fact(
            "tablespace_max_pct",
            max((row.get("used_pct") or 0) for row in tablespaces),
        )

    temp = section.store(connection, "temp_tablespaces", TEMP_SQL, optional=True)
    if temp:
        section.fact(
            "temp_max_pct", max((row.get("used_pct") or 0) for row in temp)
        )

    section.store(connection, "datafiles", DATAFILE_SQL)
    section.store(connection, "tempfiles", TEMPFILE_SQL)
    section.store(connection, "redo_logs", REDO_SQL)
    section.store(connection, "controlfiles", CONTROLFILE_SQL)

    fra = section.first(connection, FRA_SQL, optional=True)
    if fra:
        section.fact("fra_used_pct", fra.get("used_pct"))
        section.fact("fra_used_mb", fra.get("used_mb"))
        section.fact("fra_limit_mb", fra.get("limit_mb"))
    section.store(connection, "fra_usage", FRA_USAGE_SQL, optional=True)
    section.store(connection, "asm_diskgroups", ASM_SQL, optional=True)

    return section.result()

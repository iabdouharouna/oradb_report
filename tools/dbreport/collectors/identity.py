"""Section 1 - Identification de la base (version, role, conteneur, demarrage)."""

from __future__ import annotations

from ..model import CollectorResult
from ._base import Section


def collect_identity(connection, entry) -> CollectorResult:
    section = Section("identity")

    database = section.first(
        connection,
        "SELECT name, dbid, open_mode, database_role, log_mode, cdb, force_logging, "
        "platform_name, TO_CHAR(created, 'YYYY-MM-DD') AS created FROM v$database",
    )
    if database:
        for key in (
            "name",
            "dbid",
            "open_mode",
            "database_role",
            "log_mode",
            "cdb",
            "force_logging",
            "platform_name",
            "created",
        ):
            section.fact(key, database.get(key))

    instance = section.first(
        connection,
        "SELECT instance_name, host_name, version, status, database_status, "
        "TO_CHAR(startup_time, 'YYYY-MM-DD HH24:MI:SS') AS startup_time FROM v$instance",
    )
    if instance:
        for key in (
            "instance_name",
            "host_name",
            "version",
            "status",
            "database_status",
            "startup_time",
        ):
            section.fact(key, instance.get(key))

    context = section.first(
        connection,
        "SELECT SYS_CONTEXT('USERENV', 'CON_NAME') AS container, "
        "SYS_CONTEXT('USERENV', 'SERVER_HOST') AS server_host FROM dual",
    )
    if context:
        section.fact("container", context.get("container"))
        section.fact("server_host", context.get("server_host"))

    section.store(
        connection,
        "pdbs",
        "SELECT name, open_mode, restricted FROM v$pdbs ORDER BY con_id",
        optional=True,
    )
    return section.result()

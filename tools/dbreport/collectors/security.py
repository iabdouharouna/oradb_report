"""Section 5 - Securite et conformite (comptes, privileges, profils, audit, patchs)."""

from __future__ import annotations

from ..model import CollectorResult
from ._base import Section

ACCOUNTS_SQL = """
SELECT username, account_status,
       TO_CHAR(expiry_date, 'YYYY-MM-DD HH24:MI:SS') AS expiry_date,
       authentication_type, default_tablespace, profile,
       TO_CHAR(created, 'YYYY-MM-DD') AS created
FROM dba_users
ORDER BY username
"""

ADMIN_ROLES_SQL = """
SELECT grantee, granted_role, admin_option, default_role
FROM dba_role_privs
WHERE granted_role IN ('DBA', 'IMP_FULL_DATABASE', 'EXP_FULL_DATABASE',
                       'SELECT_CATALOG_ROLE', 'SCHEDULER_ADMIN', 'PDB_DBA')
ORDER BY granted_role, grantee
"""

PRIVILEGED_USERS_SQL = "SELECT username, sysdba, sysoper FROM v$pwfile_users ORDER BY username"

SYS_PRIVS_SQL = """
SELECT grantee, privilege, admin_option
FROM dba_sys_privs
WHERE privilege IN ('ALTER DATABASE', 'ALTER SYSTEM', 'CREATE ANY TABLE',
                    'DROP ANY TABLE', 'SELECT ANY TABLE', 'GRANT ANY PRIVILEGE',
                    'BECOME USER', 'CREATE ANY PROCEDURE')
ORDER BY privilege, grantee
"""

PROFILES_SQL = """
SELECT profile, resource_name, limit
FROM dba_profiles
WHERE resource_name IN ('FAILED_LOGIN_ATTEMPTS', 'PASSWORD_LIFE_TIME',
                        'PASSWORD_REUSE_TIME', 'PASSWORD_REUSE_MAX',
                        'PASSWORD_LOCK_TIME', 'PASSWORD_GRACE_TIME',
                        'PASSWORD_VERIFY_FUNCTION')
ORDER BY profile, resource_name
"""

AUDIT_PARAMS_SQL = """
SELECT name, value FROM v$parameter
WHERE name IN ('audit_trail', 'audit_sys_operations')
ORDER BY name
"""

AUDIT_POLICIES_SQL = """
SELECT policy_name, enabled_option, entity_name, success, failure
FROM audit_unified_enabled_policies
ORDER BY policy_name
"""

PATCHES_SQL = """
SELECT TO_CHAR(action_time, 'YYYY-MM-DD') AS action_time, action, status,
       patch_id, description, version
FROM dba_registry_sqlpatch
ORDER BY action_time DESC
FETCH FIRST 20 ROWS ONLY
"""

REGISTRY_SQL = """
SELECT comp_id, comp_name, version, status
FROM dba_registry
WHERE status <> 'VALID'
ORDER BY comp_id
"""


def collect_security(connection, entry) -> CollectorResult:
    section = Section("security")

    accounts = section.store(connection, "accounts", ACCOUNTS_SQL)
    if accounts:
        statuses = [str(row.get("account_status") or "") for row in accounts]
        section.fact("account_total", len(accounts))
        section.fact("account_open", sum(1 for s in statuses if s == "OPEN"))
        section.fact(
            "account_locked", sum(1 for s in statuses if "LOCKED" in s)
        )
        section.fact(
            "account_expired", sum(1 for s in statuses if s.startswith("EXPIRED"))
        )

    section.store(connection, "admin_roles", ADMIN_ROLES_SQL, optional=True)
    section.store(
        connection, "privileged_users", PRIVILEGED_USERS_SQL, optional=True
    )
    section.store(connection, "system_privileges", SYS_PRIVS_SQL, optional=True)
    section.store(connection, "profiles", PROFILES_SQL, optional=True)

    audit = section.store(connection, "audit_parameters", AUDIT_PARAMS_SQL, optional=True)
    if audit:
        for row in audit:
            section.fact(f"param_{row.get('name')}", row.get("value"))
    section.store(
        connection, "audit_policies", AUDIT_POLICIES_SQL, optional=True
    )

    section.store(connection, "patch_history", PATCHES_SQL, optional=True)
    section.store(connection, "invalid_components", REGISTRY_SQL, optional=True)

    return section.result()

"""Acces base de donnees via python-oracledb (mode thin), lecture seule."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

import oracledb

from .config import ConfigError, InventoryEntry, Settings

LOGGER = logging.getLogger("dbreport")


def one_line(exc: BaseException) -> str:
    """Retourne la premiere ligne non vide d'une exception (message ORA-xxxxx)."""

    text = str(exc).strip()
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line
    return text or exc.__class__.__name__


def _auth_mode(role: str | None) -> int | None:
    if not role:
        return None
    attribute = f"AUTH_MODE_{role.strip().upper()}"
    mode = getattr(oracledb, attribute, None)
    if mode is None:
        raise ConfigError(
            f"Role Oracle inconnu : '{role}'. Valeurs possibles : SYSDBA, SYSOPER."
        )
    return mode


def connect(entry: InventoryEntry, settings: Settings) -> oracledb.Connection:
    """Ouvre une connexion en lecture pour une base de l'inventaire."""

    if not entry.user or not entry.dsn:
        raise ConfigError(
            f"Base '{entry.name}' incomplete : renseignez 'user' et 'dsn' "
            f"dans {settings.inventory_file.name}."
        )
    if not entry.password:
        raise ConfigError(
            f"Mot de passe absent pour '{entry.name}'. Definissez {entry.env_hint()} "
            f"(fichier {settings.env_file or '.env'}) ou renseignez-le dans l'inventaire."
        )

    kwargs: dict = {"user": entry.user, "password": entry.password, "dsn": entry.dsn}
    mode = _auth_mode(entry.role)
    if mode is not None:
        kwargs["mode"] = mode

    LOGGER.debug(
        "connexion base=%s user=%s dsn=%s role=%s",
        entry.name,
        entry.user,
        entry.dsn,
        entry.role or "-",
    )
    try:
        connection = oracledb.connect(**kwargs)
    except oracledb.Error as exc:
        raise ConfigError(
            f"Connexion impossible pour '{entry.name}' "
            f"({entry.user}@{entry.dsn}) : {one_line(exc)}"
        ) from exc

    try:
        connection.call_timeout = int(settings.call_timeout * 1000)
    except Exception:  # pragma: no cover - depend du mode/thin
        LOGGER.debug("call_timeout non applique pour '%s'", entry.name)
    return connection


@contextmanager
def session(entry: InventoryEntry, settings: Settings) -> Iterator[oracledb.Connection]:
    """Context manager : connexion + fermeture systematique."""

    connection = connect(entry, settings)
    try:
        yield connection
    finally:
        try:
            connection.close()
        except oracledb.Error:  # pragma: no cover
            pass


def server_info(connection: oracledb.Connection) -> dict[str, str]:
    """Retourne des informations de session (version, utilisateur, schema, conteneur)."""

    info: dict[str, str] = {}
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT version FROM product_component_version "
            "WHERE UPPER(product) LIKE '%DATABASE%' "
            "AND UPPER(product) NOT LIKE '%CLIENT%' "
            "FETCH FIRST 1 ROW ONLY"
        )
        row = cursor.fetchone()
        info["version"] = str(row[0]) if row else "?"

        cursor.execute(
            "SELECT USER, SYS_CONTEXT('USERENV', 'DB_NAME'), "
            "SYS_CONTEXT('USERENV', 'CON_NAME') FROM dual"
        )
        row = cursor.fetchone()
        if row:
            info["user"] = row[0] or ""
            info["db_name"] = row[1] or ""
            info["container"] = row[2] or ""
    return info

"""Utilitaires partages par les collecteurs : execution de requetes et section."""

from __future__ import annotations

import datetime
import decimal
from typing import Any

import oracledb

from ..db import one_line
from ..model import NON_DISPONIBLE, OK, PARTIEL, CollectorResult


def normalize(value: Any) -> Any:
    """Convertit une valeur Oracle en type serialisable JSON (str/int/float/bool/None)."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime.datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, datetime.date):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, decimal.Decimal):
        return float(value)
    return str(value)


def fetch_rows(connection: oracledb.Connection, sql: str, params: dict | None = None):
    """Execute une requete et retourne une liste de dicts (colonnes en minuscules)."""

    with connection.cursor() as cursor:
        cursor.execute(sql, params or {})
        if cursor.description is None:
            return []
        columns = [desc[0].lower() for desc in cursor.description]
        return [
            dict(zip(columns, (normalize(value) for value in row)))
            for row in cursor.fetchall()
        ]


class Section:
    """Accumule les faits et tableaux d'une section, en tolerant les erreurs."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.facts: dict[str, Any] = {}
        self.tables: dict[str, list[dict[str, Any]]] = {}
        self.messages: list[str] = []
        self._required = 0
        self._failed = 0

    def fact(self, key: str, value: Any) -> Any:
        self.facts[key] = value
        return value

    def fetch(
        self,
        connection: oracledb.Connection,
        sql: str,
        params: dict | None = None,
        optional: bool = False,
    ) -> list[dict[str, Any]] | None:
        if not optional:
            self._required += 1
        try:
            return fetch_rows(connection, sql, params)
        except oracledb.Error as exc:
            self.messages.append(one_line(exc))
            if not optional:
                self._failed += 1
            return None

    def store(
        self,
        connection: oracledb.Connection,
        table: str,
        sql: str,
        params: dict | None = None,
        optional: bool = False,
    ) -> list[dict[str, Any]] | None:
        rows = self.fetch(connection, sql, params, optional=optional)
        if rows is not None:
            self.tables[table] = rows
        return rows

    def first(
        self,
        connection: oracledb.Connection,
        sql: str,
        params: dict | None = None,
        optional: bool = False,
    ) -> dict[str, Any] | None:
        rows = self.fetch(connection, sql, params, optional=optional)
        if rows:
            return rows[0]
        return None

    def result(self) -> CollectorResult:
        if self._failed == 0:
            status = OK
        elif self._failed < self._required:
            status = PARTIEL
        else:
            status = NON_DISPONIBLE
        return CollectorResult(
            self.name, status, self.facts, self.tables, self.messages
        )

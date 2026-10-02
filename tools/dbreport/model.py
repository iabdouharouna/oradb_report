"""Modele de donnees du snapshot : resultats par section et snapshot par base."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Statuts possibles d'une section.
OK = "OK"
PARTIEL = "PARTIEL"
NON_DISPONIBLE = "NON_DISPONIBLE"


@dataclass
class CollectorResult:
    """Resultat d'une section de collecte pour une base."""

    section: str
    status: str = OK
    facts: dict[str, Any] = field(default_factory=dict)
    tables: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    messages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "section": self.section,
            "status": self.status,
            "facts": self.facts,
            "tables": self.tables,
            "messages": self.messages,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CollectorResult":
        return cls(
            section=data.get("section", ""),
            status=data.get("status", OK),
            facts=data.get("facts", {}) or {},
            tables=data.get("tables", {}) or {},
            messages=data.get("messages", []) or [],
        )


@dataclass
class DatabaseSnapshot:
    """Snapshot complet d'une base de production."""

    name: str
    dsn: str = ""
    environment: str = ""
    service: str = ""
    tags: list[str] = field(default_factory=list)
    collected_at: str = ""
    ok: bool = True
    error: str = ""
    sections: list[CollectorResult] = field(default_factory=list)

    def section(self, name: str) -> CollectorResult | None:
        for item in self.sections:
            if item.section == name:
                return item
        return None

    def fact(self, section: str, key: str, default: Any = None) -> Any:
        item = self.section(section)
        if item is None:
            return default
        return item.facts.get(key, default)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "dsn": self.dsn,
            "environment": self.environment,
            "service": self.service,
            "tags": self.tags,
            "collected_at": self.collected_at,
            "ok": self.ok,
            "error": self.error,
            "sections": [section.to_dict() for section in self.sections],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DatabaseSnapshot":
        return cls(
            name=data.get("name", ""),
            dsn=data.get("dsn", ""),
            environment=data.get("environment", ""),
            service=data.get("service", ""),
            tags=list(data.get("tags", []) or []),
            collected_at=data.get("collected_at", ""),
            ok=bool(data.get("ok", True)),
            error=data.get("error", ""),
            sections=[CollectorResult.from_dict(item) for item in data.get("sections", [])],
        )

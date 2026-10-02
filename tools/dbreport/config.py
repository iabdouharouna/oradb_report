"""Configuration de l'outillage : variables d'environnement et inventaire du parc."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

try:  # PyYAML est optionnel : un parseur stdlib de repli est fourni.
    import yaml
except ImportError:  # pragma: no cover - selon l'environnement
    yaml = None  # type: ignore[assignment]

DEFAULT_INVENTORY = "databases.yaml"


class ConfigError(RuntimeError):
    """Erreur de configuration (fichier manquant ou entree invalide)."""


@dataclass(frozen=True)
class InventoryEntry:
    """Description d'une base a auditer."""

    name: str
    dsn: str
    user: str
    password: str = ""
    role: str | None = None
    environment: str = ""
    service: str = ""
    tags: tuple[str, ...] = ()

    @property
    def defined(self) -> bool:
        return bool(self.user and self.password and self.dsn)

    def env_hint(self) -> str:
        return f"ORAREPORT_{self.name.upper()}_PASSWORD"

    def has_tag(self, tag: str) -> bool:
        return tag.strip().lower() in {item.lower() for item in self.tags}


@dataclass
class Settings:
    """Configuration complete de l'outil."""

    repo_root: Path
    inventory_file: Path
    output_dir: Path
    databases: list[InventoryEntry] = field(default_factory=list)
    call_timeout: float = 60.0
    env_file: Path | None = None

    def select(
        self,
        names: Sequence[str] | None = None,
        tags: Sequence[str] | None = None,
    ) -> list[InventoryEntry]:
        """Filtre l'inventaire par nom de base et/ou etiquettes (OR)."""

        name_filter = {item.strip().lower() for item in names or [] if item.strip()}
        tag_filter = {item.strip().lower() for item in tags or [] if item.strip()}

        selected: list[InventoryEntry] = []
        for entry in self.databases:
            if name_filter and entry.name.lower() not in name_filter:
                continue
            if tag_filter and not any(entry.has_tag(tag) for tag in tag_filter):
                continue
            selected.append(entry)
        return selected


def _load_dotenv(path: Path) -> None:
    """Charge un fichier .env minimaliste sans ecraser l'environnement reel."""

    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def _env_float(name: str, default: float) -> float:
    raw = _env(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"Valeur numerique invalide pour {name} : {raw!r}") from exc


def _resolve(base: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (base / path)


def _strip_comment(line: str) -> str:
    out: list[str] = []
    quote: str | None = None
    for char in line:
        if quote:
            out.append(char)
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
            out.append(char)
        elif char == "#":
            break
        else:
            out.append(char)
    return "".join(out).rstrip()


def _split_inline_list(text: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    quote: str | None = None
    depth = 0
    for char in text:
        if quote:
            current.append(char)
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
            current.append(char)
        elif char in "[{":
            depth += 1
            current.append(char)
        elif char in "]}":
            depth -= 1
            current.append(char)
        elif char == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if current:
        parts.append("".join(current).strip())
    return [part for part in parts if part]


def _parse_scalar(text: str) -> object:
    text = text.strip()
    if text == "":
        return None
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    lowered = text.lower()
    if lowered in ("true", "yes"):
        return True
    if lowered in ("false", "no"):
        return False
    if lowered in ("null", "~"):
        return None
    if text.startswith("[") and text.endswith("]"):
        return [_parse_scalar(part) for part in _split_inline_list(text[1:-1])]
    if lowered.lstrip("-").isdigit():
        return int(text)
    try:
        return float(text)
    except ValueError:
        return text


def _split_key(text: str) -> tuple[str, str]:
    if ":" not in text:
        raise ConfigError(f"Ligne d'inventaire invalide : {text!r}")
    key, value = text.split(":", 1)
    key = key.strip()
    if not key:
        raise ConfigError(f"Cle manquante sur la ligne : {text!r}")
    return key, value.strip()


def _collect_block(lines: list[str], start: int) -> tuple[list[tuple[int, str]], int]:
    block: list[tuple[int, str]] = []
    index = start
    while index < len(lines):
        line = _strip_comment(lines[index])
        if not line.strip():
            index += 1
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent == 0:
            break
        block.append((indent, line.strip()))
        index += 1
    return block, index


def _parse_block_items(block: list[tuple[int, str]]) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for _indent, content in block:
        if content == "-":
            current = {}
            items.append(current)
        elif content.startswith("- "):
            current = {}
            items.append(current)
            key, value = _split_key(content[2:].strip())
            current[key] = _parse_scalar(value)
        elif current is not None:
            key, value = _split_key(content)
            current[key] = _parse_scalar(value)
    return items


def _simple_yaml_load(text: str) -> dict[str, object]:
    """Parseur stdlib d'un sous-ensemble YAML (mapping de scalaires / listes de mappings)."""

    lines = text.splitlines()
    result: dict[str, object] = {}
    index = 0
    while index < len(lines):
        line = _strip_comment(lines[index])
        if not line.strip():
            index += 1
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent != 0:
            index += 1
            continue
        key, value = _split_key(line.strip())
        if value == "":
            block, index = _collect_block(lines, index + 1)
            result[key] = _parse_block_items(block)
        else:
            result[key] = _parse_scalar(value)
            index += 1
    return result


def _parse_inventory_text(text: str, path: Path) -> dict:
    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"Inventaire JSON invalide ({path}) : {exc}") from exc
        return data if isinstance(data, dict) else {"databases": data}
    if yaml is not None:
        try:
            return yaml.safe_load(text) or {}
        except yaml.YAMLError as exc:
            raise ConfigError(f"Inventaire YAML invalide ({path}) : {exc}") from exc
    return _simple_yaml_load(text)


def load_inventory(path: Path) -> list[InventoryEntry]:
    """Lit et valide le fichier d'inventaire des bases."""

    if not path.is_file():
        raise ConfigError(f"Inventaire introuvable : {path}")

    data = _parse_inventory_text(path.read_text(encoding="utf-8"), path)
    if not isinstance(data, dict):
        raise ConfigError(f"Inventaire invalide (mapping attendu) : {path}")

    raw_entries = data.get("databases")
    if not isinstance(raw_entries, list) or not raw_entries:
        raise ConfigError(f"Inventaire vide ou cle 'databases' manquante : {path}")

    entries: list[InventoryEntry] = []
    seen: set[str] = set()
    for index, item in enumerate(raw_entries, start=1):
        if not isinstance(item, dict):
            raise ConfigError(f"Entree #{index} invalide (mapping attendu) : {path}")

        name = str(item.get("name") or "").strip()
        if not name:
            raise ConfigError(f"Entree #{index} sans champ 'name' : {path}")
        if name.lower() in seen:
            raise ConfigError(f"Nom de base duplique : {name}")
        seen.add(name.lower())

        password = str(item.get("password") or "").strip()
        if not password:
            password = _env(f"ORAREPORT_{name.upper()}_PASSWORD", "") or ""

        role = item.get("role")
        raw_tags = item.get("tags") or []
        if not isinstance(raw_tags, list):
            raw_tags = [raw_tags]

        entries.append(
            InventoryEntry(
                name=name,
                dsn=str(item.get("dsn") or "").strip(),
                user=str(item.get("user") or "").strip(),
                password=password,
                role=str(role).strip() if role else None,
                environment=str(item.get("environment") or "").strip(),
                service=str(item.get("service") or "").strip(),
                tags=tuple(str(tag).strip() for tag in raw_tags if str(tag).strip()),
            )
        )
    return entries


def from_env(
    repo_root: Path | None = None,
    env_file: str | None = None,
    inventory_file: str | None = None,
) -> Settings:
    """Construit la configuration a partir de l'environnement, du .env et de l'inventaire."""

    root = (repo_root or Path(__file__).resolve().parents[2]).resolve()

    explicit = env_file or os.environ.get("ORAREPORT_ENV_FILE")
    dotenv_path = Path(explicit).expanduser() if explicit else root / ".env"
    if not dotenv_path.is_absolute():
        dotenv_path = root / dotenv_path
    _load_dotenv(dotenv_path)

    inventory_value = inventory_file or _env("ORAREPORT_INVENTORY") or DEFAULT_INVENTORY
    inventory_path = _resolve(root, inventory_value)

    output_value = _env("ORAREPORT_OUTPUT_DIR") or "output"
    output_path = _resolve(root, output_value)

    return Settings(
        repo_root=root,
        inventory_file=inventory_path,
        output_dir=output_path.resolve(),
        databases=load_inventory(inventory_path),
        call_timeout=_env_float("ORAREPORT_CALL_TIMEOUT", 60.0),
        env_file=dotenv_path if dotenv_path.is_file() else None,
    )

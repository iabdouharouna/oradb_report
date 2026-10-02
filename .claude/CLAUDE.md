# dbreport — Claude Code Instructions

## Project Context

This is **dbreport**: a CLI tool generating standardized Oracle database reports. Read-only collection via `python-oracledb` thin mode.

## Key Files to Know

| File | Purpose |
|------|---------|
| `setup_project.py` | Bootstrap (venv, deps) + CLI entry point |
| `tools/dbreport/cli.py` | Commands: check/collect/report/run |
| `tools/dbreport/config.py` | Inventory parsing (stdlib YAML), env vars |
| `tools/dbreport/collect.py` | Orchestration, snapshot persistence |
| `tools/dbreport/model.py` | Data models (Snapshot, CollectorResult) |
| `tools/dbreport/report.py` | Markdown/HTML/CSV/Excel rendering |
| `tools/dbreport/collectors/*.py` | 6 report sections |
| `tools/dbreport/templates/report.html.j2` | HTML template |
| `databases.yaml` | DB inventory |
| `.env` | Secrets (gitignored) |

## Common Commands

```bash
# Run any command (auto-activates venv)
python setup_project.py check
python setup_project.py collect --tags prod
python setup_project.py report --format html
python setup_project.py run --names ORCL_PROD

# Self-test (no DB)
python tools/selftest.py
```

## Code Conventions

- **No comments** unless asked
- Type hints everywhere (`from __future__ import annotations`)
- Dataclasses for models
- Stdlib-first (YAML parser fallback, no external deps for config)
- Read-only Oracle queries (SELECT only)
- Error isolation: one DB failure ≠ total failure
- `logging` module for output (not print)

## Adding a Collector Section

1. Create `tools/dbreport/collectors/new_section.py`:
   ```python
   from ..model import CollectorResult
   from ._base import Section
   
   def collect_new_section(connection, entry) -> CollectorResult:
       section = Section("new_section")
       # ... queries via section.fetch/store/first ...
       return section.result()
   ```

2. Register in `tools/dbreport/collectors/__init__.py`:
   ```python
   from .new_section import collect_new_section
   COLLECTORS = (
       ...,
       ("new_section", collect_new_section),
   )
   ```

3. Section name auto-added to `SECTION_NAMES`.

## Modifying Reports

- **HTML**: Edit `tools/dbreport/templates/report.html.j2` (Jinja2, embedded CSS/JS)
- **Markdown**: `render_markdown()` in `report.py`
- **Excel**: `write_workbook()` in `report.py` (openpyxl)
- **CSV**: `write_csv()` in `report.py`

## Configuration Patterns

- Inventory: `databases.yaml` (or JSON) — parsed by stdlib fallback or PyYAML
- Passwords: `ORAREPORT_<NAME>_PASSWORD` in `.env` (never in YAML)
- Settings via `config.from_env()` → `Settings` dataclass
- CLI args → `argparse` in `cli.py`

## Testing

```bash
# Self-test validates inventory, model, all report formats
python tools/selftest.py
```

## Things to Avoid

- ❌ No DDL/DML in collectors (read-only)
- ❌ No hardcoded passwords
- ❌ No print() for logging (use `logging.getLogger("dbreport")`)
- ❌ No external deps in config.py (stdlib only)
- ❌ Don't commit `.env` or `output/`
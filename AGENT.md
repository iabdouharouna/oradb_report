# dbreport — Agent Documentation

## Project Overview

**dbreport** is a CLI tool that generates standardized "360°" reports for Oracle production databases. It performs read-only collection (SELECT only) using `python-oracledb` in thin mode — no SQL*Plus dependency.

## Quick Start

```bash
# Setup (auto-creates venv, installs deps)
python setup_project.py check      # Test connections
python setup_project.py collect    # Create timestamped snapshot
python setup_project.py report     # Generate reports (md/html/csv/xlsx)
python setup_project.py run        # Collect + report in one command

# With filters
python setup_project.py collect --tags prod --sections identity,capacity
python setup_project.py report --format html
python setup_project.py run --names ORCL_PROD
```

## Architecture

```
oracle/
├── setup_project.py            # Bootstrap (venv + deps) & CLI entry point
├── requirements.txt            # oracledb, Jinja2, openpyxl (PyYAML optional)
├── databases.yaml              # Inventory of databases to audit
├── .env.example                # Config template (copy to .env)
├── .env                        # Actual config (gitignored)
├── output/                     # Timestamped snapshots & reports (gitignored)
└── tools/dbreport/
    ├── cli.py                  # Commands: check/collect/report/run
    ├── config.py               # Inventory + env vars (stdlib YAML parser)
    ├── db.py                   # oracledb thin connection, session info
    ├── collect.py              # Orchestration + snapshot persistence
    ├── model.py                # Snapshot & section result models
    ├── report.py               # Markdown/HTML/CSV/Excel rendering
    ├── logging_utils.py        # Console + file logging
    ├── collectors/             # One module per section
    │   ├── _base.py            # Shared query execution & Section class
    │   ├── identity.py         # DB/instance info, version, role, PDBs
    │   ├── capacity.py         # Tablespaces, datafiles, redo, FRA, ASM
    │   ├── objects.py          # Object counts, invalid, stats, top segments
    │   ├── health.py           # SGA/PGA, params, waits, licenses, AWR
    │   ├── security.py         # Accounts, roles, profiles, audit, patches
    │   ├── backup.py           # RMAN jobs, Datapump jobs
    │   └── dataguard.py        # Data Guard config, sync, protection mode
    └── templates/report.html.j2  # Self-contained HTML (tabs + search)
```

## Configuration

### `databases.yaml` — Inventory
```yaml
databases:
  - name: ORCL_PROD           # Logical identifier
    dsn: orcl-prod.intra:1521/ORCLPDB1  # Easy Connect
    user: DBA_REPORT          # Read-only account (prefer SELECT_CATALOG_ROLE)
    environment: prod         # Tag: prod, recette, etc.
    service: primary          # primary | standby
    tags: [erp, sao-paulo]    # Free-form filters
```

### `.env` — Secrets & Options
```bash
# Passwords: ORAREPORT_<NAME>_PASSWORD (uppercase name)
ORAREPORT_FREE_PASSWORD=secret

# Optional overrides
ORAREPORT_INVENTORY=databases.yaml
ORAREPORT_OUTPUT_DIR=output
ORAREPORT_CALL_TIMEOUT=60
ORAREPORT_SECTIONS=identity,capacity,objects,health,security,backup
```

## Report Sections

| Section | Content |
|---------|---------|
| `identity` | Name/DBID, instance, host, version/edition, role (primary/standby), archive mode, CDB/PDB, startup |
| `capacity` | DB size, tablespaces (used/free/%/autoextend), datafiles/tempfiles, redo logs, control files, FRA, ASM groups |
| `objects` | Counts by type, invalid objects, stale stats, top segments, failed DBMS_SCHEDULER jobs |
| `health` | SGA/PGA, key params, top waits, licenses (v$option), AWR availability |
| `security` | Accounts (open/locked/expired), admin roles, privileged users, profiles, audit, patch history |
| `backup` | RMAN jobs & last backup age, Datapump jobs |
| `dataguard` | DG config (v$dataguard_config), per-standby sync (v$archive_dest_status), protection mode, stats (apply/transport lag), alerts |

## Output Structure

Each run creates `output/<YYYYMMDDThhmmssZ>/`:
- `snapshot.json` — Normalized raw data (reusable, comparable across runs)
- `rapport.md` — Readable report (fleet summary + per-DB detail)
- `rapport.html` — Standalone HTML: tabbed dashboard (Summary + per-DB), KPI cards, status badges, DB search, navigation from summary
- `rapport.xlsx` — Workbook: "Synthese" sheet + **one dedicated sheet per DB** (facts, tables, messages per section)
- `csv/` — One file per DB/section/table + `*__facts.csv`

Section statuses: `OK`, `PARTIEL` (partial privileges/objects), `NON_DISPONIBLE` (no queries succeeded).

## Key Behaviors

- **Read-only**: Only SELECT statements executed
- **Failure isolation**: Unreachable DB or missing privileges don't stop other DBs; errors logged, report still produced
- **Privilege detection**: Optional queries isolated; ORA-00942/ORA-01031 logged without breaking section
- **Exit codes**: `0` success, `1` functional failure (all DBs failed), `2` config/usage error
- **No secrets in git**: `.env` and `output/` gitignored; passwords never displayed

## Development

```bash
# Run self-test (no DB connection needed)
python tools/selftest.py

# Install deps manually (if not using setup_project.py)
pip install -r requirements.txt

# Lint/typecheck (if configured)
# No lint configured by default — add ruff/mypy as needed
```

## Common Tasks

### Add a new database
1. Add entry to `databases.yaml`
2. Set password in `.env`: `ORAREPORT_<NAME>_PASSWORD=...`
3. Run `python setup_project.py check` to verify

### Add a new collector section
1. Create `tools/dbreport/collectors/new_section.py` with `collect_new_section(connection, entry)`
2. Register in `tools/dbreport/collectors/__init__.py`:
   ```python
   from .new_section import collect_new_section
   COLLECTORS = (
       ..., 
       ("new_section", collect_new_section),
   )
   ```
3. Update `SECTION_NAMES` auto-derived from `COLLECTORS`

### Modify HTML report
Edit `tools/dbreport/templates/report.html.j2` (Jinja2 + embedded CSS/JS).

### Modify Excel output
Edit `write_workbook()` and helpers in `tools/dbreport/report.py`.

## Limitations

- AWR/ASH sections require Diagnostics Pack; falls back to V$ only
- Temporary tablespaces via `DBA_TEMP_FREE_SPACE`
- Thin mode may not support all external auth; SYSDBA may need thick mode

## Dependencies

- Python ≥ 3.11
- `oracledb>=2.0,<27` (thin mode)
- `Jinja2>=3.1`
- `openpyxl>=3.1`
- `PyYAML>=6.0` (optional — stdlib fallback included)
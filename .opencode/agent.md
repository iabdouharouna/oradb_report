# dbreport — opencode Agent Configuration

## Project Overview

**dbreport** generates standardized Oracle database reports (read-only, `python-oracledb` thin mode).

## Key Commands

```bash
python setup_project.py check      # Test connections
python setup_project.py collect    # Create snapshot
python setup_project.py report     # Generate reports
python setup_project.py run        # Collect + report
python tools/selftest.py           # Self-test (no DB)
```

## File Structure

```
oracle/
├── setup_project.py          # Bootstrap + CLI entry
├── databases.yaml            # DB inventory
├── .env                      # Secrets (gitignored)
├── output/                   # Snapshots + reports (gitignored)
└── tools/dbreport/
    ├── cli.py                # Commands
    ├── config.py             # Inventory + env
    ├── db.py                 # oracledb thin connection
    ├── collect.py            # Orchestration
    ├── model.py              # Data models
    ├── report.py             # Rendering (md/html/csv/xlsx)
    ├── collectors/           # 6 sections
    │   ├── _base.py          # Shared utilities
    │   ├── identity.py
    │   ├── capacity.py
    │   ├── objects.py
    │   ├── health.py
    │   ├── security.py
    │   └── backup.py
    └── templates/report.html.j2
```

## Development Notes

- **No comments** unless requested
- Type hints + dataclasses
- Stdlib YAML parser (PyYAML optional)
- Read-only SELECT queries only
- Error isolation per database
- Logging via `logging.getLogger("dbreport")`
- Exit codes: 0=success, 1=all failed, 2=config error

## Adding Collector Section

1. Create `tools/dbreport/collectors/new_section.py`
2. Register in `tools/dbreport/collectors/__init__.py`
3. Auto-added to `SECTION_NAMES`

## Report Customization

- HTML: `tools/dbreport/templates/report.html.j2`
- Markdown/Excel/CSV: `tools/dbreport/report.py`

## Configuration

- Inventory: `databases.yaml` (or JSON)
- Passwords: `ORAREPORT_<NAME>_PASSWORD` in `.env`
- Settings: `config.from_env()` → `Settings` dataclass
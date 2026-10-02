"""Interface en ligne de commande de l'outillage dbreport."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .collect import (
    collect_all,
    latest_snapshot_file,
    load_snapshot_file,
    new_snapshot_dir,
    resolve_sections,
    save_snapshots,
)
from .config import ConfigError, from_env
from .db import one_line, server_info, session
from .logging_utils import setup_logging
from .report import write_reports

PROG = "setup_project.py"
DEFAULT_FORMATS = "all"
DESCRIPTION = "Rapport standard des bases Oracle de production (collecte en lecture seule)."


def _reconfigure_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:  # pragma: no cover - selon l'environnement
            pass


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description=DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemples :\n"
            f"  python {PROG} check\n"
            f"  python {PROG} collect --tags prod\n"
            f"  python {PROG} report --format all\n"
            f"  python {PROG} run --names ORCL_PROD\n"
        ),
    )
    parser.add_argument("--version", action="version", version=f"dbreport {__version__}")
    parser.add_argument("--env-file", help="fichier .env a charger")
    parser.add_argument("--inventory", help="fichier d'inventaire (defaut : databases.yaml)")
    parser.add_argument(
        "-v", "--verbose", action="count", default=0,
        help="verbosite (-v : debug, -vv : debug + journal fichier)",
    )

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--names", help="bases ciblees (noms separes par des virgules)")
    common.add_argument("--tags", help="filtre par etiquettes (separees par des virgules)")
    common.add_argument("--sections", help="sections a collecter (separees par des virgules)")
    common.add_argument("--dry-run", action="store_true", help="affiche les actions sans interroger les bases")

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="teste les connexions du parc", parents=[common])
    sub.add_parser("collect", help="collecte un snapshot du parc", parents=[common])

    report = sub.add_parser("report", help="genere les rapports depuis un snapshot", parents=[common])
    report.add_argument("--snapshot", help="fichier snapshot.json (defaut : le plus recent)")
    report.add_argument(
        "--format", default=DEFAULT_FORMATS, help="md|html|csv|xlsx|all (defaut : all)"
    )

    run = sub.add_parser("run", help="collecte puis genere les rapports", parents=[common])
    run.add_argument("--snapshot", help="fichier snapshot.json (defaut : le plus recent)")
    run.add_argument(
        "--format", default=DEFAULT_FORMATS, help="md|html|csv|xlsx|all (defaut : all)"
    )
    return parser


def _split(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _select(settings, args):
    return settings.select(names=_split(getattr(args, "names", None)), tags=_split(getattr(args, "tags", None)))


def _cmd_check(args, settings) -> int:
    targets = _select(settings, args)
    if not targets:
        print("Aucune base selectionnee.")
        return 0
    failures = 0
    for entry in targets:
        if not entry.defined:
            print(f"{entry.name:<22} NON CONFIGURE  ({entry.env_hint()})")
            failures += 1
            continue
        try:
            with session(entry, settings) as connection:
                info = server_info(connection)
            print(
                f"{entry.name:<22} OK   "
                f"{info.get('user')}@{info.get('db_name')}/{info.get('container')} "
                f"(Oracle {info.get('version')})"
            )
        except ConfigError as exc:
            print(f"{entry.name:<22} ECHEC  {one_line(exc)}")
            failures += 1
    return 1 if failures == len(targets) else 0


def _cmd_collect(args, settings) -> int:
    try:
        sections = resolve_sections(args.sections)
    except ValueError as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 2

    targets = _select(settings, args)
    if args.dry_run:
        for entry in targets:
            print(f"[dry-run] {entry.name} ({entry.dsn}) sections={sections or 'toutes'}")
        return 0

    snapshots = collect_all(
        settings,
        names=_split(args.names),
        tags=_split(args.tags),
        sections=sections,
    )
    directory = new_snapshot_dir(settings)
    path = save_snapshots(snapshots, settings, directory)
    ok = sum(1 for snapshot in snapshots if snapshot.ok)
    print(f"Snapshot ecrit : {path}")
    print(f"Bases collectees : {ok}/{len(snapshots)}")
    return 0 if ok else 1


def _load_for_report(args, settings) -> tuple[Path | None, dict | None, list | None]:
    snapshot_arg = getattr(args, "snapshot", None)
    if snapshot_arg:
        path = Path(snapshot_arg)
        if not path.is_absolute():
            path = settings.repo_root / path
    else:
        path = latest_snapshot_file(settings)
    if path is None or not path.is_file():
        print("Aucun snapshot trouve. Lancez 'collect' au prealable.", file=sys.stderr)
        return None, None, None
    payload, snapshots = load_snapshot_file(path)
    return path, payload, snapshots


def _cmd_report(args, settings) -> int:
    path, payload, snapshots = _load_for_report(args, settings)
    if path is None:
        return 2
    formats = _split(getattr(args, "format", None)) or [DEFAULT_FORMATS]
    written = write_reports(payload, snapshots, path.parent, formats)
    for item in written:
        print(f"Rapport ecrit : {item}")
    return 0


def _cmd_run(args, settings) -> int:
    if getattr(args, "dry_run", False):
        return _cmd_collect(args, settings)
    code = _cmd_collect(args, settings)
    if code > 1:
        return code
    return _cmd_report(args, settings)


_HANDLERS = {
    "check": _cmd_check,
    "collect": _cmd_collect,
    "report": _cmd_report,
    "run": _cmd_run,
}


def main(argv: list[str] | None = None) -> int:
    _reconfigure_streams()
    parser = _build_parser()
    args = parser.parse_args(argv)
    setup_logging(args.verbose)

    try:
        settings = from_env(env_file=args.env_file, inventory_file=args.inventory)
    except ConfigError as exc:
        print(f"Erreur de configuration : {exc}", file=sys.stderr)
        return 2

    handler = _HANDLERS[args.command]
    try:
        return handler(args, settings)
    except ConfigError as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:  # pragma: no cover
        print("Interrompu.", file=sys.stderr)
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

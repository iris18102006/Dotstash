"""Command line interface."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, core

COLORS = {"synced": "32", "modified": "33", "no-home": "31", "no-backup": "36"}
LABELS = {"synced": "synced", "modified": "modified", "no-home": "missing in home", "no-backup": "not backed up"}


def paint(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if sys.stdout.isatty() else text


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dotstash", description="Back up and restore your dotfiles.")
    p.add_argument("-V", "--version", action="version", version=f"dotstash {__version__}")
    p.add_argument("--vault", type=Path, default=None, help="vault folder (default: ~/dotstash-vault or $DOTSTASH_VAULT)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="create a new vault")
    a = sub.add_parser("add", help="start tracking files or folders")
    a.add_argument("paths", nargs="+")
    a.add_argument("--force", action="store_true", help="allow paths that look like secrets")
    r = sub.add_parser("remove", help="stop tracking files or folders")
    r.add_argument("paths", nargs="+")
    sub.add_parser("list", help="show tracked files")
    sub.add_parser("status", help="compare your home folder with the vault")
    for name, text in (("backup", "copy tracked files from home into the vault"),
                       ("restore", "copy tracked files from the vault into home")):
        s = sub.add_parser(name, help=text)
        s.add_argument("-n", "--dry-run", action="store_true", help="show what would happen")
    return p


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    vault = (args.vault or core.default_vault()).expanduser()
    try:
        if args.cmd == "init":
            core.init_vault(vault)
            print(f"created vault at {vault}")
            print("tip: cd there and run `git init` to push it to GitHub")
        elif args.cmd == "add":
            for rel in core.add(vault, args.paths, args.force):
                print(f"tracking ~/{rel}")
        elif args.cmd == "remove":
            core.remove(vault, args.paths)
            print("removed")
        elif args.cmd == "list":
            files = core.load(vault)
            print("\n".join(f"~/{f}" for f in files) if files else "nothing tracked yet. Try: dotstash add ~/.bashrc")
        elif args.cmd == "status":
            files = core.load(vault)
            for rel in files:
                s = core.state(rel, vault)
                print(f"{paint(LABELS[s].ljust(16), COLORS[s])} ~/{rel}")
            if not files:
                print("nothing tracked yet")
        else:
            fn = core.backup if args.cmd == "backup" else core.restore
            results = fn(vault, args.dry_run)
            for rel, res in results:
                print(f"{res.ljust(34)} ~/{rel}")
            if args.dry_run:
                print("(dry run, nothing was changed)")
    except core.DotstashError as e:
        print(f"dotstash: {e}", file=sys.stderr)
        return 1
    return 0


def main() -> None:
    sys.exit(run())

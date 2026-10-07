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
    ig = sub.add_parser("ignore", help="never back up files matching a pattern, like 'fish_variables' or '*.key'")
    ig.add_argument("patterns", nargs="*")
    ig.add_argument("--list", action="store_true", dest="show", help="show the ignore list")
    ig.add_argument("--remove", action="store_true", help="remove the patterns from the ignore list")
    sub.add_parser("list", help="show tracked files")
    sub.add_parser("status", help="compare your home folder with the vault")
    d = sub.add_parser("diff", help="show line by line what backup would change")
    d.add_argument("paths", nargs="*", help="only these tracked paths")
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
        elif args.cmd == "diff":
            changes = core.diff(vault, args.paths)
            for _, text in changes:
                for line in text.splitlines():
                    code = "32" if line.startswith("+") and not line.startswith("+++") else \
                           "31" if line.startswith("-") and not line.startswith("---") else \
                           "36" if line.startswith("@@") else "0"
                    print(paint(line, code))
            if not changes:
                print("no differences")
        elif args.cmd == "ignore":
            if args.show or not args.patterns:
                print("built in: " + ", ".join(core.DEFAULT_IGNORE))
                mine = core.patterns(vault)[len(core.DEFAULT_IGNORE):]
                print("yours:    " + (", ".join(mine) if mine else "(none)"))
            elif args.remove:
                core.drop_ignore(vault, args.patterns)
                print("removed from ignore list")
            else:
                for rel in core.add_ignore(vault, args.patterns):
                    print(f"deleted from vault: {rel}")
                print("ignoring: " + ", ".join(args.patterns))
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

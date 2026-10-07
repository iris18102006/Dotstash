"""Core logic: manifest handling, copying, and comparing."""
from __future__ import annotations

import difflib
import filecmp
import fnmatch
import json
import os
import shutil
from pathlib import Path

MANIFEST = "dotstash.json"
# Never copied. fish_variables is here because `set -Ux` stores exported
# variables (often API keys) in it.
DEFAULT_IGNORE = [".git", "__pycache__", "fish_variables", "*.dotstash.bak"]
# Paths that usually hold secrets. Refused unless --force is passed.
SENSITIVE = (".ssh", ".gnupg", ".aws", ".password-store", ".netrc")


class DotstashError(Exception):
    """Anything the user can fix, shown without a traceback."""


def home() -> Path:
    return Path(os.environ.get("HOME", str(Path.home()))).resolve()


def default_vault() -> Path:
    return Path(os.environ.get("DOTSTASH_VAULT", "~/dotstash-vault")).expanduser()


def rel_to_home(path: str | Path) -> str:
    """Turn any path into a string relative to $HOME, or fail."""
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = Path.cwd() / p
    p = Path(os.path.normpath(p))
    try:
        return p.relative_to(home()).as_posix()
    except ValueError:
        raise DotstashError(f"{path} is not inside your home folder") from None


def is_sensitive(rel: str) -> bool:
    return rel.split("/")[0] in SENSITIVE or Path(rel).name.startswith("id_")


# ---------- manifest ----------
def init_vault(vault: Path) -> None:
    vault.mkdir(parents=True, exist_ok=True)
    mf = vault / MANIFEST
    if mf.exists():
        raise DotstashError(f"{vault} is already a vault")
    mf.write_text(json.dumps({"files": []}, indent=2) + "\n")


def _read(vault: Path) -> dict:
    mf = vault / MANIFEST
    if not mf.exists():
        raise DotstashError(f"no vault at {vault}. Run: dotstash init")
    try:
        data = json.loads(mf.read_text())
        data["files"] = list(data["files"])
        data["ignore"] = list(data.get("ignore", []))
        return data
    except (ValueError, KeyError) as e:
        raise DotstashError(f"{mf} is broken: {e}") from None


def _write(vault: Path, data: dict) -> None:
    out = {"files": sorted(data["files"]), "ignore": sorted(data["ignore"])}
    (vault / MANIFEST).write_text(json.dumps(out, indent=2) + "\n")


def load(vault: Path) -> list[str]:
    return _read(vault)["files"]


def save(vault: Path, files: list[str]) -> None:
    data = _read(vault)
    data["files"] = files
    _write(vault, data)


def patterns(vault: Path) -> list[str]:
    """Built-in ignore patterns plus the ones you added."""
    return DEFAULT_IGNORE + _read(vault)["ignore"]


def ignored(name: str, pats: list[str]) -> bool:
    return any(fnmatch.fnmatch(name, p) for p in pats)


def add_ignore(vault: Path, pats: list[str]) -> list[str]:
    """Add patterns, and delete anything they match from the vault."""
    data = _read(vault)
    for p in pats:
        if p not in data["ignore"] and p not in DEFAULT_IGNORE:
            data["ignore"].append(p)
    _write(vault, data)
    removed = []
    allp = DEFAULT_IGNORE + data["ignore"]
    root = vault / "files"
    for dirpath, dirs, names in os.walk(root, topdown=True):
        for n in list(dirs) + names:
            if ignored(n, allp):
                t = Path(dirpath) / n
                removed.append(t.relative_to(root).as_posix())
                shutil.rmtree(t) if t.is_dir() else t.unlink()
                if n in dirs:
                    dirs.remove(n)
    return removed


def drop_ignore(vault: Path, pats: list[str]) -> None:
    data = _read(vault)
    for p in pats:
        if p not in data["ignore"]:
            raise DotstashError(f"{p} is not in your ignore list")
        data["ignore"].remove(p)
    _write(vault, data)


# ---------- copying ----------
def _tree(p: Path, pats: list[str]) -> dict[str, Path]:
    if p.is_file() or p.is_symlink():
        return {"": p}
    out: dict[str, Path] = {}
    for root, dirs, names in os.walk(p):
        dirs[:] = [d for d in dirs if not ignored(d, pats)]
        for n in names:
            if not ignored(n, pats):
                f = Path(root) / n
                out[f.relative_to(p).as_posix()] = f
    return out


def copy(src: Path, dst: Path, pats: list[str]) -> None:
    """Mirror src onto dst (dst is replaced). Ignored names are skipped."""
    if dst.is_dir() and not dst.is_symlink():
        shutil.rmtree(dst)
    elif dst.exists() or dst.is_symlink():
        dst.unlink()
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst, symlinks=True,
                        ignore=lambda d, names: {n for n in names if ignored(n, pats)})
    else:
        shutil.copy2(src, dst, follow_symlinks=False)


def state(rel: str, vault: Path) -> str:
    """One of: synced, modified, no-home, no-backup."""
    h, v = home() / rel, vault / "files" / rel
    if not h.exists():
        return "no-home"
    if not v.exists():
        return "no-backup"
    pats = patterns(vault)
    a, b = _tree(h, pats), _tree(v, pats)
    if a.keys() != b.keys():
        return "modified"
    for k in a:
        if not filecmp.cmp(a[k], b[k], shallow=False):
            return "modified"
    return "synced"


# ---------- operations ----------
def add(vault: Path, paths: list[str], force: bool = False) -> list[str]:
    files = load(vault)
    added = []
    for raw in paths:
        rel = rel_to_home(raw)
        if not (home() / rel).exists():
            raise DotstashError(f"{raw} does not exist")
        if is_sensitive(rel) and not force:
            raise DotstashError(f"{rel} looks like a secret. Use --force if you really mean it")
        if rel not in files:
            files.append(rel)
            added.append(rel)
        copy(home() / rel, vault / "files" / rel, patterns(vault))
    save(vault, files)
    return added


def remove(vault: Path, paths: list[str]) -> None:
    files = load(vault)
    for raw in paths:
        rel = rel_to_home(raw)
        if rel not in files:
            raise DotstashError(f"{rel} is not tracked")
        files.remove(rel)
        target = vault / "files" / rel
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
    save(vault, files)


def backup(vault: Path, dry: bool = False) -> list[tuple[str, str]]:
    """Copy tracked files from $HOME into the vault. Returns (rel, result)."""
    out = []
    for rel in load(vault):
        s = state(rel, vault)
        if s == "no-home":
            out.append((rel, "skipped (missing in home)"))
        elif s == "synced":
            out.append((rel, "unchanged"))
        else:
            if not dry:
                copy(home() / rel, vault / "files" / rel, patterns(vault))
            out.append((rel, "backed up"))
    return out


def _put(src: Path, dst: Path, dry: bool) -> str | None:
    """Put one file in place. An existing different file is kept as .dotstash.bak.
    Returns a note, or None when nothing needed doing."""
    if dst.is_file() and not dst.is_symlink() and filecmp.cmp(src, dst, shallow=False):
        return None
    note = "restored"
    if dst.exists() or dst.is_symlink():
        bak = dst.with_name(dst.name + ".dotstash.bak")
        note = f"restored (old copy saved as {bak.name})"
        if not dry:
            if bak.exists() or bak.is_symlink():
                shutil.rmtree(bak) if bak.is_dir() else bak.unlink()
            dst.rename(bak)
    if not dry:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst, follow_symlinks=False)
    return note


def restore(vault: Path, dry: bool = False) -> list[tuple[str, str]]:
    """Copy tracked files from the vault into $HOME. File by file: anything
    that differs is renamed to <name>.dotstash.bak first, and files that are
    only in your home folder (like ignored ones) are left alone."""
    pats = patterns(vault)
    out = []
    for rel in load(vault):
        src, dst = vault / "files" / rel, home() / rel
        if not src.exists():
            out.append((rel, "skipped (not in vault)"))
            continue
        notes = []
        for sub, f in _tree(src, pats).items():
            note = _put(f, dst / sub if sub else dst, dry)
            if note:
                notes.append(note)
        if not notes:
            out.append((rel, "unchanged"))
        elif len(notes) == 1:
            out.append((rel, notes[0]))
        else:
            out.append((rel, f"restored {len(notes)} files"))
    return out


def _lines(p: Path | None) -> list[str] | None:
    """File as lines, [] if absent, None if it is binary."""
    if p is None or not p.exists():
        return []
    try:
        return p.read_text().splitlines(keepends=True)
    except UnicodeDecodeError:
        return None


def diff(vault: Path, only: list[str] | None = None) -> list[tuple[str, str]]:
    """Unified diffs of what `backup` would change: vault copy -> home copy.
    Returns (label, text) for every file that differs."""
    pats = patterns(vault)
    wanted = {rel_to_home(p) for p in only} if only else None
    out = []
    for rel in load(vault):
        if wanted is not None and not any(
                w == rel or w.startswith(rel + "/") or rel.startswith(w + "/") for w in wanted):
            continue
        h, v = home() / rel, vault / "files" / rel
        if not h.exists():
            continue
        a = _tree(v, pats) if v.exists() else {}
        b = _tree(h, pats)
        for sub in sorted(a.keys() | b.keys()):
            fa, fb = a.get(sub), b.get(sub)
            if fa and fb and filecmp.cmp(fa, fb, shallow=False):
                continue
            label = f"{rel}/{sub}" if sub else rel
            if wanted is not None and not any(label == w or label.startswith(w + "/") for w in wanted):
                continue
            la, lb = _lines(fa), _lines(fb)
            if la is None or lb is None:
                out.append((label, f"Binary file {label} differs\n"))
                continue
            text = "".join(difflib.unified_diff(
                la, lb,
                fromfile=f"vault/{label}" if fa else "/dev/null",
                tofile=f"~/{label}" if fb else "/dev/null"))
            out.append((label, text))
    return out

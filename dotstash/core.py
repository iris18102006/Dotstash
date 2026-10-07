"""Core logic: manifest handling, copying, and comparing."""
from __future__ import annotations

import filecmp
import json
import os
import shutil
from pathlib import Path

MANIFEST = "dotstash.json"
IGNORE = shutil.ignore_patterns(".git", "__pycache__")
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


def load(vault: Path) -> list[str]:
    mf = vault / MANIFEST
    if not mf.exists():
        raise DotstashError(f"no vault at {vault}. Run: dotstash init")
    try:
        return list(json.loads(mf.read_text())["files"])
    except (ValueError, KeyError) as e:
        raise DotstashError(f"{mf} is broken: {e}") from None


def save(vault: Path, files: list[str]) -> None:
    (vault / MANIFEST).write_text(json.dumps({"files": sorted(files)}, indent=2) + "\n")


# ---------- copying ----------
def _tree(p: Path) -> dict[str, Path]:
    if p.is_file() or p.is_symlink():
        return {"": p}
    out: dict[str, Path] = {}
    for root, dirs, names in os.walk(p):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
        for n in names:
            f = Path(root) / n
            out[f.relative_to(p).as_posix()] = f
    return out


def copy(src: Path, dst: Path) -> None:
    """Mirror src onto dst (dst is replaced)."""
    if dst.is_dir() and not dst.is_symlink():
        shutil.rmtree(dst)
    elif dst.exists() or dst.is_symlink():
        dst.unlink()
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst, symlinks=True, ignore=IGNORE)
    else:
        shutil.copy2(src, dst, follow_symlinks=False)


def state(rel: str, vault: Path) -> str:
    """One of: synced, modified, no-home, no-backup."""
    h, v = home() / rel, vault / "files" / rel
    if not h.exists():
        return "no-home"
    if not v.exists():
        return "no-backup"
    a, b = _tree(h), _tree(v)
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
        copy(home() / rel, vault / "files" / rel)
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
                copy(home() / rel, vault / "files" / rel)
            out.append((rel, "backed up"))
    return out


def restore(vault: Path, dry: bool = False) -> list[tuple[str, str]]:
    """Copy tracked files from the vault into $HOME. Existing files that
    differ are renamed to <name>.dotstash.bak first, never overwritten."""
    out = []
    for rel in load(vault):
        src, dst = vault / "files" / rel, home() / rel
        if not src.exists():
            out.append((rel, "skipped (not in vault)"))
            continue
        s = state(rel, vault)
        if s == "synced":
            out.append((rel, "unchanged"))
            continue
        note = "restored"
        if dst.exists() or dst.is_symlink():
            bak = dst.with_name(dst.name + ".dotstash.bak")
            note = f"restored (old copy saved as {bak.name})"
            if not dry:
                if bak.exists():
                    shutil.rmtree(bak) if bak.is_dir() else bak.unlink()
                dst.rename(bak)
        if not dry:
            copy(src, dst)
        out.append((rel, note))
    return out

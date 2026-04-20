from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json

from leadlag.config.models import AppConfig


HASH_SUFFIXES = {".py", ".yaml", ".yml", ".toml", ".md"}


def _digest(blob: bytes) -> str:
    h = sha256()
    h.update(blob)
    return h.hexdigest()[:16]


def hash_file(path: Path) -> str:
    return _digest(path.read_bytes())


def hash_tree(root: Path, *, suffixes: set[str] | None = None) -> str:
    suffixes = HASH_SUFFIXES if suffixes is None else suffixes
    files = [p for p in root.rglob("*") if p.is_file() and p.suffix in suffixes]
    files = sorted(files)
    h = sha256()
    for p in files:
        h.update(p.relative_to(root).as_posix().encode("utf-8"))
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return h.hexdigest()[:16] if files else "empty"


def hash_config(cfg: AppConfig) -> str:
    if hasattr(cfg, "model_dump"):
        payload = cfg.model_dump(mode="json")
    else:
        payload = cfg.dict()  # type: ignore[call-arg]
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
    return _digest(blob)


def hash_data_root(root: Path, filenames: dict[str, str]) -> str:
    h = sha256()
    count = 0
    for key, rel in sorted(filenames.items()):
        path = root / rel
        if not path.exists():
            continue
        stat = path.stat()
        h.update(key.encode("utf-8"))
        h.update(b"|")
        h.update(rel.encode("utf-8"))
        h.update(b"|")
        h.update(str(stat.st_size).encode("utf-8"))
        h.update(b"|")
        h.update(str(int(stat.st_mtime)).encode("utf-8"))
        h.update(b"\0")
        count += 1
    return h.hexdigest()[:16] if count else "missing"


def patch_version(root: Path, filenames: dict[str, str]) -> str | None:
    rel = filenames.get("patch_table")
    if not rel:
        return None
    path = root / rel
    if not path.exists():
        return None
    return hash_file(path)


def make_run_id(name: str, trade_date: str | None = None) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if trade_date:
        return f"{name}_{trade_date}_{ts}"
    return f"{name}_{ts}"

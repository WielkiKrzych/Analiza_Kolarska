"""
Local data backup.

The app is a private, single-user, local tool. All the physiology data it
produces — saved ramp-test reports, the longitudinal history database and
training notes — lives only on this machine and is gitignored. That means it
exists in exactly ONE copy: if the disk dies, it is gone.

This module packs every data directory into a single timestamped ZIP so the
user can keep an off-machine copy (external drive, cloud folder). It never
touches source code and is safe to run at any time.
"""

from __future__ import annotations

import logging
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger("Analiza_Kolarska.Backup")

# Repo root (.../Analiza_Kolarska). This file lives at modules/backup.py.
BASE_DIR = Path(__file__).resolve().parent.parent

# Where backups are written by default.
DEFAULT_BACKUP_DIR = BASE_DIR / "backups"

# Data locations to include, relative to BASE_DIR. Missing paths are skipped,
# so this list can safely name things that don't exist on every install.
DATA_TARGETS: List[str] = [
    "reports",  # saved ramp-test reports (JSON/PDF/HTML + index.csv)
    "data",  # DATA_DIR — training_history.db etc.
    "training_notes",  # per-session notes
    "methodology",  # methodology version pins
    "cycling_brain_weights.npz",  # trained MLX weights (irreplaceable)
    "brain_evolution_history.json",  # training-brain history
]

# Files never worth archiving.
_JUNK_NAMES = {".DS_Store", "Thumbs.db"}


@dataclass
class BackupInfo:
    """Result of a backup run."""

    path: Path
    size_bytes: int
    file_count: int
    created_at: datetime
    included: List[str]
    skipped: List[str]

    @property
    def size_mb(self) -> float:
        return self.size_bytes / (1024 * 1024)


def _iter_files(root: Path):
    """Yield real files under `root` (a file yields itself), skipping junk."""
    if root.is_file():
        if root.name not in _JUNK_NAMES:
            yield root
        return
    for p in root.rglob("*"):
        if p.is_file() and p.name not in _JUNK_NAMES:
            yield p


def create_backup(
    dest_dir: Optional[Path | str] = None,
    include_env: bool = False,
    base_dir: Optional[Path | str] = None,
    targets: Optional[List[str]] = None,
) -> BackupInfo:
    """Create a timestamped ZIP of all local data directories.

    Args:
        dest_dir: where to write the ZIP (default: <repo>/backups).
        include_env: also archive the .env file. Off by default because it
            holds the Intervals.icu API key — only include for a private
            off-machine copy you control.
        base_dir: override the project root (mainly for tests).
        targets: override the list of data paths (mainly for tests).

    Returns:
        BackupInfo describing what was written.
    """
    root = Path(base_dir) if base_dir else BASE_DIR
    dest = Path(dest_dir) if dest_dir else (root / "backups")
    dest.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now()
    zip_path = dest / f"analiza_kolarska_backup_{stamp:%Y%m%d_%H%M%S}.zip"
    # Avoid clobbering an existing backup made within the same second.
    _n = 2
    while zip_path.exists():
        zip_path = dest / f"analiza_kolarska_backup_{stamp:%Y%m%d_%H%M%S}_{_n}.zip"
        _n += 1

    target_names = list(targets) if targets is not None else list(DATA_TARGETS)
    if include_env:
        target_names.append(".env")

    included: List[str] = []
    skipped: List[str] = []
    file_count = 0

    # Never let the backups dir recurse into itself.
    dest_resolved = dest.resolve()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in target_names:
            src = (root / name).resolve()
            if not src.exists():
                skipped.append(name)
                continue
            wrote_any = False
            for f in _iter_files(src):
                if dest_resolved in f.resolve().parents:
                    continue  # don't archive existing backups
                arcname = f.resolve().relative_to(root)
                try:
                    zf.write(f, arcname.as_posix())
                    file_count += 1
                    wrote_any = True
                except (OSError, ValueError) as e:
                    logger.warning("Backup: skipped %s (%s)", f, e)
            (included if wrote_any else skipped).append(name)

    size = zip_path.stat().st_size
    logger.info("Backup created: %s (%d files, %.2f MB)", zip_path.name, file_count, size / 1e6)
    return BackupInfo(
        path=zip_path,
        size_bytes=size,
        file_count=file_count,
        created_at=stamp,
        included=included,
        skipped=skipped,
    )


def list_backups(dest_dir: Optional[Path | str] = None) -> List[Path]:
    """Return existing backup ZIPs, newest first."""
    dest = Path(dest_dir) if dest_dir else DEFAULT_BACKUP_DIR
    if not dest.exists():
        return []
    zips = [p for p in dest.glob("analiza_kolarska_backup_*.zip") if p.is_file()]
    return sorted(zips, key=lambda p: p.stat().st_mtime, reverse=True)


def prune_backups(keep: int = 10, dest_dir: Optional[Path | str] = None) -> List[Path]:
    """Delete all but the `keep` most recent backups. Returns removed paths."""
    if keep < 0:
        keep = 0
    backups = list_backups(dest_dir)
    removed: List[Path] = []
    for old in backups[keep:]:
        try:
            old.unlink()
            removed.append(old)
        except OSError as e:
            logger.warning("Backup: could not remove %s (%s)", old, e)
    return removed


def latest_backup(dest_dir: Optional[Path | str] = None) -> Optional[Path]:
    """Path to the most recent backup, or None."""
    backups = list_backups(dest_dir)
    return backups[0] if backups else None

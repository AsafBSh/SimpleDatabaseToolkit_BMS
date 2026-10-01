"""Byte-exact, manually restorable snapshots made before file replacement."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import uuid
from datetime import datetime
from pathlib import Path


def default_backup_root() -> Path:
    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
            ) as key:
                value, _ = winreg.QueryValueEx(key, "Personal")
                return Path(os.path.expandvars(value)) / "Simple Database Toolkit Backups"
        except (OSError, ValueError):
            pass
    return Path.home() / "Documents" / "Simple Database Toolkit Backups"


class BackupSession:
    def __init__(self, root: Path, label: str, scope: Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.scope = Path(scope).resolve()
        if self.root == self.scope or self.root.is_relative_to(self.scope):
            raise ValueError("Backup folder must be outside the selected target tree.")
        stamp = datetime.now().astimezone().strftime("%Y-%m-%d_%H%M%S")
        self.folder = self.root / f"{stamp}_{label}_{uuid.uuid4().hex[:4]}"
        self.folder.mkdir(parents=True, exist_ok=False)
        (self.folder / "restore").mkdir()
        self.entries: list[dict[str, object]] = []
        self._saved: set[Path] = set()
        self.status = "in_progress"
        self._publish()

    @property
    def count(self) -> int:
        return len(self.entries)

    def capture(self, paths: list[Path] | tuple[Path, ...]) -> None:
        for path in paths:
            original = Path(path).resolve()
            if original in self._saved or not original.exists():
                continue
            if not original.is_file():
                raise OSError(f"Cannot back up a non-file: {original}")
            if not original.is_relative_to(self.scope):
                raise ValueError(f"Edited file is outside the selected target: {original}")
            relative = original.relative_to(self.scope)
            destination = self.folder / "restore" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
            )
            os.close(descriptor)
            temporary = Path(temporary_name)
            try:
                shutil.copy2(original, temporary)
                original_hash = _sha256(original)
                backup_hash = _sha256(temporary)
                if original_hash != backup_hash or original.stat().st_size != temporary.stat().st_size:
                    raise OSError(f"Backup verification failed: {original}")
                os.replace(temporary, destination)
                self.entries.append({
                    "original": str(original),
                    "relative_path": relative.as_posix(),
                    "backup": str(destination),
                    "size": original.stat().st_size,
                    "sha256": original_hash,
                })
                self._saved.add(original)
                self._publish()
            finally:
                temporary.unlink(missing_ok=True)

    def finish(self, status: str) -> None:
        self.status = status
        self._publish()

    def _publish(self) -> None:
        manifest = {
            "created": self.folder.name,
            "source_root": str(self.scope),
            "status": self.status,
            "files": self.entries,
        }
        _atomic_text(
            self.folder / "manifest.json",
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        )
        _atomic_text(
            self.folder / "RESTORE.txt",
            "To restore the original files, copy the contents of restore/ "
            f"into:\n{self.scope}\nAllow replacement of matching files.\n"
            "The original filenames and subfolders are preserved.\n",
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_text(path: Path, content: str) -> None:
    descriptor, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)

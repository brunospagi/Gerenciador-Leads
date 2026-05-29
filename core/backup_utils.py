from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from django.conf import settings
from django.core.management import call_command
from django.utils import timezone


def _dump_database(temp_dir: Path) -> dict:
    db_info = settings.DATABASES.get("default", {})
    engine = (db_info.get("ENGINE") or "").lower()
    dump_file = temp_dir / "database_dump.json"

    call_command(
        "dumpdata",
        "--natural-foreign",
        "--natural-primary",
        "--indent",
        "2",
        "--output",
        str(dump_file),
    )

    database_meta = {
        "engine": engine,
        "dump_file": dump_file.name,
        "dump_size_bytes": dump_file.stat().st_size if dump_file.exists() else 0,
    }

    if "sqlite" in engine:
        sqlite_path = Path(str(db_info.get("NAME") or ""))
        if sqlite_path.exists():
            sqlite_copy = temp_dir / "database.sqlite3"
            shutil.copy2(sqlite_path, sqlite_copy)
            database_meta["sqlite_file"] = sqlite_copy.name
            database_meta["sqlite_size_bytes"] = sqlite_copy.stat().st_size

    return database_meta


def _copy_local_media(temp_dir: Path) -> dict:
    media_root = getattr(settings, "MEDIA_ROOT", None)
    if not media_root:
        return {"included": False, "reason": "MEDIA_ROOT nao configurado"}

    media_path = Path(str(media_root))
    if not media_path.exists():
        return {"included": False, "reason": "MEDIA_ROOT inexistente no servidor"}

    if not media_path.is_dir():
        return {"included": False, "reason": "MEDIA_ROOT nao e diretorio"}

    target = temp_dir / "media"
    shutil.copytree(media_path, target)
    file_count = sum(1 for item in target.rglob("*") if item.is_file())
    return {
        "included": True,
        "path": str(media_path),
        "copied_folder": target.name,
        "file_count": file_count,
    }


def create_system_backup(output_dir: str | Path | None = None) -> Path:
    base_dir = Path(getattr(settings, "BASE_DIR"))
    backups_dir = Path(output_dir) if output_dir else (base_dir / "backups")
    backups_dir.mkdir(parents=True, exist_ok=True)

    generated_at = timezone.now()
    timestamp = generated_at.strftime("%Y%m%d_%H%M%S")
    backup_name = f"backup_sistema_{timestamp}.zip"
    final_zip = backups_dir / backup_name

    with tempfile.TemporaryDirectory(prefix="backup_spagi_") as tmp:
        temp_dir = Path(tmp)
        database_meta = _dump_database(temp_dir)
        media_meta = _copy_local_media(temp_dir)

        metadata = {
            "generated_at": generated_at.isoformat(),
            "project": "Gerenciador-Leads",
            "database": database_meta,
            "media": media_meta,
            "restore_notes": [
                "Para restaurar dump JSON: python manage.py loaddata database_dump.json",
                "Para SQLite, opcionalmente substitua o arquivo database.sqlite3.",
            ],
        }

        metadata_file = temp_dir / "metadata.json"
        metadata_file.write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        with ZipFile(final_zip, "w", compression=ZIP_DEFLATED) as zip_file:
            for file_path in temp_dir.rglob("*"):
                if file_path.is_file():
                    zip_file.write(file_path, arcname=file_path.relative_to(temp_dir))

    return final_zip

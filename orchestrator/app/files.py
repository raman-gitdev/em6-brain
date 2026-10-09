"""Stores files users attach in the chat. Files never leave this machine."""
import datetime as dt
import hashlib
import json
import os
import re
import uuid

from fastapi import HTTPException, UploadFile

from . import config


def _safe_name(name: str) -> str:
    base = os.path.basename(name or "file").strip() or "file"
    return re.sub(r"[^\w.\- ()]", "_", base)[:120]


async def save(upload: UploadFile) -> dict:
    name = _safe_name(upload.filename or "")
    ext = os.path.splitext(name)[1].lower()
    if ext not in config.ALLOWED_UPLOAD_TYPES:
        raise HTTPException(400, f"File type '{ext or '?'}' isn't supported yet. "
                                 f"Supported: {' '.join(config.ALLOWED_UPLOAD_TYPES)}")
    file_id = uuid.uuid4().hex
    folder = os.path.join(config.FILES_DIR, file_id)
    os.makedirs(folder)
    path = os.path.join(folder, name)
    limit = config.MAX_UPLOAD_MB * 1024 * 1024
    size, sha = 0, hashlib.sha256()
    try:
        with open(path, "wb") as f:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(413, f"File is larger than {config.MAX_UPLOAD_MB} MB.")
                sha.update(chunk)
                f.write(chunk)
    except HTTPException:
        os.remove(path)
        os.rmdir(folder)
        raise
    meta = {"file_id": file_id, "original_name": name, "stored_name": name, "size": size,
            "sha256": sha.hexdigest(),
            "uploaded_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    with open(os.path.join(folder, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    return meta


def get(file_id: str) -> dict | None:
    if not re.fullmatch(r"[0-9a-f]{32}", file_id or ""):
        return None
    try:
        with open(os.path.join(config.FILES_DIR, file_id, "meta.json"), encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None

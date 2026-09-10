import hashlib
import shutil
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
from io import BytesIO

logger = logging.getLogger(__name__)

STORAGE_ROOT = Path("storage/documents")
THUMB_ROOT = Path("storage/thumbnails")
ARCHIVE_ROOT = Path("storage/archive")

STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
THUMB_ROOT.mkdir(parents=True, exist_ok=True)
ARCHIVE_ROOT.mkdir(parents=True, exist_ok=True)


def _file_hash(data: bytes) -> str:
    """Compute first 16 chars of SHA-256 hash of file bytes."""
    return hashlib.sha256(data).hexdigest()[:16]


def _safe_filename(original_filename: str, document_id: int) -> str:
    """
    Build a safe storage filename using doc_id and timestamp.
    Example: doc_42_20260829_143512.pdf
    """
    ext = Path(original_filename).suffix.lower()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"doc_{document_id}_{ts}{ext}"


def _guess_mime(filename: str) -> str:
    """Return MIME type for common land record file formats."""
    return {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
        ".bmp": "image/bmp",
    }.get(Path(filename).suffix.lower(), "application/octet-stream")


def store_document(
    file_bytes: bytes,
    original_filename: str,
    document_id: int,
) -> dict:
    """
    Save uploaded file bytes to local storage.
    Creates folder: storage/documents/{document_id}/
    Saves file as: doc_{document_id}_{timestamp}{ext}
    Saves metadata as: doc_{document_id}_meta.json
    Returns metadata dict with keys:
    document_id, original_filename, storage_path,
    file_size_bytes, sha256_prefix, stored_at, mime_type
    """
    try:
        safe_name = _safe_filename(original_filename, document_id)
        folder = STORAGE_ROOT / str(document_id)
        folder.mkdir(parents=True, exist_ok=True)

        filepath = folder / safe_name
        with open(filepath, "wb") as f:
            f.write(file_bytes)

        file_hash = _file_hash(file_bytes)
        metadata = {
            "document_id": document_id,
            "original_filename": original_filename,
            "storage_path": str(filepath),
            "file_size_bytes": len(file_bytes),
            "sha256_prefix": file_hash,
            "stored_at": datetime.now().isoformat(),
            "mime_type": _guess_mime(original_filename),
        }

        meta_path = folder / f"doc_{document_id}_meta.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        logger.info(
            f"Stored document {document_id}: {filepath} "
            f"({len(file_bytes)} bytes, hash: {file_hash})"
        )
        return metadata
    except Exception as e:
        logger.error(f"store_document error for {document_id}: {e}")
        return {
            "document_id": document_id,
            "original_filename": original_filename,
            "storage_path": "",
            "file_size_bytes": 0,
            "sha256_prefix": "",
            "stored_at": datetime.now().isoformat(),
            "mime_type": _guess_mime(original_filename),
        }


def retrieve_document(storage_path: str) -> Optional[bytes]:
    """
    Read file bytes from a storage path.
    Returns file bytes if found.
    Returns None if file does not exist or cannot be read.
    Used by Human Review UI to display original scan.
    """
    try:
        path = Path(storage_path)
        if not path.exists():
            logger.warning(f"File not found: {storage_path}")
            return None
        return path.read_bytes()
    except Exception as e:
        logger.error(f"retrieve_document error: {e}")
        return None


def generate_thumbnail(
    file_bytes: bytes,
    filename: str,
    document_id: int,
) -> Optional[str]:
    """
    Generate a 300px-wide JPEG thumbnail for a PDF or image file.
    PDF: renders page 1 using PyMuPDF at 1.5x scale.
    Image: resizes to max 300x400 using PIL LANCZOS.
    Saves to: storage/thumbnails/thumb_{document_id}.jpg
    Returns path string on success, None on any failure.
    """
    thumb_path = THUMB_ROOT / f"thumb_{document_id}.jpg"
    ext = Path(filename).suffix.lower()
    try:
        if ext == ".pdf":
            import fitz
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page = doc[0]
            mat = fitz.Matrix(1.5, 1.5)
            pix = page.get_pixmap(matrix=mat)
            from PIL import Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            img.thumbnail((300, 400), Image.LANCZOS)
            img.save(str(thumb_path), "JPEG", quality=85)
            doc.close()
        elif ext in {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp"}:
            from PIL import Image
            img = Image.open(BytesIO(file_bytes))
            img.thumbnail((300, 400), Image.LANCZOS)
            img.convert("RGB").save(str(thumb_path), "JPEG", quality=85)
        else:
            logger.warning(f"Thumbnail not supported for type: {ext}")
            return None

        logger.info(f"Thumbnail generated: {thumb_path}")
        return str(thumb_path)
    except Exception as e:
        logger.warning(f"Thumbnail generation failed for doc {document_id}: {e}")
        return None


def get_document_metadata(document_id: int) -> Optional[dict]:
    """
    Read and return the JSON metadata sidecar file for a document.
    Returns dict if found, None if not.
    """
    meta_path = STORAGE_ROOT / str(document_id) / f"doc_{document_id}_meta.json"
    if not meta_path.exists():
        return None
    try:
        with open(meta_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"get_document_metadata error for {document_id}: {e}")
        return None


def delete_document(document_id: int, storage_path: str) -> bool:
    """
    Soft delete — moves file to storage/archive/ instead of permanently deleting.
    The file can be recovered from archive if needed.
    Returns True on success, False on failure.
    """
    try:
        src = Path(storage_path)
        if src.exists():
            dest = ARCHIVE_ROOT / src.name
            shutil.move(str(src), str(dest))
            logger.info(f"Archived document {document_id}: {src} -> {dest}")
            return True
        logger.warning(f"delete_document: source not found: {storage_path}")
        return False
    except Exception as e:
        logger.error(f"delete_document error for {document_id}: {e}")
        return False


def get_storage_stats() -> dict:
    """
    Return storage usage statistics.
    Counts all files in storage/documents/ excluding JSON metadata sidecars.
    Returns dict with keys:
    total_files, total_size_mb, storage_root, thumbnail_count
    """
    try:
        all_files = [
            f for f in STORAGE_ROOT.rglob("*")
            if f.is_file() and not f.name.endswith("_meta.json")
        ]
        total_bytes = sum(f.stat().st_size for f in all_files)
        thumb_count = len(list(THUMB_ROOT.glob("thumb_*.jpg")))
        return {
            "total_files": len(all_files),
            "total_size_mb": round(total_bytes / (1024 * 1024), 2),
            "storage_root": str(STORAGE_ROOT),
            "thumbnail_count": thumb_count,
        }
    except Exception as e:
        logger.error(f"get_storage_stats error: {e}")
        return {
            "total_files": 0,
            "total_size_mb": 0.0,
            "storage_root": str(STORAGE_ROOT),
            "thumbnail_count": 0,
        }


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    print("Testing Module 12 — doc_repository.py")
    print("=" * 60)

    dummy_bytes = b"%PDF-1.4 dummy content for testing" * 100
    dummy_name = "test_land_record.pdf"
    test_doc_id = 9999

    print(f"\nTest 1: store_document()")
    meta = store_document(dummy_bytes, dummy_name, test_doc_id)
    print(f"  storage_path:    {meta['storage_path']}")
    print(f"  file_size_bytes: {meta['file_size_bytes']}")
    print(f"  sha256_prefix:   {meta['sha256_prefix']}")
    assert Path(meta["storage_path"]).exists(), "File was not saved!"

    print(f"\nTest 2: retrieve_document()")
    retrieved = retrieve_document(meta["storage_path"])
    assert retrieved == dummy_bytes, "Retrieved bytes do not match!"
    print(f"  Retrieved {len(retrieved)} bytes — matches original OK")

    print(f"\nTest 3: get_document_metadata()")
    loaded_meta = get_document_metadata(test_doc_id)
    assert loaded_meta is not None, "Metadata not found!"
    assert loaded_meta["document_id"] == test_doc_id
    print(f"  Metadata loaded: document_id={loaded_meta['document_id']} OK")

    print(f"\nTest 4: get_storage_stats()")
    stats = get_storage_stats()
    print(f"  total_files:   {stats['total_files']}")
    print(f"  total_size_mb: {stats['total_size_mb']}")
    assert stats["total_files"] >= 1

    print(f"\nTest 5: delete_document() soft delete")
    ok = delete_document(test_doc_id, meta["storage_path"])
    assert ok, "delete_document returned False!"
    assert not Path(meta["storage_path"]).exists(), "File still exists after delete!"
    archive_file = ARCHIVE_ROOT / Path(meta["storage_path"]).name
    assert archive_file.exists(), "File not found in archive!"
    print(f"  File moved to archive OK")

    print("\n" + "=" * 60)
    print("Module 12 — doc_repository.py OK")

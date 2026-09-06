import hashlib
import os
import secrets
from pathlib import Path

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_MIMES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB


def get_upload_dir() -> Path:
    base = Path(__file__).resolve().parent.parent.parent
    upload_dir = base / "uploads" / "products"
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def validate_image(
    filename: str,
    content_type: str | None,
    size: int,
) -> str | None:
    """Retorna None si es válido, o un mensaje de error."""
    ext = Path(filename).suffix.lower()

    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return (
            f"Extensión no permitida: {ext}. "
            f"Usa: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}"
        )

    if content_type and content_type.lower() not in ALLOWED_IMAGE_MIMES:
        return (
            f"Tipo MIME no permitido: {content_type}. "
            f"Usa: {', '.join(sorted(ALLOWED_IMAGE_MIMES))}"
        )

    if size > MAX_IMAGE_SIZE:
        max_mb = MAX_IMAGE_SIZE // (1024 * 1024)
        return (
            f"El archivo excede el tamaño máximo de {max_mb} MB"
        )

    return None


def save_image(
    file_content: bytes,
    original_filename: str,
) -> str:
    """Guarda una imagen y retorna la ruta relativa."""
    ext = Path(original_filename).suffix.lower()
    safe_hash = hashlib.sha256(
        file_content
    ).hexdigest()[:12]
    random_part = secrets.token_hex(4)
    safe_filename = f"{safe_hash}_{random_part}{ext}"

    upload_dir = get_upload_dir()
    file_path = upload_dir / safe_filename
    file_path.write_bytes(file_content)

    return f"products/{safe_filename}"


def delete_image(relative_path: str) -> bool:
    """Elimina una imagen por su ruta relativa."""
    if not relative_path:
        return False

    upload_dir = get_upload_dir().parent
    full_path = upload_dir / relative_path

    if full_path.exists() and full_path.is_file():
        full_path.unlink()
        return True

    return False


def get_image_url(relative_path: str | None) -> str | None:
    """Convierte una ruta relativa a URL servible."""
    if not relative_path:
        return None
    return f"/uploads/{relative_path}"


def get_image_full_path(relative_path: str) -> Path | None:
    """Retorna la ruta absoluta de una imagen."""
    if not relative_path:
        return None

    upload_dir = get_upload_dir().parent
    full_path = upload_dir / relative_path

    if full_path.exists() and full_path.is_file():
        return full_path

    return None

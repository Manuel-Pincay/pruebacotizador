"""
Procesamiento, validación y rutas de medios del ERP.
Todas las imágenes nuevas se guardan como WEBP (calidad 80%).
"""

from __future__ import annotations

import hashlib
import io
import os
import uuid
from pathlib import Path

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
BLOCKED_EXTENSIONS = {
    "exe", "zip", "svg", "js", "php", "pdf", "gif", "bmp", "tiff",
    "html", "htm", "sh", "bat", "cmd", "ps1", "py", "sql",
}

MAX_PRODUCT_BYTES = 5 * 1024 * 1024
MAX_DESIGN_BYTES = 10 * 1024 * 1024
MAX_LOGO_BYTES = 3 * 1024 * 1024
MAX_PAYMENT_RECEIPT_BYTES = 10 * 1024 * 1024

PRODUCT_MAX_PX = 1920
DESIGN_MAX_PX = 1600
PAYMENT_RECEIPT_MAX_PX = 1600
THUMB_PX = 300
WEBP_QUALITY = 80

PRODUCTS_DIR = Path("uploads/products")
PRODUCTS_THUMBS_DIR = PRODUCTS_DIR / "thumbs"
DESIGNS_DIR = Path("uploads/designs")
LOGOS_DIR = Path("uploads/logos")
PAYMENTS_DIR = Path("uploads/payments")

ALLOWED_RECEIPT_EXTENSIONS = {"jpg", "jpeg", "png", "pdf"}


class UploadValidationError(Exception):
    """Error de validación al subir un archivo."""


def _extension(filename: str | None) -> str:
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower()


def validate_upload_filename(filename: str | None) -> str:
    ext = _extension(filename)
    if not ext:
        raise UploadValidationError("Nombre de archivo no válido.")
    if ext in BLOCKED_EXTENSIONS:
        raise UploadValidationError(f"Tipo de archivo bloqueado: .{ext}")
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise UploadValidationError(
            "Formato no permitido. Use JPG, JPEG, PNG o WEBP."
        )
    return ext


async def read_upload_bytes(upload_file: UploadFile, max_bytes: int) -> bytes:
    data = await upload_file.read()
    if len(data) > max_bytes:
        mb = max_bytes // (1024 * 1024)
        raise UploadValidationError(f"El archivo supera el límite de {mb} MB.")
    if not data:
        raise UploadValidationError("El archivo está vacío.")
    return data


def read_upload_bytes_sync(upload_file: UploadFile, max_bytes: int) -> bytes:
    upload_file.file.seek(0)
    data = upload_file.file.read()
    if len(data) > max_bytes:
        mb = max_bytes // (1024 * 1024)
        raise UploadValidationError(f"El archivo supera el límite de {mb} MB.")
    if not data:
        raise UploadValidationError("El archivo está vacío.")
    return data


def _open_image(data: bytes) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
        return image
    except UnidentifiedImageError as exc:
        raise UploadValidationError("No es una imagen válida.") from exc


def _to_rgb(image: Image.Image) -> Image.Image:
    if image.mode in ("RGBA", "LA", "P"):
        background = Image.new("RGB", image.size, (255, 255, 255))
        if image.mode == "P":
            image = image.convert("RGBA")
        alpha = image.split()[-1] if image.mode in ("RGBA", "LA") else None
        background.paste(image, mask=alpha)
        return background
    if image.mode != "RGB":
        return image.convert("RGB")
    return image


def _resize_max(image: Image.Image, max_px: int) -> Image.Image:
    image.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)
    return image


def _save_webp(image: Image.Image, path: Path, quality: int = WEBP_QUALITY) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="WEBP", quality=quality, method=6)


def bytes_to_webp(data: bytes, max_px: int) -> bytes:
    image = _to_rgb(_open_image(data))
    image = _resize_max(image, max_px)
    buffer = io.BytesIO()
    image.save(buffer, format="WEBP", quality=WEBP_QUALITY, method=6)
    return buffer.getvalue()


def _new_webp_name() -> str:
    return f"{uuid.uuid4()}.webp"


def save_product_image(data: bytes) -> str:
    """Guarda imagen de producto + thumbnail. Retorna solo el nombre de archivo."""
    name = _new_webp_name()
    stem = Path(name).stem
    image = _to_rgb(_open_image(data))
    full = _resize_max(image.copy(), PRODUCT_MAX_PX)
    thumb = _resize_max(image.copy(), THUMB_PX)
    _save_webp(full, PRODUCTS_DIR / name)
    _save_webp(thumb, PRODUCTS_THUMBS_DIR / f"{stem}.webp")
    return name


def save_design_image(data: bytes) -> str:
    name = _new_webp_name()
    image = _to_rgb(_open_image(data))
    image = _resize_max(image, DESIGN_MAX_PX)
    _save_webp(image, DESIGNS_DIR / name)
    return name


def save_logo_image(data: bytes) -> str:
    name = _new_webp_name()
    image = _open_image(data)
    if image.mode in ("RGBA", "LA", "P"):
        image = image.convert("RGBA")
        image.thumbnail((800, 800), Image.Resampling.LANCZOS)
        path = LOGOS_DIR / name
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path, format="WEBP", quality=WEBP_QUALITY, method=6)
    else:
        image = _resize_max(_to_rgb(image), 800)
        _save_webp(image, LOGOS_DIR / name)
    return name


def delete_product_files(filename: str | None) -> None:
    if not filename:
        return
    stem = Path(filename).stem
    for path in (
        PRODUCTS_DIR / filename,
        PRODUCTS_DIR / f"{stem}.webp",
        PRODUCTS_THUMBS_DIR / f"{stem}.webp",
    ):
        if path.exists():
            path.unlink(missing_ok=True)


def delete_design_file(filename: str | None) -> None:
    if not filename:
        return
    path = DESIGNS_DIR / filename
    if path.exists():
        path.unlink(missing_ok=True)


def delete_logo_file(filename: str | None) -> None:
    if not filename:
        return
    path = LOGOS_DIR / filename
    if path.exists():
        path.unlink(missing_ok=True)


def _file_exists(*candidates: Path) -> Path | None:
    for path in candidates:
        if path.exists():
            return path
    return None


def product_image_url(filename: str | None, *, thumb: bool = False) -> str | None:
    if not filename:
        return None
    stem = Path(filename).stem
    if thumb:
        thumb_path = _file_exists(
            PRODUCTS_THUMBS_DIR / f"{stem}.webp",
            PRODUCTS_THUMBS_DIR / filename,
        )
        if thumb_path:
            return f"/uploads/products/thumbs/{thumb_path.name}"
    full_path = _file_exists(
        PRODUCTS_DIR / filename,
        PRODUCTS_DIR / f"{stem}.webp",
    )
    if full_path:
        rel = full_path.relative_to(PRODUCTS_DIR)
        return f"/uploads/products/{rel.as_posix()}"
    return None


def design_image_url(filename: str | None) -> str | None:
    if not filename:
        return None
    stem = Path(filename).stem
    path = _file_exists(
        DESIGNS_DIR / filename,
        DESIGNS_DIR / f"{stem}.webp",
    )
    if path:
        return f"/uploads/designs/{path.name}"
    return None


def logo_image_url(filename: str | None) -> str | None:
    if not filename:
        return None
    path = _file_exists(LOGOS_DIR / filename, LOGOS_DIR / f"{Path(filename).stem}.webp")
    if path:
        return f"/uploads/logos/{path.name}"
    return None


def resolve_design_path(filename: str | None) -> str | None:
    """Ruta en disco para PDF (soporta archivos legacy)."""
    if not filename:
        return None
    stem = Path(filename).stem
    path = _file_exists(
        DESIGNS_DIR / filename,
        DESIGNS_DIR / f"{stem}.webp",
    )
    return str(path) if path else None


def resolve_product_path(filename: str | None) -> str | None:
    """Ruta en disco para PDF de imagen de producto."""
    if not filename:
        return None
    stem = Path(filename).stem
    path = _file_exists(
        PRODUCTS_DIR / filename,
        PRODUCTS_DIR / f"{stem}.webp",
    )
    return str(path) if path else None


def quotation_item_image_path(item) -> str | None:
    """Prioridad: imagen del ítem → catálogo → None."""
    custom = getattr(item, "product_image", None)
    if custom:
        path = resolve_product_path(custom)
        if path:
            return path
    product = getattr(item, "product", None)
    if product and getattr(product, "image", None):
        return resolve_product_path(product.image)
    return None


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def format_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.2f} MB"


def _detect_receipt_mime(data: bytes) -> str:
    if data[:4] == b"%PDF":
        return "application/pdf"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    return ""


def validate_receipt_filename(filename: str | None) -> str:
    ext = _extension(filename)
    if not ext:
        raise UploadValidationError("Nombre de archivo no válido.")
    if ext not in ALLOWED_RECEIPT_EXTENSIONS:
        raise UploadValidationError(
            "Formato no permitido. Use JPG, JPEG, PNG o PDF."
        )
    return ext


def validate_receipt_content(ext: str, data: bytes) -> None:
    mime = _detect_receipt_mime(data)
    expected = {
        "pdf": "application/pdf",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
    }
    if mime != expected.get(ext):
        raise UploadValidationError(
            "El contenido del archivo no coincide con su extensión."
        )


def save_payment_receipt(data: bytes, ext: str) -> str:
    """Guarda comprobante de pago. Imágenes → WEBP; PDF sin modificar."""
    PAYMENTS_DIR.mkdir(parents=True, exist_ok=True)
    if ext == "pdf":
        name = f"{uuid.uuid4()}.pdf"
        path = PAYMENTS_DIR / name
        path.write_bytes(data)
        return name
    webp_data = bytes_to_webp(data, PAYMENT_RECEIPT_MAX_PX)
    name = _new_webp_name()
    path = PAYMENTS_DIR / name
    path.write_bytes(webp_data)
    return name


def delete_payment_receipt(filename: str | None) -> None:
    if not filename:
        return
    safe_name = Path(filename).name
    if safe_name != filename:
        return
    path = PAYMENTS_DIR / safe_name
    if path.exists() and path.is_file():
        path.unlink(missing_ok=True)


def payment_receipt_url(filename: str | None) -> str | None:
    if not filename:
        return None
    safe_name = Path(filename).name
    path = PAYMENTS_DIR / safe_name
    if path.exists() and path.is_file():
        return f"/uploads/payments/{safe_name}"
    return None


def resolve_payment_receipt_path(filename: str | None) -> Path | None:
    if not filename:
        return None
    safe_name = Path(filename).name
    if safe_name != filename:
        return None
    path = (PAYMENTS_DIR / safe_name).resolve()
    try:
        path.relative_to(PAYMENTS_DIR.resolve())
    except ValueError:
        return None
    if path.exists() and path.is_file():
        return path
    return None


def is_payment_receipt_pdf(filename: str | None) -> bool:
    if not filename:
        return False
    return _extension(filename) == "pdf"


def is_payment_receipt_image(filename: str | None) -> bool:
    if not filename:
        return False
    ext = _extension(filename)
    return ext in {"jpg", "jpeg", "png", "webp"}

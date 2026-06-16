from sqlalchemy.orm import Session

from app.models.quotation import Quotation
from app.models.quotation_design import QuotationDesign
from app.utils.image_storage import delete_design_file, design_image_url, save_design_image

MAX_QUOTATION_DESIGNS = 4


class DesignLimitError(Exception):
    """Se superó el máximo de imágenes de diseño."""


def _design_count(db: Session, quotation_id: int) -> int:
    return (
        db.query(QuotationDesign)
        .filter(QuotationDesign.quotation_id == quotation_id)
        .count()
    )


def sync_legacy_design_file(db: Session, quotation: Quotation) -> None:
    """Migra design_file legacy al nuevo modelo si aplica."""
    if not quotation.design_file:
        return
    if _design_count(db, quotation.id) > 0:
        return

    db.add(
        QuotationDesign(
            quotation_id=quotation.id,
            filename=quotation.design_file,
            sort_order=0,
        )
    )
    db.flush()


def get_design_filenames(quotation: Quotation) -> list[str]:
    filenames = [design.filename for design in quotation.designs if design.filename]
    if filenames:
        return filenames
    if quotation.design_file:
        return [quotation.design_file]
    return []


def get_design_urls(quotation: Quotation) -> list[str]:
    return [
        url
        for filename in get_design_filenames(quotation)
        if (url := design_image_url(filename))
    ]


def add_design_image(db: Session, quotation: Quotation, data: bytes) -> QuotationDesign:
    sync_legacy_design_file(db, quotation)
    current = _design_count(db, quotation.id)
    if current >= MAX_QUOTATION_DESIGNS:
        raise DesignLimitError(
            f"Máximo {MAX_QUOTATION_DESIGNS} imágenes de diseño por cotización."
        )

    filename = save_design_image(data)
    design = QuotationDesign(
        quotation_id=quotation.id,
        filename=filename,
        sort_order=current,
    )
    db.add(design)
    db.flush()

    if not quotation.design_file:
        quotation.design_file = filename

    return design


def delete_design_image(db: Session, quotation: Quotation, design_id: int) -> None:
    design = (
        db.query(QuotationDesign)
        .filter(
            QuotationDesign.id == design_id,
            QuotationDesign.quotation_id == quotation.id,
        )
        .first()
    )
    if not design:
        raise ValueError("Imagen de diseño no encontrada.")

    delete_design_file(design.filename)
    db.delete(design)
    db.flush()

    remaining = (
        db.query(QuotationDesign)
        .filter(QuotationDesign.quotation_id == quotation.id)
        .order_by(QuotationDesign.sort_order.asc())
        .all()
    )
    for index, row in enumerate(remaining):
        row.sort_order = index

    quotation.design_file = remaining[0].filename if remaining else None

"""Estadísticas de almacenamiento de archivos del ERP."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.company_config import CompanyConfig
from app.models.product import Product
from app.models.quotation import Quotation
from app.utils.image_storage import (
    DESIGNS_DIR,
    LOGOS_DIR,
    PRODUCTS_DIR,
    PRODUCTS_THUMBS_DIR,
    file_sha256,
    format_bytes,
)

MEDIA_DIRS = {
    "products": PRODUCTS_DIR,
    "designs": DESIGNS_DIR,
    "logos": LOGOS_DIR,
}


def _iter_files(directory: Path):
    if not directory.exists():
        return
    for path in directory.rglob("*"):
        if path.is_file():
            yield path


def _referenced_files(db: Session) -> dict[str, set[str]]:
    products = {p.image for p in db.query(Product.image).filter(Product.image.isnot(None))}
    products = {x for x in products if x}
    designs = {q.design_file for q in db.query(Quotation.design_file).filter(Quotation.design_file.isnot(None))}
    designs = {x for x in designs if x}
    logos = set()
    config = db.query(CompanyConfig).first()
    if config and config.logo:
        logos.add(config.logo)
    return {
        "products": products,
        "designs": designs,
        "logos": logos,
    }


def collect_storage_stats(db: Session) -> dict:
    refs = _referenced_files(db)
    stats = {
        "categories": {},
        "totals": {"files": 0, "bytes": 0, "orphans": 0, "orphan_bytes": 0},
        "duplicates": [],
        "orphans": [],
    }

    hashes: dict[str, list[str]] = defaultdict(list)

    for label, directory in MEDIA_DIRS.items():
        files = list(_iter_files(directory))
        bytes_total = sum(f.stat().st_size for f in files)
        orphan_files = []
        for path in files:
            rel = path.name
            if label == "products" and "thumbs" in path.parts:
                continue
            referenced = rel in refs.get(label, set()) or path.stem in {
                Path(r).stem for r in refs.get(label, set())
            }
            if not referenced:
                orphan_files.append(
                    {"path": str(path).replace("\\", "/"), "size": path.stat().st_size}
                )
            digest = file_sha256(path)
            hashes[digest].append(str(path).replace("\\", "/"))

        orphan_bytes = sum(item["size"] for item in orphan_files)
        stats["categories"][label] = {
            "files": len(files),
            "bytes": bytes_total,
            "human": format_bytes(bytes_total),
            "orphans": len(orphan_files),
            "orphan_bytes": orphan_bytes,
        }
        stats["totals"]["files"] += len(files)
        stats["totals"]["bytes"] += bytes_total
        stats["totals"]["orphans"] += len(orphan_files)
        stats["totals"]["orphan_bytes"] += orphan_bytes
        stats["orphans"].extend(orphan_files)

    thumb_files = list(_iter_files(PRODUCTS_THUMBS_DIR))
    thumb_bytes = sum(f.stat().st_size for f in thumb_files)
    stats["categories"]["thumbs"] = {
        "files": len(thumb_files),
        "bytes": thumb_bytes,
        "human": format_bytes(thumb_bytes),
        "orphans": 0,
        "orphan_bytes": 0,
        "excluded_from_backup": True,
    }
    stats["totals"]["files"] += len(thumb_files)
    stats["totals"]["bytes"] += thumb_bytes

    stats["duplicates"] = [
        {"hash": digest, "paths": paths}
        for digest, paths in hashes.items()
        if len(paths) > 1
    ]

    if stats["totals"]["files"]:
        stats["totals"]["avg_bytes"] = stats["totals"]["bytes"] // stats["totals"]["files"]
        stats["totals"]["avg_human"] = format_bytes(stats["totals"]["avg_bytes"])
    else:
        stats["totals"]["avg_bytes"] = 0
        stats["totals"]["avg_human"] = "0 B"

    stats["totals"]["human"] = format_bytes(stats["totals"]["bytes"])
    stats["totals"]["orphan_human"] = format_bytes(stats["totals"]["orphan_bytes"])
    stats["referenced"] = {
        "products": len(refs["products"]),
        "designs": len(refs["designs"]),
        "logos": len(refs["logos"]),
    }
    return stats

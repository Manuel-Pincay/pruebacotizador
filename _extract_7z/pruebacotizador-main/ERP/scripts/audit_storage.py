#!/usr/bin/env python3
"""Auditoría de uploads/ — duplicados, huérfanos y uso de espacio."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.services.storage_stats import collect_storage_stats


def main() -> int:
    db = SessionLocal()
    try:
        stats = collect_storage_stats(db)
    finally:
        db.close()

    report_path = ROOT / "docs" / "STORAGE_AUDIT.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# Auditoría de almacenamiento — {datetime.now():%Y-%m-%d %H:%M}",
        "",
        "## Resumen",
        "",
        f"- **Archivos totales:** {stats['totals']['files']}",
        f"- **Espacio total:** {stats['totals']['human']}",
        f"- **Tamaño promedio:** {stats['totals']['avg_human']}",
        f"- **Huérfanos:** {stats['totals']['orphans']} ({stats['totals']['orphan_human']})",
        f"- **Duplicados (grupos):** {len(stats['duplicates'])}",
        "",
        "## Por categoría",
        "",
        "| Categoría | Archivos | Espacio | Huérfanos |",
        "|-----------|----------|---------|-----------|",
    ]

    for name, cat in stats["categories"].items():
        lines.append(
            f"| {name} | {cat['files']} | {cat['human']} | {cat['orphans']} |"
        )

    lines.extend(["", "## Referenciados en BD", ""])
    for key, count in stats["referenced"].items():
        lines.append(f"- **{key}:** {count}")

    if stats["duplicates"]:
        lines.extend(["", "## Duplicados (mismo hash)", ""])
        for group in stats["duplicates"][:20]:
            lines.append(f"- `{group['hash'][:12]}...`")
            for path in group["paths"]:
                lines.append(f"  - {path}")

    if stats["orphans"]:
        lines.extend(["", "## Huérfanos (muestra)", ""])
        for item in stats["orphans"][:30]:
            lines.append(f"- `{item['path']}` ({item['size']:,} bytes)")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    json_path = ROOT / f"storage_audit_{datetime.now():%Y%m%d_%H%M%S}.json"
    json_path.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Reporte: {report_path}")
    print(f"JSON:    {json_path}")
    print(f"Total:   {stats['totals']['human']} | Huérfanos: {stats['totals']['orphans']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

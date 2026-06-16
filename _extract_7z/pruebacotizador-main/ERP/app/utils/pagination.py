import math
from urllib.parse import urlencode


def paginate_query(query, page: int, per_page: int):
    page = max(1, page)
    per_page = max(1, min(per_page, 100))
    total = query.count()
    pages = max(1, math.ceil(total / per_page))
    if page > pages:
        page = pages
    items = (
        query.offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {
        "items": items,
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": pages,
        "has_prev": page > 1,
        "has_next": page < pages,
    }


def build_page_url(base_path: str, page: int, params: dict | None = None) -> str:
    data = dict(params or {})
    data["page"] = page
    clean = {k: v for k, v in data.items() if v not in (None, "")}
    query = urlencode(clean)
    return f"{base_path}?{query}" if query else base_path

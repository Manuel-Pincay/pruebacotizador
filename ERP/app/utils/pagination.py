import math
from dataclasses import dataclass
from urllib.parse import urlencode


@dataclass
class Pagination:
    items: list
    page: int
    per_page: int
    total: int
    pages: int
    has_prev: bool
    has_next: bool

    def __getitem__(self, key: str):
        return getattr(self, key)


def paginate_query(query, page: int, per_page: int) -> Pagination:
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
    return Pagination(
        items=items,
        page=page,
        per_page=per_page,
        total=total,
        pages=pages,
        has_prev=page > 1,
        has_next=page < pages,
    )


def build_page_url(base_path: str, page: int, params: dict | None = None) -> str:
    data = dict(params or {})
    data["page"] = page
    clean = {k: v for k, v in data.items() if v not in (None, "")}
    query = urlencode(clean)
    return f"{base_path}?{query}" if query else base_path

from starlette.staticfiles import StaticFiles
from starlette.responses import Response
from starlette.types import Scope


class CachedStaticFiles(StaticFiles):
    """StaticFiles con Cache-Control para /uploads (productos y diseños)."""

    def __init__(self, *args, cache_max_age: int = 2592000, **kwargs):
        super().__init__(*args, **kwargs)
        self.cache_max_age = cache_max_age

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = (
                f"public, max-age={self.cache_max_age}, immutable"
            )
        return response

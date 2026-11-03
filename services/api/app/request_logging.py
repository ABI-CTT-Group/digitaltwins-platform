"""Log every rejected request with its reason; the response is FastAPI's default."""
import logging

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("app.request")


def _log(request: Request, status: int, detail) -> None:
    # The path only: a query string can carry values that don't belong in a log.
    logger.log(logging.ERROR if status >= 500 else logging.WARNING,
               "%s %s -> %s: %s", request.method, request.url.path, status, detail)


def install_request_error_logging(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        _log(request, exc.status_code, exc.detail)
        return await http_exception_handler(request, exc)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        _log(request, 422, exc.errors())
        return await request_validation_exception_handler(request, exc)

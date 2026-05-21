from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions.domain import DomainError


def error_response(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content={"error": {"code": code, "message": message}}
    )


async def domain_exception_handler(_: Request, exc: DomainError) -> JSONResponse:
    return error_response(exc.code, exc.message, exc.status_code)


async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return error_response("VALIDATION_ERROR", str(exc.errors()), 422)


async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    return error_response("HTTP_ERROR", str(exc.detail), exc.status_code)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, domain_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)

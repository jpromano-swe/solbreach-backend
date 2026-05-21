class DomainError(Exception):
    code = "DOMAIN_ERROR"
    status_code = 400

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.code.replace("_", " ").title()
        super().__init__(self.message)


class NotFoundError(DomainError):
    code = "NOT_FOUND"
    status_code = 404


class ConflictError(DomainError):
    code = "CONFLICT"
    status_code = 409


class UnauthorizedError(DomainError):
    code = "UNAUTHORIZED"
    status_code = 401


class ForbiddenError(DomainError):
    code = "FORBIDDEN"
    status_code = 403

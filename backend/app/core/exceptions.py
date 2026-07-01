"""Custom exception classes for the application."""


class AppException(Exception):
    """Base application exception with an HTTP status code."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class NotFoundException(AppException):
    def __init__(self, entity: str, entity_id: str | None = None):
        msg = f"{entity} not found"
        if entity_id:
            msg += f": {entity_id}"
        super().__init__(msg, status_code=404)


class DuplicateException(AppException):
    def __init__(self, entity: str, field: str, value: str):
        msg = f"{entity} with {field} '{value}' already exists"
        super().__init__(msg, status_code=409)


class UnauthorizedException(AppException):
    def __init__(self, detail: str = "Could not validate credentials"):
        super().__init__(detail, status_code=401)


class ForbiddenException(AppException):
    def __init__(self, detail: str = "Access denied"):
        super().__init__(detail, status_code=403)

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus


@dataclass(slots=True)
class AppError(Exception):
    code: str
    message: str
    status_code: int = HTTPStatus.BAD_REQUEST

    def to_payload(self) -> dict[str, object]:
        return {
            "ok": False,
            "error": {
                "code": self.code,
                "message": self.message,
            },
        }


def error_response(code: str, message: str, *, status_code: int) -> AppError:
    return AppError(code=code, message=message, status_code=status_code)

from __future__ import annotations


def ok(data: dict | list | str | int | float | bool | None = None) -> dict[str, object]:
    return {
        "ok": True,
        "data": {} if data is None else data,
    }

from __future__ import annotations

import json
import logging
import logging.handlers
import sys
from datetime import UTC, datetime
from pathlib import Path

from project_file_platform.common.config import ServiceConfig


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def setup_logging(service_name: str, config: ServiceConfig) -> None:
    root_logger = logging.getLogger()
    if getattr(root_logger, "_pfp_logging_configured", False):
        return

    level = getattr(logging, config.log_level.upper(), logging.INFO)
    root_logger.setLevel(level)

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    formatter: logging.Formatter
    if config.log_json:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )

    if config.log_to_stdout:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)

    log_dir = Path(config.log_dir).resolve()
    log_dir.mkdir(parents=True, exist_ok=True)
    file_path = log_dir / f"{service_name}.log"

    rotating = logging.handlers.RotatingFileHandler(
        filename=file_path,
        maxBytes=config.log_file_max_mb * 1024 * 1024,
        backupCount=config.log_backup_count,
        encoding="utf-8",
    )
    rotating.setFormatter(formatter)
    root_logger.addHandler(rotating)

    root_logger._pfp_logging_configured = True

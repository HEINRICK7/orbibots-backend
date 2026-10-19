import logging
import logging.config
import os
from functools import lru_cache

from app.src.infra.setup.settings import PROJECT_ROOT, load_environment


@lru_cache(maxsize=1)
def configure_logging() -> None:
    load_environment()
    level_name = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    level = getattr(logging, level_name, None)
    if not isinstance(level, int):
        raise ValueError(f"Unsupported LOG_LEVEL: {level_name}")

    logging.config.fileConfig(
        PROJECT_ROOT / "app" / "logging.conf",
        disable_existing_loggers=False,
    )
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    for handler in root_logger.handlers:
        handler.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

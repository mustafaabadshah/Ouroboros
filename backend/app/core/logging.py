import logging
import sys
from app.core.config import settings

def setup_logger(name: str = "ouroboros") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        level_str = getattr(settings, "LOG_LEVEL", "INFO").upper()
        level = getattr(logging, level_str, logging.INFO)
        logger.setLevel(level)

        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False
    return logger

logger = setup_logger("ouroboros")

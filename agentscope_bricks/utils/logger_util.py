# -*- coding: utf-8 -*-
import logging
from typing import Optional, List


def get_logger(name: Optional[str] = "base") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level=logging.INFO)

    logger.handlers = get_logging_handlers()
    logger.propagate = False
    return logger


def get_logging_handlers() -> List[logging.StreamHandler]:
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(process)d - %(lineno)d- %(levelname)s - "
        "%(message)s",
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)

    logging_handlers = [console_handler]

    return logging_handlers


logger = get_logger()

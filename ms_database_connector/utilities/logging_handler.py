"""
Logging handler.

This module contains all methods and functions to handle the logging.
"""

import json
import logging
import queue
import sys
from datetime import UTC, datetime
from logging.handlers import QueueHandler
from pathlib import Path
from typing import ClassVar

from pythonjsonlogger import jsonlogger

LOG_FOLDER: str = "./_log"
LOG_FILE_SUFFIX: str = "_log.json"


class ColorCodes:
    """Define the color codes for the console output."""

    grey = "\x1b[38;21m"
    green = "\x1b[1;32m"
    yellow = "\x1b[33;21m"
    red = "\x1b[31;21m"
    bold_red = "\x1b[31;1m"
    blue = "\x1b[1;34m"
    light_blue = "\x1b[1;36m"
    purple = "\x1b[1;35m"
    reset = "\x1b[0m"


class CustomConsoleFormatter(logging.Formatter):
    """Custom console formatter for logging with colored level.

    :param logging: formatter
    """

    FORMATS: ClassVar[dict] = {
        logging.DEBUG: ColorCodes.blue + "%(levelname)s" + ColorCodes.reset + ":   %(message)s (%(filename)s:%(lineno)d)",
        logging.INFO: ColorCodes.green + "%(levelname)s" + ColorCodes.reset + ":   %(message)s",
        logging.WARNING: ColorCodes.yellow + "%(levelname)s" + ColorCodes.reset + ":   %(message)s",
        logging.ERROR: ColorCodes.red + "%(levelname)s" + ColorCodes.reset + ":    %(message)s (%(filename)s:%(lineno)d)",
        logging.CRITICAL: ColorCodes.bold_red + "%(levelname)s:  %(message)s (%(filename)s:%(lineno)d)" + ColorCodes.reset,
    }

    def format(self, record) -> str:
        """Format the log record.

        :param record: record to format
        :return: formatted record
        """
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def _handle_file_rotation(log_file_path: Path, max_file_count: int = 5) -> None:
    log_folder: Path = log_file_path.resolve()

    if max_file_count < 1:
        return

    if not log_folder.exists():
        return

    existing_log_files: list[Path] = [file for file in log_folder.iterdir() if file.name.endswith(LOG_FILE_SUFFIX)]

    if len(existing_log_files) < max_file_count:
        return

    existing_log_files.sort(key=lambda x: x.stat().st_ctime)

    files_to_delete: int = len(existing_log_files) - (max_file_count - 1)

    for file in existing_log_files[:files_to_delete]:
        file.unlink()

    return


def initialize_logging(console_level=logging.INFO) -> Path:
    """Initialize the standard logging.

    :param debug_mode_status: Status of the debug mode
    :param log_file_name: Name of the (path and extension)
    """
    log_path = Path(LOG_FOLDER).resolve()
    log_path.mkdir(parents=True, exist_ok=True)

    log_file_path = log_path / "api.log"

    log_file_format = "%(asctime)s %(levelname)s: %(message)s   (%(filename)s:%(lineno)d)"
    logging.basicConfig(
        filename=log_file_path,
        level=logging.DEBUG,
        format=log_file_format,
        filemode="w",
    )

    # set console logging
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(CustomConsoleFormatter())
    logging.getLogger("").addHandler(console_handler)

    # set queue logging
    log_queue: queue.Queue = queue.Queue(-1)  # Use default max size
    queue_handler = QueueHandler(log_queue)
    logging.getLogger("").addHandler(queue_handler)

    logger = logging.getLogger(__name__)
    script_path = Path(sys.argv[0])
    python_version = sys.version.replace("\n", "")

    logger.info("Initialize microservice log file")
    log_file_path = set_log_file()

    print("")
    logger.info(f"Run script '{script_path.name.replace('.py', '')}'")
    logger.info(f"Script executed by Python v{python_version}")
    logger.info("Logging initialized")

    return log_file_path.resolve()


def read_log_file_as_list(log_file_path: Path) -> list[dict]:
    """Read the log file as a list of dictionaries (Json conform).

    :param log_file_path: Path to the log file
    :return: list of dictionaries (Json conform)
    """
    with Path.open(log_file_path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def set_log_file(
    max_log_files: int = 10,
) -> Path:
    """Set the log file.

    :param max_log_files: max number of log files in folder, defaults to 5
    :return: log file path
    """
    logger = logging.getLogger()  # Get the root logger

    # Remove all existing file handlers
    for handler in logger.handlers[:]:
        if isinstance(handler, logging.FileHandler):
            logger.removeHandler(handler)
            handler.close()

    now = datetime.now(tz=UTC)
    time_string = now.strftime("%Y-%m-%d_%H-%M-%S")

    # handle log file and folder
    log_path: Path = Path(LOG_FOLDER).resolve()
    log_path = Path(LOG_FOLDER, "runtime").resolve()

    log_path.mkdir(parents=True, exist_ok=True)
    log_file_name = f"runtime{LOG_FILE_SUFFIX}"
    log_file_path = log_path / f"{time_string}_{log_file_name}"

    _handle_file_rotation(log_path, max_log_files)

    # Add a new file handler with the new log file path
    json_formatter = jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s %(filename)s %(lineno)d")
    json_file_handler = logging.FileHandler(log_file_path, mode="w")
    json_file_handler.setFormatter(json_formatter)
    json_file_handler.setLevel(logging.DEBUG)
    logger.addHandler(json_file_handler)

    logging.info(f"Maximum log file number is: {max_log_files}")  # noqa: LOG015
    logging.info(f"Write log file to: '{log_file_path}'")  # noqa: LOG015

    return log_file_path.resolve()

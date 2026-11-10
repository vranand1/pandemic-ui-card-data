"""One logging format for every script, so a full run reads as a single log.

Level comes from the LOG_LEVEL environment variable (default INFO). When LOG_FILE is set (run_all.sh sets it
to out/run.log), messages are also appended there, so the log of the last full run sits next to its outputs.
"""
import logging
import os
import sys

_FMT = "%(asctime)s %(levelname)-7s %(name)-14s %(message)s"
_configured = False


def get_logger(name: str) -> logging.Logger:
    """Return a module logger; configure the root handlers once per process."""
    global _configured
    if not _configured:
        handlers = [logging.StreamHandler(sys.stdout)]
        log_file = os.environ.get("LOG_FILE")
        if log_file:
            handlers.append(logging.FileHandler(log_file, mode="a", encoding="utf-8"))
        logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper(), format=_FMT,
                            datefmt="%H:%M:%S", handlers=handlers)
        logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)   # font fallback is not news
        _configured = True
    return logging.getLogger(name)

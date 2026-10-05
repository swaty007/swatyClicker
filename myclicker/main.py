"""Entry point: DPI awareness, administrator rights, logging, then the UI."""
from __future__ import annotations

import argparse
import faulthandler
import logging
import sys
import threading

from myclicker.paths import data_dir


def _log_crashes(data) -> None:
    """The windowed exe has no console: send every unhandled error to the log, and a hard crash of the
    interpreter (faulthandler) to crash.log, so a program that "just closed" leaves a trace."""
    faulthandler.enable(open(data / "crash.log", "a", encoding="utf-8"), all_threads=True)
    sys.excepthook = lambda *exc: logging.critical("unhandled error", exc_info=exc)
    threading.excepthook = lambda args: logging.critical(
        "unhandled error in thread %s", args.thread.name if args.thread else "?",
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback))


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    parser = argparse.ArgumentParser(prog="MyClicker")
    parser.add_argument("--no-elevate", action="store_true", help="не запрашивать права администратора")
    options = parser.parse_args(argv[1:])

    from myclicker.platform_win import api, elevation
    api.enable_dpi_awareness()

    warnings = []
    if not elevation.is_admin():
        if not options.no_elevate and elevation.relaunch_as_admin(argv):
            return 0
        warnings.append("Запущено без прав администратора: в игры, запущенные от администратора, ввод не дойдёт.")

    data = data_dir()
    data.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=data / "myclicker.log", level=logging.INFO, encoding="utf-8",
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    _log_crashes(data)

    from myclicker.app.controller import Controller, PlatformServices
    from myclicker.paths import app_dir
    from myclicker.platform_win.registry import build_input_methods
    from myclicker.platform_win.windows import Win32WindowFinder, window_under_cursor
    from myclicker.ui.app import App

    services = PlatformServices(methods=build_input_methods(app_dir()), finder=Win32WindowFinder(),
                                window_under_cursor=window_under_cursor)
    controller = Controller(data, services)
    try:
        App(controller, warnings).run()
    except Exception:
        logging.exception("fatal error")
        raise
    return 0

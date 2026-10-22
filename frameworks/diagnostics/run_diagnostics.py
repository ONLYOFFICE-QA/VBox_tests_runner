# -*- coding: utf-8 -*-
"""
File based diagnostics for runs that stop responding.

The module keeps a log of the phases a run goes through. While a phase is active it writes
heartbeats with the counters collected by the instrumentation and, at a larger interval, dumps the
stacks of every thread. The dumps tell whether the process waits on the VirtualBox API, on the
output of the guest or on the host side handling of the collected log.
"""
import faulthandler
import logging
import sys
import threading
import time
import traceback
from collections.abc import Callable
from contextlib import contextmanager
from os import getpid, makedirs
from os.path import join

from rich import print

from frameworks.test_data.paths import LocalPaths

try:
    import psutil
except ImportError:  # psutil is a transitive dependency, the diagnostics work without it
    psutil = None

_LOGGER_NAME = 'vbox_runner.diagnostics'
_LOG_FORMAT = '%(asctime)s.%(msecs)03d | %(levelname)-7s | %(threadName)-14s | %(message)s'
_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


class RunDiagnostics:
    """
    Writes the phases of a run to a log file and dumps thread stacks while a phase is running.
    """

    _HEARTBEAT_INTERVAL = 30
    _STACK_DUMP_INTERVAL = 300

    def __init__(self):
        self.log_path: str | None = None
        self.threads_log_path: str | None = None
        self._logger: logging.Logger | None = None
        self._threads_file = None
        self._watchdog: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.RLock()
        self._phases: list[list] = []
        self._state_providers: list[Callable[[], str]] = []
        self._started = False

    def start(self, name: str) -> str | None:
        """
        Start writing the diagnostics of a run, doing nothing when they are already running.
        :param name: Name used for the log files, e.g. conversion_KUbuntu.
        :return: Path of the log file, None when the log file could not be opened.
        """
        with self._lock:
            if self._started:
                return self.log_path

            try:
                directory = join(LocalPaths.reports_dir, 'diagnostics')
                makedirs(directory, exist_ok=True)
                prefix = f"{self._safe_name(name)}_{time.strftime('%Y%m%d_%H%M%S')}"
                self.log_path = join(directory, f'{prefix}.log')
                self.threads_log_path = join(directory, f'{prefix}_threads.log')
                self._logger = self._create_logger(self.log_path)
                # A line buffered file keeps the dumps readable when the process is killed.
                self._threads_file = open(self.threads_log_path, 'w', encoding='utf-8', buffering=1)
            except OSError as error:
                print(f"[red]|WARNING| Unable to start the diagnostics: {error}")
                self._logger, self.log_path, self.threads_log_path = None, None, None
                return None

            # faulthandler dumps from its own thread without the GIL, so the stacks are written
            # even when a call into the VirtualBox API never gives the interpreter back.
            faulthandler.enable(file=self._threads_file, all_threads=True)
            faulthandler.dump_traceback_later(
                self._STACK_DUMP_INTERVAL, repeat=True, file=self._threads_file
            )
            self._started = True

        self.log(
            f'diagnostics started | pid={getpid()} | python={sys.version.split()[0]} | '
            f'thread dumps={self.threads_log_path}'
        )
        self._push_phase(name)
        self._start_watchdog()
        return self.log_path

    def stop(self) -> None:
        """
        Stop the diagnostics and close the log files.
        """
        with self._lock:
            if not self._started:
                return
            self._started = False

        self.log('diagnostics stopped')
        self._stop_event.set()
        faulthandler.cancel_dump_traceback_later()

        with self._lock:
            self._phases.clear()
            if self._logger is not None:
                for handler in list(self._logger.handlers):
                    self._logger.removeHandler(handler)
                    handler.close()
                self._logger = None
            if self._threads_file is not None:
                self._threads_file.close()
                self._threads_file = None

    def log(self, message: str, level: int = logging.INFO) -> None:
        """
        Write a message to the diagnostics log, doing nothing when they are not running.
        :param message: Message to write.
        :param level: Logging level of the message.
        """
        logger = self._logger
        if logger is not None:
            logger.log(level, message)

    def warning(self, message: str) -> None:
        """
        Write a warning to the diagnostics log.
        :param message: Message to write.
        """
        self.log(message, level=logging.WARNING)

    def error(self, message: str) -> None:
        """
        Write an error to the diagnostics log.
        :param message: Message to write.
        """
        self.log(message, level=logging.ERROR)

    def log_tail(self, title: str, text: str, max_lines: int = 200) -> None:
        """
        Write the size of a collected output together with its last lines.

        The whole output is not written because a full conversion run produces megabytes of it.
        :param title: Name of the output, e.g. guest script log.
        :param text: Collected output.
        :param max_lines: Number of lines written to the log.
        """
        if self._logger is None:
            return
        lines = (text or '').splitlines()
        self.log(
            f'{title} | {len(text or "")} chars | {len(lines)} lines | last {max_lines} lines:\n'
            + '\n'.join(lines[-max_lines:])
        )

    @contextmanager
    def phase(self, name: str):
        """
        Mark a step of the run, so the heartbeats and the stack dumps tell where the run stands.
        :param name: Name of the step, e.g. stop_vm.
        """
        self._push_phase(name)
        started = time.monotonic()
        self.log(f'--> {name}')
        try:
            yield
        except BaseException as error:
            self.error(f'<-- {name} failed after {time.monotonic() - started:.1f}s: {error!r}')
            raise
        else:
            self.log(f'<-- {name} done in {time.monotonic() - started:.1f}s')
        finally:
            self._pop_phase()

    def register_state_provider(self, provider: Callable[[], str]) -> None:
        """
        Add a source of counters reported by every heartbeat.
        :param provider: Callable returning a single line with the current counters.
        """
        with self._lock:
            if provider not in self._state_providers:
                self._state_providers.append(provider)

    def dump_stacks(self, reason: str) -> None:
        """
        Write the stack of every thread to the diagnostics log.
        :param reason: Why the stacks are dumped, written next to them.
        """
        if self._logger is None:
            return

        names = {thread.ident: thread.name for thread in threading.enumerate()}
        lines = [f'stack dump | {reason}']
        for ident, frame in sys._current_frames().items():
            lines.append(f"--- thread {names.get(ident, 'unknown')} ({ident}) ---")
            lines.append(''.join(traceback.format_stack(frame)).rstrip())
        self.warning('\n'.join(lines))

    def current_phase(self) -> tuple:
        """
        Get the phase the run is in and how long it has been running.
        :return: Tuple with the path of the nested phase names and the seconds of the last one.
        """
        with self._lock:
            if not self._phases:
                return 'idle', 0.0
            return (
                ' > '.join(phase[0] for phase in self._phases),
                time.monotonic() - self._phases[-1][1]
            )

    def _push_phase(self, name: str) -> None:
        """
        Add a phase to the stack of the running phases.
        :param name: Name of the phase.
        """
        with self._lock:
            self._phases.append([name, time.monotonic()])

    def _pop_phase(self) -> None:
        """
        Remove the innermost phase from the stack of the running phases.
        """
        with self._lock:
            if self._phases:
                self._phases.pop()

    def _start_watchdog(self) -> None:
        """
        Start the thread writing the heartbeats and the periodic stack dumps.
        """
        with self._lock:
            if self._watchdog is not None and self._watchdog.is_alive():
                return
            self._stop_event.clear()
            self._watchdog = threading.Thread(target=self._watch, name='diagnostics', daemon=True)
            self._watchdog.start()

    def _watch(self) -> None:
        """
        Report the running phase until the diagnostics are stopped.
        """
        last_dump = time.monotonic()
        while not self._stop_event.wait(self._HEARTBEAT_INTERVAL):
            phase, elapsed = self.current_phase()
            self.log(f'heartbeat | {phase} | {elapsed:.0f}s | {self._memory()} | {self._state()}')
            if time.monotonic() - last_dump >= self._STACK_DUMP_INTERVAL:
                last_dump = time.monotonic()
                self.dump_stacks(f'{phase} running for {elapsed:.0f}s')

    def _state(self) -> str:
        """
        Collect the counters of the registered providers.
        :return: Single line with the counters.
        """
        with self._lock:
            providers = list(self._state_providers)

        states = []
        for provider in providers:
            try:
                states.append(provider())
            except Exception as error:  # pylint: disable=broad-except -- a probe must not break the run
                states.append(f'state unavailable: {error!r}')
        return ' | '.join(states)

    @staticmethod
    def _memory() -> str:
        """
        Read the memory the process uses, as the collected guest log is kept in memory.
        :return: Readable memory usage of the process.
        """
        if psutil is None:
            return 'rss=unknown'
        try:
            return f'rss={psutil.Process().memory_info().rss / (1024 * 1024):.1f}MB'
        except Exception as error:  # pylint: disable=broad-except -- psutil raises its own types
            return f'rss=unknown ({error!r})'

    @staticmethod
    def _safe_name(name: str) -> str:
        """
        Turn a run name into a name usable for a file.
        :param name: Name of the run.
        :return: Name with the characters a path cannot hold replaced.
        """
        return ''.join(char if char.isalnum() or char in '-_' else '_' for char in name) or 'run'

    @staticmethod
    def _create_logger(log_path: str) -> logging.Logger:
        """
        Build the logger writing to the diagnostics log file.
        :param log_path: Path of the log file.
        :return: Logger with a single file handler.
        """
        logger = logging.getLogger(_LOGGER_NAME)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()

        handler = logging.FileHandler(log_path, encoding='utf-8')
        handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
        logger.addHandler(handler)
        return logger


_diagnostics: RunDiagnostics | None = None
_diagnostics_lock = threading.Lock()


def diagnostics() -> RunDiagnostics:
    """
    Get the diagnostics of the process, creating them on first use.
    :return: Shared RunDiagnostics object.
    """
    global _diagnostics
    if _diagnostics is None:
        with _diagnostics_lock:
            if _diagnostics is None:
                _diagnostics = RunDiagnostics()
    return _diagnostics

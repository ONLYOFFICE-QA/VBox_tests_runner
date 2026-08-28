# -*- coding: utf-8 -*-
"""
Instrumentation of the vboxwrapper helpers used to drive a guest.

The helpers are wrapped instead of edited because vboxwrapper is installed as a dependency and is
replaced on every sync. Every wrapper reports what it did and how long it took, and the reader of
the guest output keeps counters that the heartbeats report, so a run that stops responding shows
whether the guest, the VirtualBox API or the host side handling of the collected log is to blame.
"""
import threading
import time

from rich import print
from vboxwrapper import FileUtils, VboxApi, VirtualMachine

_MAX_COMMAND_CHARS = 200
_SLOW_SESSION_SECONDS = 3.0


class GuestOutputStats:
    """
    Counters of the reader collecting the output of a guest process.
    """

    _STATUS_INTERVAL = 10.0

    def __init__(self):
        self._lock = threading.Lock()
        self.reset('')

    def reset(self, command: str) -> None:
        """
        Start counting the output of a new command.
        :param command: Command the counters belong to.
        """
        with self._lock:
            self._command = command
            self._started = time.monotonic()
            self._reads = 0
            self._stdout_chars = 0
            self._stderr_chars = 0
            self._read_seconds = 0.0
            self._status_bar_calls = 0
            self._status_bar_seconds = 0.0
            self._last_data = None
            self._status = None
            self._status_read = 0.0

    def record_read(self, handle: int, chars: int, seconds: float) -> None:
        """
        Add the result of a single read of an output stream of the guest process.
        :param handle: Stream that was read, 1 for the standard output and 2 for the standard error.
        :param chars: Number of characters the read returned.
        :param seconds: Time the read took.
        """
        with self._lock:
            self._reads += 1
            self._read_seconds += seconds
            if handle == FileUtils._STDERR_HANDLE:
                self._stderr_chars += chars
            else:
                self._stdout_chars += chars
            if chars:
                self._last_data = time.monotonic()

    def record_status_bar(self, seconds: float) -> None:
        """
        Add the time the reader spent on keeping the lines shown by the status bar.

        The counter tells how much of the run went into the handling of the collected log on the
        host instead of into the test on the guest.
        :param seconds: Time the call took.
        """
        with self._lock:
            self._status_bar_calls += 1
            self._status_bar_seconds += seconds

    def needs_status(self) -> bool:
        """
        Whether the status of the guest process should be read again.
        :return: True when the last status was read long enough ago.
        """
        with self._lock:
            if time.monotonic() - self._status_read < self._STATUS_INTERVAL:
                return False
            self._status_read = time.monotonic()
            return True

    def record_status(self, status) -> None:
        """
        Store the status the guest process reported.
        :param status: Value of the ProcessStatus enum or a message.
        """
        with self._lock:
            self._status = status

    def summary(self) -> str:
        """
        Build the line the heartbeats report.
        :return: Counters of the reader as a single line.
        """
        with self._lock:
            idle = 'never' if self._last_data is None else f'{time.monotonic() - self._last_data:.1f}s'
            return (
                f'guest output: reads={self._reads} '
                f'stdout={self._megabytes(self._stdout_chars)} '
                f'stderr={self._megabytes(self._stderr_chars)} '
                f'read_wait={self._read_seconds:.0f}s '
                f'status_bar_calls={self._status_bar_calls} '
                f'status_bar_time={self._status_bar_seconds:.0f}s '
                f'idle={idle} process_status={self._status} '
                f'elapsed={time.monotonic() - self._started:.0f}s'
            )

    @staticmethod
    def _megabytes(chars: int) -> str:
        """
        Format a number of characters as megabytes.
        :param chars: Number of characters.
        :return: Readable size.
        """
        return f'{chars / (1024 * 1024):.1f}MB'


stats = GuestOutputStats()
_installed = False


def install(diag) -> None:
    """
    Wrap the vboxwrapper helpers with diagnostics logging, doing nothing when already wrapped.
    :param diag: RunDiagnostics collecting the messages.
    """
    global _installed
    if _installed:
        return
    _installed = True

    try:
        _wrap_file_utils(diag)
        _wrap_api(diag)
        _wrap_virtual_machine(diag)
    except Exception as error:  # pylint: disable=broad-except -- diagnostics must not stop a test
        # vboxwrapper is installed from a branch, so a helper this module wraps can disappear.
        # Losing the counters is acceptable, losing a test that runs for hours is not.
        diag.error(f'vboxwrapper instrumentation not installed: {error!r}')
        print(f"[bold yellow]|WARNING| Diagnostics of the guest output are not available: {error}")
        return

    diag.register_state_provider(stats.summary)
    diag.log('vboxwrapper instrumentation installed')


def _wrap_file_utils(diag) -> None:
    """
    Wrap the guestcontrol helpers running commands and reading their output.
    :param diag: RunDiagnostics collecting the messages.
    """
    original_run_cmd = FileUtils.run_cmd
    original_read_output = FileUtils._read_output
    original_read_stream = FileUtils._read_stream
    original_collect_lines = getattr(FileUtils, '_collect_lines', None)
    original_exit_code = FileUtils._get_exit_code
    original_create_session = FileUtils._create_guest_session
    original_close_session = FileUtils._close_guest_session

    def run_cmd(self, command: str, *args, **kwargs):
        stats.reset(command)
        diag.log(f"run_cmd start | shell={kwargs.get('shell')} | {_short(command)}")
        started = time.monotonic()
        try:
            result = original_run_cmd(self, command, *args, **kwargs)
        except BaseException as error:
            diag.error(f'run_cmd raised after {time.monotonic() - started:.1f}s: {error!r}')
            raise
        diag.log(
            f'run_cmd done in {time.monotonic() - started:.1f}s | rc={result.returncode} | '
            f'stdout={len(result.stdout)} chars | stderr={len(result.stderr)} chars | {stats.summary()}'
        )
        return result

    def _read_output(self, process, command: str, *args, **kwargs):
        diag.log(f'reading the output of the guest process | {_short(command)}')
        started = time.monotonic()
        try:
            return original_read_output(self, process, command, *args, **kwargs)
        finally:
            diag.log(
                f'output of the guest process read in {time.monotonic() - started:.1f}s | '
                f'{stats.summary()}'
            )

    def _read_stream(self, process, handle: int) -> str:
        started = time.monotonic()
        data = original_read_stream(self, process, handle)
        stats.record_read(handle, len(data), time.monotonic() - started)
        if stats.needs_status():
            stats.record_status(_status(process))
        return data

    def _collect_lines(recent_lines, unfinished_line: str, chunk: str) -> str:
        started = time.monotonic()
        result = original_collect_lines(recent_lines, unfinished_line, chunk)
        stats.record_status_bar(time.monotonic() - started)
        return result

    def _get_exit_code(self, process) -> int:
        code = original_exit_code(self, process)
        diag.log(f'guest process finished | exit_code={code} | status={_status(process)}')
        return code

    def _create_guest_session(self, session, constants, *args, **kwargs):
        started = time.monotonic()
        try:
            return original_create_session(self, session, constants, *args, **kwargs)
        finally:
            duration = time.monotonic() - started
            if duration >= _SLOW_SESSION_SECONDS:
                diag.warning(f'opening the guest session took {duration:.1f}s')

    def _close_guest_session(self, guest_session, constants=None) -> None:
        started = time.monotonic()
        try:
            return original_close_session(self, guest_session, constants)
        finally:
            duration = time.monotonic() - started
            if duration >= _SLOW_SESSION_SECONDS:
                diag.warning(f'closing the guest session took {duration:.1f}s')

    FileUtils.run_cmd = run_cmd
    FileUtils._read_output = _read_output
    FileUtils._read_stream = _read_stream
    FileUtils._get_exit_code = _get_exit_code
    if original_collect_lines is not None:
        FileUtils._collect_lines = staticmethod(_collect_lines)
    FileUtils._create_guest_session = _create_guest_session
    FileUtils._close_guest_session = _close_guest_session


def _wrap_api(diag) -> None:
    """
    Wrap the wait on the asynchronous operations of the VirtualBox API, which never times out.
    :param diag: RunDiagnostics collecting the messages.
    """
    original_wait_progress = VboxApi.wait_progress.__func__

    def wait_progress(cls, progress, error_message: str, timeout: int = -1) -> None:
        started = time.monotonic()
        diag.log(f'waiting for a VirtualBox operation | timeout={timeout}ms')
        try:
            return original_wait_progress(cls, progress, error_message, timeout)
        finally:
            diag.log(f'VirtualBox operation waited for {time.monotonic() - started:.1f}s')

    VboxApi.wait_progress = classmethod(wait_progress)


def _wrap_virtual_machine(diag) -> None:
    """
    Wrap the machine operations run at the end of a test, where the machine stays powered on.
    :param diag: RunDiagnostics collecting the messages.
    """
    original_stop = VirtualMachine.stop
    original_wait_shutdown = VirtualMachine.wait_until_shutdown

    def stop(self, wait_until_shutdown: bool = True) -> None:
        diag.log(f'stop requested | {self.name} | state={_machine_state(self)}')
        started = time.monotonic()
        try:
            return original_stop(self, wait_until_shutdown=wait_until_shutdown)
        finally:
            diag.log(
                f'stop returned after {time.monotonic() - started:.1f}s | {self.name} | '
                f'state={_machine_state(self)}'
            )

    def wait_until_shutdown(self, *args, **kwargs) -> bool:
        started = time.monotonic()
        result = original_wait_shutdown(self, *args, **kwargs)
        diag.log(
            f'waited {time.monotonic() - started:.1f}s for the shutdown of {self.name} | '
            f'powered_off={result}'
        )
        return result

    VirtualMachine.stop = stop
    VirtualMachine.wait_until_shutdown = wait_until_shutdown


def _status(process) -> str:
    """
    Read the status of a guest process without breaking the caller.
    :param process: IGuestProcess to read.
    :return: Status value or the reason it could not be read.
    """
    try:
        return str(process.status)
    except Exception as error:  # pylint: disable=broad-except -- COM raises its own types
        return f'unreadable ({error!r})'


def _machine_state(vm) -> str:
    """
    Read the state of a machine without breaking the caller.
    :param vm: VirtualMachine to read.
    :return: Readable state or the reason it could not be read.
    """
    try:
        return VboxApi.state_name(vm.machine.state)
    except Exception as error:  # pylint: disable=broad-except -- COM raises its own types
        return f'unreadable ({error!r})'


def _short(command: str) -> str:
    """
    Cut a command down to a length a log line can hold.
    :param command: Command run on the guest.
    :return: Command with the middle removed when it is too long.
    """
    command = (command or '').replace('\n', ' ')
    if len(command) <= _MAX_COMMAND_CHARS:
        return command
    return f'{command[:_MAX_COMMAND_CHARS]}... ({len(command)} chars)'

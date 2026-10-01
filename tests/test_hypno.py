import sys
from contextlib import contextmanager
from subprocess import Popen, PIPE
from pathlib import Path
from threading import Thread, current_thread, Event
from time import sleep

import pytest
from pytest import mark, param

import hypno.api
from hypno import inject_py, CodeTooLongException, run_in_thread
from hypno.api import REMOTE_EXEC_AVAILABLE

WHILE_TRUE_SCRIPT = Path(__file__).parent.resolve() / 'while_true.py'
SLEEPING_TARGET_SCRIPT = Path(__file__).parent.resolve() / 'sleeping_target.py'
SLEEPING_TARGET_SECONDS = 3
PROCESS_WAIT_TIMEOUT = 5
WAIT_FOR_PYTHON_SECONDS = 0.75
PY314 = sys.version_info[:2] >= (3, 14)
WINDOWS = sys.platform == 'win32'

skip_no_remote_exec = mark.skipif(not REMOTE_EXEC_AVAILABLE, reason='sys.remote_exec requires CPython 3.14+')
skip_unsafe_on_314 = mark.skipif(PY314, reason='immediate injection aborts the target on CPython >= 3.14')
skip_thread_unsupported = mark.skipif(PY314 or WINDOWS,
                                      reason='run_in_thread needs CPython < 3.14 and a non-Windows platform')


def _python() -> str:
    # In new virtualenv versions on Windows, python.exe re-launches the real python.exe as a subprocess, so
    # we inject into the interpreter that actually runs the script.
    return getattr(sys, '_base_executable', sys.executable)


@contextmanager
def running_target(script: Path = WHILE_TRUE_SCRIPT):
    process = Popen([_python(), str(script)], stdin=PIPE, stdout=PIPE, stderr=PIPE)
    try:
        sleep(WAIT_FOR_PYTHON_SECONDS)
        yield process
    finally:
        process.kill()


def _inject_and_wait(process: Popen) -> None:
    data = b'test_data_woohoo'
    inject_py(process.pid, b'print("' + data + b'", end=""); __import__("__main__").should_exit = True')
    assert process.wait(PROCESS_WAIT_TIMEOUT) == 0
    assert process.stdout.read() == data


def test_inject_py():
    with running_target() as process:
        _inject_and_wait(process)


def test_inject_py_without_remote_exec(monkeypatch):
    # Exercise the pyinjector fallback even where sys.remote_exec is available
    monkeypatch.setattr(hypno.api, 'REMOTE_EXEC_AVAILABLE', False)
    with running_target() as process:
        _inject_and_wait(process)


# Reports whether the injected code ran at a safe point: on the main thread, after the C call it was injected
# during had returned (rather than re-entering the interpreter in the middle of it).
SAFE_POINT_PROBE = (b'import threading, time; m = __import__("__main__"); '
                    b'print(threading.current_thread() is threading.main_thread(), '
                    b'time.monotonic() - m.sleep_started >= m.SLEEP_SECONDS, end=""); '
                    b'm.should_exit = True')


def _probe_safe_point(inject) -> bytes:
    with running_target(SLEEPING_TARGET_SCRIPT) as process:
        inject(process.pid)
        assert process.wait(PROCESS_WAIT_TIMEOUT + SLEEPING_TARGET_SECONDS) == 0
        return process.stdout.read()


@mark.parametrize('remote_exec', [param(True, marks=skip_no_remote_exec), False])
def test_inject_py_runs_at_safe_point(monkeypatch, remote_exec: bool):
    monkeypatch.setattr(hypno.api, 'REMOTE_EXEC_AVAILABLE', remote_exec)
    assert _probe_safe_point(lambda pid: inject_py(pid, SAFE_POINT_PROBE)) == b'True True'


@skip_unsafe_on_314
def test_safe_point_probe_detects_immediate_injection():
    # Control: the old immediate injection runs the code in the middle of the C call, which the probe must catch
    result = _probe_safe_point(lambda pid: hypno.api._inject_via_pyinjector(pid, SAFE_POINT_PROBE, 0o644,
                                                                            immediate=True))
    assert result == b'True False'


def test_inject_py_repeatedly():
    with running_target() as process:
        for _ in range(3):
            inject_py(process.pid, b'print("x", end="")')
            sleep(0.2)
        inject_py(process.pid, b'__import__("__main__").should_exit = True')
        assert process.wait(PROCESS_WAIT_TIMEOUT) == 0
        assert process.stdout.read() == b'xxx'


def test_inject_py_with_too_long_code(monkeypatch):
    # The size limit only applies to the pyinjector payload (remote_exec has none).
    monkeypatch.setattr(hypno.api, 'REMOTE_EXEC_AVAILABLE', False)
    with pytest.raises(CodeTooLongException):
        inject_py(-1, b'^' * 100000)


# ---- run_in_thread ----

def _wait_forever(event: Event) -> None:
    event.wait()


@contextmanager
def background_thread(name: str):
    event = Event()
    thread = Thread(name=name, target=_wait_forever, args=(event,))
    thread.start()
    try:
        yield thread
    finally:
        event.set()
        thread.join()


def _is_ptrace_denied(message: str) -> bool:
    # run_in_thread's child process must ptrace us; some sandboxes (e.g. ptrace_scope=2, seccomp) forbid it.
    lowered = message.lower()
    return any(s in lowered for s in ('permission', 'not permitted', 'operation not permitted', 'ptrace'))


def _run_in_thread_or_skip(thread, func, *args, **kwargs):
    try:
        return run_in_thread(thread, func, *args, **kwargs)
    except RuntimeError as e:
        if not _is_ptrace_denied(str(e)):
            raise
        pytest.skip(f'run_in_thread needs ptrace permission unavailable in this environment: {e}')


@skip_thread_unsupported
def test_run_in_thread_runs_on_target_thread():
    name = 'my-target-thread'
    with background_thread(name) as thread:
        result = _run_in_thread_or_skip(thread, lambda suffix: current_thread().name + suffix, '!')
    assert result == name + '!'


@skip_thread_unsupported
def test_run_in_thread_propagates_exception():
    with background_thread('t') as thread:
        _run_in_thread_or_skip(thread, lambda: None)  # skip if ptrace-of-parent isn't permitted here
        with pytest.raises(ZeroDivisionError):
            run_in_thread(thread, lambda: 1 // 0)


@skip_thread_unsupported
def test_run_in_thread_dead_thread():
    with background_thread('t') as thread:
        pass  # joined on context exit
    with pytest.raises(RuntimeError):
        run_in_thread(thread, lambda: None)


@skip_thread_unsupported
def test_run_in_thread_from_script_without_main_guard(tmp_path: Path):
    # The helper process must not re-run the calling script, as multiprocessing's spawn would
    script = tmp_path / 'script.py'
    script.write_text('import threading, hypno\n'
                      'event = threading.Event()\n'
                      'thread = threading.Thread(target=event.wait, daemon=True)\n'
                      'thread.start()\n'
                      'print(hypno.run_in_thread(thread, lambda: threading.current_thread() is thread))\n'
                      'event.set()\n')
    process = Popen([sys.executable, str(script)], stdout=PIPE, stderr=PIPE)
    out, err = process.communicate(timeout=30)
    if _is_ptrace_denied(err.decode(errors='replace')):
        pytest.skip(f'run_in_thread needs ptrace permission unavailable in this environment: {err!r}')
    assert out.strip() == b'True', err


@mark.skipif(not (PY314 or WINDOWS), reason='only where run_in_thread is intentionally unsupported')
def test_run_in_thread_unsupported_raises():
    with background_thread('t') as thread:
        with pytest.raises(NotImplementedError):
            run_in_thread(thread, lambda: None)

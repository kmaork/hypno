import sys
from contextlib import contextmanager
from subprocess import Popen, PIPE
from pathlib import Path
from threading import Thread, current_thread, Event

import pytest
from pytest import mark
from hypno import inject_py, CodeTooLongException, run_in_thread
from time import sleep

WHILE_TRUE_SCRIPT = Path(__file__).parent.resolve() / 'while_true.py'
PROCESS_WAIT_TIMEOUT = 1.5
WAIT_FOR_PYTHON_SECONDS = 0.75


@mark.parametrize('immediate_but_unsafe', [True, False])
def test_inject_py(immediate_but_unsafe):
    # In new virtualenv versions on Windows, python.exe invokes the original python.exe as a subprocess, so the
    # injection does not affect the target python process.
    python = getattr(sys, '_base_executable', sys.executable)
    data = b'test_data_woohoo'
    process = Popen([python, str(WHILE_TRUE_SCRIPT)], stdin=PIPE, stdout=PIPE)
    try:
        sleep(WAIT_FOR_PYTHON_SECONDS)
        inject_py(process.pid, b'print("' + data + b'", end=""); __import__("__main__").should_exit = True',
                  immediate_but_unsafe=False)
        assert process.wait(PROCESS_WAIT_TIMEOUT) == 0
        assert process.stdout.read() == data
    finally:
        process.kill()


def test_inject_py_with_too_long_code():
    code = b'^' * 100000
    with pytest.raises(CodeTooLongException):
        inject_py(-1, code)


def wait(event: Event, timeout=0.1):
    while not event.wait(timeout):
        pass


@contextmanager
def create_thread(name: str):
    event = Event()
    thread = Thread(name=name, target=wait, args=(event,))
    thread.start()
    try:
        yield thread
    finally:
        event.set()
        thread.join()


def test_run_in_thread():
    expected_suffix = 'bla'
    name = 'thread name lol'
    with create_thread(name) as thread:
        result = run_in_thread(thread, lambda suffix: current_thread().name + suffix, expected_suffix)
    assert result == name + expected_suffix

# TODO: make test pass
#       test with exception
#       test with non-running thread
#       test delay of each method when target is in syscall and in c call

import sys
from subprocess import Popen, PIPE
from pathlib import Path
import pytest
from pytest import mark, fixture

from hypno import inject_py, CodeTooLongException

WHILE_TRUE_SCRIPT = Path(__file__).parent.resolve() / 'while_true.py'
PROCESS_WAIT_TIMEOUT = 1.5


@fixture
def process_output():
    return 'bla\n'


@fixture
def process(process_output):
    # In new virtualenv versions on Windows, python.exe invokes the original python.exe as a subprocess, so the
    # injection does not affect the target python process.
    python = getattr(sys, '_base_executable', sys.executable)
    process = Popen([python, str(WHILE_TRUE_SCRIPT), process_output], stdin=PIPE, stdout=PIPE, stderr=PIPE)
    # Wait for process to start
    process.stderr.read(len(process_output))
    yield process
    process.kill()


def start_in_thread_code(code: bytes, use_thread: bool) -> bytes:
    if not use_thread:
        return code
    assert b"\n" not in code, "Unsupported in current impl"
    return b"from threading import Thread\ndef x():" + code + b"\nThread(target=x).start()"


@mark.parametrize('times', [1, 2, 3])
@mark.parametrize('thread', [True, False])
def test_hypno(process: Popen, times: int, thread: bool, process_output: str):
    if thread and sys.platform == "win32":
        pytest.xfail("Starting a thread from injection makes inject() never return on windows")
    data = b'test_data_woohoo'
    for _ in range(times - 1):
        inject_py(process.pid, start_in_thread_code(b'print("' + data + b'", end="");', thread))
        # Making sure the process is still working
        process.stderr.read(len(process_output))
    inject_py(process.pid, start_in_thread_code(b'__import__("__main__").should_exit = True', thread))
    assert process.wait(PROCESS_WAIT_TIMEOUT) == 0
    assert process.stdout.read() == data * (times - 1)


def test_hypno_with_too_long_code():
    code = b'^' * 100000
    with pytest.raises(CodeTooLongException):
        inject_py(-1, code)

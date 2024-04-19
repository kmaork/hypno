import sys
from subprocess import Popen, PIPE
from pathlib import Path
import pytest
from pytest import mark, fixture

from hypno import inject_py, CodeTooLongException

WHILE_TRUE_SCRIPT = Path(__file__).parent.resolve() / 'while_true.py'
PROCESS_WAIT_TIMEOUT = 1.5


@fixture
def process_loop_output():
    return 'loop!'


@fixture
def process_end_output():
    return 'end!'


@fixture
def process(process_loop_output, process_end_output):
    # In new virtualenv versions on Windows, python.exe invokes the original python.exe as a subprocess, so the
    # injection does not affect the target python process.
    python = getattr(sys, '_base_executable', sys.executable)
    process = Popen([python, str(WHILE_TRUE_SCRIPT), process_loop_output, process_end_output], stdin=PIPE, stdout=PIPE,
                    stderr=PIPE)
    # Wait for process to start
    process.stderr.read(len(process_loop_output))
    yield process
    process.kill()


def start_in_thread_code(code: bytes, use_thread: bool) -> bytes:
    if not use_thread:
        return code
    assert b"\n" not in code, "Unsupported in current impl"
    return b"from threading import Thread\ndef x():" + code + b"\nThread(target=x).start()"


@mark.parametrize('times', [0, 1, 2, 3])
@mark.parametrize('thread', [True, False])
def test_hypno(process: Popen, times: int, thread: bool, process_loop_output: str, process_end_output: str):
    if thread and (sys.platform == "win32" or (sys.platform == "darwin" and sys.version_info[:2] == (3, 8))):
        pytest.xfail("Starting a thread from injection makes inject() never return on windows, "
                     "and output an exception on macos in python 3.8")
    data = b'test_data_woohoo'
    for _ in range(times - 1):
        inject_py(process.pid, start_in_thread_code(b'print("' + data + b'", end="");', thread))
        # Making sure the process is still working
        process.stderr.read(len(process_loop_output))
    inject_py(process.pid, start_in_thread_code(b'__import__("__main__").should_exit = True', thread))
    assert process.wait(PROCESS_WAIT_TIMEOUT) == 0

    stdout = process.stdout.read()
    stderr = process.stderr.read()
    assert stderr.endswith(process_end_output.encode()), stderr
    assert stdout == data * (times - 1), stdout


def test_hypno_with_too_long_code():
    code = b'^' * 100000
    with pytest.raises(CodeTooLongException):
        inject_py(-1, code)

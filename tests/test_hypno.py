import sys
from subprocess import Popen, PIPE
from pathlib import Path
import pytest
from pytest import mark

from hypno import inject_py, CodeTooLongException
from time import sleep


WHILE_TRUE_SCRIPT = Path(__file__).parent.resolve() / 'while_true.py'
PROCESS_WAIT_TIMEOUT = 1.5
WAIT_FOR_PYTHON_SECONDS = 0.75


@mark.parametrize('times', [1, 2, 3])
def test_hypno(times: int):
    # In new virtualenv versions on Windows, python.exe invokes the original python.exe as a subprocess, so the
    # injection does not affect the target python process.
    python = getattr(sys, '_base_executable', sys.executable)
    data = b'test_data_woohoo'
    process = Popen([python, str(WHILE_TRUE_SCRIPT)], stdin=PIPE, stdout=PIPE)
    try:
        sleep(WAIT_FOR_PYTHON_SECONDS)
        for _ in range(times - 1):
            inject_py(process.pid, b'print("' + data + b'", end="");')
        inject_py(process.pid, b'__import__("__main__").should_exit = True')
        assert process.wait(PROCESS_WAIT_TIMEOUT) == 0
        assert process.stdout.read() == data * (times - 1)
    finally:
        process.kill()


def test_hypno_with_too_long_code():
    code = b'^' * 100000
    with pytest.raises(CodeTooLongException):
        inject_py(-1, code)

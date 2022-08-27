import sys
from subprocess import Popen, PIPE, TimeoutExpired
from pathlib import Path
import pytest
from hypno import inject_py, CodeTooLongException
from time import sleep


WHILE_TRUE_SCRIPT = Path(__file__).parent.resolve() / 'while_true.py'
PROCESS_WAIT_TIMEOUT = 1
WAIT_FOR_PYTHON_SECONDS = 0.5


def test_hypno():
    data = b'test_data_woohoo'
    process = Popen([sys.executable, str(WHILE_TRUE_SCRIPT)], stdin=PIPE, stdout=PIPE)
    try:
        sleep(WAIT_FOR_PYTHON_SECONDS)
        inject_py(process.pid, b'print("' + data + b'", end=""); __import__("__main__").should_exit = True')
        assert process.wait(PROCESS_WAIT_TIMEOUT) == 0
        assert process.stdout.read() == data
    finally:
        process.kill()


def test_hypno_with_too_long_code():
    code = b'^' * 100000
    with pytest.raises(CodeTooLongException):
        inject_py(-1, code)

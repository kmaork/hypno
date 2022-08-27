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
    with Popen([sys.executable, WHILE_TRUE_SCRIPT], stdin=PIPE, stdout=PIPE) as process:
        sleep(WAIT_FOR_PYTHON_SECONDS)
        inject_py(process.pid, b'print("' + data + b'", end="");'
                                                   b'import sys;'
                                                   b'sys.settrace(lambda *a: exit())')
        try:
            assert process.wait(PROCESS_WAIT_TIMEOUT) == 0
        except TimeoutExpired:
            process.kill()
            raise
        assert process.stdout.read() == data


def test_hypno_with_too_long_code():
    code = b'^' * 100000
    with pytest.raises(CodeTooLongException):
        inject_py(-1, code)

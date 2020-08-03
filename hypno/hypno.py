from importlib.util import find_spec
from typing import AnyStr

from pyinjector import inject
from os import urandom, unlink
from shutil import copy
from pathlib import Path

DATA_DIR = Path('/tmp/hypno')
DATA_DIR.mkdir(parents=True, exist_ok=True)

injection_lib_path = Path(find_spec('.injection', __package__).origin)


def inject_py(pid: int, python_code: AnyStr) -> None:
    if isinstance(python_code, str):
        python_code = python_code.encode()
    copied_lib = DATA_DIR / f'{urandom(3).hex()}-{python_code.hex()}'
    copy(injection_lib_path, copied_lib)
    inject(pid, str(copied_lib))
    unlink(copied_lib)

import os
from importlib.util import find_spec
from typing import AnyStr
from pyinjector import inject
from pyinjector.pyinjector import InjectorError
from tempfile import NamedTemporaryFile
from pathlib import Path

INJECTION_LIB_PATH = Path(find_spec('.injection', __package__).origin)
MAGIC = b'--- hypno code start ---'
WINDOWS = os.name == 'nt'


class CodeTooLongException(Exception):
    def __init__(self, code: bytes, max_size: int):
        super().__init__(f'The given python code is too long ({len(code)}). The maximum length is {max_size}.\n'
                         f'Consider writing the code to a file and executing it with runpy.run_path.\n'
                         f'Also, please report this on https://github.com/kmaork/hypno/issues/new')


def inject_py(pid: int, python_code: AnyStr) -> None:
    if isinstance(python_code, str):
        python_code = python_code.encode()
    lib = INJECTION_LIB_PATH.read_bytes()
    magic_addr = lib.find(MAGIC)
    code_addr = magic_addr - 1
    max_size_addr = magic_addr + len(MAGIC)
    max_size_end_addr = lib.find(b'\0', max_size_addr)
    max_size = int(lib[max_size_addr:max_size_end_addr])
    if len(python_code) > max_size:
        raise CodeTooLongException(python_code, max_size)
    name = None
    try:
        # Can't delete a loaded shared library on Windows
        with NamedTemporaryFile(prefix='hypno', suffix=INJECTION_LIB_PATH.suffix, delete=False) as temp:
            name = temp.name
            temp.write(lib[:code_addr])
            temp.write(python_code)
            temp.write(b'\0')
            temp.write(lib[code_addr + len(python_code) + 1:])
        try:
            inject(pid, str(temp.name))
        except InjectorError as e:
            # On Windows we are failing the load on purpose so the library will be immediately unloaded
            if not WINDOWS or e.ret_val != -5 or e.error_str != \
                    "LoadLibrary in the target process failed: " \
                    "A dynamic link library (DLL) initialization routine failed.":
                raise
    finally:
        if name is not None and Path(name).exists():
            Path(name).unlink()

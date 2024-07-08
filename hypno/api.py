import sys
from importlib.util import find_spec
from typing import AnyStr
from pyinjector import inject, InjectorError
from tempfile import NamedTemporaryFile
from pathlib import Path


INJECTION_LIB_PATH = Path(find_spec('.injection', __package__).origin)
MAGIC = b'--- hypno code start ---'
MAGIC2 = b'--- hypno script path start ---'
WINDOWS = sys.platform == 'win32'


class CodeTooLongException(Exception):
    def __init__(self, code: bytes, max_size: int):
        super().__init__(f'The given python code is too long ({len(code)}). The maximum length is {max_size}.\n'
                         f'Consider writing the code to a file and executing it with runpy.run_path.\n'
                         f'Also, please report this on https://github.com/kmaork/hypno/issues/new')


def inject_py(pid: int, python_code: AnyStr, permissions=0o644) -> None:
    """
    :param pid: PID of target python process
    :param python_code: Python code to inject to the target process.
    :param permissions: Permissions of the generated shared library file that will be injected to the target process.
                        Make sure the file is readable from the target process. By default, all users can read the file.
    """
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
    path = None
    try:
        # delete=False because can't delete a loaded shared library on Windows
        with NamedTemporaryFile(prefix='hypno', suffix=INJECTION_LIB_PATH.suffix, delete=False) as temp:
            path = Path(temp.name)
            temp.write(lib[:code_addr])
            temp.write(python_code)
            temp.write(b'\0')
            temp.write(lib[code_addr + len(python_code) + 1:])
        path.chmod(permissions)
        inject(pid, str(temp.name), uninject=True)
    finally:
        if path is not None and path.exists():
            path.unlink()

def inject_py_script(pid: int, python_script: Path, permissions=0o644) -> None:
    """
    :param pid: PID of target python process
    :param python_script: Path to python script to inject to the target process.
    :param permissions: Permissions of the generated shared library file that will be injected to the target process.
                        Make sure the file is readable from the target process. By default, all users can read the file.
    """

    script_path_null_terminated = str(python_script).encode() + b'\0'

    lib = INJECTION_LIB_PATH.read_bytes()
    magic_addr = lib.find(MAGIC2)
    path_str_addr = magic_addr - 1
    # max_size_addr = magic_addr + len(MAGIC2)
    # max_size_end_addr = lib.find(b'\0', max_size_addr)
    # max_size = int(lib[max_size_addr:max_size_end_addr])

    # if len(script_path_null_terminated) => max_size:
    #     raise CodeTooLongException(script_path_null_terminated, max_size)

    patched_lib = bytearray(lib)
    patched_lib[path_str_addr:(path_str_addr + len(script_path_null_terminated))] = script_path_null_terminated

    path = None
    try:
        # delete=False because can't delete a loaded shared library on Windows
        with NamedTemporaryFile(prefix='hypno', suffix=INJECTION_LIB_PATH.suffix, delete=False) as temp:
            path = Path(temp.name)
            temp.write(patched_lib)
        path.chmod(permissions)
        inject(pid, str(temp.name), uninject=True)
    finally:
        if path is not None and path.exists():
            path.unlink()

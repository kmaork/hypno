import os
from importlib.util import find_spec
from threading import Thread, current_thread, Event
from typing import AnyStr
from pyinjector import inject
from pyinjector.pyinjector import InjectorError
from tempfile import NamedTemporaryFile
from pathlib import Path

INJECTION_LIB_PATH = Path(find_spec('.injection', __package__).origin)
CODE_START_MARKER = b'--- hypno code start ---'
SAFE_MARKER = b'--- hypno safe marker ---'
WINDOWS = os.name == 'nt'
THREAD_COMMANDS = {}


class CodeTooLongException(Exception):
    def __init__(self, code: bytes, max_size: int):
        super().__init__(f'The given python code is too long ({len(code)}). The maximum length is {max_size}.\n'
                         f'Consider writing the code to a file and executing it with runpy.run_path.\n'
                         f'Also, please report this on https://github.com/kmaork/hypno/issues/new')


def override(data: bytearray, index: int, new: bytes) -> None:
    data[index: index + len(new)] = new


def verify_max_size(lib: bytearray, code: bytes, marker_addr: int):
    max_size_addr = marker_addr + len(CODE_START_MARKER)
    max_size_end_addr = lib.find(b'\0', max_size_addr)
    max_size = int(lib[max_size_addr:max_size_end_addr])
    if len(code) > max_size:
        raise CodeTooLongException(code, max_size)


def patch_lib_code(lib: bytearray, code: bytes) -> None:
    marker_addr = lib.find(CODE_START_MARKER)
    assert marker_addr >= 0
    code_addr = marker_addr - 1
    verify_max_size(lib, code, marker_addr)
    override(lib, code_addr, code + b'\0')


def patch_lib_safe(lib: bytearray, safe: bool) -> None:
    marker_addr = lib.find(SAFE_MARKER)
    assert marker_addr >= 0
    override(lib, marker_addr - 1, b'\1' if safe else b'\0')


def inject_py(pid: int, python_code: AnyStr, immediate_but_unsafe=False) -> None:
    if isinstance(python_code, str):
        python_code = python_code.encode()
    lib = bytearray(INJECTION_LIB_PATH.read_bytes())
    patch_lib_code(lib, python_code)
    patch_lib_safe(lib, not immediate_but_unsafe)
    name = None
    try:
        # Can't delete a loaded shared library on Windows
        with NamedTemporaryFile(prefix='hypno', suffix=INJECTION_LIB_PATH.suffix, delete=False) as temp:
            name = temp.name
            temp.write(lib)
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


class ThreadCommand:
    def __init__(self, func: callable, args: tuple, kwargs: dict):
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.result = None
        self.success = None
        self.done = Event()

    def execute(self):
        try:
            self.result = self.func(*self.args, **self.kwargs)
        except Exception as e:
            self.success = False
            self.result = e
        else:
            self.success = True
        self.done.set()

    def get_result(self):
        self.done.wait()
        if self.success:
            return self.result
        raise self.result


def run_in_thread(thread: Thread, func: callable, *args, **kwargs):
    if not thread.is_alive():
        raise RuntimeError(f'Given thread is not alive: {thread}')
    thread_id = current_thread().native_id
    command = ThreadCommand(func, args, kwargs)
    THREAD_COMMANDS[thread_id, thread.native_id] = command
    try:
        from multiprocessing import Pool
        with Pool(1) as pool:
            # Can't directly ptrace a fellow thread :(
            pool.apply(func=inject_py,
                       args=(thread.native_id,
                             f'__import__("sys").modules[{__name__!r}].'
                             f'THREAD_COMMANDS[{thread_id},{thread.native_id}].execute()'),
                       kwds=dict(immediate_but_unsafe=True))
        return command.get_result()
    finally:
        del THREAD_COMMANDS[thread_id, thread.native_id]

from __future__ import annotations
import ctypes
import os
import subprocess
import sys
import warnings
from importlib.util import find_spec
from threading import Thread, current_thread
from tempfile import NamedTemporaryFile
from pathlib import Path
from typing import Any, AnyStr, Callable, Dict, Optional, Tuple

INJECTION_LIB_PATH = Path(find_spec('.injection', __package__).origin)
CODE_START_MARKER = b'--- hypno code start ---'
SAFE_MARKER = b'--- hypno safe marker ---'
WINDOWS = sys.platform == 'win32'

# sys.remote_exec (PEP 768) landed in CPython 3.14 and lets us run code in a
# target process without ptrace-based library injection - i.e. without
# pyinjector. It requires the target to run the *same* CPython minor version.
REMOTE_EXEC_AVAILABLE = hasattr(sys, 'remote_exec')


class CodeTooLongException(Exception):
    def __init__(self, code: bytes, max_size: int):
        super().__init__(f'The given python code is too long ({len(code)}). The maximum length is {max_size}.\n'
                         f'Consider writing the code to a file and executing it with runpy.run_path.\n'
                         f'Also, please report this on https://github.com/kmaork/hypno/issues/new')


def _override(data: bytearray, index: int, new: bytes) -> None:
    data[index: index + len(new)] = new


def _verify_max_size(lib: bytearray, code: bytes, marker_addr: int) -> None:
    max_size_addr = marker_addr + len(CODE_START_MARKER)
    max_size_end_addr = lib.find(b'\0', max_size_addr)
    max_size = int(lib[max_size_addr:max_size_end_addr])
    if len(code) > max_size:
        raise CodeTooLongException(code, max_size)


def _patch_lib_code(lib: bytearray, code: bytes) -> None:
    marker_addr = lib.find(CODE_START_MARKER)
    assert marker_addr >= 0
    code_addr = marker_addr - 1
    _verify_max_size(lib, code, marker_addr)
    _override(lib, code_addr, code + b'\0')


def _patch_lib_safe(lib: bytearray, safe: bool) -> None:
    marker_addr = lib.find(SAFE_MARKER)
    assert marker_addr >= 0
    _override(lib, marker_addr - 1, b'\1' if safe else b'\0')


def _inject_via_pyinjector(pid: int, python_code: bytes, permissions: int, immediate: bool) -> None:
    # Imported lazily so hypno works without pyinjector where sys.remote_exec suffices.
    from pyinjector import inject, InjectorError

    lib = bytearray(INJECTION_LIB_PATH.read_bytes())
    _patch_lib_code(lib, python_code)
    _patch_lib_safe(lib, not immediate)
    path = None
    try:
        # delete=False because a loaded shared library can't be deleted on Windows.
        with NamedTemporaryFile(prefix='hypno', suffix=INJECTION_LIB_PATH.suffix, delete=False) as temp:
            path = Path(temp.name)
            temp.write(lib)
        path.chmod(permissions)
        try:
            # The safe path runs the code later (at a safe point), so we can't
            # uninject the library here - it must stay mapped until it runs.
            inject(pid, str(path))
        except InjectorError as e:
            # On Windows we fail the DLL load on purpose so it's unloaded
            # immediately; that surfaces as this specific error, which is fine.
            if not (WINDOWS and e.ret_val == -5 and e.error_str ==
                    "LoadLibrary in the target process failed: "
                    "A dynamic link library (DLL) initialization routine failed."):
                raise
    finally:
        if path is not None and path.exists():
            path.unlink()


def _inject_via_remote_exec(pid: int, python_code: bytes) -> None:
    if not REMOTE_EXEC_AVAILABLE:
        raise RuntimeError(
            "sys.remote_exec requires CPython 3.14+, and the target must run the same CPython minor version.")
    with NamedTemporaryFile(prefix='hypno', suffix='.py', delete=False) as temp:
        path = Path(temp.name)
        # The target reads and compiles the whole script before running it, so
        # having the script delete its own file first thing cleans up with no race.
        temp.write(f"import os as _hypno_os\n"
                   f"try:\n    _hypno_os.unlink({str(path)!r})\nexcept OSError:\n    pass\n".encode())
        temp.write(python_code)
        if not python_code.endswith(b"\n"):
            temp.write(b"\n")
    try:
        sys.remote_exec(pid, str(path))  # type: ignore[attr-defined]
    except BaseException:
        # The target never ran (and self-deleted) the script; clean it up.
        try:
            path.unlink()
        except OSError:
            pass
        raise


def inject_py(pid: int, python_code: AnyStr, permissions: int = 0o644) -> None:
    """
    Inject and run Python code in a running Python process.

    The code always runs on the target's main thread, at its interpreter's next safe point (between bytecodes,
    never in the middle of a C call). When this interpreter has sys.remote_exec (PEP 768, CPython 3.14+) and the
    target is compatible with it, that is used. Otherwise hypno injects a small library with pyinjector, which
    only schedules the code (Py_AddPendingCall) for the interpreter to run.

    :param pid: PID of the target Python process.
    :param python_code: Python code to run in the target process.
    :param permissions: Permissions of the temporary library file injected by the pyinjector fallback.
                        Make sure the target process can read it. By default, all users can read it.
    """
    if isinstance(python_code, str):
        python_code = python_code.encode()
    assert isinstance(python_code, bytes)
    if REMOTE_EXEC_AVAILABLE:
        try:
            _inject_via_remote_exec(pid, python_code)
            return
        except Exception as remote_err:
            # e.g. the target runs a different CPython version, or disabled remote debugging.
            # If pyinjector fails too, its error is the relevant one.
            warnings.warn(f"sys.remote_exec failed ({remote_err!r}); falling back to pyinjector.", RuntimeWarning)
    _inject_via_pyinjector(pid, python_code, permissions, immediate=False)


class ThreadCommand:
    def __init__(self, func: Callable, args: tuple, kwargs: dict):
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.result: Any = None
        self.exception: Optional[BaseException] = None

    def execute(self) -> None:
        try:
            self.result = self.func(*self.args, **self.kwargs)
        except BaseException as e:  # noqa: propagated to the caller
            self.exception = e

    def get_result(self) -> Any:
        if self.exception is not None:
            raise self.exception
        return self.result


# Run by run_in_thread's helper process. It waits for a line on stdin, so we can allow it to ptrace us first.
# argv[1] is the directory our hypno package lives in; we put it first on sys.path so the helper imports the
# *same* (compiled) hypno we're running, not a source checkout that happens to be the helper's cwd (python -c
# puts cwd on sys.path[0], and a source tree has no compiled .injection extension).
_THREAD_INJECTOR_CODE = ('import sys; sys.path.insert(0, sys.argv[1]); import hypno.api; sys.stdin.readline(); '
                         'hypno.api._inject_via_pyinjector(int(sys.argv[2]), sys.argv[3].encode(), 0o644, '
                         'immediate=True)')
_PR_SET_PTRACER = 0x59616d61


def _set_ptracer(pid: int) -> None:
    """
    Allow the given process to ptrace us under yama's ptrace_scope=1 (0 disallows again).
    Fails silently where yama is disabled. Note that this overrides any previous PR_SET_PTRACER of the process.
    """
    ctypes.CDLL(None, use_errno=True).prctl(_PR_SET_PTRACER, ctypes.c_ulong(pid), 0, 0, 0)


# Commands awaiting execution in a specific thread, keyed by target native id.
THREAD_COMMANDS: Dict[int, ThreadCommand] = {}


def run_in_thread(thread: Thread, func: Callable, *args: Any, **kwargs: Any) -> Any:
    """
    Run ``func(*args, **kwargs)`` synchronously in the context of an existing thread of *this* process,
    and return its result (or re-raise its exception).

    This hijacks the target thread via a short-lived child process (a thread can't ptrace a sibling thread
    of its own process), so the code truly runs on the target thread - e.g. ``threading.current_thread()``
    inside ``func`` returns ``thread``.

    Not supported on CPython >= 3.14 (the immediate injection it relies on aborts the target there) or on
    Windows (injection always spawns a new thread rather than targeting an existing one).
    """
    if sys.version_info >= (3, 14):
        raise NotImplementedError(
            "run_in_thread is not supported on CPython >= 3.14: injecting into a specific thread requires "
            "running code on the injector's scratch stack, which 3.14's C-stack guard aborts. "
            "Track https://github.com/kmaork/hypno/issues for progress.")
    if WINDOWS:
        raise NotImplementedError("run_in_thread is not supported on Windows.")
    if thread is current_thread():
        raise ValueError("Cannot run_in_thread on the current thread.")
    if not thread.is_alive():
        raise RuntimeError(f'Given thread is not alive: {thread}')
    target_native_id = thread.native_id
    assert target_native_id is not None
    command = ThreadCommand(func, args, kwargs)
    THREAD_COMMANDS[target_native_id] = command
    code = f'__import__("sys").modules[{__name__!r}].THREAD_COMMANDS[{target_native_id}].execute()'
    try:
        # A plain subprocess rather than multiprocessing, whose spawned child would re-run our __main__ script.
        hypno_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        injector = subprocess.Popen(
            [sys.executable, '-c', _THREAD_INJECTOR_CODE, hypno_parent_dir, str(target_native_id), code],
            stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        # Under yama's ptrace_scope=1 only ancestors may ptrace us, and the injector is our child
        _set_ptracer(injector.pid)
        try:
            _, error = injector.communicate(b'\n')
        finally:
            _set_ptracer(0)
        if injector.returncode != 0:
            raise RuntimeError(f'Failed injecting into thread {thread.name}:\n{error.decode(errors="replace")}')
        return command.get_result()
    finally:
        del THREAD_COMMANDS[target_native_id]

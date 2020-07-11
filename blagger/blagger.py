from importlib.util import find_spec
from pyinjector import inject
from ctypes import CDLL, c_int, c_char_p

client_path = find_spec('.client', __package__).origin.encode()
server_path = find_spec('.server', __package__).origin.encode()

server_lib = CDLL(server_path)
server_lib.serve_py_code.argtypes = c_int, c_char_p


def inject_py(pid: int, python_code: bytes) -> None:
    import threading
    threading.Thread(target=server_lib.serve_py_code, args=(pid, python_code)).start()
    inject(pid, client_path)

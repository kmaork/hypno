from argparse import Namespace, ArgumentParser
from typing import Optional, List

from hypno import inject_py


def parse_args(args: Optional[List[str]]) -> Namespace:
    parser = ArgumentParser(description='Inject python code into a running python process.')
    parser.add_argument('pid', type=int, help='pid of the process to inject code into')
    parser.add_argument('python_code', type=str.encode, help='python code to inject')
    parser.add_argument('--backend', choices=['auto', 'pyinjector', 'remote_exec'], default='auto',
                        help="Injection backend. 'auto' (default) prefers sys.remote_exec (CPython 3.14+) and "
                             "falls back to pyinjector. 'remote_exec' forces sys.remote_exec (target must run "
                             "the same CPython minor version; no pyinjector needed). 'pyinjector' forces "
                             "ptrace-based library injection.")
    parser.add_argument('--immediate-but-unsafe', action='store_true',
                        help="Run the code immediately in the hijacked thread instead of at the next safe "
                             "point. Unsafe, and unsupported on CPython >= 3.14.")
    return parser.parse_args(args)


def main(args: Optional[List[str]] = None) -> None:
    parsed_args = parse_args(args)
    inject_py(parsed_args.pid, parsed_args.python_code,
              immediate_but_unsafe=parsed_args.immediate_but_unsafe,
              backend=parsed_args.backend)


if __name__ == '__main__':
    main()

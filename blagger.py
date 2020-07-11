from argparse import ArgumentParser, Namespace
from importlib.util import find_spec
from typing import List, Optional
from pyinjector import inject

injection_path = find_spec('_injection').origin.encode()


def inject_py(pid: int, python_code: bytes) -> None:
    inject(pid, injection_path)


def parse_args(args: Optional[List[str]]) -> Namespace:
    parser = ArgumentParser(description='Inject python code into a running python process.')
    parser.add_argument('pid', type=int, help='pid of the process to inject code into')
    parser.add_argument('python_code', type=str.encode, help='python code to inject')
    return parser.parse_args(args)


def main(args: Optional[List[str]] = None) -> None:
    parsed_args = parse_args(args)
    inject_py(parsed_args.pid, parsed_args.python_code)


if __name__ == '__main__':
    main()

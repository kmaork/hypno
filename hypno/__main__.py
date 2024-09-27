from argparse import Namespace, ArgumentParser
from typing import Optional, List
from pathlib import Path

from hypno import inject_py, inject_py_script


def parse_args(args: Optional[List[str]]) -> Namespace:
    parser = ArgumentParser(description='Inject python code into a running python process.')
    parser.add_argument('pid', type=int, help='pid of the process to inject code into')
    parser.add_argument('--script', action='store_true', help='Inject a script instead of code', default=False)
    parser.add_argument('python_code', type=str, help='python code to inject')
    return parser.parse_args(args)


def main(args: Optional[List[str]] = None) -> None:
    parsed_args = parse_args(args)
    if parsed_args.script:
        inject_py_script(parsed_args.pid, Path(parsed_args.python_code))
    else:
        inject_py(parsed_args.pid, parsed_args.python_code.encode())


if __name__ == '__main__':
    main()

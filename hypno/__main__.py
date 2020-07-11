from argparse import Namespace, ArgumentParser
from typing import Optional, List

from hypno import inject_py


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

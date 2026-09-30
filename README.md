# Hypno

[![PyPI version](https://badge.fury.io/py/hypno.svg)](https://badge.fury.io/py/hypno)
[![PyPI Supported Python Versions](https://img.shields.io/pypi/pyversions/hypno.svg)](https://pypi.python.org/pypi/hypno/)
[![GitHub license](https://img.shields.io/github/license/kmaork/hypno)](https://github.com/kmaork/hypno/blob/master/LICENSE.txt)
[![Tests (GitHub Actions)](https://github.com/kmaork/hypno/workflows/Tests/badge.svg)](https://github.com/kmaork/hypno)
[![chat](https://img.shields.io/discord/850821971616858192.svg?logo=discord)](https://discord.gg/P3mN92eM2X)

A cross-platform tool/library allowing to inject python code into a running python process.
Based on [kmaork/pyinjector](https://github.com/kmaork/pyinjector).

If you are trying to debug a python process, check out [kmaork/madbg](https://github.com/kmaork/madbg).

### Installation
```shell script
pip install hypno
```
Both source distributions, manylinux, musslinux, mac and windows wheels are uploaded to pypi for every release.

### Usage
#### CLI
```shell script
hypno <pid> <python_code>
```

#### API
```python
from hypno import inject_py

inject_py(pid, python_code)
```
By default the code is scheduled to run at the target interpreter's next safe point (on its main thread).
This avoids deadlocks and is the only mode that works on CPython 3.14+.

#### Running code in a specific thread
`run_in_thread` runs a callable in the context of an existing thread of *the current* process and returns
its result (re-raising any exception):
```python
from hypno import run_in_thread

result = run_in_thread(some_thread, lambda: __import__('threading').current_thread().name)
```
It is currently supported on Linux/macOS with CPython < 3.14.

#### Backends (and injecting without pyinjector on CPython 3.14+)
By default (`backend='auto'`) hypno prefers [`sys.remote_exec`](https://peps.python.org/pep-0768/) when this
interpreter supports it (CPython 3.14+) - a safe, built-in mechanism that needs no pyinjector and no compiled
payload - and falls back to ptrace-based library injection otherwise (or when the target runs a different
CPython version). You can force a backend:
```python
inject_py(pid, python_code, backend='remote_exec')  # PEP 768; target must match this CPython minor version
inject_py(pid, python_code, backend='pyinjector')   # ptrace-based; works across CPython versions
```

#### Example
This example runs a python program that prints its pid, and then attaches to the newly created process and
injects it with another print statement using hypno. Mac users will need to use `sudo` for the second command.
```shell script
python -c "import os, time; print('Hello from', os.getpid()); time.sleep(0.5)" &\
hypno $! "import os; print('Hello again from', os.getpid())"
```

### Security
Hypno briefly generates a temporary file containing the requested python code.
This file is given 644 permissions by default, which means all users can read it.
To use custom permissions, you can pass the `permissions` argument to `inject_py()`.

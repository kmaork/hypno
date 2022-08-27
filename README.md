# Hypno

[![PyPI version](https://badge.fury.io/py/hypno.svg)](https://badge.fury.io/py/hypno)
[![PyPI Supported Python Versions](https://img.shields.io/pypi/pyversions/hypno.svg)](https://pypi.python.org/pypi/hypno/)
[![GitHub license](https://img.shields.io/github/license/kmaork/hypno)](https://github.com/kmaork/hypno/blob/master/LICENSE.txt)
[![Tests (GitHub Actions)](https://github.com/kmaork/hypno/workflows/Tests/badge.svg)](https://github.com/kmaork/hypno)
[![chat](https://img.shields.io/discord/850821971616858192.svg?logo=discord)](https://discord.gg/P3mN92eM2X)

A tool/library allowing to inject python code into a running python process.
Based on [kmaork/pyinjector](https://github.com/kmaork/pyinjector).

If you are trying to debug a python process, check out [kmaork/madbg](https://github.com/kmaork/madbg).

### Installation
```shell script
pip install hypno
```
Both source distributions, manylinux, musslinux and windows wheels are uploaded to pypi for every release.

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

#### Example
This example runs a python program that prints its pid, and then attaches to the newly created process and
injects it with another print statement using hypno.
```shell script
python -c "import os, time; print('Hello from', os.getpid()); time.sleep(0.5)" &\
hypno $! "import os; print('Hello again from', os.getpid())"
```

### How it works
We use the [pyinjector](https://github.com/kmaork/pyinjector) library as a primitive allowing us to inject arbitrary
code into processes, because it is simple to use and can be installed easily and on most linux machines.
 
 [pyinjector](https://github.com/kmaork/pyinjector) needs an `.so` to inject, so we compile a minimal library
as a C-extension. That library calls `PyRun_SimpleString` upon initialization.

In order to allow injecting a process multiple times, the injected library must have a unique path for each injection.
We do that by copying the library for every call.

As we don't want to recompile the library for every injection to replace the executed string,
and we already control the path from which our library is injected, we encode the injected python code
into the the injected libraries' paths. When the injected library is loaded, it finds its own name
using `dladdr` and parses the python code from it.

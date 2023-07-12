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

#### Example
This example runs a python program that prints its pid, and then attaches to the newly created process and
injects it with another print statement using hypno.
```shell script
python -c "import os, time; print('Hello from', os.getpid()); time.sleep(0.5)" &\
hypno $! "import os; print('Hello again from', os.getpid())"
```

### Security
Hypno briefly generates a temporary file containing the requested python code.
This file is given 644 permissions by default, which means all users can read it.
To use custom permissions, you can pass the `permissions` argument to `inject_py()`.

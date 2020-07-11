from setuptools import setup, Extension

setup(
    ext_modules=[Extension('blagger.client', sources=['blagger/client.c'], libraries=['rt']),
                 Extension('blagger.server', sources=['blagger/server.c'], libraries=['rt'])],
    entry_points={"console_scripts": ["blag=blagger.__main__:main"]}
)

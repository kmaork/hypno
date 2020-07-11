from setuptools import setup, Extension

setup(
    ext_modules=[Extension('blagger.injection', sources=['blagger/injection.c'])],
    entry_points={"console_scripts": ["blag=blagger.__main__:main"]}
)

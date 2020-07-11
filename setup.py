from setuptools import setup, Extension

setup(
    ext_modules=[Extension('_injection', sources=['injection.c'])],
    entry_points={"console_scripts": ["blag=blagger:main"]}
)

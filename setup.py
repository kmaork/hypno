from setuptools import setup, Extension

setup(
    ext_modules=[Extension('hypno.injection', sources=['hypno/injection.c'])],
    entry_points={"console_scripts": ["blag=hypno.__main__:main"]}
)

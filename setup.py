from setuptools import setup, find_packages

setup(
    name='curvycad',
    description='Utility for generating periodic features along a path, primarily for KiCad',
    author='Jeff McBride',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'numpy',
        'ezdxf',
    ]
)
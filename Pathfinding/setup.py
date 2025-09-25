from setuptools import setup, Extension
import pybind11
import sys
import sysconfig
import os

python_include = sysconfig.get_paths()["include"]
python_lib_dir = os.path.join(os.path.dirname(sys.executable), "libs")

ext_modules = [
    Extension(
        "pathfinding",
        ["pathfinding.cpp"],
        include_dirs=[
            pybind11.get_include(),
            python_include,
        ],
        library_dirs=[python_lib_dir],
        libraries=["python39"],
        language="c++",
        
        extra_compile_args=["-std=c++17", "-O3"],
    ),
]

setup(
    name="pathfinding",
    version="0.0.1",
    author="You",
    description="pathfinding module with pybind11",
    ext_modules=ext_modules,
)

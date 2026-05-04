from setuptools import setup, Extension
import pybind11

ext_modules = [
    Extension(
        "pathfinding",
        ["pathfinding.cpp"],
        include_dirs=[pybind11.get_include()],
        language="c++",
        extra_compile_args=["-std=c++17", "-O3"],
    ),
]

setup(
    name="pathfinding",
    version="0.0.1",
    description="pathfinding module with pybind11",
    ext_modules=ext_modules,
)
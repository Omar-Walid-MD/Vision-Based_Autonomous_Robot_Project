import os
import time
import json

# ✅ Add MSYS2 MinGW build path (adjust if needed)
os.add_dll_directory(r"D:\msys2\mingw64\bin")

# Import both modules
import pythonPathfinding       # pure Python version
import pathfinding          # C++ Pybind11 module


def benchmark(func, grid, src, dest, runs=10):
    """Runs a function multiple times and returns total elapsed time."""
    start = time.perf_counter()
    result = None
    for _ in range(runs):
        result = func(grid, src, dest)
    end = time.perf_counter()
    return result, end - start


def main():
    # Define a larger grid for more noticeable timing difference
    grid = []
    with open("./grid.json","r") as gridFile:
        grid = json.load(gridFile)["grid"]

    src = (30, 30)
    dest = (475, 475)

    runs = 50  # number of repetitions for each

    # Benchmark C++ module
    cpp_result, cpp_time = benchmark(pathfinding.aStarSearch, grid, src, dest, runs)
    print(f"C++ module (pybind11): total {((cpp_time * 1000) / 1):.6f} milliseconds for {runs} runs")

    # Benchmark Python module
    py_result, py_time = benchmark(pythonPathfinding.a_star_search, grid, src, dest, runs)
    print(f"Pure Python: total {((py_time * 1000 / 1)):.6f} milliseconds for {runs} runs")
    
    # print("CPP Result",cpp_result)
    # print("Python Result",py_result)

    # Speedup factor
    if py_time > 0:
        print(f"Speedup (Python / C++): {py_time / cpp_time:.2f}x")


if __name__ == "__main__":
    main()
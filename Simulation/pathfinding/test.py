import os
import sys
# Add MinGW bin folder to DLL search path
os.add_dll_directory(r"D:\msys2\mingw64\bin")
import pathfinding

# Define the grid (must be 9x10 because ROW=9, COL=10 in your C++ code)
grid = [
    [1, 1, 1, 1, 1, 1, 0, 0, 1, 1],
    [1, 0, 0, 1, 1, 1, 1, 0, 1, 0],
    [1, 1, 1, 0, 1, 1, 0, 1, 1, 1],
    [1, 1, 1, 0, 0, 1, 0, 0, 1, 1],
    [1, 1, 1, 1, 1, 0, 1, 1, 0, 1],
    [0, 0, 1, 1, 1, 1, 0, 1, 1, 1],
    [1, 1, 1, 0, 1, 1, 1, 0, 1, 1],
    [1, 1, 0, 0, 1, 0, 1, 1, 1, 1],
    [1, 1, 1, 1, 1, 1, 1, 0, 0, 1]
]

# Call the function
path = pathfinding.aStarSearch(grid, [0,0], [8,0])

print("Path:", path)

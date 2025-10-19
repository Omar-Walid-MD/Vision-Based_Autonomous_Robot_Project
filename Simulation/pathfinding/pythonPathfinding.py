
import math
from heapq import heappush, heappop
from typing import List, Tuple, Optional

class Cell:
    def __init__(self):
        self.parent_i = 0
        self.parent_j = 0
        self.f = float('inf')
        self.g = float('inf')
        self.h = float('inf')

def is_valid(row: int, col: int, grid: List[List[int]]) -> bool:
    return (0 <= row < len(grid)) and (0 <= col < len(grid[0]))

def is_unblocked(grid: List[List[int]], row: int, col: int) -> bool:
    return grid[row][col] == 1

def is_destination(row: int, col: int, dest: Tuple[int, int]) -> bool:
    return row == dest[0] and col == dest[1]

def calculate_h_value(row: int, col: int, dest: Tuple[int, int]) -> float:
    return math.sqrt((row - dest[0]) ** 2 + (col - dest[1]) ** 2)

def trace_path(cell_details: List[List[Cell]], dest: Tuple[int, int]) -> List[Tuple[int, int]]:
    row, col = dest
    dx = cell_details[row][col].parent_i - row
    dy = cell_details[row][col].parent_j - col
    
    path = []
    result_path = []
    
    path.append((row, col))
    while not (cell_details[row][col].parent_i == row and 
               cell_details[row][col].parent_j == col):
        if not (dx == cell_details[row][col].parent_i - row and 
                dy == cell_details[row][col].parent_j - col):
            path.append((row, col))
            dx = cell_details[row][col].parent_i - row
            dy = cell_details[row][col].parent_j - col
            
        temp_row = cell_details[row][col].parent_i
        temp_col = cell_details[row][col].parent_j
        row = temp_row
        col = temp_col
    
    path.append((row, col))
    
    while path:
        cell = path.pop()
        result_path.append((cell[1], cell[0]))
    
    return result_path

def a_star_search(grid: List[List[int]], src: Tuple[int, int], dest: Tuple[int, int]) -> List[Tuple[int, int]]:
    if not grid or not grid[0]:
        return []
        
    ROW, COL = len(grid), len(grid[0])
    
    # Swap coordinates to match C++ implementation
    src = (src[1], src[0])
    dest = (dest[1], dest[0])
    
    # Validate inputs
    if not is_valid(src[0], src[1], grid) or not is_valid(dest[0], dest[1], grid):
        return []
        
    if not is_unblocked(grid, src[0], src[1]) or not is_unblocked(grid, dest[0], dest[1]):
        return []
        
    if is_destination(src[0], src[1], dest):
        return [(src[1], src[0])]
    
    # Initialize closed list
    closed_list = [[False] * COL for _ in range(ROW)]
    
    # Initialize cell details
    cell_details = [[Cell() for _ in range(COL)] for _ in range(ROW)]
    
    i, j = src
    cell_details[i][j].f = 0.0
    cell_details[i][j].g = 0.0
    cell_details[i][j].h = 0.0
    cell_details[i][j].parent_i = i
    cell_details[i][j].parent_j = j
    
    # Initialize open list (using heapq for priority queue)
    open_list = []
    heappush(open_list, (0.0, i, j))
    
    # Directions (8 possible movements)
    dir_row = [-1, 1, 0, 0, -1, -1, 1, 1]
    dir_col = [0, 0, 1, -1, 1, -1, 1, -1]
    cost_g = [1.0, 1.0, 1.0, 1.0, 1.414, 1.414, 1.414, 1.414]
    
    while open_list:
        f, i, j = heappop(open_list)
        closed_list[i][j] = True
        
        for k in range(8):
            new_i = i + dir_row[k]
            new_j = j + dir_col[k]
            
            if is_valid(new_i, new_j, grid):
                if is_destination(new_i, new_j, dest):
                    cell_details[new_i][new_j].parent_i = i
                    cell_details[new_i][new_j].parent_j = j
                    return trace_path(cell_details, dest)
                
                elif not closed_list[new_i][new_j] and is_unblocked(grid, new_i, new_j):
                    g_new = cell_details[i][j].g + cost_g[k]
                    h_new = calculate_h_value(new_i, new_j, dest)
                    f_new = g_new + h_new
                    
                    if cell_details[new_i][new_j].f == float('inf') or cell_details[new_i][new_j].f > f_new:
                        heappush(open_list, (f_new, new_i, new_j))
                        cell_details[new_i][new_j].f = f_new
                        cell_details[new_i][new_j].g = g_new
                        cell_details[new_i][new_j].h = h_new
                        cell_details[new_i][new_j].parent_i = i
                        cell_details[new_i][new_j].parent_j = j
    
    return []  
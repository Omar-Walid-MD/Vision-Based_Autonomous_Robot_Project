
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

def has_line_of_sight(grid, start, end, step=0.5):
    x0, y0 = start
    x1, y1 = end
    dx = x1 - x0
    dy = y1 - y0
    dist = (dx**2 + dy**2)**0.5
    steps = int(dist / step)
    for i in range(steps + 1):
        t = i / steps
        x = x0 + t * dx
        y = y0 + t * dy
        gx, gy = int(round(x)), int(round(y))
        if gx < 0 or gy < 0 or gx >= len(grid[0]) or gy >= len(grid):
            return False
        if grid[gy][gx] == 0:  # obstacle
            return False
    return True


def smooth_path(grid, path: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    if not path:
        return []

    smoothed = [path[0]]
    start_idx = 0
    n = len(path)

    while start_idx < n - 1:
        # Find the farthest reachable point from start_idx
        last_valid = start_idx + 1
        for end_idx in range(n - 1, start_idx, -1):
            if has_line_of_sight(grid, path[start_idx], path[end_idx]):
                last_valid = end_idx
                break

        # Append the farthest reachable point
        smoothed.append(path[last_valid])

        # Move start to that point to continue smoothing
        start_idx = last_valid

        # Safety check: if start_idx didn't move, increment by 1 to avoid infinite loop
        if start_idx == last_valid and start_idx < n - 1:
            start_idx += 1

    return smoothed

def trace_path(cell_details: List[List["Cell"]], dest: Tuple[int, int]) -> List[Tuple[int, int]]:
    
    row, col = dest
    path = []
    
    # Track initial direction
    dx = cell_details[row][col].parent_i - row
    dy = cell_details[row][col].parent_j - col
    
    # Push destination first
    path.append((col, row))  # output as (x, y)
    
    # Trace back to source
    while not (cell_details[row][col].parent_i == row and 
               cell_details[row][col].parent_j == col):
        new_dx = cell_details[row][col].parent_i - row
        new_dy = cell_details[row][col].parent_j - col
        
        # Only append a point when direction changes
        if (new_dx, new_dy) != (dx, dy):
            path.append((col, row))
            dx, dy = new_dx, new_dy
        
        # Move to parent
        temp_row = cell_details[row][col].parent_i
        temp_col = cell_details[row][col].parent_j
        row, col = temp_row, temp_col
    
    # Append source
    path.append((col, row))
    
    # Reverse path to get from start → destination
    path.reverse()
    
    return path

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
                    path = trace_path(cell_details, dest)
                    return smooth_path(grid,path)
                
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
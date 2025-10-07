import math
import heapq

class Cell:
    def __init__(self):
        self.parent_i = -1
        self.parent_j = -1
        self.f = float('inf')
        self.g = float('inf')
        self.h = float('inf')


def is_valid(row, col, grid):
    return (0 <= row < len(grid)) and (0 <= col < len(grid[0]))


def is_unblocked(grid, row, col):
    return grid[row][col] == 1


def is_destination(row, col, dest):
    return row == dest[0] and col == dest[1]


def calculate_h_value(row, col, dest):
    return math.sqrt((row - dest[0])**2 + (col - dest[1])**2)


def trace_path(cell_details, dest):
    path = []
    row, col = dest
    while not (cell_details[row][col].parent_i == row and cell_details[row][col].parent_j == col):
        path.append((row, col))
        row, col = cell_details[row][col].parent_i, cell_details[row][col].parent_j
    path.append((row, col))
    path.reverse()
    return path


def a_star_search(grid, src, dest):
    ROW, COL = len(grid), len(grid[0])

    if not is_valid(src[0], src[1], grid) or not is_valid(dest[0], dest[1], grid):
        return []

    if not is_unblocked(grid, src[0], src[1]) or not is_unblocked(grid, dest[0], dest[1]):
        return []

    if is_destination(src[0], src[1], dest):
        return [tuple(src)]

    closed_list = [[False for _ in range(COL)] for _ in range(ROW)]
    cell_details = [[Cell() for _ in range(COL)] for _ in range(ROW)]

    i, j = src
    cell_details[i][j].f = 0.0
    cell_details[i][j].g = 0.0
    cell_details[i][j].h = 0.0
    cell_details[i][j].parent_i = i
    cell_details[i][j].parent_j = j

    open_list = []
    heapq.heappush(open_list, (0.0, i, j))

    directions = [(-1, 0), (1, 0), (0, 1), (0, -1),
                  (-1, -1), (-1, 1), (1, -1), (1, 1)]
    cost_g = [1.0, 1.0, 1.0, 1.0, 1.414, 1.414, 1.414, 1.414]

    while open_list:
        f, i, j = heapq.heappop(open_list)
        closed_list[i][j] = True

        for k, (di, dj) in enumerate(directions):
            new_i, new_j = i + di, j + dj

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
                        heapq.heappush(open_list, (f_new, new_i, new_j))
                        cell_details[new_i][new_j].f = f_new
                        cell_details[new_i][new_j].g = g_new
                        cell_details[new_i][new_j].h = h_new
                        cell_details[new_i][new_j].parent_i = i
                        cell_details[new_i][new_j].parent_j = j

    return []  # No path found

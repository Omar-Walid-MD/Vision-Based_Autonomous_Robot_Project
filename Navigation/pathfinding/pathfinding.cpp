#include <bits/stdc++.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace py = pybind11;
using namespace std;

typedef pair<int, int> Pair;
typedef pair<double, pair<int, int>> pPair;

struct cell {
    int parent_i, parent_j;
    double f, g, h;
};

// Check valid cell inside dynamic grid
bool isValid(int row, int col, const std::vector<std::vector<int>>& grid) {
    return (row >= 0) && (row < (int)grid.size()) &&
           (col >= 0) && (col < (int)grid[0].size());
}

// Check if cell is unblocked
bool isUnBlocked(const std::vector<std::vector<int>>& grid, int row, int col) {
    return grid[row][col] == 1;
}

// Check if destination reached
bool isDestination(int row, int col, Pair dest) {
    return (row == dest.first && col == dest.second);
}

// Heuristic (Euclidean distance)
double calculateHValue(int row, int col, Pair dest) {
    return sqrt((row - dest.first) * (row - dest.first) +
                (col - dest.second) * (col - dest.second));
}

std::vector<std::pair<int,int>> tracePath(
    const std::vector<std::vector<cell>>& cellDetails,
    std::pair<int,int> dest)
{
    int row = dest.first;
    int col = dest.second;

    std::vector<std::pair<int,int>> path;

    int dx = cellDetails[row][col].parent_i - row;
    int dy = cellDetails[row][col].parent_j - col;

    // push destination (x, y)
    path.emplace_back(col, row);

    while (!(cellDetails[row][col].parent_i == row &&
             cellDetails[row][col].parent_j == col))
    {
        int new_dx = cellDetails[row][col].parent_i - row;
        int new_dy = cellDetails[row][col].parent_j - col;

        if (new_dx != dx || new_dy != dy) {
            path.emplace_back(col, row);
            dx = new_dx;
            dy = new_dy;
        }

        int temp_row = cellDetails[row][col].parent_i;
        int temp_col = cellDetails[row][col].parent_j;

        row = temp_row;
        col = temp_col;
    }

    // push source
    path.emplace_back(col, row);

    std::reverse(path.begin(), path.end());
    return path;
}

bool hasLineOfSight(
    const std::vector<std::vector<int>>& grid,
    std::pair<int,int> start,
    std::pair<int,int> end,
    double step = 0.5)
{
    double x0 = start.first;
    double y0 = start.second;
    double x1 = end.first;
    double y1 = end.second;

    double dx = x1 - x0;
    double dy = y1 - y0;

    double dist = std::sqrt(dx*dx + dy*dy);
    int steps = static_cast<int>(dist / step);

    if (steps == 0) return true;

    for (int i = 0; i <= steps; i++) {
        double t = static_cast<double>(i) / steps;

        double x = x0 + t * dx;
        double y = y0 + t * dy;

        int gx = static_cast<int>(std::round(x));
        int gy = static_cast<int>(std::round(y));

        if (gy < 0 || gx < 0 ||
            gy >= (int)grid.size() ||
            gx >= (int)grid[0].size())
            return false;

        if (grid[gy][gx] == 0)
            return false;
    }

    return true;
}

std::vector<std::pair<int,int>> smoothPath(
    const std::vector<std::vector<int>>& grid,
    const std::vector<std::pair<int,int>>& path)
{
    if (path.empty())
        return {};

    std::vector<std::pair<int,int>> smoothed;
    smoothed.push_back(path[0]);

    int start_idx = 0;
    int n = path.size();

    while (start_idx < n - 1) {
        int last_valid = start_idx + 1;

        for (int end_idx = n - 1; end_idx > start_idx; --end_idx) {
            if (hasLineOfSight(grid, path[start_idx], path[end_idx])) {
                last_valid = end_idx;
                break;
            }
        }

        if (last_valid <= start_idx) {
            throw std::runtime_error("Smoothing failed: no forward progress");
        }

        smoothed.push_back(path[last_valid]);
        start_idx = last_valid;
    }

    return smoothed;
}

std::vector<std::vector<int>> marginizeGrid(
    const std::vector<std::vector<int>>& grid,
    double cell_size,
    double robot_size)
{
    int rows = grid.size();
    int cols = grid[0].size();

    int radius_cells = std::ceil((robot_size / 2.0) / cell_size);

    std::vector<std::vector<int>> inflated = grid;

    for (int y = 0; y < rows; y++) {
        for (int x = 0; x < cols; x++) {
            if (grid[y][x] == 0) {
                for (int dy = -radius_cells; dy <= radius_cells; dy++) {
                    for (int dx = -radius_cells; dx <= radius_cells; dx++) {
                        int nx = x + dx;
                        int ny = y + dy;

                        if (nx >= 0 && ny >= 0 &&
                            nx < cols && ny < rows)
                        {
                            if (dx*dx + dy*dy <= radius_cells * radius_cells) {
                                inflated[ny][nx] = 0;
                            }
                        }
                    }
                }
            }
        }
    }

    return inflated;
}

// A* search on dynamic grid
std::vector<std::pair<int,int>> aStarSearch(
    const std::vector<std::vector<int>>& grid,
    std::pair<int,int> src,
    std::pair<int,int> dest
) {
    int ROW = grid.size();
    int COL = grid[0].size();

    std::swap(src.first, src.second);
    std::swap(dest.first, dest.second);

    // Validate inputs
    if (!isValid(src.first, src.second, grid) ||
        !isValid(dest.first, dest.second, grid))
        return {};

    if (!isUnBlocked(grid, src.first, src.second) ||
        !isUnBlocked(grid, dest.first, dest.second))
        return {};

    if (isDestination(src.first, src.second, dest))
        return {{src.first, src.second}};

    // Closed list
    std::vector<std::vector<bool>> closedList(ROW, std::vector<bool>(COL, false));

    // Cell details
    std::vector<std::vector<cell>> cellDetails(ROW, std::vector<cell>(COL));
    for (int i = 0; i < ROW; i++) {
        for (int j = 0; j < COL; j++) {
            cellDetails[i][j].f = FLT_MAX;
            cellDetails[i][j].g = FLT_MAX;
            cellDetails[i][j].h = FLT_MAX;
            cellDetails[i][j].parent_i = -1;
            cellDetails[i][j].parent_j = -1;
        }
    }

    int i = src.first, j = src.second;
    cellDetails[i][j].f = 0.0;
    cellDetails[i][j].g = 0.0;
    cellDetails[i][j].h = 0.0;
    cellDetails[i][j].parent_i = i;
    cellDetails[i][j].parent_j = j;

    set<pPair> openList;
    openList.insert(make_pair(0.0, make_pair(i, j)));

    // Directions
    int dir_row[] = {-1, 1, 0, 0, -1, -1, 1, 1};
    int dir_col[] = {0, 0, 1, -1, 1, -1, 1, -1};
    double cost_g[] = {1.0, 1.0, 1.0, 1.0, 1.414, 1.414, 1.414, 1.414};

    while (!openList.empty()) {
        pPair p = *openList.begin();
        openList.erase(openList.begin());

        i = p.second.first;
        j = p.second.second;
        closedList[i][j] = true;

        for (int k = 0; k < 8; ++k) {
            int new_i = i + dir_row[k];
            int new_j = j + dir_col[k];

            if (isValid(new_i, new_j, grid)) {
                if (isDestination(new_i, new_j, dest)) {
                    cellDetails[new_i][new_j].parent_i = i;
                    cellDetails[new_i][new_j].parent_j = j;
                    return smoothPath(grid,tracePath(cellDetails, dest));
                }
                else if (!closedList[new_i][new_j] && isUnBlocked(grid, new_i, new_j)) {
                    double gNew = cellDetails[i][j].g + cost_g[k];
                    double hNew = calculateHValue(new_i, new_j, dest);
                    double fNew = gNew + hNew;

                    if (cellDetails[new_i][new_j].f == FLT_MAX ||
                        cellDetails[new_i][new_j].f > fNew) {
                        openList.insert(make_pair(fNew, make_pair(new_i, new_j)));
                        cellDetails[new_i][new_j].f = fNew;
                        cellDetails[new_i][new_j].g = gNew;
                        cellDetails[new_i][new_j].h = hNew;
                        cellDetails[new_i][new_j].parent_i = i;
                        cellDetails[new_i][new_j].parent_j = j;
                    }
                }
            }
        }
    }

    return {}; // No path found
}

// Pybind11 module definition
PYBIND11_MODULE(pathfinding, m) {
    m.doc() = "pybind11 A* pathfinding module";

    m.def("aStarSearch",
        [](const std::vector<std::vector<int>>& grid,
           py::sequence src_seq,
           py::sequence dest_seq) {

            if (src_seq.size() != 2 || dest_seq.size() != 2)
                throw std::runtime_error("src and dest must each be length-2 sequences");

            std::pair<int,int> src(src_seq[0].cast<int>(), src_seq[1].cast<int>());
            std::pair<int,int> dest(dest_seq[0].cast<int>(), dest_seq[1].cast<int>());

            return aStarSearch(grid, src, dest);
        },
        py::arg("grid"),
        py::arg("src"),
        py::arg("dest")
    );

    // ✅ Add this
    m.def("marginizeGrid",
        &marginizeGrid,
        py::arg("grid"),
        py::arg("cell_size"),
        py::arg("robot_size"),
        "Inflate obstacles based on robot size"
    );
}
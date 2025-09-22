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

// Trace path from destination to source
std::vector<std::pair<int, int>> tracePath(
    const std::vector<std::vector<cell>>& cellDetails, Pair dest) {
    
    int row = dest.first;
    int col = dest.second;
    int dx = cellDetails[row][col].parent_i - row;
    int dy = cellDetails[row][col].parent_j - col;
    int temp_row, temp_col;

    std::stack<Pair> Path;
    std::vector<std::pair<int, int>> resultPath;

    Path.push(make_pair(dest.first, dest.second));
    while (!(cellDetails[row][col].parent_i == row &&
             cellDetails[row][col].parent_j == col)) {
        if (!((dx == cellDetails[row][col].parent_i - row) &&
              dy == cellDetails[row][col].parent_j - col)) {
            Path.push(make_pair(row, col));
            dx = cellDetails[row][col].parent_i - row;
            dy = cellDetails[row][col].parent_j - col;
        }

        temp_row = cellDetails[row][col].parent_i;
        temp_col = cellDetails[row][col].parent_j;
        row = temp_row;
        col = temp_col;
    }
    Path.push(make_pair(row, col));

    while (!Path.empty()) {
        resultPath.push_back(Path.top());
        Path.pop();
    }
    return resultPath;
}

// A* search on dynamic grid
std::vector<std::pair<int,int>> aStarSearch(
    const std::vector<std::vector<int>>& grid,
    std::pair<int,int> src,
    std::pair<int,int> dest
) {
    int ROW = grid.size();
    int COL = grid[0].size();

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
                    return tracePath(cellDetails, dest);
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
        py::arg("dest"));
}

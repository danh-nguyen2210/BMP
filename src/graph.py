"""Module quản lý và xử lý dữ liệu đồ thị (GraphData) cho bài toán BMP.

Bao gồm:
- Đọc ma trận từ file .mtx (Matrix Market) hoặc Harwell-Boeing.
- Tối ưu 4.4.2: Tính toán Cận dưới (LB) từ bậc/đường kính và Cận trên (UB) bằng Heuristic Reverse Cuthill-McKee (RCM).
- Tối ưu 4.4.3: Phân rã đồ thị thành các Thành phần liên thông (Connected Components).
"""

from collections import deque
import os
import tarfile
import urllib.request
import numpy as np
from scipy.io import mmread
from scipy.sparse import csgraph, csr_matrix


class GraphData:

    def __init__(self, n, edges, name="graph"):
        """Khởi tạo đồ thị với n đỉnh (đánh số từ 1 đến n) và danh sách cạnh vô

        hướng.
        """
        self.name = name
        self.n = n
        # Lưu các cạnh dưới dạng chuẩn hóa u < v, loại bỏ khuyên (self-loop)
        self.edges = set()
        self.adj = {u: set() for u in range(1, n + 1)}

        for u, v in edges:
            if u != v:
                u_std, v_std = min(u, v), max(u, v)
                self.edges.add((u_std, v_std))
                self.adj[u_std].add(v_std)
                self.adj[v_std].add(u_std)

        self.m = len(self.edges)

    @classmethod
    def from_mtx(cls, file_path, name=None):
        """Đọc ma trận từ file .mtx (Matrix Market format)"""
        if name is None:
            name = os.path.splitext(os.path.basename(file_path))[0]

        mat = mmread(file_path).tocoo()
        n = max(mat.shape[0], mat.shape[1])
        edges = set()

        for u, v in zip(mat.row, mat.col):
            # Ma trận 0-indexed sang đỉnh 1-indexed
            if u != v:
                edges.add((int(u) + 1, int(v) + 1))

        return cls(n=n, edges=edges, name=name)

    @classmethod
    def from_edge_list(cls, n, edges, name="custom_graph"):
        """Tạo đồ thị trực tiếp từ danh sách cạnh"""
        return cls(n=n, edges=edges, name=name)

    def get_max_degree(self):
        """Tính bậc lớn nhất của các đỉnh (Delta)"""
        if not self.adj:
            return 0
        return max(len(neighbors) for neighbors in self.adj.values())

    def get_diameter(self):
        """Tính đường kính đồ thị (khoảng cách lớn nhất giữa 2 đỉnh liên thông)

        bằng BFS.
        """
        if self.n <= 1 or not self.edges:
            return 1

        max_dist = 1
        for start in range(1, self.n + 1):
            dist = {start: 0}
            queue = deque([start])
            while queue:
                curr = queue.popleft()
                for neighbor in self.adj[curr]:
                    if neighbor not in dist:
                        dist[neighbor] = dist[curr] + 1
                        queue.append(neighbor)
                        if dist[neighbor] > max_dist:
                            max_dist = dist[neighbor]
        return max_dist

    def compute_lb(self):
        """Tối ưu 4.4.2 (Phần LB): Tính cận dưới lý thuyết:

        LB = max( ceil(Delta / 2), ceil((n - 1) / diameter), 1 )
        """
        if self.n <= 2:
            return max(1, self.m)

        delta = self.get_max_degree()
        lb_deg = (delta + 1) // 2

        dia = self.get_diameter()
        lb_dia = int(np.ceil((self.n - 1) / max(1, dia)))

        return max(lb_deg, lb_dia, 1)

    def compute_rcm_ub(self):
        """Tối ưu 4.4.2 (Phần UB): Chạy Heuristic Reverse Cuthill-McKee (RCM) để

        lấy Cận trên chặt chẽ ban đầu.
        """
        if self.n <= 2 or not self.edges:
            return max(0, self.m)

        # Xây dựng ma trận kề đối xứng dạng CSR
        row_ind = []
        col_ind = []
        for u, v in self.edges:
            row_ind.extend([u - 1, v - 1])
            col_ind.extend([v - 1, u - 1])

        data = np.ones(len(row_ind), dtype=int)
        csr = csr_matrix((data, (row_ind, col_ind)), shape=(self.n, self.n))

        # Áp dụng thuật toán RCM của scipy
        perm = csgraph.reverse_cuthill_mckee(csr, symmetric_mode=True)

        # Tính toán băng thông thực tế đạt được bởi hoán vị RCM
        # perm[i] là đỉnh ở vị trí i (0-indexed)
        # label[u] là vị trí mới của đỉnh u (1-indexed)
        label = np.zeros(self.n, dtype=int)
        for new_pos, old_node in enumerate(perm):
            label[old_node] = new_pos + 1

        rcm_bw = 0
        for u, v in self.edges:
            diff = abs(int(label[u - 1]) - int(label[v - 1]))
            if diff > rcm_bw:
                rcm_bw = diff

        return max(1, rcm_bw)

    def get_rcm_labeling(self):
        """Trả về từ điển {u: f(u)} của hoán vị Reverse Cuthill-McKee (1-indexed)."""
        if self.n == 0:
            return {}
        if self.n == 1:
            return {1: 1}
        if not self.edges:
            return {u: u for u in range(1, self.n + 1)}
        row_ind = []
        col_ind = []
        for u, v in self.edges:
            row_ind.extend([u - 1, v - 1])
            col_ind.extend([v - 1, u - 1])
        data = np.ones(len(row_ind), dtype=int)
        csr = csr_matrix((data, (row_ind, col_ind)), shape=(self.n, self.n))
        perm = csgraph.reverse_cuthill_mckee(csr, symmetric_mode=True)
        label = {}
        for new_pos, old_node in enumerate(perm):
            label[old_node + 1] = new_pos + 1
        return label

    def get_connected_components(self):
        """Tối ưu 4.4.3: Phân rã đồ thị thành các Thành phần liên thông độc lập.

        Trả về danh sách các đối tượng GraphData con. Băng thông của đồ thị tổng
        = max các thành phần con.
        """
        visited = set()
        components = []

        for node in range(1, self.n + 1):
            if node not in visited:
                comp_nodes = []
                queue = deque([node])
                visited.add(node)

                while queue:
                    curr = queue.popleft()
                    comp_nodes.append(curr)
                    for nbr in self.adj[curr]:
                        if nbr not in visited:
                            visited.add(nbr)
                            queue.append(nbr)

                # Ánh xạ các đỉnh trong thành phần liên thông sang 1..k
                node_map = {
                    old: idx + 1 for idx, old in enumerate(sorted(comp_nodes))
                }
                sub_edges = set()
                for old_u in comp_nodes:
                    for old_v in self.adj[old_u]:
                        if old_u < old_v:
                            sub_edges.add((node_map[old_u], node_map[old_v]))

                sub_graph = GraphData(
                    n=len(comp_nodes),
                    edges=sub_edges,
                    name=f"{self.name}_comp{len(components) + 1}",
                )
                sub_graph.original_nodes = sorted(comp_nodes)
                components.append(sub_graph)

        return components

    def verify_labeling(self, labeling, claimed_bw=None):
        """Kiểm tra toán học tính hợp lệ của phép gán nhãn f: V -> {1..n}.
        1. Song ánh: tập nhãn {f(u)} phải là hoán vị của {1, 2, ..., n}.
        2. Băng thông: độ lệch |f(u) - f(v)| trên mọi cạnh (u, v) <= claimed_bw.
        """
        if len(labeling) != self.n:
            return False, f"Thiếu đỉnh: có {len(labeling)} đỉnh, cần {self.n}"
        labels = set(labeling.values())
        if labels != set(range(1, self.n + 1)):
            return False, f"Không phải song ánh: số nhãn phân biệt = {len(labels)}"
        max_diff = 0
        for u, v in self.edges:
            diff = abs(labeling[u] - labeling[v])
            if diff > max_diff:
                max_diff = diff
        if claimed_bw is not None and max_diff > claimed_bw:
            return False, f"Vi phạm băng thông: max diff={max_diff} > claimed={claimed_bw}"
        return True, max_diff

    @staticmethod
    def download_matrix(matrix_name, target_dir="data"):
        """Tải tự động ma trận Harwell-Boeing từ kho lưu trữ mở nếu chưa có sẵn."""
        os.makedirs(target_dir, exist_ok=True)
        mtx_path = os.path.join(target_dir, f"{matrix_name}.mtx")
        if os.path.exists(mtx_path):
            return mtx_path

        tar_path = os.path.join(target_dir, f"{matrix_name}.tar.gz")
        # Thử tải từ SuiteSparse / MatrixMarket
        urls = [
            f"https://sparse.tamu.edu/MM/HB/{matrix_name}.tar.gz",
            f"https://sparse.tamu.edu/MM/Harwell-Boeing/{matrix_name}.tar.gz",
        ]

        success = False
        for url in urls:
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": "Mozilla/5.0"}
                )
                with (
                    urllib.request.urlopen(req, timeout=15) as resp,
                    open(tar_path, "wb") as f,
                ):
                    f.write(resp.read())
                # Giải nén tìm file .mtx
                with tarfile.open(tar_path, "r:gz") as tar:
                    for member in tar.getmembers():
                        if member.name.endswith(".mtx"):
                            member.name = os.path.basename(member.name)
                            tar.extract(member, path=target_dir)
                            extracted = os.path.join(target_dir, member.name)
                            if extracted != mtx_path:
                                os.rename(extracted, mtx_path)
                            success = True
                            break
                if os.path.exists(tar_path):
                    os.remove(tar_path)
                if success:
                    break
            except Exception:
                continue

        if success and os.path.exists(mtx_path):
            return mtx_path
        return None

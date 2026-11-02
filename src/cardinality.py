"""Module mã hóa ràng buộc đếm (Cardinality Encodings) cho bài toán BMP.

Bao gồm các phương pháp cài đặt cho ALO (At-Least-Once) và AMO (At-Most-Once):
1. Pairwise Encoding: Ngây thơ, O(n^2) mệnh đề nhị phân, 0 biến phụ.
2. Sequential Counter Encoding (Sinz, 2005): Tuyến tính O(n) mệnh đề qua PySAT EncType.seqcounter.
3. Binary / Bitwise Encoding: Logarit biến phụ qua PySAT EncType.bitwise.
4. Commander Encoding (Klieber & Kwon, 2007): Chia nhóm kích thước g=3, O(n) mệnh đề.
5. Product Encoding (Chen, 2010): Lưới 2D kích thước p x q, O(n) mệnh đề, O(sqrt(n)) biến phụ.
6. Ladder / Totalizer: Gọi qua PySAT EncType.
"""

import math
from pysat.card import CardEnc, EncType


def encode_alo(lits):
    """Mã hóa ràng buộc At-Least-Once (ALO): \bigvee lits.
    Trả về danh sách chứa 1 mệnh đề gồm tất cả các literal.
    """
    if not lits:
        return []
    return [list(lits)]


def encode_pairwise_amo(lits):
    """Mã hóa Pairwise AMO: \forall i < j, (\neg y_i \lor \neg y_j).
    Số mệnh đề: n(n-1)/2, số biến phụ: 0.
    """
    clauses = []
    n = len(lits)
    for i in range(n):
        for j in range(i + 1, n):
            clauses.append([-lits[i], -lits[j]])
    return clauses


def encode_commander_amo(lits, top_id, group_size=3):
    """Mã hóa Commander AMO (Klieber & Kwon, 2007).
    Chia tập biến thành các nhóm nhỏ kích thước group_size.
    Mỗi nhóm có một biến commander đại diện:
    1. Trong mỗi nhóm: AMO(grp)
    2. Mỗi phần tử trong grp kéo theo commander: x -> c <=> -x \lor c
    3. Commander kéo theo ít nhất một phần tử: c -> \bigvee grp <=> -c \lor \bigvee grp
    4. Đệ quy áp dụng AMO trên danh sách các biến commander.
    """
    n = len(lits)
    if n <= 1:
        return [], top_id
    if n <= group_size:
        return encode_pairwise_amo(lits), top_id

    clauses = []
    current_top = top_id
    commanders = []

    for i in range(0, n, group_size):
        grp = lits[i:i + group_size]
        if len(grp) == 1:
            commanders.append(grp[0])
            continue

        current_top += 1
        c = current_top
        commanders.append(c)

        # 1. AMO trong nhóm
        for a in range(len(grp)):
            for b in range(a + 1, len(grp)):
                clauses.append([-grp[a], -grp[b]])

        # 2. grp[a] -> c
        for x in grp:
            clauses.append([-x, c])

        # 3. c -> \bigvee grp
        clauses.append([-c] + list(grp))

    # Đệ quy AMO trên các commander
    rec_clauses, final_top = encode_commander_amo(commanders, current_top, group_size)
    clauses.extend(rec_clauses)
    return clauses, final_top


def encode_product_amo(lits, top_id):
    """Mã hóa 2-Product AMO (Chen, 2010).
    Sắp xếp n biến vào ma trận kích thước p x q (p = floor(sqrt(n)), q = ceil(n/p)).
    Biến phụ hàng u_1..u_p, biến phụ cột v_1..v_q.
    1. lit(r, c) -> u_r và lit(r, c) -> v_c
    2. AMO trên các biến hàng u_1..u_p (Pairwise)
    3. AMO trên các biến cột v_1..v_q (Pairwise)
    """
    n = len(lits)
    if n <= 1:
        return [], top_id
    if n <= 3:
        return encode_pairwise_amo(lits), top_id

    p = int(math.isqrt(n))
    q = math.ceil(n / p)

    current_top = top_id
    row_vars = [current_top + i + 1 for i in range(p)]
    current_top += p
    col_vars = [current_top + j + 1 for j in range(q)]
    current_top += q

    clauses = []
    for k, lit in enumerate(lits):
        r = k // q
        c = k % q
        if r < p and c < q:
            clauses.append([-lit, row_vars[r]])
            clauses.append([-lit, col_vars[c]])

    # AMO trên hàng
    for i in range(p):
        for j in range(i + 1, p):
            clauses.append([-row_vars[i], -row_vars[j]])

    # AMO trên cột
    for i in range(q):
        for j in range(i + 1, q):
            clauses.append([-col_vars[i], -col_vars[j]])

    return clauses, current_top


def encode_amo(lits, top_id, method="pairwise"):
    """Hàm điều phối mã hóa At-Most-Once (AMO) chung.
    Hỗ trợ các phương pháp:
    - 'pairwise': Cặp đôi truyền thống (0 biến phụ)
    - 'sequential' / 'seqcounter': Sequential Counter qua PySAT
    - 'binary' / 'bitwise': Bitwise / Binary qua PySAT
    - 'commander': Commander Encoding
    - 'product': 2-Product Encoding
    - 'ladder': Ladder qua PySAT
    - 'totalizer': Totalizer qua PySAT
    """
    n = len(lits)
    if n <= 1:
        return [], top_id

    m = method.lower().replace("-", "_").replace(" ", "")

    if m in ("pairwise", "direct"):
        return encode_pairwise_amo(lits), top_id

    elif m in ("sequential", "seqcounter", "sinz"):
        cnf = CardEnc.atmost(lits, bound=1, encoding=EncType.seqcounter, top_id=top_id)
        return cnf.clauses, cnf.nv

    elif m in ("binary", "bitwise", "bit"):
        cnf = CardEnc.atmost(lits, bound=1, encoding=EncType.bitwise, top_id=top_id)
        return cnf.clauses, cnf.nv

    elif m in ("commander", "comm"):
        return encode_commander_amo(lits, top_id, group_size=3)

    elif m in ("product", "prod", "chen"):
        return encode_product_amo(lits, top_id)

    elif m in ("ladder",):
        cnf = CardEnc.atmost(lits, bound=1, encoding=EncType.ladder, top_id=top_id)
        return cnf.clauses, cnf.nv

    elif m in ("totalizer", "tot"):
        cnf = CardEnc.atmost(lits, bound=1, encoding=EncType.totalizer, top_id=top_id)
        return cnf.clauses, cnf.nv

    else:
        # Fallback to pairwise
        return encode_pairwise_amo(lits), top_id


def encode_bijective_assignment(n, get_var_func, top_id, amo_method="pairwise"):
    """BƯỚC 1: Ràng buộc Song ánh cho biến X (Bijective Assignment).
    Đảm bảo mỗi đỉnh nhận duy nhất 1 nhãn, và không có 2 đỉnh nào trùng nhãn.

    (1.1) Mỗi đỉnh nhận ít nhất 1 nhãn (At-Least-Once - ALO):
          \forall u \in V: \bigvee_{i=1}^n X_{u, i}
          -> n mệnh đề, mỗi mệnh đề độ dài n.

    (1.2) Mỗi đỉnh nhận nhiều nhất 1 nhãn (At-Most-Once - AMO):
          \forall u \in V: AMO(X_{u, 1}, ..., X_{u, n})

    (1.3) Không có 2 đỉnh khác nhau nhận cùng một nhãn (Đơn ánh - Injective AMO):
          \forall i \in {1, ..., n}: AMO(X_{1, i}, ..., X_{n, i})

    Trả về (clauses, new_top_id).
    """
    clauses = []
    current_top = top_id

    # (1.1) ALO: Mỗi đỉnh nhận ít nhất 1 nhãn
    for u in range(1, n + 1):
        row_lits = [get_var_func(u, i) for i in range(1, n + 1)]
        clauses.extend(encode_alo(row_lits))

    # (1.2) AMO: Mỗi đỉnh nhận tối đa 1 nhãn
    for u in range(1, n + 1):
        row_lits = [get_var_func(u, i) for i in range(1, n + 1)]
        amo_cls, current_top = encode_amo(row_lits, current_top, method=amo_method)
        clauses.extend(amo_cls)

    # (1.3) Đơn ánh (Injective): Mỗi nhãn gán cho tối đa 1 đỉnh
    for i in range(1, n + 1):
        col_lits = [get_var_func(u, i) for u in range(1, n + 1)]
        amo_cls, current_top = encode_amo(col_lits, current_top, method=amo_method)
        clauses.extend(amo_cls)

    return clauses, current_top

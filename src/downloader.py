"""Module tải tự động các ma trận thuộc bộ benchmark Harwell-Boeing từ NIST
Matrix Market cho toàn bộ Bảng 6 và Bảng 7 (Harwell-Boeing Sparse Matrix Collection).
"""

import argparse
import gzip
import os
import urllib.request

# Ánh xạ đầy đủ 72 ma trận từ Bảng 6 và Bảng 7 (Part I) trên NIST Matrix Market
NIST_MAP = {
    # --------------------------------------------------------------------------
    # BẢNG 6 (TABLE 6): 31 ma trận nhỏ (n <= 199)
    # --------------------------------------------------------------------------
    "arc130": "pub/MatrixMarket2/Harwell-Boeing/smtape/arc130.mtx.gz",
    "ash85": "pub/MatrixMarket2/Harwell-Boeing/smtape/ash85.mtx.gz",
    "bcspwr01": "pub/MatrixMarket2/Harwell-Boeing/bcspwr/bcspwr01.mtx.gz",
    "bcspwr02": "pub/MatrixMarket2/Harwell-Boeing/bcspwr/bcspwr02.mtx.gz",
    "bcspwr03": "pub/MatrixMarket2/Harwell-Boeing/bcspwr/bcspwr03.mtx.gz",
    "bcsstk01": "pub/MatrixMarket2/Harwell-Boeing/bcsstruc1/bcsstk01.mtx.gz",
    "bcsstk04": "pub/MatrixMarket2/Harwell-Boeing/bcsstruc1/bcsstk04.mtx.gz",
    "bcsstk05": "pub/MatrixMarket2/Harwell-Boeing/bcsstruc1/bcsstk05.mtx.gz",
    "bcsstk22": "pub/MatrixMarket2/Harwell-Boeing/bcsstruc3/bcsstk22.mtx.gz",
    "can_144": "pub/MatrixMarket2/Harwell-Boeing/cannes/can__144.mtx.gz",
    "can_161": "pub/MatrixMarket2/Harwell-Boeing/cannes/can__161.mtx.gz",
    "curtis54": "pub/MatrixMarket2/Harwell-Boeing/smtape/curtis54.mtx.gz",
    "fs_183_1": "pub/MatrixMarket2/Harwell-Boeing/facsimile/fs_183_1.mtx.gz",
    "gent113": "pub/MatrixMarket2/Harwell-Boeing/smtape/gent113.mtx.gz",
    "gre_115": "pub/MatrixMarket2/Harwell-Boeing/grenoble/gre__115.mtx.gz",
    "gre_185": "pub/MatrixMarket2/Harwell-Boeing/grenoble/gre__185.mtx.gz",
    "ibm32": "pub/MatrixMarket2/Harwell-Boeing/smtape/ibm32.mtx.gz",
    "impcol_b": "pub/MatrixMarket2/Harwell-Boeing/chemimp/impcol_b.mtx.gz",
    "impcol_c": "pub/MatrixMarket2/Harwell-Boeing/chemimp/impcol_c.mtx.gz",
    "lns_131": "pub/MatrixMarket2/Harwell-Boeing/lns/lns__131.mtx.gz",
    "lund_a": "pub/MatrixMarket2/Harwell-Boeing/smtape/lund_a.mtx.gz",
    "lund_b": "pub/MatrixMarket2/Harwell-Boeing/smtape/lund_b.mtx.gz",
    "mcca": "pub/MatrixMarket2/Harwell-Boeing/astroph/mcca.mtx.gz",
    "nos4": "pub/MatrixMarket2/Harwell-Boeing/lanpro/nos4.mtx.gz",
    "pores_1": "pub/MatrixMarket2/Harwell-Boeing/pores/pores_1.mtx.gz",
    "steam3": "pub/MatrixMarket2/Harwell-Boeing/steam/steam3.mtx.gz",
    "west0132": "pub/MatrixMarket2/Harwell-Boeing/chemwest/west0132.mtx.gz",
    "west0156": "pub/MatrixMarket2/Harwell-Boeing/chemwest/west0156.mtx.gz",
    "west0167": "pub/MatrixMarket2/Harwell-Boeing/chemwest/west0167.mtx.gz",
    "will199": "pub/MatrixMarket2/Harwell-Boeing/smtape/will199.mtx.gz",
    "will57": "pub/MatrixMarket2/Harwell-Boeing/smtape/will57.mtx.gz",

    # --------------------------------------------------------------------------
    # BẢNG 7 (TABLE 7 - PART I): 41 ma trận kích thước lớn
    # --------------------------------------------------------------------------
    "494_bus": "pub/MatrixMarket2/Harwell-Boeing/psadmit/494_bus.mtx.gz",
    "662_bus": "pub/MatrixMarket2/Harwell-Boeing/psadmit/662_bus.mtx.gz",
    "685_bus": "pub/MatrixMarket2/Harwell-Boeing/psadmit/685_bus.mtx.gz",
    "ash292": "pub/MatrixMarket2/Harwell-Boeing/smtape/ash292.mtx.gz",
    "bcspwr04": "pub/MatrixMarket2/Harwell-Boeing/bcspwr/bcspwr04.mtx.gz",
    "bcspwr05": "pub/MatrixMarket2/Harwell-Boeing/bcspwr/bcspwr05.mtx.gz",
    "bcsstk06": "pub/MatrixMarket2/Harwell-Boeing/bcsstruc2/bcsstk06.mtx.gz",
    "bcsstk19": "pub/MatrixMarket2/Harwell-Boeing/bcsstruc3/bcsstk19.mtx.gz",
    "bcsstk20": "pub/MatrixMarket2/Harwell-Boeing/bcsstruc3/bcsstk20.mtx.gz",
    "bcsstm07": "pub/MatrixMarket2/Harwell-Boeing/bcsstruc1/bcsstm07.mtx.gz",
    "bp_0": "pub/MatrixMarket2/Harwell-Boeing/smtape/bp_____0.mtx.gz",
    "bp_200": "pub/MatrixMarket2/Harwell-Boeing/smtape/bp___200.mtx.gz",
    "bp_400": "pub/MatrixMarket2/Harwell-Boeing/smtape/bp___400.mtx.gz",
    "bp_600": "pub/MatrixMarket2/Harwell-Boeing/smtape/bp___600.mtx.gz",
    "bp_800": "pub/MatrixMarket2/Harwell-Boeing/smtape/bp___800.mtx.gz",
    "bp_1000": "pub/MatrixMarket2/Harwell-Boeing/smtape/bp__1000.mtx.gz",
    "bp_1200": "pub/MatrixMarket2/Harwell-Boeing/smtape/bp__1200.mtx.gz",
    "bp_1400": "pub/MatrixMarket2/Harwell-Boeing/smtape/bp__1400.mtx.gz",
    "bp_1600": "pub/MatrixMarket2/Harwell-Boeing/smtape/bp__1600.mtx.gz",
    "can_292": "pub/MatrixMarket2/Harwell-Boeing/cannes/can__292.mtx.gz",
    "can_445": "pub/MatrixMarket2/Harwell-Boeing/cannes/can__445.mtx.gz",
    "can_715": "pub/MatrixMarket2/Harwell-Boeing/cannes/can__715.mtx.gz",
    "can_838": "pub/MatrixMarket2/Harwell-Boeing/cannes/can__838.mtx.gz",
    "dwt_209": "pub/MatrixMarket2/Harwell-Boeing/dwt/dwt__209.mtx.gz",
    "dwt_221": "pub/MatrixMarket2/Harwell-Boeing/dwt/dwt__221.mtx.gz",
    "dwt_234": "pub/MatrixMarket2/Harwell-Boeing/dwt/dwt__234.mtx.gz",
    "dwt_245": "pub/MatrixMarket2/Harwell-Boeing/dwt/dwt__245.mtx.gz",
    "dwt_310": "pub/MatrixMarket2/Harwell-Boeing/dwt/dwt__310.mtx.gz",
    "dwt_361": "pub/MatrixMarket2/Harwell-Boeing/dwt/dwt__361.mtx.gz",
    "dwt_419": "pub/MatrixMarket2/Harwell-Boeing/dwt/dwt__419.mtx.gz",
    "dwt_503": "pub/MatrixMarket2/Harwell-Boeing/dwt/dwt__503.mtx.gz",
    "dwt_592": "pub/MatrixMarket2/Harwell-Boeing/dwt/dwt__592.mtx.gz",
    "dwt_878": "pub/MatrixMarket2/Harwell-Boeing/dwt/dwt__878.mtx.gz",
    "dwt_918": "pub/MatrixMarket2/Harwell-Boeing/dwt/dwt__918.mtx.gz",
    "dwt_992": "pub/MatrixMarket2/Harwell-Boeing/dwt/dwt__992.mtx.gz",
    "fs_541_1": "pub/MatrixMarket2/Harwell-Boeing/smtape/fs_541_1.mtx.gz",
    "fs_680_1": "pub/MatrixMarket2/Harwell-Boeing/facsimile/fs_680_1.mtx.gz",
    "fs_760_1": "pub/MatrixMarket2/Harwell-Boeing/facsimile/fs_760_1.mtx.gz",
    "gr_30_30": "pub/MatrixMarket2/Harwell-Boeing/laplace/gr_30_30.mtx.gz",
    "gre_216a": "pub/MatrixMarket2/Harwell-Boeing/grenoble/gre_216a.mtx.gz",
    "gre_343": "pub/MatrixMarket2/Harwell-Boeing/grenoble/gre__343.mtx.gz",
}


def get_matrix_url(name):
    """Lấy URL tải chính thức từ NIST Matrix Market."""
    if name not in NIST_MAP:
        return None
    return f"https://math.nist.gov/{NIST_MAP[name]}"


def download_hb_matrix(name, target_dir="data", timeout=20):
    """Tải và giải nén 1 ma trận từ NIST Matrix Market về thư mục target_dir."""
    os.makedirs(target_dir, exist_ok=True)
    mtx_path = os.path.join(target_dir, f"{name}.mtx")
    if os.path.exists(mtx_path):
        return mtx_path

    if name not in NIST_MAP:
        print(f"[Warning] Không tìm thấy URL cấu hình cho {name}")
        return None

    path_part = NIST_MAP[name]
    url = f"https://math.nist.gov/{path_part}"
    gz_path = os.path.join(target_dir, f"{name}.mtx.gz")

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        print(f"Downloading {name} from {url} ...")
        with urllib.request.urlopen(req, timeout=timeout) as resp, open(gz_path, "wb") as f:
            f.write(resp.read())

        with gzip.open(gz_path, "rb") as gz_in, open(mtx_path, "wb") as mtx_out:
            mtx_out.write(gz_in.read())

        if os.path.exists(gz_path):
            os.remove(gz_path)
        print(f"-> Successfully downloaded: {mtx_path}")
        return mtx_path
    except Exception as e:
        print(f"Error downloading {name}: {e}")
        if os.path.exists(gz_path):
            os.remove(gz_path)
        return None


def download_all_matrices(target_dir="data", table=None):
    """Tải tất cả các ma trận benchmark."""
    os.makedirs(target_dir, exist_ok=True)
    success = 0
    total = len(NIST_MAP)
    print(f"Bắt đầu tải toàn bộ {total} ma trận benchmark về thư mục '{target_dir}'...")

    for i, name in enumerate(NIST_MAP, 1):
        print(f"[{i}/{total}] Đang xử lý: {name} ...")
        res = download_hb_matrix(name, target_dir=target_dir)
        if res:
            success += 1

    print(f"\nHoàn tất tải dữ liệu: {success}/{total} ma trận sẵn sàng trong '{target_dir}'.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tải benchmark ma trận Harwell-Boeing từ NIST")
    parser.add_argument("--all", action="store_true", help="Tải toàn bộ 72 ma trận trong Bảng 6 & Bảng 7")
    parser.add_argument("names", nargs="*", help="Tên các ma trận cần tải (ví dụ: bcspwr01 can_144)")
    args = parser.parse_args()

    if args.all:
        download_all_matrices()
    elif args.names:
        for n in args.names:
            download_hb_matrix(n)
    else:
        # Mặc định tải mẫu vài ma trận tiêu biểu
        for m in ["bcspwr01", "bcspwr02", "bcsstk01", "curtis54", "pores_1"]:
            download_hb_matrix(m)

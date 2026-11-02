"""Module tải tự động các ma trận thuộc bộ benchmark Harwell-Boeing từ NIST

Matrix Market.
"""

import gzip
import os
import urllib.request

# Ánh xạ tên ma trận sang thư mục tương ứng trên NIST Matrix Market
NIST_MAP = {
    # Các ma trận nhỏ từ Bảng 6 (Table 6)
    "ibm32": "data/Harwell-Boeing/ibm/ibm32.html",
    "bcspwr01": "pub/MatrixMarket2/Harwell-Boeing/bcspwr/bcspwr01.mtx.gz",
    "bcspwr02": "pub/MatrixMarket2/Harwell-Boeing/bcspwr/bcspwr02.mtx.gz",
    "bcspwr03": "pub/MatrixMarket2/Harwell-Boeing/bcspwr/bcspwr03.mtx.gz",
    "bcsstk01": "pub/MatrixMarket2/Harwell-Boeing/bcsstk/bcsstk01.mtx.gz",
    "bcsstk04": "pub/MatrixMarket2/Harwell-Boeing/bcsstk/bcsstk04.mtx.gz",
    "bcsstk05": "pub/MatrixMarket2/Harwell-Boeing/bcsstk/bcsstk05.mtx.gz",
    "bcsstk22": "pub/MatrixMarket2/Harwell-Boeing/bcsstk/bcsstk22.mtx.gz",
    "curtis54": "pub/MatrixMarket2/Harwell-Boeing/curtis/curtis54.mtx.gz",
    "will57": "pub/MatrixMarket2/Harwell-Boeing/will/will57.mtx.gz",
    "impcol_b": "pub/MatrixMarket2/Harwell-Boeing/smtape/impcol_b.mtx.gz",
    "steam3": "pub/MatrixMarket2/Harwell-Boeing/steam/steam3.mtx.gz",
    "ash85": "pub/MatrixMarket2/Harwell-Boeing/ash/ash85.mtx.gz",
    "nos4": "pub/MatrixMarket2/Harwell-Boeing/nos/nos4.mtx.gz",
    "arc130": "pub/MatrixMarket2/Harwell-Boeing/arc/arc130.mtx.gz",
}


def download_hb_matrix(name, target_dir="data"):
    os.makedirs(target_dir, exist_ok=True)
    mtx_path = os.path.join(target_dir, f"{name}.mtx")
    if os.path.exists(mtx_path):
        return mtx_path

    if name not in NIST_MAP:
        print(f"[Warning] No configured URL for {name}")
        return None

    path_part = NIST_MAP[name]
    url = f"https://math.nist.gov/{path_part}"
    gz_path = os.path.join(target_dir, f"{name}.mtx.gz")

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        print(f"Downloading {name} from {url} ...")
        with (
            urllib.request.urlopen(req, timeout=20) as resp,
            open(gz_path, "wb") as f,
        ):
            f.write(resp.read())

        with gzip.open(gz_path, "rb") as gz_in, open(mtx_path, "wb") as mtx_out:
            mtx_out.write(gz_in.read())

        if os.path.exists(gz_path):
            os.remove(gz_path)
        print(f"-> Successfully downloaded: {mtx_path}")
        return mtx_path
    except Exception as e:
        print(f"Error downloading {name}: {e}")
        return None


if __name__ == "__main__":
    for m in ["bcspwr01", "bcspwr02", "bcsstk01", "curtis54", "will57"]:
        download_hb_matrix(m)

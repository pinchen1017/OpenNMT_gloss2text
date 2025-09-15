# split_dataset.py
from pathlib import Path
import argparse, random

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="全部資料的 src 檔，例如 data/all.src")
    ap.add_argument("--tgt", required=True, help="全部資料的 tgt 檔，例如 data/all.tgt")
    ap.add_argument("--out_dir", default="data", help="輸出資料夾（預設 data）")
    ap.add_argument("--train_ratio", type=float, default=0.90)
    ap.add_argument("--valid_ratio", type=float, default=0.05)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    out = Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)

    src_lines = Path(args.src).read_text(encoding="utf-8").splitlines()
    tgt_lines = Path(args.tgt).read_text(encoding="utf-8").splitlines()
    assert len(src_lines) == len(tgt_lines), f"行數不一致：src={len(src_lines)} tgt={len(tgt_lines)}"

    n = len(src_lines)
    random.seed(args.seed)
    idx = list(range(n))
    random.shuffle(idx)

    n_train = int(n * args.train_ratio)
    n_valid = int(n * args.valid_ratio)
    # 至少留 1 筆給每個 split（若資料很少）
    if n_valid == 0 and n >= 3:
        n_valid = 1
    n_test = max(0, n - n_train - n_valid)
    if n_test == 0 and n - n_train - n_valid > 0:
        n_test = 1
        n_train = max(1, n - n_valid - n_test)

    tr = idx[:n_train]
    va = idx[n_train:n_train+n_valid]
    te = idx[n_train+n_valid:]

    def dump(split, ids):
        (out/f"{split}.src").write_text("\n".join(src_lines[i] for i in ids), encoding="utf-8")
        (out/f"{split}.tgt").write_text("\n".join(tgt_lines[i] for i in ids), encoding="utf-8")

    dump("train", tr)
    dump("valid", va)
    dump("test", te)

    print(f"總數: {n}")
    print(f"train/valid/test = {len(tr)}/{len(va)}/{len(te)}")

if __name__ == "__main__":
    main()

# build_parallel_from_csv.py
import csv, re, os, glob, random, unicodedata
from pathlib import Path
random.seed(42)

ANS = "ans.csv"  # 第一欄=句子ID, 第二欄=繁中最終句子（若不同請改）
GLOSS_DIR = "gloss_csvs"  # 放各句的 gloss csv
OUT = Path("data"); OUT.mkdir(exist_ok=True)

def clean_and_filter_gloss(rows):
    """
    rows: list of dict/row，預期有 'gloss' 欄（可選 'score'）
    規則：
      - 正規化/去頭尾空白
      - 移除黑名單與不符合 ALLOW 的 token
      - 同 token 連續重複只保留一次
      - 若有 score 欄位：先以 score 降冪排序再截斷至長度上限
    """
    toks = []
    # 1) 取出 (gloss, score)
    pairs = []
    for r in rows:
        g = znormalize(str(r.get("gloss", r[0] if isinstance(r, list) and r else "")).strip())
        sc = r.get("score", r[1] if isinstance(r, list) and len(r) > 1 else "")
        try: sc = float(sc)
        except: sc = 1.0
        pairs.append((g, sc))

    # 2) 先依 score 排序（如果沒有 score 基本等值不影響）
    pairs.sort(key=lambda x: x[1], reverse=True)

    # 3) 逐一篩選
    last = None
    MAX_LEN = 80  # 一句最多保留 80 個 gloss，可自行調
    for g, _ in pairs:
        if not g or g in BLACK: continue
        if not ALLOW.match(g): continue
        if g == last: continue
        toks.append(g)
        last = g
        if len(toks) >= MAX_LEN:
            break

    # 4) 以空白連接成 src 字串
    return " ".join(toks)

# ---- 1) 讀取答案表 ----
# 假設 ans.csv 形式：id, text
id2tgt = {}
with open(ANS, "r", encoding="utf-8") as f:
    r = csv.reader(f)
    for row in r:
        if not row: continue
        sid = str(row[0]).strip()
        tgt = str(row[1]).strip()
        if sid and tgt:
            id2tgt[sid] = tgt

# ---- 2) 工具：繁中/全半形正規化 + gloss 清洗規則 ----
def znormalize(s: str) -> str:
    # NFKC 正規化，常見全形符號 → 半形
    return unicodedata.normalize("NFKC", s)

# 允許的 gloss 形狀（繁中詞、拉丁字、數字、連字號），避免雜訊
ALLOW = re.compile(r"^[\u4e00-\u9fffA-Za-z0-9\-]+$")
BLACK = set(["", "UNK", "<unk>", "<noise>", "SIL", "SP", "PAD"])

# ---- 3) 讀每句的 gloss csv 並配對答案 ----
src_lines, tgt_lines = [], []

for fp in glob.glob(os.path.join(GLOSS_DIR, "*.csv")):
    # 嘗試從檔名擷取句子 ID（你可依命名規則修改）
    # 例如：課文_L1_CH1_1-1__final.csv → 句子ID = 課文_L1_CH1_1（示例）
    name = Path(fp).stem
    # 若你的 ans.csv 裡的 ID 恰好等於完整檔名，可直接：sid = name
    sid = name.split("__")[0].split("-")[0]  # 依實際調整
    if sid not in id2tgt:
        # 找不到就略過（或印出提醒）
        # print("No target for", sid)
        continue

    # 讀 gloss 檔（允許沒有表頭）
    rows = []
    with open(fp, "r", encoding="utf-8") as f:
        sniffer = csv.Sniffer()
        sample = f.read(1024); f.seek(0)
        has_header = False
        try: has_header = sniffer.has_header(sample)
        except: pass
        r = csv.DictReader(f) if has_header else csv.reader(f)
        for row in r:
            rows.append(row)

    src = clean_and_filter_gloss(rows)
    tgt = znormalize(id2tgt[sid]).strip()
    if src and tgt:
        src_lines.append(src)
        tgt_lines.append(tgt)

assert len(src_lines) == len(tgt_lines) and len(src_lines) > 0, "沒有對齊到任何句子，請檢查命名或欄位"
print("pairs:", len(src_lines))

# ---- 4) 輸出 train（先全部當 train；稍後切 dev/test）----
(Path("data/train.src")).write_text("\n".join(src_lines), encoding="utf-8")
(Path("data/train.tgt")).write_text("\n".join(tgt_lines), encoding="utf-8")

print("Wrote data/train.src, data/train.tgt")

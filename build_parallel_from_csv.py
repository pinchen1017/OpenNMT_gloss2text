# build_parallel_from_csv.py  (robust)
import csv, re, os, glob, random, unicodedata, argparse
from pathlib import Path
random.seed(42)

def z(s): return unicodedata.normalize("NFKC", str(s)).strip()

def read_ans(ans_path):
    id2tgt = {}
    with open(ans_path, "r", encoding="utf-8") as f:
        sample = f.read(2048); f.seek(0)
        has_header = False
        try:
            has_header = csv.Sniffer().has_header(sample)
        except:
            pass
        if has_header:
            r = csv.DictReader(f)
            # 嘗試常見欄名
            cand_id = ["id","ID","sid","句子ID","句子id","編號"]
            cand_txt= ["text","Text","sentence","句子","答案","target"]
            for row in r:
                if not row: continue
                sid = None; tgt = None
                for k in cand_id:
                    if k in row: sid = z(row[k]); break
                if sid is None:
                    sid = z(list(row.values())[0])
                for k in cand_txt:
                    if k in row: tgt = z(row[k]); break
                if tgt is None:
                    vals = list(row.values())
                    tgt = z(vals[1] if len(vals)>1 else "")
                if sid and tgt: id2tgt[sid]=tgt
        else:
            r = csv.reader(f)
            for row in r:
                if not row: continue
                sid = z(row[0]); tgt = z(row[1]) if len(row)>1 else ""
                if sid and tgt: id2tgt[sid]=tgt
    return id2tgt

def name_to_id(name, id_regex):
    cand = set()
    cand.add(name)
    # 去除 __final* 後綴
    cand.add(re.split(r"__final.*$", name)[0])
    # 去除 -數字 片段
    cand.update(re.split(r"-\d+(?:-\d+)*", c) [0] for c in list(cand))
    # 自訂 regex 擷取
    if id_regex:
        m = re.search(id_regex, name)
        if m:
            cand.add(m.group(1) if m.groups() else m.group(0))
    # 乾淨化
    return [c for c in {z(c) for c in cand} if c]

def choose_best_id(name, id2tgt, id_regex):
    cands = name_to_id(name, id_regex)
    # 完全相等
    for c in cands:
        if c in id2tgt: return c
    # 子字串最大重疊
    best = None; best_len = -1
    keys = list(id2tgt.keys())
    for c in cands:
        for k in keys:
            if c in k and len(c) > best_len:
                best, best_len = k, len(c)
            elif k in c and len(k) > best_len:
                best, best_len = k, len(k)
    return best

# def load_gloss_rows(csv_path):
#     rows=[]
#     with open(csv_path, "r", encoding="utf-8") as f:
#         sample = f.read(2048); f.seek(0)
#         has_header=False
#         try:
#             has_header = csv.Sniffer().has_header(sample)
#         except:
#             pass
#         if has_header:
#             r = csv.DictReader(f)
#             for row in r: rows.append(row)
#         else:
#             r = csv.reader(f)
#             for row in r: rows.append(row)
#     return rows

def load_gloss_rows(csv_path):
    rows=[]
    with open(csv_path, "r", encoding="utf-8") as f:
        sample = f.read(2048); f.seek(0)
        has_header=False
        try:
            has_header = csv.Sniffer().has_header(sample)
        except:
            pass
        if has_header:
            r = csv.DictReader(f)
            # 嘗試常見欄名：gloss, token, word, 詞, 候選, 文字...
            prefer_keys = ["gloss","Gloss","GLOSS","token","word","詞","候選","文字","詞彙","gloss_all","top1","候選詞"]
            for row in r:
                if not row: continue
                # 轉成統一鍵：gloss / score
                dd = {}
                # 找 gloss 欄
                g = None
                for k in prefer_keys:
                    if k in row and str(row[k]).strip():
                        g = row[k]; break
                if g is None:
                    # 退化：取第一欄
                    g = list(row.values())[0]
                dd["gloss"] = g
                # 找 score 欄
                sc = None
                for k in ["score","Score","conf","confidence","prob","概率","信心","分數","得分"]:
                    if k in row:
                        sc = row[k]; break
                dd["score"] = sc if sc is not None else 1.0
                rows.append(dd)
        else:
            r = csv.reader(f)
            for row in r:
                if not row: continue
                rows.append({"gloss": row[0], "score": (row[1] if len(row)>1 else 1.0)})
    return rows

# def clean_and_filter(rows, allow_regex, blacklist, score_key, score_min, max_len):
#     ALLOW = re.compile(allow_regex)
#     BLACK = set(blacklist)
#     pairs=[]
#     for r in rows:
#         g = z(r.get("gloss", r[0] if isinstance(r, list) and r else ""))
#         sc = r.get(score_key, r[1] if isinstance(r, list) and len(r)>1 else 1.0)
#         try: sc = float(sc)
#         except: sc = 1.0
#         pairs.append((g, sc))
#     # 先依分數
#     pairs.sort(key=lambda x:x[1], reverse=True)
#     toks=[]; last=None
#     for g, sc in pairs:
#         if sc < score_min: continue
#         if not g or g in BLACK: continue
#         if not re.match(ALLOW, g): continue
#         if g == last: continue
#         toks.append(g); last=g
#         if len(toks) >= max_len: break
#     return " ".join(toks)

def clean_and_filter(rows, allow_regex, blacklist, score_key, score_min, max_len):
    ALLOW = re.compile(allow_regex)
    BLACK = set(blacklist)
    pairs=[]
    for r in rows:
        graw = z(r.get("gloss",""))
        sc = r.get(score_key, 1.0)
        try: sc = float(sc)
        except: sc = 1.0
        pairs.append((graw, sc))
    # 分數由高到低
    pairs.sort(key=lambda x:x[1], reverse=True)

    toks=[]; last=None
    for graw, sc in pairs:
        if sc < score_min: continue
        # 一列可能是「我 想 去 市場」→ 逐 token 檢核
        for g in re.split(r"\s+", graw):
            g = z(g)
            if not g or g in BLACK: continue
            if not ALLOW.match(g): continue
            if g == last: continue
            toks.append(g); last = g
            if len(toks) >= max_len:
                return " ".join(toks)
    return " ".join(toks)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ans", required=True, help="路徑：ans.csv")
    ap.add_argument("--gloss_dir", required=True, help="路徑：放各句 gloss 的 csv 資料夾")
    ap.add_argument("--out_dir", default="data", help="輸出資料夾（預設 data）")
    ap.add_argument("--id_regex", default=r"^(課文_[^_]+_CH\d+_\d+)", help="自訂從檔名擷取 ID 的 regex")
    ap.add_argument("--allow_regex", default=r"^[\u4e00-\u9fffA-Za-z0-9\-]+$", help="允許的 token 形狀")
    ap.add_argument("--blacklist", default="UNK,<unk>,<noise>,SIL,SP,PAD", help="以逗號分隔")
    ap.add_argument("--score_key", default="score", help="CSV 中分數欄位名稱（沒有就會退化）")
    ap.add_argument("--score_min", type=float, default=0.3, help="低於此分數的 gloss 直接丟棄")
    ap.add_argument("--max_len", type=int, default=80, help="最多保留幾個 gloss")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    out = Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)

    id2tgt = read_ans(args.ans)
    if args.debug:
        print("ANS keys (sample 5):", list(id2tgt.keys())[:5])

    src_lines=[]; tgt_lines=[]
    files = glob.glob(os.path.join(args.gloss_dir, "*.csv"))
    if args.debug:
        print("Gloss files:", len(files))
    miss = []

    for fp in files:
        name = Path(fp).stem
        sid = choose_best_id(name, id2tgt, args.id_regex)
        if not sid:
            miss.append(name)
            continue
        rows = load_gloss_rows(fp)
        src = clean_and_filter(
            rows,
            allow_regex=args.allow_regex,
            blacklist=[z(x) for x in args.blacklist.split(",") if x],
            score_key=args.score_key,
            score_min=args.score_min,
            max_len=args.max_len,
        )
        tgt = z(id2tgt[sid])
        if src and tgt:
            src_lines.append(src); tgt_lines.append(tgt)
        elif args.debug:
            print("[SKIP] empty after filter:", name)

    if args.debug and miss:
        print("Unmatched files count:", len(miss))
        print("Unmatched examples:", miss[:10])

    assert len(src_lines)==len(tgt_lines) and len(src_lines)>0, "沒有對齊到任何句子，請檢查命名/regex/欄位或加 --debug 觀察"

    (out/"train.src").write_text("\n".join(src_lines), encoding="utf-8")
    (out/"train.tgt").write_text("\n".join(tgt_lines), encoding="utf-8")
    print("pairs:", len(src_lines))
    print("Wrote", out/"train.src", "and", out/"train.tgt")

if __name__ == "__main__":
    main()

import sys, json, collections
sys.path.insert(0, sys.argv[1])
import xlsx_read
out = {}
for f in sys.argv[2:]:
    data = open(f, "rb").read()
    rows = [[r.get(i) for i in range(8)] for r in xlsx_read.rows(data)]
    rows = [r for r in rows if any(c not in (None, "") for c in r)]
    hdr = rows[0]
    out[f] = {"hdr": [str(h) for h in hdr], "n": len(rows)}
    ag = collections.defaultdict(float); pg = collections.defaultdict(float); cc = collections.defaultdict(float); fu = collections.defaultdict(float)
    for r in rows[3:]:
        a, fnd, p, c = r[0], r[1], r[2], r[3]
        if not a or str(a).startswith("Total"): continue
        try: v = float(r[-1] or 0)
        except: v = 0
        ag[a] += v; pg[(a, p)] += v; cc[c] += v; fu[fnd] += v
    out[f].update(ag=sorted(ag.items(), key=lambda x: -x[1]), pg=[[a, p, v] for (a, p), v in pg.items()], cc=sorted(cc.items(), key=lambda x: -x[1]), fu=list(fu.items()))
json.dump(out, open(sys.argv[2].rsplit("/", 2)[0] + "/work/ogp_lists.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
for f, d in out.items():
    print(f.rsplit("/",1)[-1], d["hdr"], d["n"], "agencies", len(d["ag"]), "programs", len(d["pg"]), "concepts", len(d["cc"]))
    print("  funds", d["fu"]); print("  concepts", [(c, round(v/1e3)) for c, v in d["cc"]])

"""Independent recompute of T14b lowfloor_probe.json. Does not trust stored summary/verdict."""
import json, math, statistics, sys
from pathlib import Path
import lowfloor_probe as L

D = json.loads(Path('lowfloor_probe.json').read_text())
rows = D['rows']
FIELDS = ('rho_bar','N_eff','delta_inst','delta_priv','rate_cand','rate_total','pass_rate')
# 1. recompute summary from raw rows
by = {}
for r in rows:
    by.setdefault((r['id'], r['rho_param'], r['N']), []).append(r)
mismatches = []
stored = {(x['id'], x['rho_param'], x['N']): x for x in D['summary']}
for k, sub in by.items():
    for f in FIELDS:
        c = statistics.fmean(x[f] for x in sub)
        s = stored[k][f]
        if abs(c - s) > 1e-9:
            mismatches.append(f'summary {k} {f} computed={c} stored={s}')
# 2. recompute verdicts from RECOMPUTED summary, compare to stored
recomp_s = {k: {f: statistics.fmean(x[f] for x in sub) for f in FIELDS} for k, sub in by.items()}
C = {c['id']: c for c in L.CONSTRUCTORS}
for cid, Cfg in C.items():
    rv = L.verdict_for(Cfg, recomp_s)
    sv = D['verdicts'][cid]
    for k in ('rho0','rho1','pearson','monotone','Neff0','span','V1','V2','judgeable','D1_shape','D2','D4_tax_min'):
        if rv[k] != sv[k]:
            mismatches.append(f'verdict {cid} {k} recomputed={rv[k]} stored={sv[k]}')
# 3. prove-red: inject a perfect constructor by editing recomputed summary; gate must flip
fake = {k: dict(v) for k,v in recomp_s.items()}
for rr in L.RHO_GRID:
    fake[(L.CONSTRUCTORS[0]['id'], rr, 16)]['rho_bar'] = rr
    fake[(L.CONSTRUCTORS[0]['id'], rr, 16)]['N_eff'] = L.P.n_eff(16, rr)
inj = L.verdict_for(L.CONSTRUCTORS[0], fake)
red_ok = inj['judgeable'] and not D['verdicts']['C0']['judgeable']
# 4. report
maxspan = max(v['span'] for v in D['verdicts'].values())
minrho0 = min(v['rho0'] for v in D['verdicts'].values())
flips = [cid for cid,v in D['verdicts'].items() if v['D2']=='RATE_FLIP_ANY']
print(f'rows={len(rows)} summary_cells={len(by)*len(FIELDS)} mismatches={len(mismatches)}')
for m in mismatches[:20]: print('  MISMATCH', m)
print(f'max_span={maxspan:.4f} (threshold 3.0)  min_rho0={minrho0:.4f} (threshold 0.40 / V2 needs <=0.2889)')
print(f'D2_rate_flip_constructors={flips}')
print(f'prove_red_injected_judgeable={inj["judgeable"]} base_judgeable={D["verdicts"]["C0"]["judgeable"]} red_ok={red_ok}')
print(f'floor_decomp={D["floor_decomp"]}')
verdict = 'OK' if not mismatches and red_ok else 'FAIL'
print('verdict='+verdict)
sys.exit(0 if verdict=='OK' else 1)

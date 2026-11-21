"""T14b: low-floor proposer search. Can task-geometry rho floor be pushed below 0.289?

Read-only reuse of T14-deep engine. Pre-registration: PRE_REGISTRATION.md.
Usage:
  python3 lowfloor_probe.py --self-test
  python3 lowfloor_probe.py --out lowfloor_probe.json
"""
from __future__ import annotations
import argparse, json, math, random, statistics, sys
from pathlib import Path

DEEP = Path(__file__).resolve().parents[1] / 'T14-deep'
sys.path.insert(0, str(DEEP))
import frozen_anchor as F  # noqa: E402

P, Ctx, HP, V = F.P, F.ContextualTask, F.HeuristicPolicy, F.verdict
BASELINE, Z0, TRUE_W = F.BASELINE, F.Z0, F.TRUE_W
from rsi_agent.core import ScoreVector  # noqa: E402
from rsi_agent.gates import paired_gate, estimate_noise_floor  # noqa: E402

RHO_GRID = F.RHO_GRID  # 0..1 step .1
INNER_PROBES = F.INNER_PROBES

# constructor space (pre-registered §2)
CONSTRUCTORS = [
    {'id':'C0',   'rho_param':'sqrt',   'step':1.0, 'eps_norm':False,'anchor':'base','multi':False,'delta_base':'baseline','na':6},
    {'id':'C1',   'rho_param':'linear', 'step':1.0, 'eps_norm':False,'anchor':'base','multi':False,'delta_base':'baseline','na':6},
    {'id':'C2a',  'rho_param':'sqrt',   'step':2.0, 'eps_norm':False,'anchor':'base','multi':False,'delta_base':'baseline','na':6},
    {'id':'C2b',  'rho_param':'sqrt',   'step':3.0, 'eps_norm':False,'anchor':'base','multi':False,'delta_base':'baseline','na':6},
    {'id':'C3',   'rho_param':'sqrt',   'step':1.0, 'eps_norm':True, 'anchor':'base','multi':False,'delta_base':'baseline','na':6},
    {'id':'C4',   'rho_param':'sqrt',   'step':1.0, 'eps_norm':False,'anchor':'base','multi':True, 'delta_base':'baseline','na':6},
    {'id':'C5',   'rho_param':'sqrt',   'step':1.0, 'eps_norm':False,'anchor':'base','multi':False,'delta_base':'zero','na':6},
    {'id':'C6a',  'rho_param':'sqrt',   'step':1.0, 'eps_norm':False,'anchor':'zero','multi':False,'delta_base':'baseline','na':6},
    {'id':'C6b',  'rho_param':'sqrt',   'step':1.0, 'eps_norm':False,'anchor':'orth','multi':False,'delta_base':'baseline','na':6},
    {'id':'C7',   'rho_param':'sqrt',   'step':1.0, 'eps_norm':False,'anchor':'base','multi':False,'delta_base':'baseline','na':12},
]


def choose_anchor(mode):
    if mode == 'base':
        return F.ANCHOR
    if mode == 'zero':
        return (0.0, 0.0, 0.0)
    if mode == 'orth':
        # integer vector perpendicular to TRUE_W=(0.9,-0.6,1.2): 0.9a-0.6b+1.2c=0 -> (2,3,0)
        return (2.0/7.0, 3.0/7.0, 0.0)
    raise ValueError(mode)


def propose_c(rho, g, n, seed, anchor, z, C):
    rng = random.Random(f"t14b:{C['id']}:{seed}:{g}")
    s = C['step'] * F.step_of(g)
    if C['rho_param'] == 'sqrt':
        sh, ind = rho ** 0.5, (1.0 - rho) ** 0.5
    else:
        sh, ind = rho, 1.0 - rho
    anchors = P.D2_ANCHORS if C['multi'] else (anchor,)
    out = []
    for i in range(n):
        a = anchors[i % len(anchors)]
        eps = tuple(rng.gauss(0.0, 1.0) for _ in range(3))
        if C['eps_norm']:
            en = math.sqrt(sum(x*x for x in eps)) or 1.0
            eps = tuple(x / en * math.sqrt(3.0) for x in eps)
        w = tuple(round(a[j] + s * (sh * z[j] + ind * eps[j]), 4) for j in range(3))
        out.append(HP(w, name=f"g{g}c{i}"))
    return out


def run_c(rho, n, gens, seed, C, capture=False):
    na = C['na']
    public = Ctx(seed=1000 + seed, n_episodes=128, n_actions=na)
    private = Ctx(seed=90000 + seed, n_episodes=128, n_actions=na)
    floor = estimate_noise_floor(public, BASELINE)
    base_pub = F.evaluate_cached(public, BASELINE)
    base_priv = F.evaluate_cached(private, BASELINE)
    if C['delta_base'] == 'zero':
        base_view = ScoreVector(tuple(0.0 for _ in base_pub.values))
    else:
        base_view = ScoreVector(base_pub.values)
    base_mean = base_pub.mean
    alphas = [0.05 / max(gens - g, 1) for g in range(gens)]
    anchor, z = choose_anchor(C['anchor']), Z0
    per_gen_rho, deltas_inst, deltas_acc = [], [], []
    pass_tot = promoted = 0
    delta_mats = []
    for g in range(gens):
        pool = propose_c(rho, g, n, seed, anchor, z, C)
        pv_pub = [F.evaluate_cached(public, p) for p in pool]
        pv_priv = [F.evaluate_cached(private, p) for p in pool]
        dvecs = [P.delta_vector(x, base_view) for x in pv_pub]
        if n >= 2:
            per_gen_rho.append(P.mean_pairwise_rho(dvecs))
            if capture:
                delta_mats.append(dvecs)
        deltas_inst.append(max(x.mean for x in pv_pub) - base_mean)
        views = [ScoreVector(x.values) for x in pv_pub]
        passes = [i for i in range(n) if paired_gate(base_view, views[i], floor, alphas[g]).passed]
        pass_tot += len(passes)
        k = max(passes, key=lambda i: views[i].mean) if passes else None
        if k is not None:
            deltas_acc.append(pv_priv[k].mean - base_priv.mean)
            promoted += 1
        if C['anchor'] in ('base','zero','orth'):
            z = F.inner_update(g, seed, choose_anchor(C['anchor']), z, public, base_mean)
    rho_bar = statistics.fmean(per_gen_rho) if per_gen_rho else 1.0
    row = {
        'id': C['id'], 'rho_param': rho, 'N': n, 'seed': seed, 'gens': gens,
        'rho_bar': round(rho_bar, 6),
        'N_eff': round(P.n_eff(n, rho_bar), 4),
        'delta_inst': round(statistics.fmean(deltas_inst), 6),
        'delta_priv': round(statistics.fmean(deltas_acc), 6) if deltas_acc else 0.0,
        'rate_cand': round(statistics.fmean(deltas_acc) / max(gens*n,1) * 1000, 4) if deltas_acc else 0.0,
        'rate_total': round(statistics.fmean(deltas_acc) / max(gens*(n+INNER_PROBES),1) * 1000, 4) if deltas_acc else 0.0,
        'pass_rate': round(pass_tot/max(gens*n,1), 6), 'promoted': promoted,
        '_rho_gen': [round(x,6) for x in per_gen_rho],
    }
    if capture:
        row['_delta_mats'] = delta_mats
    return row


def summarize(rows):
    s = {}
    by = {}
    for r in rows:
        by.setdefault((r['id'], r['rho_param'], r['N']), []).append(r)
    for (cid, rho, n), sub in by.items():
        s[(cid, rho, n)] = {k: statistics.fmean(x[k] for x in sub)
                            for k in ('rho_bar','N_eff','delta_inst','delta_priv','rate_cand','rate_total','pass_rate')}
    return s


def common_signal(delta_mats):
    """mean_i pearson(delta_i, m) over gens; m = cross-candidate mean. prereg §3."""
    vals = []
    for dvecs in delta_mats:
        m = tuple(statistics.fmean(row[j] for row in dvecs) for j in range(len(dvecs[0])))
        cs = [P.pearson(row, m) for row in dvecs]
        vals.append(statistics.fmean(cs))
    return round(statistics.fmean(vals), 6) if vals else 0.0


def verdict_for(C, s):
    cid = C['id']
    rb = [s[(cid, r, 16)]['rho_bar'] for r in RHO_GRID]
    mono = all(rb[i] <= rb[i+1] + 1e-9 for i in range(len(rb)-1))
    pear = P.pearson(tuple(RHO_GRID), tuple(rb))
    v1 = mono and rb[0] <= 0.40 and abs(rb[-1]-1.0) <= 0.002 and pear >= 0.95
    ne0 = s[(cid, 0.0, 16)]['N_eff']; ne1 = s[(cid, 1.0, 16)]['N_eff']
    span = ne0 / max(ne1, 1e-9)
    v2 = span >= 3.0
    flips = [r for r in RHO_GRID if s[(cid, r, 16)]['rate_total'] >= s[(cid, r, 4)]['rate_total']] if all((cid,r,4) in s for r in RHO_GRID) else ['NA']
    taxes = [s[(cid,r,4)]['rate_total']/max(s[(cid,r,16)]['rate_total'],1e-9) for r in RHO_GRID if (cid,r,4) in s]
    d2 = 'RATE_FLIP_ANY' if flips and flips[0]!='NA' else ('RATE_ROBUST_ACROSS_RHO' if flips==[] else 'NA_no_N4')
    d4 = round(min(taxes),4) if taxes else None
    dinst = [s[(cid,r,16)]['delta_inst'] for r in RHO_GRID]
    sp = F.spearman(RHO_GRID, dinst)
    gap = dinst[0]-dinst[-1]
    shape = 'COLLAPSE_REPRODUCED' if sp<=-0.8 and gap>=0.05 else ('REVERSED_SIGNAL_DOMINANT' if sp>=0.8 and gap<=-0.05 else 'MIXED_SHAPE')
    return {'rho0':round(rb[0],4),'rho1':round(rb[-1],4),'pearson':round(pear,4),'monotone':mono,
            'Neff0':round(ne0,4),'span':round(span,4),'V1':v1,'V2':v2,
            'judgeable':v1 and v2,'D1_shape':shape,'spearman_dinst_rho':round(sp,4),
            'gap_dinst':round(gap,6),'D2':d2,'D2_flips':flips,'D4_tax_min':d4,
            'gain_v2_lost_d2':bool(v2 and d2=='RATE_FLIP_ANY')}


def self_test():
    for seed in (1000+1, 90000+1):
        for na in (6,12):
            task = Ctx(seed=seed, n_episodes=128, n_actions=na)
            for w in [(1.0,0.0,0.0),(0.9,-0.6,1.2),(0.5,0.5,0.5)]:
                assert F.evaluate_cached(task, HP(w)).values == task.evaluate(HP(w)).values, f'S1 {seed} {na} {w}'
    assert abs(P.n_eff(16,1.0)-1.0)<1e-9 and abs(P.n_eff(16,0.0)-16.0)<1e-9, 'S2'
    assert P.pearson((2.0,2.0,2.0),(2.0,2.0,2.0))==0.0, 'S3'
    # S5: non-multi constructors must have rho=1 exactly 1 every gen (constant-vector trap guard)
    for C in CONSTRUCTORS:
        if C['multi']:
            continue
        a1 = run_c(1.0, 16, 6, 1, C)
        assert all(abs(x-1.0)<=1e-9 for x in a1['_rho_gen']), f'S5 {C["id"]} {a1["_"+chr(39)+chr(39)] if False else a1["_rho_gen"]}'
    # S4 red proof: inject a fake passing verdict from failing base -> must flip
    s = {}
    for r in RHO_GRID:
        for n in (4,16):
            rows = [run_c(r,n,12,sd,CONSTRUCTORS[0]) for sd in (1,2,3)]
            s[(CONSTRUCTORS[0]['id'],r,n)] = {k: statistics.fmean(x[k] for x in rows)
                                               for k in ('rho_bar','N_eff','delta_inst','delta_priv','rate_cand','rate_total','pass_rate')}
    base = verdict_for(CONSTRUCTORS[0], s)
    assert not base['judgeable'], f'S4 base unexpectedly judgeable {base}'
    fake = {k: dict(v) for k,v in s.items()}
    for rr in RHO_GRID:
        key = (CONSTRUCTORS[0]['id'], rr, 16)
        fake[key]['rho_bar'] = rr        # force perfectly linear rho_bar=rho -> pearson=1, monotone
        fake[key]['N_eff'] = P.n_eff(16, rr)
    inj = verdict_for(CONSTRUCTORS[0], fake)
    assert inj['V1'] and inj['V2'] and inj['judgeable'], f'S4 inject did not flip {inj}'
    # common signal red: perturb one delta vector, common must change
    dv = [tuple((i+1)*0.1*(j+1) for j in range(8)) for i in range(4)]
    dv2 = [tuple(-x for x in dv[0])] + dv[1:]
    c1 = common_signal([dv]); c2 = common_signal([dv2])
    assert c1 != c2, f'S4 common not reactive {c1} {c2}'
    print('self-test S1-S5 PASS; base judgeable=False, injected judgeable=True')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--self-test', action='store_true')
    ap.add_argument('--out', default='lowfloor_probe.json')
    a = ap.parse_args()
    if a.self_test:
        self_test(); return
    rows = []
    for C in CONSTRUCTORS:
        for r in RHO_GRID:
            for n in (4,16):
                for sd in (1,2,3):
                    rows.append(run_c(r,n,12,sd,C))
    s = summarize(rows)
    verdicts = {C['id']: verdict_for(C, s) for C in CONSTRUCTORS}
    winner = [cid for cid,v in verdicts.items() if v['judgeable'] and not v['gain_v2_lost_d2']]
    cap = run_c(0.0,16,12,1,CONSTRUCTORS[0],capture=True)
    floor = {'C0_rho0_common': common_signal(cap.pop('_delta_mats')), 'C0_rho0_rho_bar': cap['rho_bar']}
    out = {
        'config':{'constructors':CONSTRUCTORS,'rho_grid':list(RHO_GRID),'ns':[4,16],'seeds':[1,2,3],'gens':12,
                  'pre_registration':'PRE_REGISTRATION.md'},
        'rows':[{k:v for k,v in r.items() if not k.startswith('_')} for r in rows],
        'summary':[{'id':cid,'rho_param':r,'N':n,**s[(cid,r,n)]} for cid in [c['id'] for c in CONSTRUCTORS] for r in RHO_GRID for n in (4,16)],
        'verdicts':verdicts,
        'winner':winner,
        'overall':('JUDGEABLE_GAINED' if winner else 'FLOOR_NOT_PUSHABLE'),
        'floor_decomp':floor,
    }
    Path(a.out).write_text(json.dumps(out, indent=1), encoding='utf-8')
    print(f"{'id':5s} {'rho0':>6s} {'rho1':>6s} {'pear':>6s} {'mono':>5s} {'Neff0':>6s} {'span':>6s} {'V1':>5s} {'V2':>5s} {'judg':>5s} {'D2':>22s} {'shape':>22s}")
    for cid,v in verdicts.items():
        print(f"{cid:5s} {v['rho0']:6.4f} {v['rho1']:6.4f} {v['pearson']:6.4f} {str(v['monotone']):>5s} {v['Neff0']:6.3f} {v['span']:6.3f} {str(v['V1']):>5s} {str(v['V2']):>5s} {str(v['judgeable']):>5s} {v['D2']:>22s} {v['D1_shape']:>22s}")
    print('winner=',winner,' overall=',out['overall'],' floor=',floor)
    print('wrote '+a.out+' rows='+str(len(rows)))


if __name__ == '__main__':
    main()

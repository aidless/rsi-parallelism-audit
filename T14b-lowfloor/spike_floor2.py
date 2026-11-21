import sys, math, random, statistics
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'T14-deep'))
import frozen_anchor as F
P, Ctx, HP = F.P, F.ContextualTask, F.HeuristicPolicy

def rho_of(rho, n=16, gens=12, seed=1, norm=False, multi_anchor=False, base_zero=False, eps_scale=1.0):
    public = Ctx(seed=1000 + seed, n_episodes=128)
    base_vec = F.evaluate_cached(public, F.BASELINE)
    if base_zero:
        from rsi_agent.core import ScoreVector
        base_vec = ScoreVector(tuple(0.0 for _ in base_vec.values))
    rng = random.Random(f'spike2:{seed}:{rho}:{norm}:{multi_anchor}:{eps_scale}')
    per = []
    anchors = F.P.D2_ANCHORS if multi_anchor else (F.ANCHOR,)
    for g in range(gens):
        s = F.step_of(g)
        z = F.Z0
        sh, ind = rho**0.5, (1-rho)**0.5
        pool=[]
        for i in range(n):
            a = anchors[i % len(anchors)]
            eps0=tuple(rng.gauss(0,1) for _ in range(3))
            en=math.sqrt(sum(x*x for x in eps0)) or 1.0
            eps=tuple(x/en*math.sqrt(3) for x in eps0) if norm else eps0
            w=tuple(round(a[j]+s*(sh*z[j]+ind*eps_scale*eps[j]),4) for j in range(3))
            pool.append(HP(w))
        dv=[P.delta_vector(F.evaluate_cached(public,p),base_vec) for p in pool]
        per.append(P.mean_pairwise_rho(dv))
    return statistics.fmean(per)

grid=[round(i/10,2) for i in range(11)]
def report(tag, **kw):
    rs=[rho_of(r, **kw) for r in grid]
    pear=P.pearson(tuple(grid),tuple(rs))
    mono=all(rs[i]<=rs[i+1]+1e-9 for i in range(len(grid)-1))
    ne0=P.n_eff(16,rs[0]); span=ne0/max(P.n_eff(16,rs[-1]),1e-9)
    print(f'{tag:22s} rho0={rs[0]:.4f} rho1={rs[-1]:.4f} pear={pear:.4f} mono={str(mono):5s} Neff0={ne0:.3f} span={span:.3f}')
    print('   seq:', ' '.join(f'{x:.3f}' for x in rs))

report('baseline')
report('norm_eps', norm=True)
report('norm_eps_scale2', norm=True, eps_scale=2.0)
report('multi_anchor', multi_anchor=True)
report('norm+multi', norm=True, multi_anchor=True)
report('base_zero', base_zero=True)
report('norm+base_zero', norm=True, base_zero=True)

import sys, math, random, statistics
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'T14-deep'))
import frozen_anchor as F
P, Ctx, HP = F.P, F.ContextualTask, F.HeuristicPolicy

def rho_of(kind, c, rho, n=16, gens=12, seed=1):
    public = Ctx(seed=1000 + seed, n_episodes=128)
    base = F.evaluate_cached(public, F.BASELINE)
    anchor, z = F.ANCHOR, F.Z0
    rng = random.Random(f'spike:{seed}:{rho}:{kind}:{c}')
    per = []
    for g in range(gens):
        s = c * F.step_of(g)
        sh, ind = (rho**0.5, (1-rho)**0.5) if kind=='sqrt' else (rho, 1-rho)
        pool=[]
        for i in range(n):
            eps=tuple(rng.gauss(0,1) for _ in range(3))
            w=tuple(round(anchor[j]+s*(sh*z[j]+ind*eps[j]),4) for j in range(3))
            pool.append(HP(w))
        dv=[P.delta_vector(F.evaluate_cached(public,p),base) for p in pool]
        per.append(P.mean_pairwise_rho(dv))
    return statistics.fmean(per)

grid=[round(i/10,2) for i in range(11)]
print(f'{"kind":6s} {"c":>4s} {"rho0":>7s} {"rho1":>7s} {"pear":>7s} {"mono":>5s} {"Neff0":>7s} {"span":>6s}')
for kind in ('sqrt','linear'):
    for c in (1,1.5,2,3,5):
        rs=[rho_of(kind,c,r) for r in grid]
        pear=P.pearson(tuple(grid),tuple(rs))
        mono=all(rs[i]<=rs[i+1]+1e-9 for i in range(len(grid)-1))
        ne0=P.n_eff(16,rs[0]); ne1=P.n_eff(16,rs[-1])
        span=ne0/max(ne1,1e-9)
        print(f'{kind:6s} {c:4.1f} {rs[0]:7.4f} {rs[-1]:7.4f} {pear:7.4f} {str(mono):>5s} {ne0:7.3f} {span:6.3f}')

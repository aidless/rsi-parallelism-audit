import sys, math, random, statistics
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'T14-deep'))
import frozen_anchor as F
P, Ctx, HP = F.P, F.ContextualTask, F.HeuristicPolicy

def rho_of(rho, na, n=16, gens=12, seed=1):
    public = Ctx(seed=1000 + seed, n_episodes=128, n_actions=na)
    base_vec = F.evaluate_cached(public, F.BASELINE)
    rng = random.Random(f'spike3:{seed}:{rho}:{na}')
    per = []
    for g in range(gens):
        s = F.step_of(g); z=F.Z0; sh=rho**0.5; ind=(1-rho)**0.5
        pool=[]
        for i in range(n):
            eps=tuple(rng.gauss(0,1) for _ in range(3))
            w=tuple(round(F.ANCHOR[j]+s*(sh*z[j]+ind*eps[j]),4) for j in range(3))
            pool.append(HP(w))
        dv=[P.delta_vector(F.evaluate_cached(public,p),base_vec) for p in pool]
        per.append(P.mean_pairwise_rho(dv))
    return statistics.fmean(per)

grid=[round(i/10,2) for i in range(11)]
for na in (6,12,24,48):
    rs=[rho_of(r,na) for r in grid]
    pear=P.pearson(tuple(grid),tuple(rs))
    mono=all(rs[i]<=rs[i+1]+1e-9 for i in range(len(grid)-1))
    ne0=P.n_eff(16,rs[0]); span=ne0/max(P.n_eff(16,rs[-1]),1e-9)
    print(f'na={na:3d} rho0={rs[0]:.4f} rho1={rs[-1]:.4f} pear={pear:.4f} mono={mono} Neff0={ne0:.3f} span={span:.3f}')
    print('   ', ' '.join(f'{x:.3f}' for x in rs))

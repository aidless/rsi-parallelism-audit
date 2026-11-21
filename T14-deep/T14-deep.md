# T14-deep：冻结 anchor + 可学习内层目标 —— ρ 外生化后的 D1 复判

> 2026-11-20。预注册（含执行前补丁）见 PRE_REGISTRATION_DEEP.md；仪器 frozen_anchor.py；原始 99 臂 frozen_anchor.json；独立复算 recompute_deep.py。本地 CPU、未推送、未改其他轨。

## 0. 结论先行

D1 没有从「降级」升为「可判」，但降级理由变了。冻结外层 anchor 后 ρ 确实变成外生旋钮：N=16 实测 ρ̄ 随 ρ_param 严格单调 0.3763→1.0000，内层 z 轨迹在同一 seed 下跨全部 11 个 ρ 完全相同；T14 的 drift 反证模式则非单调（0.862/0.848/0.790/…/1.000）。但预注册 V1 的 Pearson 门槛未过（0.8064 < 0.95，ρ→1 处有 0.65→1.00 跳变）、V2 的 N_eff 跨度未过（2.4083× < 3×，ρ=0 的 ρ̄ 底噪 0.376 把 Kish N_eff 顶在 2.41），故 D1 = DEGRADED_INSTRUMENT。与此同时，过闸前 best-of-N 增益的 T10 凸塌缩形态在真实闸上复现：Δ_inst(16) 随 ρ 单调降（Spearman −0.9，0.4194→0.1664，gap 0.252977），与 N_eff 同向（Spearman +0.9）；因此可以说「形态复现、幅度不可判」，不能说「T10 曲面在真实闸被触发」。

## 1. 产物路径

- analyses/tracks/rsi-after/T14-deep/PRE_REGISTRATION_DEEP.md —— 执行前判据 + §6 执行前补丁
- analyses/tracks/rsi-after/T14-deep/frozen_anchor.py —— 新仪器，--self-test 10/10 PASS
- analyses/tracks/rsi-after/T14-deep/frozen_anchor.json —— rows(99) / summary(33) / traces_seed1_N16 / verdict
- analyses/tracks/rsi-after/T14-deep/recompute_deep.py —— 独立复算器，--self-test 2/2 PASS（含篡改判红）
- analyses/tracks/rsi-after/T14-deep/self_test.log、sweep.log、recompute.log

## 2. 仪器与自证（这次没有重踩 T14 的常量向量坑）

- 外层 anchor 恒为 BASELINE.weights=(1,0,0)，arm 内记 anchor_distinct=1；S8 用 drift 模式证明该断言可红（anchor_distinct>1）。
- 内层目标 z_t 起点 normalize((1,1,1))，每代用自己的 2 次 public 探针做 REINFORCE 方向估计，inner_update 入参无 ρ。S9：学到策略 public mean 0.7257 > baseline 0.6412；冻结内层（η=0）复核必须红。
- S6 核心单调门：完整 arm（N=16, seed=1, gens=12）上 ρ_param→实测 ρ̄ = 0.371/0.381/0.387/0.401/0.417/0.436/0.470/0.520/0.583/0.685/1.000，严格单调；drift 反证非单调。S6d 另钉「ρ=1 逐代 ρ̄ 全为 1.0」。
- 自检阶段抓出并修掉两个会毁掉读数的 bug，都写进日志：① z₀ 与 anchor 平行时 ρ=1 的 Δ 向量恒为 0，Pearson 分母为 0 返回 0，ρ̄(1) 被拉成 11/12≈0.917；② 缓存评测器把 action/feature 维度写反，S10 对表逐值不等。两者均在全矩阵读数之前修复，判据未改。

## 3. 主表（3 seeds 均值，N=16）

| ρ_param | ρ̄ | N_eff | Δ_inst | Δ_priv | rate_total/1k | rate_cand/1k | pass_rate | tax_total |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.00 | 0.3763 | 2.408 | 0.4194 | 0.3928 | 1.819 | 2.046 | 0.3229 | 2.302 |
| 0.10 | 0.3819 | 2.378 | 0.4283 | 0.3978 | 1.841 | 2.072 | 0.3785 | 2.212 |
| 0.20 | 0.3922 | 2.325 | 0.4276 | 0.3962 | 1.834 | 2.063 | 0.4062 | 2.217 |
| 0.30 | 0.4033 | 2.270 | 0.4281 | 0.3929 | 1.819 | 2.046 | 0.4167 | 2.213 |
| 0.40 | 0.4173 | 2.204 | 0.4256 | 0.3885 | 1.799 | 2.024 | 0.4444 | 2.248 |
| 0.50 | 0.4324 | 2.138 | 0.4129 | 0.3808 | 1.763 | 1.984 | 0.4809 | 2.257 |
| 0.60 | 0.4599 | 2.026 | 0.4017 | 0.3704 | 1.715 | 1.929 | 0.5226 | 2.180 |
| 0.70 | 0.5014 | 1.879 | 0.3796 | 0.3549 | 1.643 | 1.848 | 0.5521 | 2.219 |
| 0.80 | 0.5556 | 1.716 | 0.3517 | 0.3303 | 1.529 | 1.720 | 0.5920 | 2.291 |
| 0.90 | 0.6499 | 1.491 | 0.3094 | 0.2875 | 1.331 | 1.497 | 0.6562 | 2.431 |
| 1.00 | 1.0000 | 1.000 | 0.1664 | 0.1676 | 0.776 | 0.873 | 0.7778 | 3.000 |

Δ_inst = 过闸前 best-of-N 增益 mean_gen max_i mean(public_i−base)，与 T10 的 Δ 同语义；Δ_priv = 被采纳代的 private 增益（3 seeds 均值）。N=1 全部 ρ̄=1、N_eff=1，只作控制；完整 99 行见 JSON。

## 4. 预注册判决

| 判据 | 预注册门槛 | 实测 | 判决 |
|---|---|---|---|
| V1 | ρ̄ 对 ρ 严格单调 + ρ̄(0)≤0.40 + 端点 1.0 + Pearson≥0.95 | 单调 True；0.3763；1.0000；Pearson 0.8064 | FAIL（仅 Pearson 未过；事后 Spearman=1.0） |
| V2 | N_eff(0)/N_eff(1) ≥ 3 | 2.4083（2.408→1.000） | FAIL |
| D1 | V1∧V2 | 两 gate 均 FAIL | DEGRADED_INSTRUMENT（未升级） |
| D1'-shape | Spearman(Δ_inst,ρ)≤−0.8 且 gap≥0.05 | Spearman −0.9；gap 0.252977 | COLLAPSE_REPRODUCED（形态层） |
| 归因 | Spearman(Δ_inst,N_eff) / (Δ_inst,cos(z_T,TRUE_W)) | +0.9 / 0.0 | 形状跟 N_eff 走，不跟内层学习目标走 |
| D2 | 任一 ρ rate(16)≥rate(4) | total/cand 两种口径 flip 均为 [] | RATE_ROBUST_ACROSS_RHO |
| D4 | tax 全档 ≥3 | total 2.180–3.000；cand-only 2.9067–4.0001 | TAX_MIDDLE |

Δ_priv 的 0→1 落差为 0.225210（0.392804→0.167594），与 Δ_inst 落差 0.252977 同向，但两者都不能当作 T10 幅度的复现（N_eff 只跑了 2.41→1，不是 16→1）。

## 5. 机理诊断（为什么仍不可判）

1. ρ 已外生：seed=1 的 z 轨迹在 11 个 ρ 下逐代完全相同；cos_z_truew 在同一 seed 下跨 ρ、跨 N 恒定（seed1/2/3 = 0.777267 / 0.945228 / 0.946766）。TRUE_W 只用于事后诊断，从未进提案器或闸。
2. ρ̄ 底噪来自任务几何，不是 anchor 漂移：gen0、ρ=0、seed=1、N=16 时，权重扰动两两 cosine = −0.0589（几乎独立），但 per-episode Δ 向量两两 Pearson = 0.4066；argmax 选择把独立权重扰动投影成高度相似的 Δ 向量。Kish N_eff 因此最高只有 2.41，T10 的 ρ=0→N_eff=16 曲面在这台真实闸底物上仍不可达。
3. D4 降级是成本口径造成的：内层每代 2 次 probe 计入 total 后，tax 被乘上 (4/6)/(16/18)=0.75（cand 2.9067–4.0001 → total 2.180–3.000，端点比恰为 0.75）。这是会计效应，不是新的协调税机制；两种口径都列出，主判用 total。

## 6. 复算命令

~~~bash
cd analyses/tracks/rsi-after/T14-deep
python3 frozen_anchor.py --self-test                                   # 10/10 PASS
python3 frozen_anchor.py --seeds 1,2,3 --gens 12 --n 1,4,16 --out frozen_anchor.json
python3 recompute_deep.py --self-test                                  # 2/2 PASS（含篡改判红）
python3 recompute_deep.py                                              # 复算主表与全部 verdict
~~~

两条诊断（事后，非预注册）复算：

~~~bash
cd analyses/tracks/rsi-after/T14-deep && python3 - <<'PY'
import json, frozen_anchor as F, proposer_diversity as P
from rsi_agent.tasks import ContextualTask
D=json.load(open('frozen_anchor.json'))
for s in (1,2,3):
  v=[x['cos_z_truew'] for x in D['rows'] if x['seed']==s]
  print(s, min(v), max(v))
tr=D['traces_seed1_N16']; zs=[tuple(tuple(a) for a in x['z']) for x in tr.values()]
print('z identical across rho:', all(z==zs[0] for z in zs))
t=ContextualTask(seed=1001,n_episodes=128); base=F.evaluate_cached(t,F.BASELINE)
pool=F.frozen_propose(0.0,0,16,1,F.ANCHOR,F.Z0)
dv=[P.delta_vector(F.evaluate_cached(t,p),base) for p in pool]
dw=[tuple(p.weights[k]-F.ANCHOR[k] for k in range(3)) for p in pool]
print('dw_cos', P.mean_pairwise_rho(dw), 'delta_pearson', P.mean_pairwise_rho(dv))
PY
~~~

环境：本机 CPU；全矩阵 17.2 s，self-test 7.0 s，零 GPU。

## 7. 遗留问题

1. D1 要升为可判，缺的不是 anchor 冻结，而是 ρ̄ 仪器：需要一种能把 ρ=0 的 Δ 向量 Pearson 底噪从 0.376 降下来的构造（直接对 per-episode Δ 做正交化，或换一个 argmax 不产生共同分量的任务族）。这是新轨，不在本轨内事后改判据。
2. V1 Pearson 门槛是否过严？严格单调成立、Spearman=1.0，仅因 0.65→1.00 的端点跳变使 Pearson=0.8064。即使把 V1 改成单调判据，V2（2.4083<3）仍失败，D1 结论不变。
3. rate 税的两套口径需要在 SUMMARY 层明确选一套：total（诚实计入内层 probe，2.18–3.00×）或 cand-only（与 T14 可比，2.91–4.00×）。本轨不修改 SUMMARY.md。

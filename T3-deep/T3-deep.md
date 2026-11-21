# T3-deep：budget-concentrated 单体 portfolio vs 采样群体的等预算对撞

## 结论先行

1. 同一 T7 底物、同一评估预算 B 下，答案端点 A 的胜者不是固定的：rho=0 且 m=1/2/4 时，B=8/16 群体赢、B=32/64/128 单体赢，交叉带落在 B≈16–32；m=1 与 T7 single 臂逐 seed 对表 1200 字段、0 mismatch。
2. 生态端点 E 在低 rho 仍正，但优势被 portfolio 规模稀释：rho=0、m=4 时等预算 gain_E 从 B=8 的 +0.152 升到 B=128 的 +0.739；即使按 T3 §6 重固定成本 premium（B_swarm=128 vs B_single=32, t_fixed=50）计算，净效率仍为 +0.067。
3. 「集中赢答案、群体赢生态」是同一预算分配轴的两端：rho=0、B=32 时 m=1→8 令 A_mono 从 0.986 降到 0.914（tax_A 从 +0.066 变到 −0.006），同时 E_mono 从 0.141 升到 0.744（gain_E 从 +0.672 降到 +0.070）。m=8 且 B≤16 是碎预算边界，不应当作一般结论。

## 1. 闭合的问题

T3-collective/T3.md §5 遗留 2 指出缺 budget-concentrated 对照；§4 又要求 best-of-N 与 budget-concentrated 两种口径都算。本轨只补这一格：把「一个单体拿满 B」扩展为「一个单体持 m 个策略、总预算仍为 B」，再和「k 个采样 agent 各押一族」在同一底物上等预算对撞。不改 T7/T3 任何原文件。

## 2. 底物与口径

- 底物：直接 import `analyses/tracks/rsi-after/T7-collision/collision_endpoints.py`，复用 `make_families(rng,k,dim,rho)` 与 `best_of(n,score,rng,dim,base=None)`；随机数顺序保持 T7 的 swarm→single 次序，故 m=1 可逐 seed 复现。
- 群体：k 个 agent 各押一族，每族 B/k 次评估；A_swarm=max_i dot(p_i,w_i)，E_swarm=mean_j max_p dot(p,w_j)。
- 单体 portfolio：m 个策略全部押 oracle 族 0，总预算 B 按 `alloc_counts` 分给各策略；A_mono=max_p dot(p,w_0)，E_mono=mean_j max_p dot(p,w_j)。
- 胜者记法：tax_A=A_mono−A_swarm，正=单体赢；gain_E=E_swarm−E_mono，正=群体赢。T 端点同理。
- token 口径沿用 T3 §6：mono=t_fixed+B*t_eval，swarm=k*t_fixed+B*t_eval；同 token T 反解 B_mono=(T−t_fixed)/t_eval、B_swarm=(T−k*t_fixed)/t_eval。
- 默认网格：k=8, dim=3, seeds=40, B∈{8,16,32,64,128}, rho∈{0,0.25,0.5,0.75,1.0}, m∈{1,2,4,8}；共 4000 粒逐 seed 记录、100 个聚合格、25 个生态格、125 个 token 格。

## 3. 仪器与门禁

新增 `analyses/tracks/rsi-after/T3-deep/budget_matched_swarm.py`，带 `--self-test` 与 `--prove-red`。

- st0：m=1 与 T7 `collision.json` 逐 seed 对表，checked=1200、mismatches=0；注入 +0.01 偏移必须检出（红控检出 25）。
- st1：m=1, rho=0, t_fixed=0 时 last swarm B=16、first mono B=32；反转判据必须 False。
- st2：m=4 时 rho=0 gain_E=+0.4288 高于 rho=1 的 +0.0446，t_fixed=50 净效率 +0.0666；符号反转必须 False。
- st3：m=1 ecosystem_table 复算 T3 §6 既有 token 表，mismatches=0/5。
- st4：所有 A/E/T 端点落在 [-1.0001, 1.0001]，越界数=0。

`--prove-red` 注入胜者翻转与符号翻转后输出 `FAIL (correctly fired)` 且 exit 1，证明门不是装饰。正常 self-test 输出 `SELF-TEST PASS`，exit 0。

## 4. 结果

### 4.1 答案端点 A：交叉带 B≈16–32

序列按 B=8/16/32/64/128 排列，S=群体赢，M=单体赢。

| rho | m=1 | m=2 | m=4 | m=8 |
|---|---|---|---|---|
| 0    | SSMMM | SSMMM | SSMMM | MSSSS |
| 0.25 | SMMMM | SSMMM | SSMMM | MSSMS |
| 0.5  | SMMMM | SSMMM | SSMMM | SSMSM |
| 0.75 | SMMMM | SSMMM | SSMMM | SMMMS |
| 1.0  | SMMMM | SSMMM | SSMMM | SMSSM |

rho=0 的 tax_A 明细：m=1 在 B=16 为 −0.028266、B=32 为 +0.065955；m=4 在 B=16 为 −0.020、B=32 为 +0.035；m=2 同向（−0.009 / +0.061）。m=8 在 B=8 已出现 M，是每策略只分到 1 次评估的碎预算边界，不推翻 m≤4 的交叉结论。

### 4.2 生态端点 E：低 rho 正、被 m 稀释

等预算 gain_E（rho=0,m=4）：B=8 +0.152，B=16 +0.181，B=32 +0.294，B=64 +0.520，B=128 +0.739；全程为正。m=1 同列为 +0.654 / +0.674 / +0.672 / +0.721 / +0.803；m=8 在 B=8/16 转为 −0.027 / −0.018，B=32 才回到 +0.070。

按 T3 §6 的 premium 口径（B_swarm=128 vs B_single=32）汇总 m=4：

| rho | gain_E | net(t_fixed=0) | net(t_fixed=50) |
|---|---:|---:|---:|
| 0    | +0.429 | +0.107 | +0.067 |
| 0.25 | +0.368 | +0.092 | +0.057 |
| 0.5  | +0.249 | +0.062 | +0.039 |
| 0.75 | +0.113 | +0.028 | +0.018 |
| 1.0  | +0.045 | +0.011 | +0.007 |

m=1 复算 T3 既有表3 为 0.2017 / 0.1732 / 0.1136 / 0.0419 / 0.0025，0 mismatch；m=4 是「单体也持多策略」后的稀释版，仍全 rho 为正，rho=1 仅剩约 0.007–0.011，按原判据属于「≈0」。

### 4.3 token 预算下的可负担性与胜者

- t_fixed=0：rho=0 时 T=8/16 群体赢、T≥32 单体赢；rho=1 时 T=8 群体赢、T≥16 单体赢。
- t_fixed=2 时 T=8/16 因 k*t_fixed=16 导致 B_swarm<1，记为不可负担；T=32 起可负担且单体赢。
- t_fixed=5 时 T≤32 不可负担，T=64/128 可负担且单体赢；t_fixed=20/50 在本网格 T≤128 全部不可负担。这里限制来自固定成本，不是端点翻转。

## 5. 复算命令

```bash
# 自检 / 反证 / 主跑
python3 analyses/tracks/rsi-after/T3-deep/budget_matched_swarm.py --self-test
python3 analyses/tracks/rsi-after/T3-deep/budget_matched_swarm.py --prove-red
python3 analyses/tracks/rsi-after/T3-deep/budget_matched_swarm.py

# 从落盘 CSV 复算 rho=0 的交叉点与 m=4 生态增益
python3 - <<'PY'
import csv
p = 'analyses/tracks/rsi-after/T3-deep/outputs/budget_matched.csv'
for r in csv.DictReader(open(p, encoding='utf-8')):
    if float(r['rho']) == 0.0 and int(r['m']) in (1, 4) and int(r['budget']) in (16, 32):
        print(r['m'], r['budget'], r['A_mono'], r['A_swarm'], r['tax_A'], r['gain_E'])
PY
```

主跑墙钟 6.5s（Python 3.12.3，本机 CPU），无 GPU、无长跑。落盘证据：`outputs/self_test.json`、`outputs/budget_matched.json`、`outputs/budget_matched.csv`。

## 6. 边界与遗留

- m=8、B≤16 的 A/E 反转未做更高 seeds 或置信区间；按「亚分钟级、禁长跑」约束标为未核，不作推广。
- t_fixed≥20 且 T≤128 的 token 格全部不可负担，没有扩展 T 网格；高固定成本区间标未核。
- 只覆盖 k=8、dim=3、40 seeds 的 T7 底物；其它 k/dim 未核。
- 本轨未改 T7/T3 源文件，未改 SUMMARY.md，未 git add/commit/push。

## 7. provenance

主跑生成于 2026-11-20T13:35:29Z，Python 3.12.3，Linux-7.0.0-43-generic-x86_64-with-glibc2.39。

| 文件 | sha256 |
|---|---|
| budget_matched_swarm.py | 309d72f90e19995226a744133d9aca700aa90f27f9ca3f339f331627f099b723 |
| T7-collision/collision_endpoints.py | eb10fb30c902b36482cba32a0c816ed03060285a2f6875f51def5d54d2ad6e09 |
| T3-collective/T3.md | bd35e84f03750a1959b72551a7fd2277c332157c29261c7b099ac8d0501c3979 |
| T7-collision/outputs/collision.json | 28b178c88d06fdb7866aa9e76a8bc79279db3fe463590ea4b35f4cf2bef42dcb |
| T3-collective/outputs/token_cost.json | df9cd6eea5e8e7352989a2a258653b5b2a7172d6c04ee405e2a6f4758381037d |

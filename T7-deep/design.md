# T7-deep 预注册设计（执行前落盘）

- 目标：闭合 T7.md §5 局限「k 扫过但只在 ρ∈{0,0.5}」；判「协调税≈4× 预算是否只在低 ρ 成立」。
- 假设 H1：4× 不是只在低 ρ 成立（ρ=0.75 的 k=8 仍应出现 4×）；ρ=1.0 群体在答案端点不追平。
- 判据：B∈{32,64,128,256}、40 seeds、dim=3；追平 B=最小 A_swarm(B)≥A_single(32)−1e-12；倍数=追平 B/32；到 256 未追平记 None。
- 4×=倍数 4.0；只在低 ρ=(k=8,ρ=0/0.5 均 4.0)且(ρ=0.75/1.0 所有 k 非 4.0)；任一高 ρ 为 4.0 即 NO。
- 对表：重跑 ρ=0/0.5、B=32 的 5 个 k，与 T7-collision/outputs/k_sweep_{2,4,8,16,32}.json 逐 seed 逐字段严格相等，mismatches=0。
- 新仪器 --self-test 四格：正控/反向注入/对表红控/判决翻转；失败 exit≠0。
- 零 GPU、亚分钟；只写 analyses/tracks/rsi-after/T7-deep/；不改输入轨、不改 SUMMARY.md、不 git add/commit/push。

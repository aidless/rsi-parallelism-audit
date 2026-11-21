# T11 · 路 1「筛现成基准」总表

> 日期 2026-11-19。任务来源：用户 m00739「可以」=同意开路 1（筛现成基准，非造基准）。六门槛定义见主 SUMMARY「方法回答」节：A1 no-terminal / A2 分布漂移 / A3 压力来自交互（ecosystem 非 breeder）/ B1 held-out 迁移排名相关 / B2 抗 Goodhart / B3 判分器外环冻结。

## 结论先行

四路交叉（T11a continual 8 候选 / T11b openworld 6 候选 / T11c scientific 9 候选 / T11d game-openworld-eval 4 候选）合计核查 **27 个候选**，**严格六门槛全绿 = 0，核心 4 项（A1/A2/B1/B2）全绿 = 0**。最接近的载体是 **FutureWorld**（arXiv:2604.26733，A1/A2/A3/B2 绿，B1 未测、B3 未核）与 **ASB**（arXiv:2610.18449，B1/B2 判分门最干净但 A1 固定终点），二者互补但都不是现成证伪入口。路 1 未筛到证伪入口——与 T2「11 组无一满足」结论独立复现一致。

## B1 口径裁决（主项目拍板：**不放宽，维持 ⚠️**）

T11c 请求把 B1 从「跨任务 held-out 排名相关系数保持（Spearman ρ 过阈值）」放宽到「跨域/跨格式迁移且性能保持」，理由是 FutureWorld 报了「跨域鲁棒迁移 + 四类题型训练中未见」。裁决不放宽，三条理由：

1. **未测 ≠ 未达标**。FutureWorld 报的是跨格式泛化的**性能保持**（unseen formats 上得分非零），没有报任何排名相关系数。它没测 B1，不是测了没过。把它记成 ✅ 是把「未测」写成「通过」。
2. **换口径会偷换判据**。B1 的本意是判分/策略迁移到新环境后**不失真**。「整体均分维持」与「个体排序相关保持」是两个统计量：判分器完全可以在新环境让均分维持却把排序打乱——这恰是 B1 要防的失效。放宽等于把 B1 换成 B1′，让门槛自我取消。
3. **更根本：即便六项全绿，FutureWorld 也只是「证伪入口的载体」，不是证伪本身**。它是单 agent 的 live prediction RL 环境（预测→现实结果回填奖励→策略更新），根本没有多候选/并行/验证器带宽这一层。终局判断是「并行买到的是独立度不是候选数、验证器主要落配角位」；证伪它必须在这个载体上跑 T7/T10 式 (ρ,B) 对撞与 N_eff 曲面，看独立度→改进速率关系是否翻转。那一步属于路 2 的实验，不在路 1 的「筛」范围。

→ 路 1 的诚实产出：**找到了最接近的载体，没找到现成的证伪**；严格全绿仍为 0。

## 四路候选总表（六门槛速记：✅绿 / ◐部分或未测 / ❌红）

| 候选（文献号） | 来源轨 | A1 | A2 | A3 | B1 | B2 | B3 | 核心 4 |
|---|---|---|---|---|---|---|---|---|
| **FutureWorld** (2604.26733) | T11c | ✅ | ✅ | ✅ | ◐未测 | ✅ | ◐未核 | 不绿（B1 未测） |
| **ASB** (2610.18449) | T11c | ❌固定 6 campaign | ◐ | ✅ | ✅ | ✅ | ◐ | 不绿（A1 红） |
| ScienceClaw (2610.08691) | T11c | ✅ | ◐ | ◐ | ✅ | ✅ | ◐ | 不绿（A3 弱） |
| SciLaws-Bench (2609.01552) | T11c | ❌ | ✅ | ◐ | ✅ | ✅ | ◐ | 不绿（A1 红） |
| ServeLearnBench (2610.07792) | T11c | ✅ | ✅ | ◐ | ◐ | ◐ | ❌ | 不绿 |
| ProEvolve (2603.05910) | T11c | ◐ | ✅ | ❌ breeder | ◐ | ◐ | ◐ | 不绿 |
| CLE (2610.33956) | T11c | ❌ | ❌ | ❌ | ◐ | ◐ | ❌ | 不绿 |
| BEAKER (2611.06911) | T11c | ❌ | ❌ | ❌ | ❌ | ◐ | ✅ | 不绿 |
| ScienceAgentBench (2410.05080) | T11c | ❌ | ❌ | ◐ | ◐ | ✅ | ✅ | 不绿 |
| CRUX / Open-World Evals (2605.20520) | T11b/T11d | ◐项目级 | ✅ | ❌ human | ❌自承"Not reproducible" | ◐ | ✅ | 不绿（B1 红） |
| OpenComputer (2605.19769) | T11b | ❌ | ❌ | ❌ breeder | ❌ | ◐ | ❌共演化 verifier | 不绿 |
| Wild-Time (2211.14238) | T11b | ◐ Eval-Stream | ✅ ID→OOD 掉 20% | ❌ | ❌ | ❌ | ✅ | 不绿 |
| TRACE (2310.06762) | T11b | ❌ | ◐ | ❌ | ◐ | ❌ | ✅ | 不绿 |
| StreamingQA (2205.11388) | T11b | ✅ 14yr quarterly | ✅ | ❌ | ❌ | ❌ | ✅ | 不绿 |
| Dreaming in Code / DiCode (2602.08194) | T11d | ❌固定 Craftax 目标 | ✅代码级重写环境 | ◐人写 learnability | ◐同域 held-out 无排名相关 | ❌无独立 adjudicator | ✅ | 不绿 |
| NetHack (2006.13760) | T11d | — 老 RL 环境，非 self-improvement 基准 | | | | | | 不入判 |
| CL-Bench (2606.05661) | T11a | ◐ | ◐ | ❌ | ◐未核 | ◐ | ✅ | 不绿 |
| EvoAgentBench (2607.05202) | T11a | ❌ | ❌ | ❌ | ✅ | ◐ | ✅ | 不绿（A1/A2 红） |
| LifelongAgentBench (2505.11942) | T11a | ◐ | ❌ | ❌ | ◐ | ◐ | ✅ | 不绿 |
| PATH-Bench (2608.01149) | T11a | ❌ | ❌ | ❌ | ◐ | ◐未核 | ✅ | 不绿 |
| AgentCL (2606.02461) | T11a | ◐ | ◐ | ❌ | ◐ | ◐未核 | ◐ | 不绿 |
| LifeMem (2609.12655) | T11a | ◐ | ◐ | ❌ | ◐ | ◐未核 | ◐未核 | 不绿 |
| StreamBench (2406.08747) | T11a | ◐ | ❌ | ❌ | ◐未核 | ◐未核 | ✅ | 不绿 |
| Evo-Memory (2511.20857) | T11a | ◐ | ◐ | ❌ | ◐ | ◐未核 | ✅ | 不绿 |
| Implicit Assumptions (2610.41792) | T11b | N/A 理论/立场文，提供 task-cut 三层框架，非 benchmark | | | | | | 不入判 |

## 关键理论证据（为什么两轴交点空手）

- **CRUX**（T11b + T11d 两路独立命中）原文逐字："To turn a task into a benchmark, it needs to be precisely specified and automatically verifiable. The catch is that **whatever is precise enough to benchmark is also precise enough to optimize for**." 它自承 open-world eval 的 sample size 常为 1、"not useful for comparing the accuracy of different models or agents"、Non-stationary environments 使跨时间比较失效。→ A 满 B 空，与 SwarmWorld 同型。它从评测方法论侧面**独立佐证终局判断**：判分精确性 ↔ 环境真实性是结构张力，不是没人想到。
- **FutureWorld + ASB 互补**：FutureWorld 有 A1/A2/A3 开放性（每日 72+ 源流式事件、实测突变漂移、现实结果回填奖励）但 B1 未测、B3 未核；ASB 有最干净的 B1/B2（discovery gate + held-out learning gate 双校准门、lab service 回读湿实验真值）但 A1 固定 6 campaign。两者思路组合正是路 2 的缝法。
- **B1/B3 共性缺口**：T11b 的结构性发现——开放世界方向（CRUX）有真 OOD 但自承放弃可复现判分（B1 红）；可验证环境方向（OpenComputer/Wild-Time/TRACE/StreamingQA）有冻结判分但缺开放到达（A1）与生态压力（A3）。两轴反相关，交点无现成基准。
- **根因（T11a 补上）**：持续学习主线 8/8 候选中 **A3 无一来自 ecosystem 交互**（全部人写死 reward 或源基准），B3 成片绿却是唯一达标维度。根因同 T2——**开放的是记忆机制而非环境，没有外部真值锚**。这条把前三路的「两轴反相关」推进到「开放维度本身就选错了对象」：现有 continual/streaming 工作开放的是 agent 的记忆/技能库，任务分布与判分仍由设计者冻结。

## 路 1 → 路 2 的交接判断

路 1 结论为**筛不到严格证伪入口**（四路交叉一致）。按 m00738 既定顺序，此时评估路 2 构造成本：缝 FutureWorld 的开放流 + ASB 的可迁移判分门 + 独立未入环 adjudicator（防 Inventa 式环内 26.0→环外 17.5 的 Goodhart），造完在载体上重跑 T7/T10，看终局判断翻转否。**这一步需要新建基准 + 跑实验，超出「筛」的范围**，交给用户决定是否启动。

## 复现命令

```bash
# 各轨验号（示例，全部 abs 页 HTTP200 + 号-题一致）
curl -sI https://arxiv.org/abs/2604.26733 | head -1   # FutureWorld
curl -sI https://arxiv.org/abs/2610.18449 | head -1   # ASB
curl -sI https://arxiv.org/abs/2605.20520 | head -1   # CRUX 论文
curl -sI https://arxiv.org/abs/2605.19769 | head -1   # OpenComputer
curl -sI https://arxiv.org/abs/2602.08194 | head -1   # DiCode
# FutureWorld B1 裁决依据（abs + API 两种独立来源，均无排名相关、代码未释放/实验 ongoing）
curl -s https://export.arxiv.org/api/query?id_list=2604.26733 | grep -oE 'robust transfer|rank correlation|code will be released|experiments are currently ongoing'
```

## 遗留未核

- FutureWorld B1 排名相关系数、B3 独立 adjudicator：abs + API 摘要均无数值，HTML 全文 web_fetch 超时，代码未释放、摘要自承 "experiments are currently ongoing"——判**未测**，不是未达标。
- T11b 的 CITB/Split-SuperGLUE/PermutedLM/SplitQA 未逐一验号（检索词典污染，按同构归并 TRACE/StreamingQA 一类）；CRUX 正文 §5.3 外未逐段核。
- T11d DiCode 全文未逐段搜 "transfer"/"cross-domain"；只读了项目页与摘要。
- T11a 遗留：CL-Bench 官网未核；全部候选的 Spearman ρ 排名相关数字未核（B1 均记 ◐未核而非红）；LifeMem/StreamBench 判分器冻结声明未核；各候选 B2 的独立 adjudicator 细节全文未见即标未核、未编造。

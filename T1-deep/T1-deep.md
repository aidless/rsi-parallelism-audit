# T1-deep｜77.8% vs 71.4% 六因子口径闸

**结论**：当前 T1.md §5.1 的证据是 **1 项对齐 / 5 项失败**，闸输出 **「不可分解·禁相减」**（生产运行 rc=1，红线生效）。6.4pp 只能作为跨系统描述差引用，不能作同口径 A/B 比较或因子归因。

## 产物

- analyses/tracks/rsi-after/T1-deep/caliber_decompose.py（只读闸；--self-test 8/8 PASS，rc=0）
- analyses/tracks/rsi-after/T1-deep/T1-deep.md（本文件）

## 判据

1. 六因子全集固定为 benchmark / hardware / code_version / seed_count / max_token / implementation；缺格按失败处理，不按 0 或跳过。
2. 生产规则 rule=all：六格全 ALIGNED 才翻绿；任一 MISALIGNED 或 UNKNOWN 立即输出「不可分解·禁相减」，rc=1。
3. 只读 T1.md §5.1（### 5.1 到 ### 5.2 之前）；§5.2 之后不进入判定，需 GPU 的重叠遗留未纳入、未改动。自检含越界反证。
4. 数字从 §5.1 表格现场复算：77.8 - 71.4 = 6.4pp、2658/1360 = 1.95×、(556-519)/519 = 7.1%。
5. 退出码：0=六因子全对齐；1=口径闸红；3=闸没执行（不等于通过）。用法错由 argparse 报 2。

## 当前逐因子读数

| 因子 | 状态 | 证据锚点 |
|---|---|---|
| benchmark | ALIGNED | analyses/tracks/rsi-after/T1-parallel-conv/T1.md:161，测试集行 ✅ 同 |
| hardware | MISALIGNED | T1.md:159，硬件行 ❌ |
| code_version | MISALIGNED | T1.md:163，「其余（代码版本、实现、硬件、seed 数、max token）全不对齐」 |
| seed_count | MISALIGNED | T1.md:160，5 runs vs 4 seeds，❌ |
| max_token | MISALIGNED | T1.md:158，519 vs 556，❌ 不同 |
| implementation | MISALIGNED | T1.md:163，同上分解结论行 |

生产报告指纹：全文 sha256[:12]=f09f63b22231，§5.1 段 sha256[:12]=f897d0b90c1b。指纹随源文件变化，重跑以当次 JSON 为准。

## 复算命令

从工作区根目录执行（路径含字面反斜杠，保持相对路径）：

~~~bash
python3 analyses/tracks/rsi-after/T1-deep/caliber_decompose.py --self-test
# 期望：passed=8 total=8 rc=0

python3 analyses/tracks/rsi-after/T1-deep/caliber_decompose.py
# 期望：verdict=不可分解·禁相减；aligned_count=1；failed_count=5；rc=1
# rc=1 是闸红证据，不是脚本异常
~~~

自检 8 条中，「注入单因子对齐必须变绿（反证）」的构造是：其余五格已对齐、仅 hardware 失败时红；把该格注入为 ALIGNED 后必须绿。另有「判据变异 all→any 必须翻绿（反证）」与「漏枚举 seed_count 不得翻绿（覆盖闸）」，分别证明判据与六格枚举不是装饰。

## 引用边界

- 可写：两套系统在本任务上的表观差为 6.4pp（跨系统描述差）。
- 禁写：这 6.4pp 证明 RecursiveMAS 更强 / ConvRSI 更弱，或把它拆成某单因子的贡献。
- 解除条件：补齐桥接实验（同代码版本、同实现、同硬件、同 seed 数、同 max token），使六格全绿后再复跑本闸。

## 遗留

桥接实验未落盘，本轮不新增算力实验；本机零可用 GPU，相关复跑不在本闸范围。需 GPU 的 §5.3 条目保持原样，未触碰。

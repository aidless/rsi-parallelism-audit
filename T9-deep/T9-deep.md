# T9-deep — Q3 600 条 P2=0 样本假象闭合

## 结论

旧 Q3 600 条样本的 P2=0 是**未捕获**，不是真零。按 T9 现役量具复算，旧样本 Wilson 95% 比例区间为 [0, 0.00636193]，映射为估计篇数区间 [0, 75]、每万率区间 [0.00, 37.52]；上界明确大于 0，样本零不能写成真实零。

q3retry 另取 600 条浅偏移样本，已实测 1 条 P2：点估计 20 篇 = 10.01/万，每万 CI [1.50, 55.03]。两批合并为 n=1200、P2=1：点估计 10 篇 = 5.00/万，每万 CI [1.00, 27.52]。判决字段为 `OLD_ZERO_IS_UNOBSERVED_NOT_TRUE_ZERO`。

## 口径与底物

- 输入只读：`analyses/tracks/rsi-after/T9-verifier-share/outputs/README.md`、`outputs_p2x/sample.jsonl`、`outputs_p2x/verifier_share.csv`、`outputs_q3retry/sample.jsonl`、`outputs_q3retry/verifier_share.csv`、`compare_p2x.py`。
- 分档沿用 T9 字面判据：P1 / P2 / P3 / NONE 互斥，P2 是贡献句级命中；本轮不重新定义 P2。
- 估计公式沿用 T9 源码：`est = round(union_api * P2_hits / sample_n)`；`per_10k = round(10000 * est / total)`。
- Wilson 95% 比例区间用 `verifier_share.py:299-306` 的同式（z=1.96），再乘 `union_api` 得估计篇数区间，最后用 `total` 换算每万区间。
- 合并口径：两批 `total` 都是 19989；`union_api` 用按样本量加权均值 `(11718*600 + 11717*600)/1200 = 11717.5`，写死在脚本中，可从两份 CSV 复算。

## 关键数字

- 旧样本 `p2x_q3_600`：n=600，tier 计数 P1=20 / P2=0 / P3=86 / NONE=494；p_hat=0；Wilson95 比例 [0, 0.00636193]；est=0 篇；CI篇 [0, 75]；0.00/万；CI每万 [0.00, 37.52]；判决 `UNOBSERVED_NOT_TRUE_ZERO`。
- 补抓样本 `q3retry_q3_600`：n=600，tier 计数 P1=19 / P2=1 / P3=93 / NONE=487；p_hat=0.00166667；Wilson95 比例 [0.00029426, 0.00937980]；est=20 篇；CI篇 [3, 110]；10.01/万；CI每万 [1.50, 55.03]；判决 `OBSERVED_POSITIVE`。
- 合并样本 `pooled_q3`：n=1200，P2=1；p_hat=0.00083333；Wilson95 比例 [0.00014712, 0.00470535]；est=10 篇；CI篇 [2, 55]；5.00/万；CI每万 [1.00, 27.52]。
- 两份样本的 `stored_tier_counts` 与 `recomputed_tier_counts` 逐档相同；`reconciliation_checks` 各 7/7 为真；`cross_check_gate.mismatches = []`。输入哈希见 `q3_reconfirm.json:14-19`：旧 CSV `70d237847608`、旧 sample `49660cf9a85c`、补抓 CSV `4f6ee6ebae14`、补抓 sample `083df35d727a`。

## 判决逻辑

1. 零命中样本给出的是 `p_hat=0`，不是 `p_true=0`。Wilson 上界 0.00636193（37.52/万）仍允许正值，因此旧 Q3 的零只能判“未观测到”。
2. 补抓样本在同一字面判据下观测到 1 条 P2，直接否证“这两批 Q3 样本里 P2 恒为零”的说法。
3. 合并读数把稀疏性量化为正但很小的区间：1/1200，5.00/万，95% 上界 27.52/万。它只回答样本统计，不等同于全季 `union_api` 全量枚举的真实率。

## 仪器自检

- `python3 analyses/tracks/rsi-after/T9-deep/q3_reconfirm.py --self-test` → exit 0，`self-test 10/10 PASS`。
- 核心反证夹具：`(k=1,n=600,union=11718,total=19989)` 必须使点估计 > 0；零命中夹具必须给出 Wilson 上界 > 0 且判决不是真零。
- 红例：`python3 analyses/tracks/rsi-after/T9-deep/q3_reconfirm.py --prove-red` → exit 1，报错 `注入一条 P2 必须使点估计 > 0`。这证明自检不是装饰。
- 正式运行：`python3 analyses/tracks/rsi-after/T9-deep/q3_reconfirm.py` → exit 0，`mismatches = 0`，落盘 `analyses/tracks/rsi-after/T9-deep/q3_reconfirm.json`。

## 不外推因果

本记录只闭合“样本零是否被误读成真实零”的统计问题。不解释 P2 为什么稀疏，不把唯一命中论文的题材当作机制证据，也不把 CI 重叠解释成趋势因果。T9 已知的 P2 判据精度问题（README 记载 14 条复核中 4 条边界误判）本轮未重估；因此每万数是 T9 正则口径下的测量，不是人工复核后的真实主题率。

## 复算命令

从工作区根运行：

```bash
python3 analyses/tracks/rsi-after/T9-deep/q3_reconfirm.py --self-test
python3 analyses/tracks/rsi-after/T9-deep/q3_reconfirm.py --prove-red
python3 analyses/tracks/rsi-after/T9-deep/q3_reconfirm.py
python3 -c "import json;d=json.load(open('analyses/tracks/rsi-after/T9-deep/q3_reconfirm.json'));print(d['decision']['verdict'],d['cross_check_gate']['mismatches'])"
```

期望：第一条 exit 0；第二条 exit 1；第三条 exit 0 并刷新 JSON；第四条打印 `OLD_ZERO_IS_UNOBSERVED_NOT_TRUE_ZERO []`。

## 遗留问题

- 未做 `union_api` 全量枚举，不能给出全季层面的真实零/非零判定。
- 两批各 600 条是连续块 / 浅偏移样本，不覆盖季内全部时间片；Wilson CI 不含时间聚集误差。
- P2 判据精度未按 q3retry 样本重新人工复核，沿用 T9 README 的已知边界误判披露。

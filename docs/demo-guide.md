# 训练—评测—准入演示指南

前置条件：完成 `make preflight && make bootstrap && make build && make deploy && make demo`，打开页面显示的前端地址。

1. 点击“加载示例”，介绍 13 节点闭环：版本化数据、画像、数据门禁、预处理、并行训练/评测、排行榜、模型门禁、登记或拒绝报告。
2. 删除任意必填连线并点击“校验”，展示类型化端口和后端权威校验；随后恢复连线。
3. 点击“运行”，观察基线与候选训练并行执行；点击训练节点查看参数、25/50/75/100% 日志、资源规格和 `ModelRef`。
4. 运行完成后打开右侧“排行榜”，确认候选模型位于第一名；在“Lineage”查看 Dataset、Model、Evaluation、Candidate、Decision、RegisteredModel 和 Report 引用。
5. 默认阈值下，模型门禁为 `APPROVED`：登记模型与通过报告成功，拒绝报告为 `SKIPPED`。
6. 将“模型准入门禁”的 `minAccuracy` 改为 `0.99` 后重新运行：登记模型与通过报告变为 `SKIPPED`，拒绝报告成功，Workflow 本身仍为 `SUCCEEDED`。
7. 把两个训练节点的 `durationSeconds` 改为 30；运行后停止其中一个节点，确认并行训练继续。Workflow 终态后从该节点重跑，确认只重跑它和下游。
8. 把一个训练节点的 `failMode` 改为 `always`、`retryLimit` 设为 2，查看系统失败、自动重试与业务拒绝的区别。演示后改回 `never`。
9. 查看 Pipeline JSON 和 Workflow YAML，确认只有固定 `templateRef`，不存在用户镜像、Shell、ServiceAccount 或原始 Argo YAML。

机器回归：`make smoke` 验证通过/拒绝门禁与基础执行；`make node-smoke` 验证单节点停止、并行分支继续和局部重跑。

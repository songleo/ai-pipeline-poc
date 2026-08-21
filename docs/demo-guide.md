# 5 分钟演示指南

前置条件：完成 `make preflight && make bootstrap && make build && make deploy && make demo`，打开 `http://localhost:5173`。

1. **加载完整流程（30 秒）**：点击“加载示例”，Fit View，指出预处理后的两条训练分支和汇合点。
2. **制造校验错误（30 秒）**：删除 `train-b → compare.modelB`，点击“校验”，展示必填输入错误；重新连回并再次校验。
3. **运行与并行（60 秒）**：点击“运行”。观察节点从等待（黄）到运行（蓝）到成功（绿），强调 `train-a` 与 `train-b` 同时为蓝色。
4. **日志和输出（45 秒）**：点击训练节点，查看 25/50/75% 日志和 accuracy；点击 compare/report 查看 JSON 输出。
5. **查看编译边界（30 秒）**：点击“Pipeline JSON”和“Workflow YAML”，展示执行/UI 分离、固定 `templateRef`，以及没有用户镜像或 Shell。
6. **停止单个节点（45 秒）**：把两个训练节点的 `durationSeconds` 调到 30 后运行。两者同时为蓝色时，点击 `train-a`，进入“运行”页签并点击“停止此节点”。观察 `train-a` 进入 `CANCELLED`，而 `train-b` 继续并最终成功。
7. **从节点重新运行（45 秒）**：Workflow 到达 `FAILED` 后，仍在 `train-a` 的“运行”页签点击“重新运行此节点”并确认。观察 `train-a`、compare、report 重新执行，`train-b` 保持成功且不重复运行，最终 Workflow 为 `SUCCEEDED`。
8. **固定失败和自动重试（45 秒）**：把一个训练节点的 `failMode` 改为 `always`、`retryLimit` 设为 2 后运行；查看相同节点稳定退出 42 和 Argo retry count。演示后改回 `never`。人为停止与普通失败不同，不会触发自动重试。
9. **停止整个流程（30 秒）**：运行较长流程后点击顶部“停止”，观察整个 Workflow 进入取消终态。它和抽屉中的“停止此节点”是两个不同范围的操作。
10. **Argo UI 对照（30 秒）**：打开 `http://localhost:2746`，找到带 `demo.pipeline.io/project=pipeline-demo` 标签的 Workflow，对照 DAG、Pod 重试和日志。

若需要机器证据，运行 `make smoke` 验证基础执行，运行 `make node-smoke` 验证“单节点停止不自动重试、并行分支继续、从节点重跑下游”的完整闭环。


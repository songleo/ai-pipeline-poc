# 5 分钟演示指南

前置条件：完成 `make preflight && make bootstrap && make build && make deploy && make demo`，打开 `http://localhost:5173`。

1. **加载完整流程（30 秒）**：点击“加载示例”，Fit View，指出预处理后的两条训练分支和汇合点。
2. **制造校验错误（30 秒）**：删除 `train-b → compare.modelB`，点击“校验”，展示必填输入错误；重新连回并再次校验。
3. **运行与并行（60 秒）**：点击“运行”。观察节点从等待（黄）到运行（蓝）到成功（绿），强调 `train-a` 与 `train-b` 同时为蓝色。
4. **日志和输出（45 秒）**：点击训练节点，查看 25/50/75% 日志和 accuracy；点击 compare/report 查看 JSON 输出。
5. **查看编译边界（30 秒）**：点击“Pipeline JSON”和“Workflow YAML”，展示执行/UI 分离、固定 `templateRef`，以及没有用户镜像或 Shell。
6. **固定失败和重试（45 秒）**：把一个训练节点的 `failMode` 改为 `always`、`retryLimit` 设为 2 后运行；查看相同节点稳定退出 42 和 Argo retry count。演示后改回 `never`。
7. **手动停止（30 秒）**：把 duration 调长并运行，节点为蓝色时点击“停止”，观察 Workflow/节点进入取消或失败终态。
8. **Argo UI 对照（30 秒）**：打开 `http://localhost:2746`，找到带 `demo.ssli.io/project=ssli-demo` 标签的 Workflow，对照 DAG、Pod 重试和日志。

若时间区间重叠需要机器证据，运行 `make smoke`；脚本会断言两个训练节点 `startedAt/finishedAt` 区间相交。

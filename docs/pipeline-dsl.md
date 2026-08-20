# Pipeline JSON DSL

## 顶层结构

`apiVersion` 固定为 `demo.ssli.io/v1alpha1`，`kind` 固定为 `Pipeline`。`metadata.name` 是 DNS 风格 Pipeline 名。`spec` 是执行定义；`uiLayout` 只是编辑器坐标，Compiler 不依赖它。

```json
{
  "apiVersion": "demo.ssli.io/v1alpha1",
  "kind": "Pipeline",
  "metadata": {"name": "model-comparison-demo"},
  "spec": {
    "nodes": [],
    "edges": [],
    "runPolicy": {"timeoutSeconds": 300}
  },
  "uiLayout": {"nodes": {}}
}
```

## 节点与连线

节点包含唯一 `id`、Registry 中的 `type` 和 `version`、显示用 `name` 以及 `parameters`。节点不能提供镜像、命令、ServiceAccount 或模板名。

Edge 必须同时声明源/目标端口：

```json
{"source":"train-a","sourcePort":"model","target":"compare","targetPort":"modelA"}
```

`uiLayout.nodes.<nodeId>` 保存 `{x,y}`，移动节点不会改变执行语义。

## 类型系统

当前端口类型是 `DatasetRef`、`ModelMetricRef`、`ReportRef`。只有完全相同类型可以连接。参数使用 Registry 的 JSON Schema 子集：`string`、`integer`、`number`、枚举、required、minimum/maximum。后端是最终权威校验方。

## 参数传递

普通参数从 node `parameters` 编译成 WorkflowTemplate inputs。Edge 编译成上游 Argo output parameter 引用。例如 `train-a.model → compare.modelA` 变成 `{{tasks.train-a.outputs.parameters.model}}`。一个非 multi 输入端口只能有一个上游。必填输入必须连接。

本规则只适合小型 JSON。真实数据/模型应传资源 ID 或 URI，或改为 Artifact/PVC，不应内嵌到 Workflow parameters。

## DAG 约束

- node ID 全局唯一，Edge 引用必须存在。
- 禁止自连接、完全重复 Edge 和循环。
- 源/目标端口必须存在且类型一致。
- 必填输入必须有且只有一个上游（除非 Registry 明确 `multiple=true`）。
- 完全不参与 Edge 的节点被视为孤立节点；单节点 Pipeline 是允许执行的特例。

校验响应把 `errors` 与 `warnings` 分开；每个 issue 包含 `code`、易懂 `message`，并尽可能包含 `nodeId`、`field`。

## 运行策略

`spec.runPolicy.timeoutSeconds` 控制 Workflow 整体 active deadline。节点 Registry 提供默认超时和重试；当前 Compiler 会生成 `retryLimit`，节点默认超时作为后续扩展元数据保留。Argo v4 不允许在本 PoC 使用的 steps 包装器上设置 `timeout`，因此当前由 Workflow 总超时兜底。

## 当前限制与扩展

v1alpha1 不支持条件、循环、子 Pipeline、动态扇出、跨集群、用户模板和 Artifact Lineage。后续可新增版本化端口 Schema、可选/多输入端口、条件表达式、Artifact 描述符和 Adapter 执行目标，但必须通过新 DSL 版本演进并保留 Compiler 兼容层。

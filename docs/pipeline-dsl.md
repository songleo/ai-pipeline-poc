# Pipeline JSON DSL

## 顶层结构

`apiVersion` 固定为 `demo.pipeline.io/v1alpha1`，`kind` 固定为 `Pipeline`。`metadata.name` 是 DNS 风格 Pipeline 名。`spec` 是执行定义；`uiLayout` 只是编辑器坐标，Compiler 不依赖它。

```json
{
  "apiVersion": "demo.pipeline.io/v1alpha1",
  "kind": "Pipeline",
  "metadata": {
    "name": "comment-classification-demo",
    "experimentName": "小林的 AI 评论分类项目",
    "scenario": "training-evaluation-admission",
    "tags": ["poc", "nlp", "comment-classification"]
  },
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
{"source":"train-candidate","sourcePort":"model","target":"eval-candidate","targetPort":"model"}
```

`uiLayout.nodes.<nodeId>` 保存 `{x,y}`，移动节点不会改变执行语义。

## 类型系统

当前端口类型覆盖 `DatasetRef`、`DataProfileRef`、`ModelRef`、`EvaluationRef`、`CandidateModelRef`、`LeaderboardRef`、`GateDecisionRef`、`RegisteredModelRef`、`InferenceTestRef`、`DeploymentRequestRef` 和 `ReportRef`。只有完全相同类型可以连接。参数使用 Registry 的 JSON Schema 子集，后端是最终权威校验方。

## 参数传递

普通参数从 node `parameters` 编译成 WorkflowTemplate inputs。Edge 编译成上游 Argo output parameter 引用。例如 `eval-candidate.evaluation → leaderboard.evaluationB` 变成 `{{tasks.eval-candidate.outputs.parameters.evaluation}}`。一个非 multi 输入端口只能有一个上游。必填输入必须连接。

## 门禁与条件分支

条件不是用户填写的任意表达式。Registry 为受控门禁输出声明固定分支：`approved*` 编译为 `decision == APPROVED`，`rejected*` 编译为 `decision == REJECTED`。门禁本身正常结束并输出 `GateDecisionRef`；未命中的下游显示 `SKIPPED`，业务拒绝不会伪装成系统失败。

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

v1alpha1 只支持 Registry 预定义的门禁条件，不支持用户表达式、循环、子 Pipeline、动态扇出、跨集群和用户模板。当前 Lineage 来自一次 Workflow 的小型输出，不是持久化 ML Metadata。后续扩展必须通过版本化 DSL 演进并保留 Compiler 兼容层。

# 架构说明

## 组件关系

```text
Vue Flow 编辑器
  │ Pipeline DSL / 状态、日志、输出
  ▼
FastAPI ── Node Registry ── Validator ── Compiler
  │                                      │
  │ Kubernetes Python Client             └─ 只生成白名单 templateRef
  ▼
Workflow CRD ── Argo Controller ── WorkflowTemplate ── Pods
```

Node Registry 是节点类型、版本、参数 Schema、端口类型、模板名、默认重试和超时的唯一来源。浏览器从 `/api/node-types` 获取它，不复制业务定义。Validator 是最终权威；前端校验只用于即时反馈。Compiler 与路由分离，可以被单元测试和未来 Adapter 复用。

## 安全边界

浏览器不能直接访问 Kubernetes，因为 kubeconfig 或 ServiceAccount token 会把集群凭据暴露给不可信客户端，也无法集中执行租户、配额、审计和节点白名单约束。后端 ServiceAccount 仅能在 `pipeline-demo` Namespace 操作 Workflow，并读取 Pod 与日志；不是 cluster-admin。

WorkflowTemplate 固定镜像和命令，DSL 只选择已注册节点并填写经过 Schema 校验的参数。禁止用户输入任意镜像、Shell、ServiceAccount 或原始 Argo YAML，避免把 Pipeline 编辑器变成远程代码执行入口。Workflow 使用另一低权限 ServiceAccount。

## 编译和执行链路

1. 前端生成执行定义与 `uiLayout` 分离的 JSON。
2. 后端校验名称、节点、参数、端口、必填输入、重复边和 DAG。
3. Compiler 把 node ID 规范化为安全且唯一的 Argo task 名。
4. Edge 变成 task dependency 和 `{{tasks.<task>.outputs.parameters.<port>}}` 引用。
5. 每个 task 只引用 `pipeline-demo-nodes` 中映射的 template，并附带运行/节点映射标签或注解。
6. Kubernetes API 在 `pipeline-demo` 创建 Workflow；Argo controller 创建 Pod。
7. 后端把 Argo phase 映射为统一状态，解析节点/Pod/重试次数与 output parameters。

预处理完成后两个训练 task 仅依赖 preprocess，因此可以并行；compare 同时依赖两者，report 依赖 compare。

## 状态、日志和输出链路

前端运行期间每 2 秒请求 run detail。后端从 Workflow `status.phase` 和 `status.nodes` 映射 `PENDING/RUNNING/SUCCEEDED/FAILED/ERROR/CANCELLED/SKIPPED`。点击节点后，后端用 Workflow 名和 node ID 映射到 task/Pod，通过 Pod Log API读取完整日志，并从 Argo node outputs 返回小型 JSON。

停止调用对 Workflow status 的 `shutdown: Terminate` patch。终态后重复停止返回幂等结果，不删除 Workflow。

## 数据边界

本 PoC 只验证小型 JSON parameter。它不适合传递真实数据集或模型；后续应传资源 ID、对象存储 URI，或使用 PVC/Argo Artifact。参数大小、Kubernetes 对象大小和日志保存都不是生产级 Artifact 通道。

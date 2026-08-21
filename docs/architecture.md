# 架构说明

## 组件关系

```text
Pipeline 列表 / 模板 / Vue Flow 三栏编辑器 / 独立运行视图
  │ Pipeline DSL / 状态、日志、输出
  ▼
FastAPI ── Node Registry ── Validator ── Compiler
  │                                      │
  │ Kubernetes Python Client             └─ 只生成白名单 templateRef
  ▼
Workflow CRD ── Argo Controller ── WorkflowTemplate ── Pods
```

Node Registry 是节点类型、版本、参数 Schema、中文展示名、参数分组、PoC 模拟标识、端口类型、模板名、默认重试和超时的唯一来源。浏览器从 `/api/node-types` 获取它，不复制业务定义。Validator 是最终权威；前端校验用于即时反馈、问题列表和节点定位。Compiler 与路由分离，可以被单元测试和未来 Adapter 复用。`backend/app/adapters/contracts.py` 定义了最小 `start/get/cancel` 能力契约和显式 project/tenant/actor 上下文；当前 Argo 执行器尚未实现该平台契约。

## 安全边界

浏览器不能直接访问 Kubernetes，因为 kubeconfig 或 ServiceAccount token 会把集群凭据暴露给不可信客户端，也无法集中执行租户、配额、审计和节点白名单约束。后端 ServiceAccount 仅能在 `pipeline-demo` Namespace 操作 Workflow，并读取 Pod 与日志；不是 cluster-admin。

WorkflowTemplate 固定镜像和命令，DSL 只选择已注册节点并填写经过 Schema 校验的参数。禁止用户输入任意镜像、Shell、ServiceAccount 或原始 Argo YAML，避免把 Pipeline 编辑器变成远程代码执行入口。Workflow 使用另一低权限 ServiceAccount。

## 编译和执行链路

1. 前端生成执行定义与 `uiLayout` 分离的 JSON。
2. 后端校验名称、节点、参数、端口、必填输入、重复边和 DAG。
3. Compiler 把 node ID 规范化为安全且唯一的 Argo task 名。
4. Edge 变成 task dependency 和 `{{tasks.<task>.outputs.parameters.<port>}}` 引用。
5. 每个 task 只引用 `pipeline-demo-nodes` 中映射的 template，并附带运行/节点映射标签、12 位 Pipeline 定义摘要或注解。
6. Kubernetes API 在 `pipeline-demo` 创建 Workflow；Argo controller 创建 Pod。
7. 后端把 Argo phase 映射为统一状态，解析节点/Pod/重试次数与 output parameters。

门禁节点是受控的特殊节点：固定模板输出 `APPROVED` 或 `REJECTED`，Registry 把业务输出端口映射成固定 Argo `when` 条件。用户不能提交表达式。未命中分支映射为 `SKIPPED`，因此业务拒绝仍可让 Workflow 正常成功，并与容器失败、系统错误区分。

评论数据预处理完成后两个微调 task 仅依赖 preprocess，因此可以并行；compare 同时依赖两路评测。准入通过后登记模型，推理冒烟验证结构化预测，再由部署交接节点生成 `DeploymentRequestRef`。交接节点不创建推理服务，只证明未来 `InferenceDeploymentAdapter/v1` 的输入可由 Pipeline 产出。

## 状态、日志和输出链路

前端运行期间每 2 秒请求 run detail。后端从 Workflow `status.phase` 和 `status.nodes` 映射 `PENDING/RUNNING/SUCCEEDED/FAILED/ERROR/CANCELLED/SKIPPED`。点击节点后，后端用 Workflow 名和 node ID 映射到 task/Pod，通过 Pod Log API读取完整日志，并从 Argo node outputs 返回小型 JSON。

顶部“停止”调用对整个 Workflow 的 `shutdown: Terminate` patch。终态后重复停止返回幂等结果，不删除 Workflow。

## 节点级停止与重新运行

节点代表一次可观察的执行尝试，不是常驻服务。当前 PoC 的控制语义如下：

- `PENDING/RUNNING`：可请求“停止此节点”。内置节点每秒从后端读取一次由 Workflow annotation 持久化的控制状态；收到 `STOP_REQUESTED` 后以保留退出码 64 结束。
- 退出码 64 在固定 WorkflowTemplate 的容器级 `retryStrategy.expression` 中被排除，因此人为停止不会消耗或触发自动重试；普通失败仍遵循节点的 `retryLimit`。
- 被停止节点映射为 `CANCELLED`，依赖它的下游节点不运行；不依赖它的并行分支继续执行。
- Workflow 到达终态后，可“重新运行此节点”。后端用编译器生成的安全 task 名调用 Argo 定向 retry，并开启 `restartSuccessful`；所选节点及下游重新执行，其他成功分支复用原结果。

浏览器不能提交 node selector、容器、命令或 Argo YAML；后端只接受 Workflow 名和 Pipeline node ID，并通过服务端 node map 生成选择器。Argo v4 的 `stop + nodeFieldSelector` 只支持 suspend node，不能用于终止普通运行 Pod，因此本 PoC 对固定内置节点采用协作式停止。生产节点应提供同样的取消检查或适配器，并为外部训练系统实现明确的 cancel API、幂等键和检查点。

## 数据边界

本 PoC 使用小型类型化 JSON 引用演示 Dataset、Model、Evaluation、Decision、InferenceTest、DeploymentRequest、Report 和单次运行 Lineage。它不适合传递真实数据集或模型；后续应传资源 ID、对象存储 URI，或使用 PVC/Argo Artifact。参数大小、Kubernetes 对象大小、Lineage 保留和日志保存都不是生产级 Artifact 通道。

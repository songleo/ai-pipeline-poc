# 接入 ai-platform 的后续建议

本文件只给出 PoC 边界内的设计建议，没有扫描、修改或调用 `ai-platform`。所有平台路径、API、CRD、鉴权和配额结论目前都是 **UNKNOWN**，接入前必须以目标分支代码和真实只读环境重新确认。

## 可复用部分

- 版本化 Pipeline DSL、执行定义与 UI 布局分离原则。
- Registry 驱动的前端节点/动态表单、端口类型校验和 DAG 校验。
- 独立 Compiler 接口、安全 task 名映射、统一运行/节点状态模型。
- 前端轮询、状态着色、日志/输出抽屉的交互骨架。
- WorkflowTemplate 白名单、禁止任意镜像/Shell/ServiceAccount 的安全边界。

## 仅演示代码

Python sleep 模拟任务、小型 JSON parameter、单 Namespace RBAC、无认证 API、localStorage、完整日志一次性读取、单实例前后端和 Kind 自动化都不能直接用于平台生产环境。

## Node Registry 对接

Registry 应变成平台能力目录的受控投影：节点类型映射训练、评测、模型或数据 API，带明确版本、输入输出资源契约、权限与配额要求。不能让前端直接拼平台 API。需要先扫描平台现有 capability/service/CRD 定义，确认谁是 source of truth。

## HTTP Adapter 与 CRD Adapter

- 平台任务本身已有 Kubernetes CRD、controller、status/conditions 且生命周期由控制器管理时，优先 CRD Adapter。
- 平台只提供稳定、幂等、可查询/可取消的服务 API 时，使用 HTTP Adapter。
- 不应仅为 Pipeline 强行复制一套 CRD。选择必须基于平台实际 API/CRD、错误模型、身份传递和停止语义的代码证据。

Adapter 至少实现 `submit(idempotencyKey)`、`getStatus(externalId)`、`getOutputs(externalId)`、`cancel(externalId)`。Workflow retry 会重复调用，所以平台创建 API 必须使用由 run ID + node ID 导出的幂等键；重试前先查询已存在外部任务。

## 停止与恢复

停止 Workflow 不等于停止外部训练。Adapter 的 exit handler 或控制器必须调用外部 cancel，并处理“已结束、重复取消、暂时不可达”。外部 ID 要持久化到可恢复位置，不能只存在 Pod 内存或日志中。

## 真实 Artifact

DSL Edge 传递的是 `ArtifactRef`（资源 ID、对象存储 URI、版本、校验和、媒体类型和权限范围），不是大对象。平台授权层在执行时换取短期凭据。根据现有存储能力决定对象存储、PVC 或 Argo Artifact；需要验证生命周期、加密、跨 Namespace 访问和垃圾回收。

## 身份、项目与 GPU 配额

后端必须从登录身份解析 project/tenant，服务端决定 Namespace 和 ServiceAccount，不能接受客户端覆盖。提交前后都要校验 GPU、队列、Namespace、镜像策略和资源配额，并把平台审计 ID 关联到 Pipeline run。具体字段和组件名称必须在扫描 `ai-platform` 后确认。

## 接入前必须确认的 UNKNOWN

- 训练、评测、模型、数据服务的实际 API/CRD 和版本策略。
- 身份与项目上下文如何传播，Namespace/ServiceAccount 谁负责分配。
- 队列、GPU quota、镜像准入、网络策略和审计接口。
- 外部任务的幂等、取消、重试、事件和日志接口。
- Artifact 存储、凭据、保留和 Lineage 实现。

验证方法：在明确授权的只读工作树中搜索 API/CRD/controller/SDK；再由平台各能力 owner 复核契约，并在隔离环境做最小 Adapter 冒烟测试。

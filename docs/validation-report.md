# 验证报告

更新时间：2026-08-20（Asia/Shanghai）

## 结论摘要

PoC 已完成真实端到端验证。Vue Flow 能支持拖拽、连线、端口和动态配置；版本化 DSL 能表达示例 DAG；独立 Compiler 能生成 Argo Workflow；Kind 中的 Argo Workflows 实际完成串行、并行、参数传递、固定失败重试和手动停止；前后端 Deployment、节点状态、Pod 日志和最终输出查询均已跑通。

建议继续采用“Vue Flow + 后端唯一 Node Registry + 版本化 DSL + 独立 Compiler + 固定 WorkflowTemplate + Argo”的方向进入下一阶段，但当前实现仍是单机 PoC，不是生产基线。

## 实际环境与版本

- Docker Desktop `4.85.0`，Docker Engine/CLI `29.6.2`。
- WSL Ubuntu `26.04`；APT 下载切换至清华镜像。
- 现有 Kind `v0.33.0-alpha+b5d66e1d2924df`；本地节点镜像实际 Kubernetes `v1.36.1`。
- kubectl `v1.36.3`；Helm `v3.21.3`。
- Argo Workflows `v4.0.8`，chart `1.0.23`，官方索引 SHA256 `a20365b94f3c286eed01c1ca7bd1ec428efa002f5610f140dd4c933322d6bc6d`。
- 容器运行时：Python `3.12.13`、Node `22.23.2`、npm `11.6.2`、Nginx `1.27.5`。
- 前端依赖：Vue `3.5.41`、Vite `8.2.0`、Vue Flow `1.48.2`、Element Plus `2.14.0`、Vitest `4.1.7`。
- 后端依赖：FastAPI `0.136.3`、Pydantic `2.13.4`、Kubernetes Client `33.1.0`、PyYAML `6.0.3`。

项目默认仍锁定 Kind `v0.29.0` + Kubernetes `v1.33.1` digest，以贴近 Argo v4.0.8 官方 tested matrix。本次按用户要求复用已有 Kind/节点镜像，因此实际是 Kubernetes v1.36.1；该版本不在官方 tested matrix，结论只适用于本次 PoC 实测。

## 实际命令与结果

### 2026-08-20 本轮 WSL/Kind 重新部署

本轮先做实时检查，确认 WSL 工具链和 Docker 正常、5173/8000/8080/2746 端口空闲，且当时只有 `ai-platform-local` 集群、目标 `pipeline-demo` 不存在。随后复用本机已有 Kind 节点镜像，只创建独立的 `pipeline-demo` 集群；所有 Kubernetes 操作均显式限定到 `kind-pipeline-demo`，未操作 `ai-platform-local`。

```bash
bash scripts/preflight.sh
KIND_NODE_IMAGE=kindest/node@sha256:3489c7674813ba5d8b1a9977baea8a6e553784dab7b84759d1014dbd78f7ebd5 \
  bash scripts/create-cluster.sh
bash scripts/install-argo.sh
bash scripts/build-images.sh
bash scripts/deploy-demo.sh
bash scripts/port-forward.sh
bash scripts/smoke-test.sh
```

结果：Kind 控制面约 18 秒 Ready，节点实际为 Kubernetes `v1.36.1`；Argo chart SHA256 校验通过，release revision 1、状态 `deployed`，controller/server 均 `1/1 Available`；前后端 Deployment 均 `1/1 Available`。实时健康检查返回 API `{"status":"ok","version":"0.1.0"}`、前端 HTTP 200、Argo HTTP 200。

完整 smoke 退出码 0：成功 Workflow `model-comparison-demo-pncz7` 为 `SUCCEEDED`；固定失败重试 Workflow `model-comparison-demo-v6l4c` 按预期为 `FAILED`；手动停止 Workflow `model-comparison-demo-m5ldx` 返回 `CANCELLED`。健康、Registry、DSL 校验、并行区间、日志、输出、固定失败重试和手动停止断言全部通过。

本轮 WSL 主机的 `python3` 实际为 `3.14.4`，与报告早前记录的主机版本不同；应用容器仍按 Dockerfile 使用锁定的 Python `3.12.13`。前端构建仍有主 JS chunk `1,188.79 kB`（gzip `384.12 kB`）超过 500 kB 的非阻塞告警。

### 预检、集群和 Argo

```bash
bash scripts/preflight.sh
KIND_NODE_IMAGE=kindest/node@sha256:3489c7674813ba5d8b1a9977baea8a6e553784dab7b84759d1014dbd78f7ebd5 bash scripts/create-cluster.sh
bash scripts/install-argo.sh
```

结果：预检退出码 0；Kind 在 21 秒达到 Ready；`kind-pipeline-demo` 节点 Ready；Argo controller/server 均 `1/1 Running`。改进后的安装脚本重复执行成功，chart SHA 校验 `OK`，Helm release revision 2、状态 `deployed`、app version `v4.0.8`。部署后再次运行预检时，项目 PID 文件和进程命令行校验能把 5173、8000、2746 识别为 `OWNED`，不再误报为外部端口冲突。

### 单元测试和构建

```bash
make test
npm.cmd audit --audit-level=high
PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
NPM_REGISTRY=https://registry.npmmirror.com bash scripts/build-images.sh
bash scripts/deploy-demo.sh
```

结果：后端 `22 passed`；前端 Vitest `3 passed`；`vue-tsc` 通过；Vite 生产构建通过，`1588 modules transformed`；npm audit `found 0 vulnerabilities`。前后端镜像成功加载 Kind；两个 Deployment 均 `1/1 Available`；WorkflowTemplate `pipeline-demo-nodes` 已创建。

Vite 唯一构建警告是主 JS chunk `1,188.79 kB`（gzip `384.12 kB`）超过 500 kB。PoC 不阻塞，生产化需要路由/组件级代码分割。

### Kubernetes schema 与完整 smoke

编译结果经 Kubernetes server-side dry-run 接受：

```text
workflow.argoproj.io/model-comparison-demo-m9pxg created (server dry run)
```

完整命令：

```bash
bash scripts/smoke-test.sh
```

结果：提交后的完整复测退出码 0，用时 `116.6s`，最终输出：

```text
Smoke test passed: health, registry, validation, success, parallel overlap,
logs, output, fixed failure retries, and manual stop.
```

实际 Workflow 证据：

- 成功：`model-comparison-demo-4c7t9`，PENDING → RUNNING → SUCCEEDED。
- 固定失败与自动重试：`model-comparison-demo-dt667`，终态 FAILED；脚本断言 `train-a.retryCount >= 2`，并读到 `fixed failure requested` 日志。
- 手动停止：`model-comparison-demo-vddlh`，后端 RUNNING → CANCELLED；Argo 最终为 `Failed / shutdown=Terminate / Stopped with strategy 'Terminate'`。
- 成功流程中 train-a/train-b 的开始结束区间实际重叠，脚本结构化断言通过。
- `train-a` 日志查询读到 `training completed`。
- `report` 输出返回 `ReportRef`，摘要为最佳模型及 accuracy。

### 删除集群后的全新部署复测

2026-08-20 再次执行 `make clean`，确认删除 `pipeline-demo-control-plane` 后，从零创建 Kind、首次安装 Argo、构建并加载应用镜像、创建 Namespace/RBAC/WorkflowTemplate/Deployment，再运行完整 smoke。Kind 控制面 19 秒 Ready；Argo release revision 1、controller/server 均 `1/1`；前后端 Deployment 均 `1/1`。

全新集群 smoke 退出码 0、用时 `136.5s`：成功 Workflow `model-comparison-demo-22l69` 为 `Succeeded`；固定失败重试 Workflow `model-comparison-demo-2zncj` 为预期 `Failed`；停止 Workflow `model-comparison-demo-jv5cz` 最终为 `Failed / shutdown=Terminate`，后端返回 `CANCELLED`。并行区间、日志和最终输出断言全部通过。

### 页面验证

此前本地浏览器实测完成：加载 6 节点示例、Vue Flow DAG、服务端校验、动态参数抽屉、Pipeline JSON 和 Workflow YAML。部署后从 Windows 通过当前 WSL IP `172.21.248.217` 验证：前端返回 200，后端返回 `{"status":"ok","version":"0.1.0"}`，Argo UI 返回 200。本机未启用 WSL localhost 自动转发，因此 Windows 需使用 `make demo` 输出的动态 WSL IP。前端每 2 秒轮询，终态停止轮询。

## 集成中发现并修复的问题

- Ubuntu 官方源下载卡住：备份后切换清华 APT 镜像，33.6 MB 索引约 14 秒完成。
- 全新构建发现 `build-images.sh` 默认仍指向官方 PyPI/npm registry，冷缓存下载耗时过长：脚本和 Dockerfile 默认值已改为清华 PyPI 与 npmmirror，仍可用环境变量按单次命令覆盖，不修改系统全局配置。
- Helm 仓库客户端超时：改为国内 GitHub 加速下载固定 chart，并按官方 index digest 校验。
- Docker 构建把 Windows `node_modules` 加入上下文导致内存不足：新增前后端 `.dockerignore`。
- Windows 生成的 lockfile 有两个 Rolldown 可选依赖缺失版本：补全固定 `1.2.5` 元数据，Linux 空目录 `npm ci` 通过。
- Kind 加载带 provenance 的 manifest list 失败：项目镜像改为 `--provenance=false` 单平台导出。
- Argo v4 拒绝 steps template 的 `timeout`：移除非法节点包装器 timeout，保留 Workflow 级 `activeDeadlineSeconds`。
- Argo v4 Pod v2 命名与 NodeStatus id 不完全相同：按稳定 node-id 后缀映射 Pod。
- Argo Pod 有 `wait/main` 两容器：日志 API 明确读取 `main`。
- 端口转发脚本的严格模式变量和生命周期问题已修复；cleanup 会核验 PID 命令行后再停止。
- 已启动的项目端口转发曾导致重复 `preflight` 误报端口占用：现在通过 PID 文件、存活进程和完整命令行三重校验识别项目自有端口。
- 首次提交后 smoke 在 WSL 内存紧张时，两次启动 Python 解析轮询响应出现 `Errno 12`，但脚本最终通过：高频状态解析已替换为 `jq` 并显式检查依赖；清理 7 个带项目标签的已终止测试 Workflow 后完整 smoke 复测通过，未再出现该错误。

## 当前限制与风险

- Kubernetes v1.36.1 不在 Argo v4.0.8 官方 tested matrix；虽然本次 smoke 通过，升级或生产采用前必须按目标版本重新资格验证。
- 项目默认 Kubernetes v1.33.1 已 EOL，仅适合隔离本地 PoC。
- 只通过 Argo parameters 传递小 JSON；真实数据集/模型需资源 ID、对象存储 URI、PVC 或 Artifact。
- 无登录、多租户、数据库、GPU、真实训练、WebSocket 日志、条件/循环/子 Pipeline、跨集群、HA 和生产监控。
- 前端 bundle 偏大；PoC 可接受，产品化需代码分割。
- 节点级默认超时目前仅作为 Registry 元数据保留；Argo steps 包装器不接受 timeout，现阶段由 Workflow 总超时兜底。生产化应改用兼容的模板级/任务级超时设计并单独验证。

## 技术建议

建议继续使用 Vue Flow + Argo。可复用边界是 DSL、Registry schema、校验器、Compiler 分层、状态模型、固定模板白名单和 API 契约；模拟脚本、单 Namespace、localStorage、端口转发和当前 RBAC/镜像布局只能作为演示实现。接入 ai-platform 前必须扫描其当前训练/评测/模型 API、鉴权、Namespace、配额、幂等和停止语义。


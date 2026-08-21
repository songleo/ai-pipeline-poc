# 验证报告

更新时间：2026-08-21（Asia/Shanghai）

## 结论摘要

PoC 已完成真实端到端验证。Vue Flow 能支持拖拽、连线、端口和动态配置；版本化 DSL 能表达示例 DAG；独立 Compiler 能生成 Argo Workflow；Kind 中的 Argo Workflows 实际完成串行、并行、参数传递、固定失败重试、整个流程停止、单节点停止和从节点重新运行；前后端 Deployment、节点状态、Pod 日志和最终输出查询均已跑通。

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

### 2026-08-21 自编排拖放与连线回归

问题根因是 `flowNodes` / `flowEdges` 使用 `shallowRef`，但节点拖放和锁定版 Vue Flow `addEdge()` 都会原地修改数组；相同数组引用不会触发画布更新。修复后，拖入节点和新增 Edge 均使用新数组引用，运行状态、Edge 动画和节点配置变更也显式触发画布更新；Handle 扩大到 14px 并强化了可见性。

前端验证命令：

```bash
docker build --provenance=false --target test \
  --build-arg NPM_REGISTRY=https://registry.npmmirror.com \
  -t pipeline-demo-frontend-test:0.1.0 frontend
```

结果：`vue-tsc` 严格类型检查通过，Vite 生产构建通过，Vitest `6 passed`。新增用例覆盖节点拖入时的新数组引用、`生成数据.dataset -> 数据预处理.dataset` 成功连线、Edge 到 DSL 的端口映射、端口类型不兼容拒绝，以及单输入端口重复连线拒绝。

Chrome 实际交互回归通过：点击“新建”，依次拖入“生成数据”和“数据预处理”，从生成数据的 `dataset: DatasetRef` 输出 Handle 拖到数据预处理同类型输入 Handle；画布 Edge 数为 1。Pipeline JSON 出现正确的 `sourcePort: dataset` 和 `targetPort: dataset`，页面前后端联合校验返回“校验通过”。

修复镜像 `pipeline-demo-frontend:0.1.0` 已加载到 `kind-pipeline-demo` 并滚动更新，前后端 Deployment 均 `1/1 Available`。完整 smoke 中成功 Workflow `model-comparison-demo-8kxqx` 达到 `SUCCEEDED`；随后固定失败重试 Workflow `model-comparison-demo-g5cdc` 在脚本 180 秒上限内仍为 `RUNNING`，因此本轮完整 smoke 退出 1，不能记为完整通过。该结果与前端拖放/连线回归分开记录。

原 WSL 5173 端口转发在长时间 smoke 后无响应。为避免关闭 WSL 或影响其他终端，使用同版本 `kindest/node:v1.33.1` 中的 kubectl 启动独立 Docker 转发容器 `pipeline-demo-frontend-forward-5174`；Windows 实测 `http://localhost:5174/` 返回 200，`http://localhost:5174/api/health` 返回 `{"status":"ok","version":"0.1.0"}`。

### 2026-08-21 WSL 扩容与节点级控制回归

按用户授权把 `%UserProfile%/.wslconfig` 从 1 CPU / 4GB / 2GB swap 调整为 8 CPU / 12GB / 4GB swap，并执行一次 WSL 整体重启。重启后实时读取为 `cpu=8`、内存约 `11Gi`、swap `4.0Gi`；`pipeline-demo-control-plane` 恢复为 Ready。前端曾因 CoreDNS 尚未 Ready 而先启动失败，DNS 就绪后仅滚动重启 `pipeline-demo-frontend` 即恢复。

节点控制实现前先对 Argo Workflows v4.0.8 做真实 API 探针。对运行中的普通节点调用 `/stop` 并传 `nodeFieldSelector=displayName=train-a`，服务端拒绝并返回：`currently, set only targets suspend nodes`。因此没有把该接口误包装为普通节点停止，而是为固定内置节点增加协作式取消检查；控制状态持久化在 Workflow annotation，退出码 64 在容器模板的 retry expression 中排除。用户仍不能提交任意 selector、镜像、命令或 YAML。

静态验证结果：

```text
backend: 25 passed
frontend: Vitest 6 passed
frontend: vue-tsc passed
frontend: Vite production build passed (1588 modules transformed)
git diff --check: passed（仅现有 CRLF 转换提示）
```

第一次节点停止探针 `node-control-e2e-frlc6` 发现 retry expression 放在 Steps 包装层时看不到 Pod 退出码，`train-a.retryCount=2`；该轮不计通过。随后把 retry strategy 移到固定 WorkflowTemplate 的容器层，并把受校验的 `retry-limit` 作为模板参数传入。

修正后真实 Workflow `node-control-e2e-fixed-5bkjz` 的结构化结果：

- `train-a` 与 `train-b` 同时进入 RUNNING 后，请求停止 `train-a`。
- `train-a` 终态为 `CANCELLED`，`retryCount=0`，没有触发自动重试。
- `train-b` 未受影响并达到 `SUCCEEDED`；其原始 `startedAt=2026-08-21T07:24:15Z`。
- Workflow 先按 DAG 规则达到 `FAILED`，compare/report 为 SKIPPED。
- 对 `train-a` 请求定向重新运行后，`train-a`、compare、report 重新执行并成功；`train-b.startedAt` 仍为 `2026-08-21T07:24:15Z`，证明并行成功分支没有重跑。
- Workflow 最终达到 `SUCCEEDED`，report 返回 `ReportRef`。
- 对已成功的 compare 再次请求重新运行后，仅 compare 和 report 进入 PENDING/RUNNING 并重新成功，上游生成、预处理和训练节点保持成功。

新增 `make node-smoke`，用于自动断言上述“停止无自动重试、并行分支继续、从节点重跑下游”的闭环。实际运行退出码 0，Workflow 为 `node-control-smoke-pcsz4`，最终输出 `Node control smoke passed`。

Chrome 页面回归也使用 30 秒双训练分支完成。页面中打开 `train-a` 的“运行”页签后，“停止此节点”可用；点击后立即显示 `控制请求=正在停止` 和“并行分支不会受影响”反馈。Workflow `model-comparison-demo-mf98c` 最终结构化结果为 `train-a=CANCELLED/retryCount=0`、`train-b=SUCCEEDED`、Workflow `FAILED`。另一个成功 Workflow `model-comparison-demo-dbx95` 中，从已成功的 `train-a` 点击“重新运行此节点”并确认后，页面正确显示 `train-a/compare/report=PENDING`、`train-b=SUCCEEDED`。默认 8 秒任务上也观察到停止请求与任务完成竞态；若任务先完成，最终状态保持 `SUCCEEDED`，当前后端不会继续把已终态节点显示为“正在停止”。

最终部署检查：`pipeline-demo-control-plane Ready / Kubernetes v1.33.1`，`pipeline-demo-backend 1/1`，`pipeline-demo-frontend 1/1`，`/api/health` 返回 `status=ok`。

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
- 无登录、多租户、数据库、真实 GPU、真实训练、WebSocket 日志、循环/子 Pipeline、跨集群、HA 和生产监控；后续 P0 已新增受 Registry 控制的固定条件门禁，但仍不支持用户表达式。
- 前端 bundle 偏大；PoC 可接受，产品化需代码分割。
- 节点级默认超时目前仅作为 Registry 元数据保留；Argo steps 包装器不接受 timeout，现阶段由 Workflow 总超时兜底。生产化应改用兼容的模板级/任务级超时设计并单独验证。

## 2026-08-21 P0 训练—评测—准入闭环

本轮把原有技术演示升级为 13 节点专业场景：数据集版本、数据画像、数据质量门禁、特征预处理、两路并行训练、两路模型评测、排行榜、模型准入门禁、模拟模型登记，以及通过/拒绝资格报告。仍不调用 `ai-platform`；所有执行继续由独立后端直接提交到 `kind-pipeline-demo` 的 Argo Workflows。

实现证据：

- Registry 使用 `DatasetRef`、`DataProfileRef`、`ModelRef`、`EvaluationRef`、`CandidateModelRef`、`LeaderboardRef`、`GateDecisionRef`、`RegisteredModelRef` 和 `ReportRef` 类型化端口。
- 门禁输出由服务端固定映射为 Argo `when` 条件；用户不能提交任意表达式。业务拒绝使未命中分支成为 `SKIPPED`，不会伪装成系统失败。
- 固定 WorkflowTemplate 只调用 `pipeline-demo-backend:0.1.0` 中的 `app.workflow_nodes`；未开放镜像、Shell、ServiceAccount 或原始 YAML。
- 固定 Pod resources 对 CPU/内存形成真实 Kubernetes 约束；`gpu-demo` 输出明确标记 `SIMULATED`，不请求 Kind 中不存在的 GPU。
- 页面新增实验名称/标签、运行概览、门禁决策、模型排行榜和单次 Workflow Artifact Lineage。

自动化验证：

```text
backend: 28 passed
frontend Vitest: 6 passed
frontend vue-tsc: passed
frontend production build: passed, 1588 modules transformed
bash -n scripts/*.sh: passed
```

Kind 部署和真实工作流：

- 后端和前端镜像重新构建并加载到 `pipeline-demo-control-plane`，显式滚动重启后两个 Deployment 均 `1/1 Available`。
- `make smoke` 等价脚本通过：默认准入流程 `training-qualification-demo-rvbwx` 为 `SUCCEEDED`，模型登记/通过报告成功、拒绝报告 `SKIPPED`；高阈值流程 `training-qualification-rejected-gtvfj` 为 `SUCCEEDED`，登记/通过报告 `SKIPPED`、拒绝报告成功。
- 固定失败节点完成两次自动重试后 Workflow 为 `FAILED`；长流程收到停止请求后为 `CANCELLED`。
- 节点控制流程 `node-control-smoke-7nn98` 通过：基线训练被协作式停止且未自动重试，候选训练继续成功；从基线训练节点重跑后，只重跑所选节点及其下游，最终 Workflow 成功。

Chrome 实际交互回归：

- 点击“新建”，从节点面板拖入“选择数据集版本”和“数据画像”，再从 `dataset: DatasetRef` 输出 Handle 连到同类型输入；Pipeline JSON 出现正确 `sourcePort=dataset`、`targetPort=dataset` Edge。
- 从 Chrome 点击“加载示例”和“运行”创建 `training-qualification-demo-94xcs`，最终 13/13 节点终态、Workflow `SUCCEEDED`，拒绝报告显示 `SKIPPED`。
- 右侧排行榜显示 xgboost `accuracy=0.915, f1=0.8625` 排名 1，lightgbm `accuracy=0.88, f1=0.825` 排名 2；概览显示数据质量和模型准入均 `APPROVED`；Lineage 显示从 Dataset 到 Report 的全部类型化引用。
- Windows 实测 `http://localhost:5173/` 返回 HTTP 200，`http://localhost:5173/api/health` 返回 `status=ok`。

边界：这些是本机 Kind PoC 证据，不代表真实训练、真实 GPU、生产模型登记或 `ai-platform` 集成。当前 Lineage 只来自保留中的 Workflow 小型输出，不是持久化 ML Metadata 服务。

## 技术建议

建议继续使用 Vue Flow + Argo。可复用边界是 DSL、Registry schema、校验器、Compiler 分层、状态模型、固定模板白名单和 API 契约；模拟脚本、单 Namespace、localStorage、端口转发和当前 RBAC/镜像布局只能作为演示实现。接入 ai-platform 前必须扫描其当前训练/评测/模型 API、鉴权、Namespace、配额、幂等和停止语义。

## 2026-08-21 通用 Pipeline Studio 与评论分类模板

本轮按评审意见保持产品能力通用：列表页、模板入口、三栏编辑器、运行视图、节点检查器、版本记录和运行历史不绑定具体业务。“小林的 AI 评论分类项目”只作为内置 Pipeline 模板，业务名称、样例文本和模型参数均保留在模板 DSL 中。新增通用“推理冒烟测试”和“推理部署交接”节点，以及尚未接入 `ai-platform` 的适配器协议边界；执行仍是 Kind 中固定白名单模板和 sleep 模拟。

静态验证结果：

```text
backend pytest: 30 passed
frontend Vitest: 8 passed
frontend vue-tsc: passed
frontend production build: passed
```

首次完整 smoke 暴露了拒绝分支缺陷：模型登记被门禁跳过后，推理冒烟仍解析其缺失输出，Workflow `training-qualification-rejected-qg2h8` 达到 `ERROR`。编译器随后增加门禁条件向后继节点的安全传播，并新增断言覆盖登记、推理冒烟和部署交接的同一准入条件；修复后的后端测试 30/30 通过。

修复镜像重新构建并加载到 `kind-pipeline-demo`，后端显式滚动更新。最终验证结果：

- 主流程 `comment-classification-demo-spclf` 为 `SUCCEEDED`，推理冒烟和部署交接均成功。
- 拒绝流程 `training-qualification-rejected-w4dx2` 为 `SUCCEEDED`，登记、推理冒烟和部署交接均为 `SKIPPED`，没有被误报成系统错误。
- 固定失败重试流程 `comment-classification-demo-rc2ft` 按预期为 `FAILED`；手动停止流程 `comment-classification-demo-htws6` 为 `CANCELLED`。
- `scripts/smoke-test.sh` 退出码 0，覆盖健康检查、Registry、校验、通过/拒绝门禁、并行训练、推理冒烟、部署交接、日志、重试和手动停止。
- 节点控制流程 `node-control-smoke-4kbfc` 退出码 0：基线训练独立停止且未自动重试，候选训练继续，随后从选定分支重跑成功。
- `pipeline-demo-backend` 与 `pipeline-demo-frontend` 均为 `1/1 Available`；`/api/health` 返回 `status=ok`，前端返回 HTTP 200。

Chrome 自动交互回归本轮未完成，不能记为通过。诊断确认 Chrome 已安装，但当前 Windows 用户下浏览器扩展数据目录不存在，且 `HKCU` 下 Native Messaging Host 注册项与清单文件缺失，因此可信控制通道不可用。需从 Codex/ChatGPT 插件界面重新安装 Browser 插件并确认 Chrome 扩展启用后，再补做拖拽、连线、模板运行和版本保存的 Chrome 实际交互回归。

## 2026-08-21 算法工程师体验改进

本轮按评审批准范围补齐通用编辑器与实验查看体验，没有增加真实训练或 `ai-platform` 调用：

- 编辑模式新增删除节点、关联连线清理、清空画布、撤销/重做、未保存提示、自动布局、适应画布、全屏和左右面板折叠；运行视图仍禁止结构修改。
- Node Registry 的 `uiSchema` 新增中文参数名、分组、单位、帮助信息和 `simulation` 标记。训练配置、资源、运行策略与 PoC 模拟参数分开展示；模拟 Accuracy/F1 明确不代表真实可配置结果。
- 校验结果改为问题列表，可点击定位并高亮节点；前后端用户可见校验消息统一为中文。
- 运行记录默认按最新时间排序，支持搜索、状态以及业务运行/系统验证筛选。回归脚本为新运行增加 `system-test` 标签。
- Compiler 为每次运行记录 12 位 Pipeline 定义摘要；运行详情增加完整 Accuracy/F1/延迟排行榜、候选相对基线差值和准入检查。

静态验证：

```text
frontend Vitest: 3 files, 13 tests passed
frontend vue-tsc: passed
frontend production build: passed, 1594 modules transformed
backend pytest: 31 passed
bash -n scripts/*.sh: passed
git diff --check: passed（仅 CRLF 转换提示）
```

新增前端单元回归覆盖：删除一个节点后所有入边/出边同步移除、整画布清空、左到右自动布局、必填输入缺失定位、运行记录最新优先、系统验证隔离和中文状态。Registry 单元回归确认训练参数中文标签、资源分组与模拟结果标识。

Kind 部署与真实执行：

- 后端镜像 `sha256:630bda5e2e7225a19a3c3963ebcdb026e54a6ca29824401dd3822d2a64a54ca4`、最终前端镜像 `sha256:cd5be93fe5662b03466c8a6cace66a78e83e70fe13aed8752420491b13a23fad` 已加载到 `pipeline-demo-control-plane`，两个 Deployment 滚动更新成功。
- `scripts/smoke-test.sh` 退出码 0：主链 `comment-classification-demo-z5qn4` 为 `SUCCEEDED`，定义摘要 `0706fb5b3c47`；拒绝分支 `training-qualification-rejected-xssbc` 为 `SUCCEEDED`；固定失败 `comment-classification-demo-h5dwv` 为 `FAILED`；手动停止 `comment-classification-demo-fvsvp` 为 `CANCELLED`。
- `scripts/node-control-smoke.sh` 退出码 0，Workflow `node-control-smoke-88rtj` 验证基线训练独立停止且不自动重试、候选训练继续、选定分支及下游重跑成功。

内置浏览器实际交互回归：

- 模板编辑页可见删除节点、清空画布、撤销/重做、自动布局、适应画布、全屏和面板折叠入口；未选择节点时删除禁用，空画布时清空与布局禁用。
- 点击自动布局后“撤销”可用并显示未保存提示；执行撤销后“重做”可用。
- 训练节点参数按中文分组显示，模拟执行时间、失败模式、Accuracy、F1 和延迟均标记“仅 PoC 模拟”，并展示正式接入边界说明。
- 空画布点击校验显示 `EMPTY_PIPELINE` 中文问题列表；清空按钮处于禁用状态。
- 系统验证筛选显示最新运行，`comment-classification-demo-z5qn4` 行包含成功状态与定义摘要 `0706fb5b3c47`。
- 成功运行详情显示 Accuracy/F1/延迟、三项准入检查、`Accuracy +0.0350 / F1 +0.0375` 候选增益和部署交接 READY。

浏览器回归没有代用户确认执行删除/清空动作，因此不能把确认后的页面删除动画记为浏览器通过；删除、关联连线清理和清空的数据行为由 13 项前端单元测试覆盖。当前实际页面地址 `http://localhost:5173`。

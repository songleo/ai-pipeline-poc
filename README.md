# pipeline-demo

`pipeline-demo` 是一个通用、独立的可视化 AI Pipeline PoC；编辑器、Registry、DSL 和运行视图不绑定具体业务。内置的“小林的 AI 评论分类项目”只是一份业务模板，用来演示“数据 → 训练/微调 → 评测 → 准入 → 模型登记 → 推理冒烟 → 部署交接”闭环。它不接入 `ai-platform`，由 FastAPI 后端直接把受控 DSL 编译为 Argo Workflow，也不允许浏览器直接访问 Kubernetes。

## 架构简介

浏览器通过 Vue Flow 编辑 Pipeline，只向 FastAPI 提交受约束的 DSL。后端以唯一 Node Registry 校验节点、参数、端口和 DAG，再把节点编译为白名单 `WorkflowTemplate` 引用并通过 Kubernetes API 创建 Argo Workflow。前端每 2 秒轮询统一状态，并按节点查询 Pod 日志和小型 JSON 输出。详见 [架构说明](docs/architecture.md)。

## 锁定版本

- Node.js `22.23.2`、npm `11.6.2`、Vue `3.5.41`、Vite `8.2.0`、Vue Flow `1.48.2`、Element Plus `2.14.0`
- Python `3.12.13`、FastAPI `0.136.3`、Pydantic `2.13.4`、Kubernetes Python Client `33.1.0`、PyYAML `6.0.3`
- Nginx `1.27.5`
- Argo Workflows `v4.0.8`（Helm chart `1.0.23`）
- Kind `v0.29.0`、Kubernetes `v1.33.1`（固定镜像 digest）

Kubernetes 1.33 已结束支持；这里选择它仅因为它在 Argo v4.0.8 官方测试矩阵内，且只用于隔离本地 PoC，不能作为生产基线。

本次实际集成按“优先使用现有工具/镜像”执行：Kind `v0.33.0-alpha`、Kubernetes `v1.36.1`、kubectl `v1.36.3`、Helm `v3.21.3`。该组合不在 Argo v4.0.8 官方 tested matrix 内，但完整 smoke 已通过；这只是本机 PoC 证据，不代表生产兼容承诺。

## 环境要求

Docker、Kind、kubectl、Helm、Node.js 22.12+、npm、Python 3.12、jq 和 Bash。所有 Kubernetes 脚本只接受 context `kind-pipeline-demo`；若 context 不匹配会拒绝执行。

## 快速启动

```bash
make preflight
make bootstrap
make build
make deploy
make demo
```

若本机已有可用 Kind 节点镜像，可在首次建群时使用 `KIND_NODE_IMAGE=<本地镜像引用> make bootstrap`。Argo chart 默认通过国内 GitHub 加速地址下载，并以官方索引 SHA256 校验；可用 `ARGO_CHART_URL` 或 `ARGO_CHART_ARCHIVE` 覆盖。

访问 `http://localhost:5173`；后端健康检查为 `http://localhost:8000/api/health`；Argo UI 为 `http://localhost:2746`。端口转发日志写在仓库根目录的 `*-port-forward.log`。

若 Windows 未启用 WSL localhost 自动转发，`make demo` 会同时输出当前 WSL IP 回退地址，例如 `http://172.x.x.x:5173`；该 IP 在 WSL 重启后可能变化。

## 开发方式

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.lock
uvicorn app.main:app --reload

cd ../frontend
npm ci
npm run dev
```

镜像构建默认使用清华 PyPI 与 npmmirror，不修改系统全局配置；可通过 `PIP_INDEX_URL` 和 `NPM_REGISTRY` 为单次命令覆盖。后端本地开发也可使用：`pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -e '.[dev]'`。

前端开发服务器把 `/api` 代理到 `localhost:8000`。Pipeline 列表和版本在 PoC 阶段保存到浏览器 localStorage；正式集成时应替换为平台存储适配器。Node Registry 只由后端维护，前端动态生成组件库、类型化端口和参数表单。

## 演示与测试

在 Pipeline 列表页选择“小林的 AI 评论分类项目”模板，然后点击“校验”和“运行”。默认示例包含 15 个可编排节点、两个受控条件门禁、并行微调/评测、模型排行榜、模拟推理和 `DeploymentRequestRef` 交接。详细步骤见 [5 分钟演示指南](docs/demo-guide.md)。

```bash
make test
make smoke
```

`make smoke` 检查健康、Registry、校验、提交、通过/拒绝两种门禁路径、排行榜、节点状态、日志、输出和两训练节点时间区间重叠。实际执行证据见 [验证报告](docs/validation-report.md)。

## 停止和清理

页面“停止”对 Workflow 使用 Argo shutdown `Terminate` 语义。只清理本项目集群：

```bash
make clean
```

该命令只终止本项目记录的端口转发 PID，并删除名为 `pipeline-demo` 的 Kind 集群；不会删除其他集群、目录或镜像。

## 常见故障

- `current context ... expected kind-pipeline-demo`：脚本主动保护了其他集群；先运行 `make bootstrap`。
- Docker 不可用：启用 Docker Desktop 的 WSL integration，再运行 `make preflight`。
- Helm 或 Kind 缺失：从官方发行页安装锁定版本；脚本不会替你执行系统级安装。
- Workflow 一直 Pending：检查 `kubectl --context kind-pipeline-demo -n pipeline-demo get pods,workflow` 以及 Argo controller 日志。
- 前端无法访问 API：确认 8000 端口转发存在，并查看 `backend-port-forward.log`。
- 模拟训练固定失败：`failMode=always` 是可靠的演示开关；改回 `never` 后再运行成功流程。

## 当前限制

本 PoC 的 Dataset/Model/Evaluation/InferenceTest/DeploymentRequest/Report 都是小型结构化引用，所有业务任务只是固定 sleep 与模拟 JSON；没有真实评论、模型文件或推理服务。Lineage 也只属于本次 Workflow。真实接入必须改用平台资源 ID、对象存储 URI、PVC 或 Argo Artifact。CPU/内存由固定 Pod resources 约束，`gpu-demo` 只展示模拟规格，不请求真实 GPU。当前没有登录、多租户、数据库、真实训练、持久化 Artifact Metadata、WebSocket 日志、定时/循环/子 Pipeline、任意镜像或 Shell、跨集群和生产级高可用。

## 官方版本依据

- [Argo Workflows v4.0.8](https://github.com/argoproj/argo-workflows/releases/tag/v4.0.8) 与 [官方测试 Kubernetes 版本](https://github.com/argoproj/argo-workflows/blob/v4.0.8/docs/tested-kubernetes-versions.md)
- [Argo Helm chart 1.0.23](https://github.com/argoproj/argo-helm/blob/argo-workflows-1.0.23/charts/argo-workflows/Chart.yaml)
- [Kind v0.29.0](https://github.com/kubernetes-sigs/kind/releases/tag/v0.29.0) 与 [Kubernetes 发布周期](https://kubernetes.io/releases/)
- [Vue Flow v1.48.2](https://github.com/bcakmakoglu/vue-flow/releases/tag/v1.48.2)、[Vue v3.5.41](https://github.com/vuejs/core/releases/tag/v3.5.41)、[Vite v8.2.0](https://github.com/vitejs/vite/releases/tag/v8.2.0)、[Element Plus v2.14.0](https://github.com/element-plus/element-plus/releases/tag/2.14.0)
- [Node.js v22 发布线](https://nodejs.org/en/about/previous-releases)
- [FastAPI v0.136.3](https://github.com/fastapi/fastapi/releases/tag/0.136.3)、[Pydantic v2.13.4](https://github.com/pydantic/pydantic/releases/tag/v2.13.4)、[Kubernetes Python Client v33.1.0](https://github.com/kubernetes-client/python/releases/tag/v33.1.0)


# Scheduled tasks

- 创建 scheduled task 时，优先使用云端运行

# Project rules

- Keep every project artifact inside this repository.
- Documentation and user-facing demo guidance are written in Chinese; code identifiers are English.
- Never operate on a Kubernetes context other than `kind-pipeline-demo`.
- Do not install system packages or integrate with `ai-platform`.
- Commit changes only after confirming required files are in expected state and tests/validation evidence is recorded.
- 禁止在仓库内任何代码、脚本、文档保留历史命名前缀残留。
- Prefer a minimal demonstrable pipeline over production infrastructure.
- Never accept arbitrary container images, shell commands, service accounts, or raw Argo YAML from users.
- Record commands and truthful results in `docs/validation-report.md`.
- Keep destructive operations explicit and avoid operations outside this repository without approval.
- 使用 HTTPS 方式维护 `origin`（推荐 `https://github.com/songleo/ai-pipeline-poc.git`）以降低 SSH 环境阻断风险。


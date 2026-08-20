# Scheduled tasks

- When creating scheduled tasks, prefer cloud execution by default.

# Project rules

- Keep every project artifact inside this repository.
- Documentation and user-facing demo guidance are written in Chinese; source code and script identifiers are English.
- Do not operate Kubernetes with any context other than `kind-pipeline-demo`.
- Do not install system packages.
- Do not integrate with `ai-platform`.
- Commit only after required files are in expected state and validation/verification evidence is recorded.
- Use consistent naming: do not keep legacy naming remnants in repository code, scripts, or docs.
- Prefer a minimal, demonstrable pipeline over production-grade infrastructure.
- Never accept arbitrary container images, shell commands, service accounts, or raw Argo YAML from users.
- Record commands and truthful results in `docs/validation-report.md`.
- Keep destructive operations explicit, and avoid operations outside this repository without approval.
- Maintain `origin` using HTTPS (prefer `https://github.com/songleo/ai-pipeline-poc.git`) to avoid SSH-related push failures.


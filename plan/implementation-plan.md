# 实施计划（核心能力优先）

更新时间：2026-03-06

## 1. 里程碑

### M1：本地可用原型（1-2 天）

交付：
- 项目目录结构初始化。
- API：列表、上传、下载、删除（重名覆盖）。
- 通过 Docker 启动并接入 filebrowser。

验收：
- 能在两个项目目录中分别上传和下载文件。
- 不能跨项目访问文件。

### M2：MCP 接入（1 天）

交付：
- 使用 FastMCP 暴露 6 个核心 tools（含大文件分片工具）。
- tools 调用后端 API 完成文件操作。

验收：
- MCP 可以按项目列文件、上传、下载、删除。
- MCP 与前端行为一致。

### M3：稳定化（1-2 天）

交付：
- 大小限制、路径校验、错误码统一。
- 大文件分片上传（init/chunk/complete/abort）。
- 配置文件管理（`config/app.toml`）。
- PostgreSQL 接入（分片会话与状态）。

验收：
- 异常场景有明确错误返回。
- 关键配置无需改代码即可调整。
- 分片上传中断后可终止并清理临时分片。

## 2. 推荐目录结构（新仓库）

```text
project-file-platform/
  web/
  api/
  mcp-server/
  storage/
  plan/
```

## 3. 首批任务清单

1. 定义 `project_id -> root_path` 映射配置。
2. 实现统一路径规范化函数（防穿越）。
3. 完成 5 个 API。
4. 基于 FastMCP 绑定 6 个 tools（含分片上传）。
5. 用 10 个端到端用例做回归验证。
6. 使用 `uv` 初始化 Python 工程依赖管理（`uv init` / `uv sync`）。
7. 锁定 Python `3.13` 版本管理（维护 `.python-version` 为 `3.13`）。
8. 增加 filebrowser Docker 启动配置（如 `docker compose`）。
9. 增加 PostgreSQL Docker 启动配置（无需宿主机安装 PG）。
10. 定义 `config/app.toml` 模板（项目映射、文件上限、分片大小、PG DSN）。
11. 实现重名覆盖策略与分片上传 4 个接口。

## 4. 建议排期（5 天）

起始日期按 `2026-03-06` 计算，可顺延。

1. Day 1（2026-03-06）：工程与环境基线
完成内容：`uv + Python 3.13` 初始化，创建工程目录，补齐 `docker compose`（api/mcp/filebrowser/postgres）。
验收标准：容器可启动，API 与 MCP 空服务可运行，PG 可连接。

2. Day 2（2026-03-07）：核心 API（非分片）
完成内容：`projects/files/upload/download/delete`，路径规范化与项目隔离校验，同名覆盖策略。
验收标准：跨项目访问被拦截；上传、下载、删除、列表全可用。

3. Day 3（2026-03-08）：分片上传与配置管理
完成内容：`upload/init/chunk/complete/abort`，PG 上传会话表，`config/app.toml` + 环境变量覆盖。
验收标准：大文件可分片上传并合并；中断后可 `abort` 清理。

4. Day 4（2026-03-09）：MCP 工具对齐
完成内容：6 个 MCP tools 接入统一 API，补齐 `download_file` 2MB 内联上限策略与错误码。
验收标准：MCP 行为与 API/前端一致；大文件下载超限返回 `MCP_PAYLOAD_TOO_LARGE`。

5. Day 5（2026-03-10）：联调与验收
完成内容：至少 10 个 E2E 场景回归（隔离、穿越、覆盖、分片、超限、删除一致性）。
验收标准：核心场景全部通过，错误码与日志输出一致，形成上线前检查清单。

## 5. 生产化补充（已纳入）

1. 数据库迁移机制
完成内容：引入 `migrations/*.sql` 与 `schema_migrations` 版本表；支持 `uv run pfp-migrate` 手动迁移。
验收标准：迁移可重复执行且幂等，版本记录可追踪。

2. 日志落盘与轮转
完成内容：统一日志配置（JSON + 文件轮转 + stdout），输出 `logs/api.log`、`logs/mcp.log`。
验收标准：容器重启后日志持续可写，单文件大小和保留数可配置。

3. CI 自动化
完成内容：新增 CI 工作流，自动执行测试和 Docker 镜像构建。
验收标准：提交或 PR 时自动触发，失败可阻断合入。

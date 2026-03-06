# Project File Platform

快速使用文档见：`docs/USAGE.md`

按项目隔离的文件平台（FastAPI + FastMCP），支持：

- 项目隔离文件管理
- 小文件上传/下载/列表/删除
- 大文件分片上传（init/chunk/complete/abort）
- MCP 工具暴露（仅通过 API 调用）
- filebrowser Docker 前端

## 技术基线

- Python `3.13`
- 依赖管理：`uv`
- 数据库：PostgreSQL（默认 Docker）
- 前端：`filebrowser/filebrowser`（Docker）

## 目录结构

```text
project-file-platform/
  api/
  mcp-server/
  web/
  config/
  storage/
  src/
  tests/
  plan/
```

## 本地开发（uv）

1. 安装依赖

```bash
uv sync
```

2. 启动 API

```bash
uv run pfp-api
```

如端口冲突可改本地端口：`API_PORT=18000 uv run pfp-api`

3. 启动 MCP（另一个终端）

```bash
uv run pfp-mcp
```

默认以 `streamable-http` 方式启动在 `http://localhost:8001/mcp`。  
如需 stdio 模式可使用：`MCP_TRANSPORT=stdio uv run pfp-mcp`

4. 运行测试

```bash
uv run pytest -q
```

## Docker 一键启动

```bash
docker compose up --build
```

如有端口冲突，可通过 `.env` 覆盖宿主机端口映射（见 `docs/USAGE.md`）。

服务端口：

- API: `http://localhost:8000`
- MCP: `http://localhost:8001/mcp`
- filebrowser: `http://localhost:8080`
- PostgreSQL: `localhost:5432`

## 生产化能力

- 数据库迁移：`migrations/*.sql` + `schema_migrations` 版本记录
- 启动时自动迁移（可关）：`postgres.run_migrations_on_startup`
- 日志落盘与轮转：`logs/api.log`、`logs/mcp.log`
- CI：`.github/workflows/ci.yml`（自动测试 + 镜像构建）

手动执行迁移：

```bash
uv run pfp-migrate
```

## 配置

主配置文件：`config/app.toml`

关键项：

- `[projects]`: `project_id -> root_path`
- `[storage].max_file_size_mb`: 单文件大小上限
- `[storage].chunk_size_mb`: 分片大小
- `[mcp].max_inline_download_mb`: MCP 下载内联返回上限
- `[postgres].dsn`: PostgreSQL 连接串
- `[postgres].run_migrations_on_startup`: 启动时是否自动执行迁移
- `[service].log_dir`: 日志目录
- `[service].log_json`: 是否输出 JSON 日志
- `[service].log_file_max_mb`: 单日志文件大小上限（MB）
- `[service].log_backup_count`: 轮转保留文件数
- `[service].log_to_stdout`: 是否同时输出到标准输出

环境变量覆盖：

- `APP_CONFIG_PATH`
- `APP_STORAGE_MAX_FILE_SIZE_MB`
- `APP_STORAGE_CHUNK_SIZE_MB`
- `APP_MCP_MAX_INLINE_DOWNLOAD_MB`
- `APP_POSTGRES_DSN`
- `APP_POSTGRES_RUN_MIGRATIONS_ON_STARTUP`
- `APP_SERVICE_LOG_LEVEL`
- `APP_SERVICE_LOG_DIR`
- `APP_SERVICE_LOG_JSON`
- `APP_SERVICE_LOG_FILE_MAX_MB`
- `APP_SERVICE_LOG_BACKUP_COUNT`
- `APP_SERVICE_LOG_TO_STDOUT`
- `APP_MIGRATIONS_DIR`

## API 概览

- `GET /health`
- `GET /api/v1/projects`
- `GET /api/v1/files`
- `POST /api/v1/files/upload`
- `GET /api/v1/files/download`
- `DELETE /api/v1/files`
- `POST /api/v1/files/upload/init`
- `PUT /api/v1/files/upload/chunk`
- `POST /api/v1/files/upload/complete`
- `POST /api/v1/files/upload/abort`

统一响应：

- 成功：`{"ok": true, "data": ...}`
- 失败：`{"ok": false, "error": {"code": "...", "message": "..."}}`

## MCP 工具

- `list_projects`
- `list_files`
- `upload_file`
- `upload_file_chunked`
- `download_file`
- `delete_file`

`download_file` 内联返回上限默认 `2MB`，超限返回 `MCP_PAYLOAD_TOO_LARGE`。

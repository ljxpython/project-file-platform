# 使用文档（启动、运行、功能说明）

更新时间：2026-03-06

## 1. 项目功能

本系统是一个按 `project_id` 隔离的文件平台，当前已实现：

- 项目隔离文件管理（禁止跨项目访问、禁止 `../` 穿越）
- 小文件上传、下载、列表、删除
- 大文件分片上传（`init/chunk/complete/abort`）
- MCP 工具暴露（6 个 tools）
- filebrowser 前端浏览（Docker）
- PostgreSQL 存储分片会话
- SQL 迁移机制（支持启动自动迁移 + 手动迁移）
- JSON 日志落盘与轮转

## 2. 运行方式总览

支持两种方式：

- Docker（推荐）：一键启动全部服务
- 本地开发：`uv` 启动 API/MCP，数据库用本机或 Docker PG

## 3. 环境要求

- Python `3.13`
- `uv`（依赖管理）
- Docker + Docker Compose（用于容器部署）

## 4. Docker 一键启动（推荐）

在项目根目录执行：

```bash
docker compose up -d --build
```

查看状态：

```bash
docker compose ps -a
```

查看日志：

```bash
docker compose logs -f api mcp postgres filebrowser
```

停止服务：

```bash
docker compose down
```

访问地址：

- API: `http://localhost:8000`
- MCP: `http://localhost:8001/mcp`
- filebrowser: `http://localhost:8080`
- PostgreSQL: `localhost:5432`

### 4.1 端口冲突处理（重要）

如果你本机已有服务占用了 `8000/8001/8080/5432`，请先配置 `.env` 再启动：

```bash
cp .env.example .env
```

例如将 API 改到 `18000`，filebrowser 改到 `18080`：

```bash
API_HOST_PORT=18000
FILEBROWSER_HOST_PORT=18080
```

然后重启：

```bash
docker compose up -d --build
```

说明：

- 容器内部端口不变（API 仍是容器内 `8000`）
- 容器间通信不受影响（MCP 仍通过 `http://api:8000` 调 API）

## 5. 本地开发运行（uv）

1. 安装依赖

```bash
uv sync --dev
```

2. 启动 API

```bash
uv run pfp-api
```

如需改端口（避免与本机前端冲突）：

```bash
API_PORT=18000 uv run pfp-api
```

3. 启动 MCP（另一个终端）

```bash
uv run pfp-mcp
```

默认 MCP 走 `streamable-http`，地址：`http://localhost:8001/mcp`  
如需 `stdio` 模式：

```bash
MCP_TRANSPORT=stdio uv run pfp-mcp
```

4. 运行测试

```bash
uv run pytest -q
```

## 6. 数据库迁移

手动执行迁移：

```bash
uv run pfp-migrate
```

说明：

- 迁移文件目录：`migrations/`
- 版本记录表：`schema_migrations`
- API 启动时会自动迁移（可配置关闭）

## 7. 配置说明

主配置文件：`config/app.toml`

关键配置：

- `[projects]`：`project_id -> root_path` 映射
- `[storage].max_file_size_mb`：单文件大小限制
- `[storage].chunk_size_mb`：分片大小
- `[mcp].max_inline_download_mb`：MCP 内联下载大小上限
- `[postgres].dsn`：数据库连接串
- `[postgres].run_migrations_on_startup`：启动自动迁移开关
- `[service].log_*`：日志行为配置

常用环境变量覆盖：

- `APP_CONFIG_PATH`
- `APP_POSTGRES_DSN`
- `APP_POSTGRES_RUN_MIGRATIONS_ON_STARTUP`
- `APP_STORAGE_MAX_FILE_SIZE_MB`
- `APP_STORAGE_CHUNK_SIZE_MB`
- `APP_MCP_MAX_INLINE_DOWNLOAD_MB`
- `APP_SERVICE_LOG_LEVEL`
- `APP_SERVICE_LOG_DIR`
- `APP_SERVICE_LOG_JSON`
- `APP_SERVICE_LOG_FILE_MAX_MB`
- `APP_SERVICE_LOG_BACKUP_COUNT`
- `APP_SERVICE_LOG_TO_STDOUT`
- `APP_MIGRATIONS_DIR`

## 8. API 功能清单

统一响应：

- 成功：`{"ok": true, "data": ...}`
- 失败：`{"ok": false, "error": {"code": "...", "message": "..."}}`

接口列表：

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

## 9. MCP 功能清单

MCP 已暴露 6 个工具：

- `list_projects`
- `list_files`
- `upload_file`
- `upload_file_chunked`
- `download_file`
- `delete_file`

说明：

- MCP 不直接读写磁盘，全部通过 API。
- `download_file` 超过内联阈值会返回 `MCP_PAYLOAD_TOO_LARGE`。

## 10. 日志与数据目录

日志目录：

- `logs/api.log`
- `logs/mcp.log`

数据目录：

- `storage/projects/*`：业务文件
- `.data/postgres`：PostgreSQL 数据
- `.data/filebrowser`：filebrowser 数据

## 11. 快速验收（建议）

启动后按顺序检查：

1. 健康检查

```bash
curl http://localhost:8000/health
```

2. 项目列表

```bash
curl http://localhost:8000/api/v1/projects
```

3. filebrowser 页面

打开 `http://localhost:8080/`，确认可浏览 `storage` 目录。

4. MCP 连通性（示例）

用 FastMCP Client 连 `http://localhost:8001/mcp`，调用 `list_projects`。

## 12. 常见问题

1. `api is unhealthy`
- 先看日志：`docker compose logs --tail=200 api`
- 常见原因：数据库未就绪、迁移目录缺失、配置路径错误

2. filebrowser 启动报权限错误
- 确保目录存在并可写：`.data/filebrowser`
- 必要时修复权限后重启：`docker compose restart filebrowser`

3. 拉镜像超时
- 配置 Docker 镜像源后重试
- 分开手动 `docker pull` 相关镜像再 `compose up`

4. `port is already allocated` / 端口冲突
- 使用 `.env` 覆盖端口映射（见“4.1 端口冲突处理”）
- 查看占用：`ss -ltnp | grep ':8000'`

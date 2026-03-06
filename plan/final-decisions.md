# 最终决策清单（v1.1）

更新时间：2026-03-06

## 1. 已确认范围

- 当前阶段不做权限系统与鉴权。
- 核心能力：项目隔离、上传、下载、列表查询、MCP 工具暴露。

## 2. 项目隔离与路径规则

- 使用配置文件维护 `project_id -> root_path` 映射。
- 所有接口必须传 `project_id`，`path` 为项目内相对路径。
- 服务端执行 `normalize + resolve` 并校验目标路径在项目根目录下。
- 禁止 `../` 穿越、禁止跨项目访问。
- 文件名允许中文、英文、数字、空格、`-`、`_`、`.`；禁止控制字符。

## 3. 上传下载策略

- 同名文件处理：覆盖（overwrite）。
- 上传写入流程：临时文件写入后原子重命名。
- 单文件上限：`500MB`（可配置）。
- 大文件采用分片上传，默认分片大小 `8MB`（可配置）。
- 下载使用流式返回，避免一次性加载内存。

## 4. 大文件分片协议（API 约定）

- `POST /api/v1/files/upload/init`
  - 入参：`project_id`、`path`、`filename`、`total_size`、`chunk_size`
  - 出参：`upload_id`
- `PUT /api/v1/files/upload/chunk`
  - 入参：`upload_id`、`part_number`、chunk 二进制
- `POST /api/v1/files/upload/complete`
  - 入参：`upload_id`、`parts`
  - 行为：按分片顺序合并并覆盖目标文件
- `POST /api/v1/files/upload/abort`
  - 入参：`upload_id`
  - 行为：清理临时分片

## 5. 前端与 filebrowser

- 前端展示使用 `filebrowser/filebrowser` Docker 部署。
- filebrowser 与 API/MCP 使用同一存储目录，保证数据视图一致。
- `docker compose` 统一编排 filebrowser、api、mcp、postgres。

## 6. MCP 工具暴露

- 最小工具集：
  - `list_projects`
  - `list_files`
  - `upload_file`（小文件直传）
  - `upload_file_chunked`（大文件分片）
  - `download_file`
  - `delete_file`
- MCP 不直接操作磁盘，只调用后端 API。
- `download_file` 返回大小阈值 `2MB`（base64）；超限返回 `MCP_PAYLOAD_TOO_LARGE`。

## 7. 配置管理方案

- 服务配置以文件为主，环境变量覆盖。
- 推荐文件：`config/app.toml`。
- 最小配置项：
  - `projects`：项目根目录映射
  - `storage.max_file_size_mb`
  - `storage.chunk_size_mb`
  - `mcp.max_inline_download_mb`
  - `postgres.dsn`
  - `service.log_level`

## 8. 数据库方案（PostgreSQL）

- 数据库确定使用 PostgreSQL。
- 当前机器未安装 PostgreSQL，阶段 1 通过 Docker 容器提供 PG 服务，不要求宿主机安装。
- PG 用途（最小）：
  - 文件元数据索引（可选）
  - 分片上传会话与分片状态
  - 操作日志索引

## 9. API 列表与错误码细化

- 列表接口默认分页：`page=1&page_size=100`，`page_size` 上限 `500`。
- 默认排序：`updated_at desc`。
- 统一错误码新增：
  - `UPLOAD_SESSION_NOT_FOUND`
  - `UPLOAD_PART_MISSING`
  - `MCP_PAYLOAD_TOO_LARGE`

## 10. 运维与可靠性

- 日志字段：`request_id`、`project_id`、`action`、`path`、`result`、`cost_ms`。
- 日志保留建议：30 天。
- 备份策略：每日增量 + 每周全量（存储目录与 PG 同步备份）。
- 恢复目标：优先恢复项目目录，再恢复上传会话与索引数据。

## 11. 测试基线（E2E）

- 至少覆盖 10 个端到端场景：
  - 项目隔离
  - 路径穿越拦截
  - 同名覆盖
  - 分片上传成功/中断/恢复
  - 超限上传
  - MCP 大文件下载超限
  - 删除与列表一致性

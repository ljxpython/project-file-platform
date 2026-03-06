# API 与 MCP 规范（核心能力）

更新时间：2026-03-06

## 1. 业务 API（最小集合）

基础前缀：`/api/v1`

1. `GET /projects`
- 返回可用项目列表。

2. `GET /files?project_id={id}&path={path}`
- 列出目录内容。
- 支持可选关键字过滤：`keyword`。
- 分页参数：`page`、`page_size`（默认 `1`、`100`，上限 `500`）。
- 排序参数：`sort_by`（默认 `updated_at`）与 `order`（默认 `desc`）。

3. `POST /files/upload`
- 小文件直传。
- 入参：`project_id`、`path`、文件二进制。
- 同名文件处理：覆盖（overwrite）。
- 出参：文件元数据（name, size, updated_at）。

4. `GET /files/download?project_id={id}&path={path}`
- 下载文件流。

5. `DELETE /files?project_id={id}&path={path}`
- 删除文件（仅当前阶段简单删除）。

6. `POST /files/upload/init`
- 大文件分片初始化。
- 入参：`project_id`、`path`、`filename`、`total_size`、`chunk_size`。
- 出参：`upload_id`。

7. `PUT /files/upload/chunk`
- 上传分片。
- 入参：`upload_id`、`part_number`、chunk 二进制。

8. `POST /files/upload/complete`
- 合并分片并落盘（同名覆盖）。
- 入参：`upload_id`、`parts`。

9. `POST /files/upload/abort`
- 终止分片上传并清理临时分片。
- 入参：`upload_id`。

## 2. 返回结构建议

成功：
```json
{
  "ok": true,
  "data": {}
}
```

失败：
```json
{
  "ok": false,
  "error": {
    "code": "FILE_NOT_FOUND",
    "message": "file does not exist"
  }
}
```

## 3. MCP Tools（FastMCP）

建议最小工具集：

1. `list_projects()`
2. `list_files(project_id, path="/", keyword="", page=1, page_size=100, sort_by="updated_at", order="desc")`
3. `upload_file(project_id, path, content_base64)`（小文件直传，重名覆盖）
4. `upload_file_chunked(project_id, path, filename, chunks_base64[])`（大文件）
5. `download_file(project_id, path)`
6. `delete_file(project_id, path)`

约束：
- MCP 不直接操作磁盘，只调用业务 API。
- 所有工具必须传 `project_id`。
- `download_file` 内联返回上限 `2MB`，超限返回错误码 `MCP_PAYLOAD_TOO_LARGE`。

## 4. 错误码（最小）

- `INVALID_PROJECT`
- `INVALID_PATH`
- `FILE_NOT_FOUND`
- `FILE_TOO_LARGE`
- `UNSUPPORTED_FILE_TYPE`
- `UPLOAD_SESSION_NOT_FOUND`
- `UPLOAD_PART_MISSING`
- `MCP_PAYLOAD_TOO_LARGE`
- `INTERNAL_ERROR`

## 5. 鉴权策略（当前阶段）

- 权限先不设置，API 与 MCP 暂不启用鉴权校验。
- 仍保留 `project_id` 必填和路径边界校验，保证项目级隔离。

## 6. 配置与数据库约束

- 服务配置由 `config/app.toml` 管理，环境变量可覆盖。
- 数据库使用 PostgreSQL 保存分片上传会话与状态。
- 当前机器未安装 PostgreSQL，部署阶段通过 Docker 容器提供 PG 服务。

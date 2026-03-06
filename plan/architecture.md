# 架构设计（仅核心能力）

更新时间：2026-03-06

## 1. 目标范围

本架构只覆盖：
- 按项目管理文件
- 上传/下载
- 文件列表与名称搜索

## 2. 逻辑架构

```text
Web UI (filebrowser 或自研前端)
        |
        v
Backend API (Python/FastAPI)
        |
        +--> Local Storage / NAS
        |
        +--> PostgreSQL (upload 会话/元数据索引, Docker)
        |
        +--> MCP Server (FastMCP, 调用同一 API)
```

说明：
- 前端给人用。
- MCP 给 AI/Agent 用。
- 两者都走同一套后端 API，确保行为一致。
- 当前阶段权限先不设置（默认内网受控环境），后续再接入鉴权。
- 配置管理采用配置文件 + 环境变量覆盖。

## 3. 项目隔离模型（最小）

目录即项目：
- `/data/projects/project-a/`
- `/data/projects/project-b/`

约束：
- 每个 API 调用必须带 `project_id`。
- 服务端只允许访问对应项目根目录及其子目录。
- 禁止跨项目路径访问和 `../` 路径穿越。

## 4. 存储策略

阶段 1：
- 直接存本地磁盘或挂载 NAS。

阶段 2（可选）：
- 抽象 Storage 接口后切换到 MinIO。

## 5. 非功能最小要求

- 单文件大小限制（例如 500MB，可配置）。
- 大文件分片上传（默认 8MB 分片，可配置）。
- 上传超时与重试策略。
- 文件名与路径合法性校验。
- 基础健康检查接口：`/health`。

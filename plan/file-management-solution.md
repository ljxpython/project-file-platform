# 文件管理平台方案总览（核心能力版）

更新时间：2026-03-06

## 1. 目标

构建一个小企业内部可用的文件服务，只做最核心能力：
- 项目区分
- 文件上传
- 文件下载
- 文件列表与基础查询

## 2. 当前技术结论

- 前端文件管理：`filebrowser/filebrowser`（Docker 部署）
- MCP 框架：`PrefectHQ/fastmcp`
- Python 环境与包管理：`uv`
- Python 版本管理：固定 `3.13`（使用 `.python-version` 与 `uv` 保持一致）
- 服务配置管理：配置文件（`config/app.toml`）+ 环境变量覆盖
- 数据库：`PostgreSQL`（当前未安装，先用 Docker 部署）
- 存储：先用本地磁盘或 NAS（后续可替换 MinIO）

## 3. 明确不做（当前阶段）

- 复杂成员体系（如多级角色模型）
- 权限系统与鉴权接入（当前阶段先不设置）
- 审计平台化与复杂报表
- API 网关层
- 审批流、在线编辑、自动化工作流

## 4. 核心设计原则

- 先跑通最小闭环，再扩展能力。
- Web 与 MCP 共用同一套后端 API，避免两套逻辑。
- 项目隔离优先用目录边界实现，降低实现复杂度。
- 上传冲突按“同名覆盖”处理，减少人工冲突处理成本。

## 5. 文档导航

- 架构设计：`plan/architecture.md`
- API 与 MCP 定义：`plan/api-and-mcp-spec.md`
- 分阶段实施计划：`plan/implementation-plan.md`
- 最终决策清单：`plan/final-decisions.md`

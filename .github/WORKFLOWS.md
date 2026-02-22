# GitHub Actions Workflows

本项目使用 GitHub Actions 实现自动化 CI/CD 流程。

## 工作流说明

### 1. CI (持续集成)

**触发条件**：

- Push 到 `main` 分支
- Pull Request 到 `main` 分支

**功能**：

- 代码质量检查（ruff check）
- 代码格式检查（ruff format）
- 自动构建 Docker 镜像并推送到 GHCR

**状态徽章**：

```markdown
[![CI](https://github.com/CPU-JIA/grok2api/actions/workflows/ci.yml/badge.svg)](https://github.com/CPU-JIA/grok2api/actions/workflows/ci.yml)
```

### 2. Release (发布)

**触发条件**：

- 推送版本标签（如 `v1.0.0`）

**功能**：

- 构建多平台 Docker 镜像（amd64, arm64）
- 推送到 GHCR，打上版本标签和 `latest` 标签
- 创建 GitHub Release，自动生成 Release Notes

**使用方法**：

```bash
# 创建版本标签
git tag v1.0.0
git push origin v1.0.0

# GitHub Actions 会自动：
# 1. 构建 Docker 镜像
# 2. 推送到 ghcr.io/cpu-jia/grok2api:1.0.0
# 3. 推送到 ghcr.io/cpu-jia/grok2api:latest
# 4. 创建 GitHub Release
```

### 3. PR Check (PR 质量检查)

**触发条件**：

- Pull Request 打开、同步或重新打开

**功能**：

- 代码质量检查
- 检查大文件（>10MB）
- 检查敏感数据模式
- PR 大小检查（文件数、行数）
- 自动评论 PR 质量报告

### 4. Auto Format (自动格式化)

**触发条件**：

- Push 到 `main` 分支且修改了 `.py` 文件
- 手动触发（workflow_dispatch）

**功能**：

- 自动运行 `ruff format`
- 自动运行 `ruff check --fix`
- 自动提交格式化后的代码

**手动触发**：
在 GitHub Actions 页面点击 "Run workflow"

### 5. Dependency Check (依赖检查)

**触发条件**：

- 每周一 00:00 UTC 自动运行
- 手动触发（workflow_dispatch）

**功能**：

- 检查过期的依赖
- 检查安全漏洞（使用 pip-audit）
- 发现漏洞时自动创建 Issue

### 6. Docker Test (Docker 测试)

**触发条件**：

- PR 修改了 Dockerfile 或 docker-compose 文件
- 手动触发（workflow_dispatch）

**功能**：

- 测试 Docker 镜像构建
- 测试容器启动和健康检查
- 测试 docker-compose.yml 配置
- 测试 docker-compose.full.yml 配置（包括 Redis）

## 所需的 GitHub Secrets

### 自动配置的 Secrets

以下 secrets 由 GitHub 自动提供，无需手动配置：

- `GITHUB_TOKEN` - 用于推送 Docker 镜像到 GHCR 和创建 Release

### 可选的 Secrets

如果需要推送到其他 Docker Registry，可以添加：

- `DOCKERHUB_USERNAME` - Docker Hub 用户名
- `DOCKERHUB_TOKEN` - Docker Hub 访问令牌

## 启用 GitHub Container Registry (GHCR)

1. 确保仓库设置中启用了 "Packages"
2. 首次推送后，在 Packages 页面将镜像设为 Public（可选）
3. 镜像地址：`ghcr.io/cpu-jia/grok2api:latest`

## 本地测试工作流

使用 [act](https://github.com/nektos/act) 在本地测试 GitHub Actions：

```bash
# 安装 act
# macOS
brew install act

# Linux
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

# Windows
choco install act-cli

# 测试 CI 工作流
act push

# 测试 PR 工作流
act pull_request

# 测试特定工作流
act -W .github/workflows/ci.yml
```

## 工作流状态

在 README.md 中添加状态徽章：

```markdown
[![CI](https://github.com/CPU-JIA/grok2api/actions/workflows/ci.yml/badge.svg)](https://github.com/CPU-JIA/grok2api/actions/workflows/ci.yml)
[![Release](https://github.com/CPU-JIA/grok2api/actions/workflows/release.yml/badge.svg)](https://github.com/CPU-JIA/grok2api/actions/workflows/release.yml)
[![Docker Test](https://github.com/CPU-JIA/grok2api/actions/workflows/docker-test.yml/badge.svg)](https://github.com/CPU-JIA/grok2api/actions/workflows/docker-test.yml)
```

## 故障排查

### Docker 镜像推送失败

1. 检查 GITHUB_TOKEN 权限
2. 确保仓库设置中启用了 "Packages"
3. 检查 workflow 文件中的 `permissions` 配置

### 工作流运行缓慢

1. 使用 cache 加速依赖安装（已配置）
2. 使用 Docker layer cache（已配置）
3. 考虑使用 self-hosted runners

### 依赖检查失败

1. 检查 pip-audit 输出
2. 更新有漏洞的依赖
3. 如果是误报，可以在 workflow 中添加忽略规则

## 最佳实践

1. **保持工作流简洁**：每个工作流专注于一个任务
2. **使用缓存**：加速依赖安装和 Docker 构建
3. **并行执行**：独立的 job 可以并行运行
4. **失败快速**：在早期步骤发现问题，避免浪费时间
5. **定期维护**：定期更新 actions 版本和依赖

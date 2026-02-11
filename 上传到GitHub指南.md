# 上传到 GitHub 指南

## 方法 1: 使用命令行（推荐）

### 步骤 1: 初始化 Git 仓库

```bash
# 初始化 git 仓库
git init

# 添加所有文件
git add .

# 查看将要提交的文件
git status
```

### 步骤 2: 创建首次提交

```bash
# 配置 git 用户信息（如果还没配置）
git config user.name "你的名字"
git config user.email "你的邮箱"

# 创建首次提交
git commit -m "Initial commit: 小红书自动化工具"
```

### 步骤 3: 连接到 GitHub 仓库

```bash
# 在 GitHub 上创建新仓库后，连接远程仓库
git remote add origin https://github.com/你的用户名/仓库名.git

# 或者使用 SSH（如果已配置 SSH key）
git remote add origin git@github.com:你的用户名/仓库名.git

# 推送到 GitHub
git branch -M main
git push -u origin main
```

## 方法 2: 使用 GitHub Desktop

1. 打开 GitHub Desktop
2. 点击 "Add" → "Add Existing Repository"
3. 选择项目目录
4. 点击 "Create Repository"
5. 填写仓库信息
6. 点击 "Publish repository"

## 方法 3: 使用 VS Code

1. 打开项目文件夹
2. 点击左侧的 "Source Control" 图标
3. 点击 "Initialize Repository"
4. 输入提交信息
5. 点击 "Publish to GitHub"

## 完整命令（复制粘贴）

```bash
# 1. 初始化并提交
git init
git add .
git commit -m "Initial commit: 小红书自动化工具

功能特性：
- 高级搜索：DrissionPage 监听接口获取数据
- AI 分析：百炼大模型分析爆款逻辑
- 文生图：万相 2.6 生成小红书风格配图
- RPA 发布：模拟人工操作发布笔记
- 会话管理：自动保存所有数据

技术栈：
- Python 3.8+
- DrissionPage
- 阿里云百炼 API
- 万相 2.6 API"

# 2. 连接远程仓库（替换为你的仓库地址）
git remote add origin https://github.com/你的用户名/xhs-automation.git

# 3. 推送到 GitHub
git branch -M main
git push -u origin main
```

## 在 GitHub 上创建新仓库

1. 访问 https://github.com/new
2. 填写仓库信息：
   - **Repository name**: `xhs-automation`（或其他名称）
   - **Description**: `小红书自动化工具 - 基于 DrissionPage + 阿里云百炼大模型`
   - **Public/Private**: 选择公开或私有
   - **不要**勾选 "Initialize this repository with a README"（因为我们已经有了）
3. 点击 "Create repository"
4. 复制仓库地址，用于上面的 `git remote add origin` 命令

## 后续更新

```bash
# 查看修改
git status

# 添加修改的文件
git add .

# 提交修改
git commit -m "更新说明"

# 推送到 GitHub
git push
```

## 注意事项

### ✅ 会被上传的文件
- 源代码（.py 文件）
- 配置模板（config.yaml.example）
- 文档（.md 文件）
- 依赖列表（requirements.txt）
- 测试脚本

### ❌ 不会被上传的文件（已在 .gitignore 中）
- `.env` - 环境变量文件（包含 API Key）
- `config/config.yaml` - 配置文件（包含 API Key）
- `results/` - 生成的结果
- `images/` - 生成的图片
- `logs/` - 日志文件
- `__pycache__/` - Python 缓存
- `venv/` - 虚拟环境

### 🔒 安全检查

上传前请确认：

```bash
# 检查是否有敏感信息
git diff --cached

# 确认 .env 文件不在提交列表中
git status | grep .env

# 确认 config.yaml 不在提交列表中
git status | grep config.yaml
```

如果看到这些文件，说明它们会被上传，需要立即移除：

```bash
# 移除已添加的敏感文件
git reset HEAD .env
git reset HEAD config/config.yaml
```

## 推荐的仓库设置

### 1. 添加 Topics（标签）

在 GitHub 仓库页面，点击 "Add topics"，添加：
- `python`
- `automation`
- `xiaohongshu`
- `ai`
- `web-scraping`
- `rpa`

### 2. 添加 License

建议选择 MIT License

### 3. 添加 .github 目录

可以添加：
- Issue 模板
- Pull Request 模板
- GitHub Actions（CI/CD）

## 常见问题

### Q: 如何修改已提交的内容？

```bash
# 修改最后一次提交
git commit --amend

# 修改提交信息
git commit --amend -m "新的提交信息"
```

### Q: 如何删除远程仓库中的文件？

```bash
# 删除文件但保留本地
git rm --cached 文件名
git commit -m "删除文件"
git push
```

### Q: 不小心上传了敏感信息怎么办？

```bash
# 1. 立即修改 API Key（在阿里云控制台）
# 2. 从历史记录中删除（需要 git filter-branch 或 BFG Repo-Cleaner）
# 3. 强制推送

# 简单方法：删除仓库重新创建
```

### Q: 如何同步 fork 的仓库？

```bash
# 添加上游仓库
git remote add upstream https://github.com/原作者/仓库名.git

# 获取上游更新
git fetch upstream

# 合并更新
git merge upstream/main

# 推送到自己的仓库
git push
```

## 推荐的 README 徽章

在 README.md 顶部添加：

```markdown
![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-active-success.svg)
```

## 完成后

上传成功后，你的仓库地址将是：
```
https://github.com/你的用户名/xhs-automation
```

分享给其他人时，他们可以通过以下命令克隆：
```bash
git clone https://github.com/你的用户名/xhs-automation.git
```

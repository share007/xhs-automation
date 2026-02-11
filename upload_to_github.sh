#!/bin/bash
# 上传到 GitHub 的快速脚本

echo "========================================================================"
echo "📤 准备上传到 GitHub"
echo "========================================================================"
echo ""

# 检查是否已初始化 git
if [ ! -d .git ]; then
    echo "🔧 初始化 Git 仓库..."
    git init
    echo "✅ Git 仓库已初始化"
    echo ""
fi

# 检查敏感文件
echo "🔒 安全检查..."
if [ -f .env ]; then
    if grep -q "sk-" .env 2>/dev/null; then
        echo "⚠️  警告: .env 文件包含 API Key"
        echo "   请确认 .env 已在 .gitignore 中"
    fi
fi

if [ -f config/config.yaml ]; then
    if grep -q "sk-" config/config.yaml 2>/dev/null; then
        echo "⚠️  警告: config.yaml 包含 API Key"
        echo "   请确认 config/config.yaml 已在 .gitignore 中"
    fi
fi

# 检查 .gitignore
if [ -f .gitignore ]; then
    echo "✅ .gitignore 文件存在"
else
    echo "❌ .gitignore 文件不存在！"
    exit 1
fi

echo ""
echo "📋 将要提交的文件："
echo "----------------------------------------------------------------------"
git add -n .
echo ""

read -p "❓ 确认要添加这些文件吗？(y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ 已取消"
    exit 1
fi

# 添加文件
echo ""
echo "📦 添加文件..."
git add .

# 显示状态
echo ""
echo "📊 Git 状态："
echo "----------------------------------------------------------------------"
git status
echo ""

# 提交
read -p "📝 请输入提交信息（直接回车使用默认信息）: " commit_msg
if [ -z "$commit_msg" ]; then
    commit_msg="Initial commit: 小红书自动化工具

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
fi

echo ""
echo "💾 创建提交..."
git commit -m "$commit_msg"

# 检查是否已配置远程仓库
if git remote | grep -q origin; then
    echo ""
    echo "✅ 远程仓库已配置"
    remote_url=$(git remote get-url origin)
    echo "   URL: $remote_url"
    echo ""
    read -p "❓ 是否推送到远程仓库？(y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "📤 推送到 GitHub..."
        git branch -M main
        git push -u origin main
        echo ""
        echo "✅ 上传完成！"
    fi
else
    echo ""
    echo "⚠️  远程仓库未配置"
    echo ""
    echo "请按以下步骤操作："
    echo "1. 在 GitHub 上创建新仓库: https://github.com/new"
    echo "2. 复制仓库地址"
    echo "3. 运行以下命令："
    echo ""
    echo "   git remote add origin https://github.com/你的用户名/仓库名.git"
    echo "   git branch -M main"
    echo "   git push -u origin main"
    echo ""
fi

echo ""
echo "========================================================================"
echo "✅ 完成！"
echo "========================================================================"
echo ""
echo "💡 提示："
echo "   - 查看状态: git status"
echo "   - 查看日志: git log"
echo "   - 推送更新: git push"
echo ""

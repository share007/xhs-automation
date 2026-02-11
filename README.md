# 小红书自动化工具

基于 DrissionPage + 阿里云百炼大模型的小红书内容自动化工具，实现搜索→分析→生成→发布全流程。

## ✨ 功能特性

- **🔍 高级搜索**: DrissionPage 监听接口获取数据，支持排序、类型筛选
- **📊 数据质量**: 按点赞/评论/收藏多维度筛选高质量笔记
- **🤖 AI 分析**: 百炼大模型分析爆款逻辑，生成新话题
- **🎨 文生图**: 万相 2.6 模型生成小红书风格配图，支持多种视觉风格
- **📤 RPA 发布**: 模拟人工操作发布笔记，降低风控风险
- **💾 会话管理**: 自动保存所有数据，支持断点续传

## 🚀 快速开始

### 1. 安装依赖

```bash
# 克隆项目
git clone <repository-url>
cd xhs_automation

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置 API Key

**方式 1：使用 .env 文件（推荐）**

```bash
# 编辑 .env 文件
nano .env

# 设置你的 API Key
DASHSCOPE_API_KEY=sk-你的真实key
```

**方式 2：使用环境变量**

```bash
# Linux/Mac
export DASHSCOPE_API_KEY="sk-你的真实key"

# Windows PowerShell
$env:DASHSCOPE_API_KEY="sk-你的真实key"
```

**方式 3：使用配置文件**

```bash
# 编辑 config/config.yaml
nano config/config.yaml

# 填入你的 API Key
aliyun:
  api_key: "sk-你的真实key"
```

> 💡 获取 API Key: https://bailian.console.aliyun.com/

### 3. 测试配置

```bash
# 测试 API Key 是否配置正确
python test_config.py

# 运行诊断
python diagnose.py
```

### 4. 运行程序

```bash
# 快速测试（推荐新手）
python main.py -k "测试" -n 20 -t 3

# 完整流程
python main.py -k "春日穿搭" -n 50 -t 10

# 查看帮助
python main.py --help
```

## 📖 使用示例

### 基础使用

```bash
# 完整流程（搜索→分析→生成图片→发布）
python main.py --keyword "春日穿搭"

# 自定义爬取数量和话题数量
python main.py -k "春日穿搭" -n 100 -t 15
# -n 100: 爬取 100 条笔记
# -t 15: 生成 15 个话题

# 快速测试（少量数据）
python main.py -k "春日穿搭" -n 20 -t 3
```

### 模型选择

```bash
# 使用快速模型（推荐）
python main.py -k "春日穿搭" --ai-model qwen-turbo

# 使用默认模型（平衡）
python main.py -k "春日穿搭" --ai-model qwen-plus

# 使用最强模型（高质量）
python main.py -k "春日穿搭" --ai-model qwen-max
```

### 调试模式

```bash
# 查看详细输出
python main.py -k "春日穿搭" --verbose

# 查看数据结构
python main.py -k "春日穿搭" --debug

# 同时开启
python main.py -k "春日穿搭" -d -v
```

### 分步执行

```bash
# 1. 只搜索
python main.py -k "春日穿搭" --skip-ai --skip-image --skip-publish

# 2. 从已有数据继续分析
python main.py -k "春日穿搭" --skip-search --notes-file results/春日穿搭_xxx/data/notes.json

# 3. 只生成图片
python main.py -k "春日穿搭" --skip-search --skip-ai --topics-file results/春日穿搭_xxx/data/topics_with_images.json --skip-publish

# 4. 只发布
python main.py -k "春日穿搭" --skip-search --skip-ai --skip-image --topics-file results/春日穿搭_xxx/data/topics_with_images.json
```

### 高级用法

```bash
# 只要爆款内容（点赞数 >= 1000）
python main.py -k "春日穿搭" -n 100 -l 1000

# 保存输出到文件
python main.py -k "春日穿搭" --verbose 2>&1 | tee output.log

# 全自动发布（⚠️ 高风险）
python main.py -k "春日穿搭" --auto-publish
```

## 📂 项目结构

```
xhs_automation/
├── config/
│   ├── config.yaml              # 配置文件
│   └── config.yaml.example      # 配置模板
├── modules/
│   ├── __init__.py
│   ├── search.py                # 高级搜索模块
│   ├── ai_engine.py             # AI 分析引擎
│   ├── image_gen.py             # 文生图模块
│   └── publisher.py             # 发布模块
├── results/                     # 会话结果目录
│   └── {关键词}_{时间戳}/
│       ├── data/                # 数据文件
│       │   ├── notes.json       # 搜索结果
│       │   ├── ai_result.json   # AI 分析结果
│       │   └── topics_with_images.json  # 话题和图片
│       └── images/              # 生成的图片
│           └── {时间戳}_{话题}/
│               ├── 01_扁平插画_孟菲斯.png
│               ├── 02_3D渲染_C4D.png
│               └── ...
├── logs/                        # 日志目录
├── .env                         # 环境变量（需创建）
├── main.py                      # 主程序
├── test_config.py               # 配置测试
├── diagnose.py                  # 系统诊断
├── requirements.txt             # 依赖列表
└── README.md                    # 本文档
```

## ⚙️ 配置说明

### 命令行参数

| 参数 | 简写 | 说明 | 默认值 |
|------|------|------|--------|
| `--keyword` | `-k` | 搜索关键词（必需） | - |
| `--max-notes` | `-n` | 爬取笔记数量 | 50 |
| `--topics` | `-t` | AI 提取话题数量 | 10 |
| `--min-likes` | `-l` | 最小点赞数过滤 | 0 |
| `--ai-model` | - | AI 模型选择 | qwen-plus |
| `--debug` | `-d` | 调试模式 | 关闭 |
| `--verbose` | `-v` | 详细输出 | 关闭 |
| `--skip-search` | - | 跳过搜索 | 否 |
| `--skip-ai` | - | 跳过 AI 分析 | 否 |
| `--skip-image` | - | 跳过图片生成 | 否 |
| `--skip-publish` | - | 跳过发布 | 否 |

详细参数说明：查看 `命令行参数说明.md`

### 配置文件

编辑 `config/config.yaml`:

```yaml
aliyun:
  api_key: ""  # 留空，使用环境变量

search:
  default_sort: "time_descending"  # 排序方式
  max_notes: 50                    # 最大笔记数
  min_likes: 10                    # 最小点赞数

content:
  topic_count: 10          # 话题数量
  images_per_topic: 5      # 每个话题图片数
  image_size: "768*1152"   # 图片尺寸（2:3 竖屏）

publish:
  min_interval: 120        # 发布最小间隔（秒）
  max_interval: 180        # 发布最大间隔（秒）
  manual_confirm: true     # 人工确认发布
```

## 🔄 工作流程

```
┌─────────────┐
│  搜索笔记   │  DrissionPage 监听接口获取数据
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  质量筛选   │  按点赞/评论/收藏筛选高质量内容
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  AI 分析    │  分析爆款逻辑，提炼关键词
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  生成话题   │  基于分析结果生成新话题
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  生成配图   │  万相 2.6 为每个话题生成多张图片
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  发布笔记   │  RPA 模拟人工操作发布
└─────────────┘
```

## 🎨 图片生成特性

- **多种视觉风格**：扁平插画、3D 渲染、手绘水彩、复古胶片、极简主义、国潮风、赛博朋克
- **差异化生成**：每个话题自动使用不同的视觉风格
- **高质量输出**：支持多种尺寸，默认 768*1152（最适合小红书）
- **自动保存**：图片按话题分类保存，便于管理

## 🛠️ 故障排查

### 问题 1: API 请求超时

**解决方案**：
```bash
# 使用快速模型
python main.py -k "测试" --ai-model qwen-turbo
```

详见：`QUICK_FIX.md`

### 问题 2: 文件没有保存

**解决方案**：
```bash
# 运行诊断
python diagnose_save.py

# 测试文件保存
python test_file_save.py
```

详见：`文件保存问题排查.md`

### 问题 3: 图片没有下载

**解决方案**：
```bash
# 测试图片生成
python test_simple.py
```

详见：`图片下载问题排查.md`

### 运行完整诊断

```bash
# 运行所有测试
./run_all_tests.sh

# 或单独运行
python test_config.py      # 测试配置
python diagnose.py          # 系统诊断
python test_simple.py       # 测试图片生成
```

## 📚 文档

- `命令行参数说明.md` - 详细的参数说明
- `使用说明.md` - 完整使用指南
- `BUGFIX_LOG.md` - 修复日志
- `QUICK_FIX.md` - 快速修复指南
- `输出格式优化说明.md` - 输出格式说明
- `examples.sh` - 常用命令示例

## ⚠️ 注意事项

### 账号安全
- ✅ 建议先用小号测试
- ✅ 控制每日发布数量（建议 ≤ 10 篇）
- ✅ 使用人工确认模式（默认）
- ❌ 避免使用全自动发布模式

### 内容质量
- ✅ AI 生成内容建议人工审核
- ✅ 检查图片是否符合要求
- ✅ 确保内容符合平台规范
- ❌ 不要发布违规内容

### 网络环境
- ✅ 使用家庭宽带
- ✅ 保持稳定的网络连接
- ❌ 避免频繁更换 IP
- ❌ 避免使用代理

### 发布频率
- ✅ 控制发布间隔（默认 2-3 分钟）
- ✅ 模拟真实用户行为
- ❌ 不要短时间大量发布
- ❌ 不要在深夜发布

## 🔧 依赖库

- **DrissionPage** >= 4.0.0 - 浏览器自动化
- **dashscope** >= 1.14.0 - 阿里云百炼 SDK
- **requests** >= 2.31.0 - HTTP 请求
- **pyyaml** >= 6.0.1 - YAML 配置解析
- **python-dotenv** >= 1.0.0 - 环境变量加载

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## ⚖️ 免责声明

本工具仅供学习研究使用，请遵守小红书平台规则和相关法律法规。使用本工具产生的任何后果由使用者自行承担。

## 🆘 获取帮助

- 查看文档：`docs/` 目录
- 运行诊断：`python diagnose.py`
- 查看示例：`./examples.sh`
- 查看帮助：`python main.py --help`

## 📝 更新日志

### v1.1.0 (2026-02-12)

**新增功能**：
- ✨ 添加环境变量支持（.env 文件）
- ✨ 添加模型选择功能（qwen-turbo/plus/max）
- ✨ 添加详细输出模式（--verbose）
- ✨ 添加会话管理（自动保存所有数据）
- ✨ 优化输出格式（层级清晰）

**Bug 修复**：
- 🐛 修复 API 请求超时问题
- 🐛 修复文件保存验证问题
- 🐛 修复图片下载路径问题
- 🐛 修复输出缓冲问题

**改进**：
- 📈 输出量减少 80%
- 📈 可读性提升显著
- 📈 响应速度提升（使用快速模型）
- 📈 添加完整的测试工具

详见：`BUGFIX_LOG.md`
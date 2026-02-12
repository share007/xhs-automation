#!/usr/bin/env python3
"""
小红书自动化工具 - 主程序
整合搜索、AI分析、图片生成、发布全流程

使用方法:
    python main.py --keyword "春日穿搭" --max-notes 50 --topics 10
"""

import argparse
import json
import os
import sys
import time
import traceback
import yaml
from datetime import datetime
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

# 添加模块路径
sys.path.insert(0, str(Path(__file__).parent))

from modules.search import XHSAdvancedSearch, DataQualityFilter
from modules.ai_engine import AIEngine
from modules.image_gen import ImageGenerator
from modules.publisher import XHSPublisher
from utils.colors import (
    C,
    colorize,
    success,
    error,
    warning,
    info,
    highlight,
    dim,
    print_banner,
    print_step,
    print_config_item,
    print_summary,
    print_progress_bar,
    emoji_status,
)
from utils.config_validator import validate_config, config_to_dict


def safe_print(text: str, end: str = "\n", flush: bool = True) -> None:
    """安全打印函数，确保输出被正确显示"""
    print(text, end=end, flush=flush)


def _verbose_log(msg: str) -> None:
    """详细日志回调（供各步骤使用）"""
    safe_print(msg, flush=True)


def _save_json_file(data, file_path: Path, label: str = "数据") -> bool:
    """
    保存 JSON 数据到文件，并进行验证

    Args:
        data: 要保存的数据
        file_path: 文件路径
        label: 数据描述（用于日志）

    Returns:
        是否保存成功
    """
    print()
    print(f"{emoji_status('save')} 正在保存{label}...")
    print(f"   文件路径: {file_path}")

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        if file_path.exists():
            file_size = file_path.stat().st_size / 1024
            print(success(f"   ✅ 保存成功: {file_size:.1f} KB"))
            return True
        else:
            print(error(f"   ❌ 保存失败: 文件不存在"))
            return False
    except Exception as e:
        print(error(f"   ❌ 保存失败: {e}"))
        traceback.print_exc()
        return False


def print_header():
    """打印美化后的程序头部信息"""
    print_banner()
    print()
    print(colorize("🔧 基于 DrissionPage + 阿里云百炼大模型", C.DIM))
    print(colorize("📖 详细文档: https://github.com/your-repo/xhs-automation", C.DIM))
    print()


class XHSAutomation:
    """小红书自动化主控类"""

    def __init__(self, config_path: str = "config/config.yaml"):
        """
        初始化自动化工具

        Args:
            config_path: 配置文件路径
        """
        self.config = self._load_config(config_path)
        # 优先从环境变量读取 API Key，其次从配置文件读取
        self.api_key = (
            os.environ.get("DASHSCOPE_API_KEY")
            or os.environ.get("ALIYUN_API_KEY")
            or self.config.get("aliyun", {}).get("api_key", "")
        )

        if not self.api_key or self.api_key == "your-dashscope-api-key-here":
            error_msg = f"""
{error("❌ 配置错误：缺少阿里云百炼 API Key")}

{colorize("请通过以下方式之一配置 API Key:", C.YELLOW, C.BOLD)}

  {colorize("方法1：", C.CYAN)}设置环境变量
     {colorize("export DASHSCOPE_API_KEY=your-api-key", C.DIM)}
     {colorize("或", C.DIM)}
     {colorize("export ALIYUN_API_KEY=your-api-key", C.DIM)}

  {colorize("方法2：", C.CYAN)}编辑配置文件
     {colorize("config/config.yaml", C.DIM)} → 填写 aliyun.api_key

  {colorize("方法3：", C.CYAN)}创建 .env 文件
     {colorize("DASHSCOPE_API_KEY=your-api-key", C.DIM)}

{colorize("💡 获取 API Key:", C.BRIGHT_YELLOW)} https://bailian.console.aliyun.com/
{colorize("⚠️  安全提示:", C.BRIGHT_RED)} 请勿将真实 API Key 提交到代码仓库
"""
            raise ValueError(error_msg)

    def _load_config(self, path: str) -> dict:
        """加载并校验配置文件"""
        raw_config = {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw_config = yaml.safe_load(f) or {}
                print(success(f"✅ 配置文件加载成功: {path}"))
        except FileNotFoundError:
            print(warning(f"⚠️ 配置文件不存在: {path}"))
            print(info("   使用默认配置..."))
        except Exception as e:
            print(error(f"❌ 配置文件读取失败: {e}"))
            print(info("   使用默认配置..."))

        # Pydantic 配置校验
        try:
            validated = validate_config(raw_config)
            config = config_to_dict(validated)
            print(success("✅ 配置校验通过"))
            return config
        except Exception as e:
            print(warning(f"⚠️ 配置校验警告: {e}"))
            print(info("   使用默认配置补全缺失字段..."))
            return self._default_config()

    def _default_config(self) -> dict:
        """默认配置"""
        return {
            "aliyun": {"api_key": ""},
            "search": {
                "default_sort": "time_descending",
                "default_note_type": 51,
                "max_notes": 50,
                "min_likes": 0,
            },
            "content": {
                "topic_count": 10,
                "images_per_topic": 5,
                "image_size": "768*1152",
            },
            "publish": {
                "min_interval": 120,
                "max_interval": 180,
                "manual_confirm": True,
            },
        }

    def _create_session_dir(self, keyword: str, timestamp: str) -> Path:
        """
        创建会话目录（keyword + 时间戳）

        Args:
            keyword: 关键词
            timestamp: 时间戳

        Returns:
            会话目录路径
        """
        # 清理关键词，移除特殊字符
        safe_keyword = "".join(
            c for c in keyword if c.isalnum() or c in (" ", "_", "-")
        ).strip()
        safe_keyword = safe_keyword[:20] if len(safe_keyword) > 20 else safe_keyword

        # 创建目录：results/{keyword}_{timestamp}/
        session_dir = Path("results") / f"{safe_keyword}_{timestamp}"
        session_dir.mkdir(parents=True, exist_ok=True)

        # 创建子目录
        (session_dir / "images").mkdir(exist_ok=True)
        (session_dir / "data").mkdir(exist_ok=True)

        return session_dir

    def run(
        self,
        keyword: str,
        max_notes: int = 50,
        topic_count: int = 10,
        min_likes: int = 0,
        skip_search: bool = False,
        skip_ai: bool = False,
        skip_image: bool = False,
        skip_publish: bool = False,
        notes_file: str = "",
        topics_file: str = "",
        debug: bool = False,
        auto_publish: bool = False,
        verbose: bool = False,
        ai_model: str = "qwen3-max-2026-01-23",
        enable_thinking: Optional[bool] = None,
    ):
        """
        运行完整流程

        Args:
            keyword: 搜索关键词
            max_notes: 最大获取笔记数
            topic_count: 生成话题数量
            min_likes: 最小点赞数过滤（0表示不过滤）
            skip_search: 跳过搜索
            skip_ai: 跳过AI分析
            skip_image: 跳过图片生成
            skip_publish: 跳过发布
            notes_file: 从文件加载笔记
            topics_file: 从文件加载话题
            debug: 开启调试模式
            auto_publish: 自动发布（无人工确认，可能触发风控）
            verbose: 详细输出模式（显示完整的API输入输出）
            ai_model: AI模型选择（默认: qwen3-max-2026-01-23）
            enable_thinking: 是否启用思考模式（默认自动：复杂任务启用，简单任务禁用）
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 使用配置或参数
        max_notes = max_notes or self.config["search"].get("max_notes", 50)
        topic_count = topic_count or self.config["content"].get("topic_count", 10)
        min_likes = (
            min_likes if min_likes >= 0 else self.config["search"].get("min_likes", 0)
        )

        # 创建会话目录
        session_dir = self._create_session_dir(keyword, timestamp)
        data_dir = session_dir / "data"
        images_dir = session_dir / "images"

        # 验证目录是否创建成功
        if not session_dir.exists():
            print(f"❌ 无法创建会话目录: {session_dir}")
            return
        if not data_dir.exists():
            print(f"❌ 无法创建数据目录: {data_dir}")
            return
        if not images_dir.exists():
            print(f"❌ 无法创建图片目录: {images_dir}")
            return

        # 打印配置摘要
        print_header()
        print_config_item("📌 搜索关键词", highlight(keyword), emoji_status("target"))
        print_config_item("📊 爬取笔记数", f"{max_notes} 条", emoji_status("info"))
        print_config_item("✨ 生成话题数", f"{topic_count} 个", emoji_status("sparkle"))
        print_config_item(
            "👍 最小点赞数", f"{min_likes}（0=不过滤）", emoji_status("info")
        )
        print_config_item("🤖 AI 模型", ai_model, emoji_status("brain"))
        # 思考模式显示
        if enable_thinking is None:
            thinking_status = "自动（复杂任务启用）"
        elif enable_thinking:
            thinking_status = "强制开启"
        else:
            thinking_status = "强制关闭"
        print_config_item(
            "💭 思考模式",
            thinking_status,
            emoji_status("info"),
        )
        print_config_item(
            "🔧 调试模式", "开启" if debug else "关闭", emoji_status("info")
        )
        print_config_item(
            "📢 详细输出", "开启" if verbose else "关闭", emoji_status("info")
        )
        print_config_item(
            "🔘 发布模式",
            "全自动（高风险）" if auto_publish else "人工确认（推荐）",
            emoji_status("warning") if auto_publish else emoji_status("success"),
        )
        print_config_item("📁 工作目录", str(session_dir), emoji_status("info"))
        print()
        print(colorize("─" * 70, C.DIM))
        print()

        notes = []
        ai_result = {}
        topics = []

        # ========== Step 1: 高级搜索 ==========
        if not skip_search and notes_file == "":
            print_step(
                1,
                4,
                f"{emoji_status('search')} 搜索热门笔记",
                f"关键词: {highlight(keyword)} | 目标: {max_notes} 条笔记",
            )

            with XHSAdvancedSearch() as searcher:
                notes = searcher.search_with_filter(
                    keyword=keyword,
                    sort=self.config["search"].get("default_sort", "time_descending"),
                    note_type=self.config["search"].get("default_note_type", 51),
                    max_notes=max_notes,
                    min_likes=min_likes,
                    debug=debug,
                )

            # 精品笔记筛选（加权评分 + 内容多样性）
            if len(notes) > 20:
                print()
                print(info(f"🔍 精品笔记筛选（加权评分 + 多样性去重）..."))
                quality_filter = DataQualityFilter()
                notes = quality_filter.select_premium_notes(
                    notes,
                    n=min(50, len(notes)),
                    diversity_threshold=0.6,
                    log_callback=_verbose_log,
                )

            # 保存搜索结果到会话目录
            if notes:
                notes_path = data_dir / "notes.json"
                print(f"   笔记数量: {highlight(str(len(notes)))}")
                _save_json_file(notes, notes_path, "搜索结果")

        elif notes_file != "":
            print()
            print(info(f"📂 从文件加载笔记: {highlight(notes_file)}"))
            try:
                with open(notes_file, "r", encoding="utf-8") as f:
                    notes = json.load(f)
                print(success(f"✅ 已加载 {len(notes)} 条笔记"))
            except Exception as e:
                print(error(f"❌ 加载笔记失败: {e}"))
                return
        else:
            print(info("⏭️ 跳过搜索步骤"))

        # 只有在需要AI分析时才检查notes
        if not skip_ai and topics_file == "":
            if not notes:
                print(error("❌ 没有可用的笔记数据，退出"))
                return

        # ========== Step 2: AI 分析 ==========
        if not skip_ai and topics_file == "":
            print_step(
                2,
                4,
                f"{emoji_status('brain')} AI 热点分析",
                f"模型: {highlight(ai_model)} | 生成话题: {topic_count} 个",
            )

            ai = AIEngine(
                api_key=self.api_key, model=ai_model, enable_thinking=enable_thinking
            )

            # 验证 API Key
            if not ai.validate_api_key(log_callback=_verbose_log):
                print(error("❌ API Key 验证失败，请检查配置"))
                return
            print()

            if verbose:
                print()
                print(colorize("=" * 70, C.DIM))
                print(info("📋 详细输出模式已开启，将显示完整的API交互内容"))
                print(colorize("=" * 70, C.DIM))
                print()

            images_per_topic = self.config["content"].get("images_per_topic", 5)
            ai_result = ai.analyze_and_create_topics(
                notes=notes,
                keyword=keyword,
                top_n=topic_count,
                images_per_topic=images_per_topic,
                log_callback=_verbose_log,
            )
            topics = ai_result["topics"]

            # 保存分析结果到会话目录
            ai_path = data_dir / "ai_result.json"
            _save_json_file(ai_result, ai_path, "AI分析结果")

            # 打印分析摘要
            print()
            print(info("📊 分析摘要:"))
            analyze = ai_result["analyze_result"]
            keywords = analyze.get("top_keywords", [])[:5]
            emotions = analyze.get("emotion_points", [])[:3]
            if keywords:
                print(f"   关键词: {highlight(', '.join(keywords))}")
            if emotions:
                print(f"   情绪点: {highlight(', '.join(emotions))}")

        elif topics_file != "":
            print()
            print(info(f"📂 从文件加载话题: {highlight(topics_file)}"))
            try:
                with open(topics_file, "r", encoding="utf-8") as f:
                    if topics_file.endswith(".json"):
                        data = json.load(f)
                        if "topics" in data:
                            topics = data["topics"]
                        else:
                            topics = data
                    else:
                        topics = json.load(f)
                print(success(f"✅ 已加载 {len(topics)} 个话题"))
            except Exception as e:
                print(error(f"❌ 加载话题失败: {e}"))
                return
        else:
            print(info("⏭️ 跳过AI分析步骤"))

        if not topics:
            print(error("❌ 没有可用的话题数据，退出"))
            return

        # ========== Step 3: 文生图 ==========
        if not skip_image:
            print_step(
                3,
                4,
                f"{emoji_status('image')} 生成配图",
                f"每个话题: {self.config['content'].get('images_per_topic', 5)} 张 | 尺寸: {self.config['content'].get('image_size', '768*1152')}",
            )

            img_gen = ImageGenerator(
                api_key=self.api_key,
                save_dir=str(images_dir),  # 使用会话目录下的 images 文件夹
            )

            topics = img_gen.generate_for_topics(
                topics=topics,
                n_per_topic=self.config["content"].get("images_per_topic", 5),
                size=self.config["content"].get("image_size", "768*1152"),
                log_callback=_verbose_log,
            )

            # 保存带图片路径的话题到会话目录
            topics_img_path = data_dir / "topics_with_images.json"
            print(f"   话题数量: {highlight(str(len(topics)))}")
            _save_json_file(topics, topics_img_path, "话题数据")

        else:
            print(info("⏭️ 跳过图片生成步骤"))

        # 初始化 results 变量
        results = []

        # ========== Step 4: 发布 ==========
        if not skip_publish:
            print_step(
                4,
                4,
                f"{emoji_status('publish')} 发布笔记",
                f"模式: {'人工确认' if not auto_publish else '全自动'} | 间隔: {self.config['publish'].get('min_interval', 120)}-{self.config['publish'].get('max_interval', 180)}s",
            )

            # 检查是否有图片
            valid_topics = [t for t in topics if t.get("image_paths")]
            if not valid_topics:
                print(warning("⚠️ 没有带图片的话题，跳过发布"))
                return

            print(info(f"📋 准备发布 {len(valid_topics)} 篇笔记\n"))

            with XHSPublisher() as publisher:
                results = publisher.publish_batch(
                    topics=valid_topics,
                    min_interval=self.config["publish"].get("min_interval", 120),
                    max_interval=self.config["publish"].get("max_interval", 180),
                    manual_confirm=not auto_publish,
                )

            # 保存发布结果到会话目录
            publish_result = {
                "timestamp": timestamp,
                "keyword": keyword,
                "total": len(valid_topics),
                "success": sum(results),
                "failed": len(results) - sum(results),
                "topics": [
                    {**t, "published": r} for t, r in zip(valid_topics, results)
                ],
            }
            publish_path = data_dir / "publish_result.json"
            _save_json_file(publish_result, publish_path, "发布结果")

        else:
            print(info("⏭️ 跳过发布步骤"))

        # 打印执行摘要
        results_count = {"success": 0, "failed": 0}
        if results:
            results_count["success"] = sum(results)
            results_count["failed"] = len(results) - sum(results)

        summary_data = {
            "关键词": keyword,
            "工作目录": str(session_dir),
            "爬取笔记": len(notes) if notes else 0,
            "生成话题": len(topics) if topics else 0,
            "发布成功": results_count["success"],
            "发布失败": results_count["failed"],
        }
        print_summary(summary_data, "执行完成")
        print(
            success(f"🎉 流程执行完毕！所有文件保存在: {highlight(str(session_dir))}")
        )
        print()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="小红书自动化工具 - 搜索→分析→生成→发布",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 完整流程（默认使用 qwen3-max，自动启用思考模式）
  python main.py --keyword "春日穿搭"

  # 使用快速模型（适合快速测试）
  python main.py --keyword "春日穿搭" --ai-model qwen-turbo

  # 自定义爬取数量和话题数量
  python main.py --keyword "春日穿搭" --max-notes 100 --topics 15
  python main.py --keyword "春日穿搭" -n 100 -t 15  # 简写形式

  # 快速测试（少量数据）
  python main.py --keyword "春日穿搭" -n 20 -t 3

  # 强制启用思考模式（所有任务都启用）
  python main.py --keyword "春日穿搭" --enable-thinking

  # 强制禁用思考模式（所有任务都不启用）
  python main.py --keyword "春日穿搭" --disable-thinking

  # 全自动发布（⚠️ 高风险，可能触发风控）
  python main.py --keyword "春日穿搭" --auto-publish

  # 调试模式（查看数据结构）
  python main.py --keyword "春日穿搭" --debug

  # 详细输出模式（查看完整API交互）
  python main.py --keyword "春日穿搭" --verbose

  # 不限制点赞数（获取更多笔记）
  python main.py --keyword "春日穿搭" --min-likes 0

  # 仅搜索
  python main.py --keyword "美妆" --skip-ai --skip-image --skip-publish

  # 从已有内容直接发布
  python main.py --keyword "马年春节" --skip-search --skip-ai --topics-file results/马年春节_xxx/data/topics_with_images.json

  # 查看帮助
  python main.py --help

思考模式说明:
  • 默认自动模式：复杂任务（热点分析、话题生成）启用思考模式
  • 简单任务（提示词优化）不启用思考模式以提高速度
  • 使用 --enable-thinking 强制所有任务启用思考模式
  • 使用 --disable-thinking 强制所有任务禁用思考模式
        """,
    )

    parser.add_argument("--keyword", "-k", required=True, help="搜索关键词")
    parser.add_argument(
        "--max-notes",
        "-n",
        type=int,
        default=50,
        help="爬取笔记数量 (默认: 50，建议 20-100)",
    )
    parser.add_argument(
        "--topics",
        "-t",
        type=int,
        default=10,
        help="AI 智能提取的话题数量 (默认: 10，建议 5-20)",
    )
    parser.add_argument(
        "--min-likes",
        "-l",
        type=int,
        default=0,
        help="最小点赞数过滤，0表示不过滤 (默认: 0)",
    )
    parser.add_argument(
        "--config", "-c", default="config/config.yaml", help="配置文件路径"
    )
    parser.add_argument(
        "--debug", "-d", action="store_true", help="开启调试模式，输出详细数据结构"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="详细输出模式，显示完整的API输入输出内容",
    )

    parser.add_argument(
        "--ai-model",
        default="qwen3-max-2026-01-23",
        choices=["qwen-plus", "qwen-max", "qwen-turbo", "qwen3-max-2026-01-23"],
        help="AI模型选择 (默认: qwen3-max-2026-01-23，最强性能)",
    )
    parser.add_argument(
        "--enable-thinking",
        action="store_true",
        default=None,
        help="强制启用思考模式（仅支持qwen3系列，会显著增加响应时间）",
    )
    parser.add_argument(
        "--disable-thinking",
        action="store_true",
        help="强制禁用思考模式（所有任务都不使用思考模式）",
    )

    parser.add_argument("--skip-search", action="store_true", help="跳过搜索步骤")
    parser.add_argument("--skip-ai", action="store_true", help="跳过AI分析步骤")
    parser.add_argument("--skip-image", action="store_true", help="跳过图片生成步骤")
    parser.add_argument("--skip-publish", action="store_true", help="跳过发布步骤")

    parser.add_argument("--notes-file", help="从JSON文件加载笔记数据")
    parser.add_argument("--topics-file", help="从JSON文件加载话题数据")
    parser.add_argument(
        "--auto-publish",
        action="store_true",
        help="自动发布（无人工确认，⚠️高风险：可能触发平台风控）",
    )

    args = parser.parse_args()

    # 处理思考模式参数
    # None = 自动模式（复杂任务启用，简单任务禁用）
    # True = 强制启用
    # False = 强制禁用
    if args.disable_thinking:
        enable_thinking = False
    elif args.enable_thinking:
        enable_thinking = True
    else:
        enable_thinking = None  # 自动模式

    try:
        app = XHSAutomation(config_path=args.config)
        app.run(
            keyword=args.keyword,
            max_notes=args.max_notes,
            topic_count=args.topics,
            min_likes=args.min_likes,
            skip_search=args.skip_search,
            skip_ai=args.skip_ai,
            skip_image=args.skip_image,
            skip_publish=args.skip_publish,
            notes_file=args.notes_file or "",
            topics_file=args.topics_file or "",
            debug=args.debug,
            auto_publish=args.auto_publish,
            verbose=args.verbose,
            ai_model=args.ai_model,
            enable_thinking=enable_thinking,
        )
    except KeyboardInterrupt:
        print()
        print()
        print(warning("⚠️ 用户中断执行"))
        print(info("   您可以随时重新运行程序继续"))
        sys.exit(1)
    except ValueError as e:
        # 配置错误（如缺少API Key）
        print()
        print()
        print(str(e))
        sys.exit(1)
    except Exception as e:
        print()
        print()
        print(error("❌ 执行出错"))
        print()
        print(colorize(f"错误类型: {type(e).__name__}", C.BRIGHT_RED))
        print(colorize(f"错误信息: {str(e)}", C.RED))
        print()

        if args.debug if "args" in locals() else False:
            print(colorize("─" * 70, C.DIM))
            print(colorize("详细堆栈跟踪（调试模式）:", C.DIM))
            traceback.print_exc()
            print(colorize("─" * 70, C.DIM))
        else:
            print(dim("💡 提示: 使用 --debug 参数查看详细错误信息"))

        sys.exit(1)


if __name__ == "__main__":
    main()

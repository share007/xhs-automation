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
import yaml
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

# 添加模块路径
sys.path.insert(0, str(Path(__file__).parent))

from modules.search import XHSAdvancedSearch, DataQualityFilter
from modules.ai_engine import AIEngine
from modules.image_gen import ImageGenerator
from modules.publisher import XHSPublisher


def safe_print(text: str, end: str = "\n", flush: bool = True):
    """安全打印函数，确保输出被正确显示"""
    print(text, end=end, flush=flush)


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
        self.api_key = os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("ALIYUN_API_KEY") or self.config.get("aliyun", {}).get("api_key", "")

        if not self.api_key or self.api_key == "your-dashscope-api-key-here":
            raise ValueError(
                "请先配置阿里云百炼 API Key！\n"
                "方法1: 设置环境变量 DASHSCOPE_API_KEY 或 ALIYUN_API_KEY\n"
                "方法2: 在 config/config.yaml 中填写 api_key\n"
                "提示: 请勿将真实 API Key 提交到代码仓库"
            )

    def _load_config(self, path: str) -> dict:
        """加载配置文件"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print(f"⚠️ 配置文件不存在: {path}")
            print("使用默认配置...")
            return self._default_config()
        except Exception as e:
            print(f"⚠️ 配置文件读取失败: {e}")
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
        ai_model: str = "qwen-plus",
        enable_thinking: bool = False,
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
            ai_model: AI模型选择（qwen-plus/qwen-max/qwen-turbo）
            enable_thinking: 是否启用思考模式（会显著增加响应时间）
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

        print("\n" + "=" * 70)
        print("🚀 小红书自动化工具启动")
        print("=" * 70)
        print(f"📌 关键词: {keyword}")
        print(f"📊 爬取笔记数: {max_notes} 条")
        print(f"✨ AI 提取话题数: {topic_count} 个")
        print(f"👍 最小点赞数: {min_likes}")
        print(f"🔧 调试模式: {'开启' if debug else '关闭'}")
        print(f"📢 详细输出: {'开启' if verbose else '关闭'}")
        print(f"🤖 AI模型: {ai_model}")
        print(f"💭 思考模式: {'开启（响应较慢）' if enable_thinking else '关闭（推荐）'}")
        print(
            f"🔘 发布模式: {'全自动（高风险）' if auto_publish else '人工确认（推荐）'}"
        )
        print(f"📁 工作目录: {session_dir}")
        print(f"⏰ 时间戳: {timestamp}")
        print("=" * 70 + "\n")

        notes = []
        ai_result = {}
        topics = []

        # ========== Step 1: 高级搜索 ==========
        if not skip_search and notes_file == "":
            safe_print("\n" + "#"*70)
            safe_print("📥 STEP 1: 搜索笔记")
            safe_print("#"*70 + "\n", flush=True)

            with XHSAdvancedSearch() as searcher:
                notes = searcher.search_with_filter(
                    keyword=keyword,
                    sort=self.config["search"].get("default_sort", "time_descending"),
                    note_type=self.config["search"].get("default_note_type", 51),
                    max_notes=max_notes,
                    min_likes=min_likes,
                    debug=debug,
                )

            # 数据质量二次筛选（仅在有足够数据时）
            if len(notes) > 20:
                print("\n🔍 数据质量筛选...")
                quality_filter = DataQualityFilter()
                notes = quality_filter.get_top_notes(notes, n=min(50, len(notes)))

            # 保存搜索结果到会话目录
            if notes:
                notes_path = data_dir / "notes.json"
                print(f"\n💾 正在保存搜索结果...")
                print(f"   文件路径: {notes_path}")
                print(f"   笔记数量: {len(notes)}")
                
                try:
                    with open(notes_path, "w", encoding="utf-8") as f:
                        json.dump(notes, f, ensure_ascii=False, indent=2)
                    
                    # 验证文件是否真的保存了
                    if notes_path.exists():
                        file_size = notes_path.stat().st_size / 1024
                        print(f"   ✅ 保存成功: {file_size:.1f} KB")
                    else:
                        print(f"   ❌ 保存失败: 文件不存在")
                except Exception as e:
                    print(f"   ❌ 保存失败: {e}")
                    import traceback
                    traceback.print_exc()

        elif notes_file != "":
            print(f"\n📂 从文件加载笔记: {notes_file}")
            with open(notes_file, "r", encoding="utf-8") as f:
                notes = json.load(f)
            print(f"✅ 已加载 {len(notes)} 条笔记")
        else:
            print("⏭️ 跳过搜索步骤")

        # 只有在需要AI分析时才检查notes
        if not skip_ai and topics_file == "":
            if not notes:
                print("❌ 没有可用的笔记数据，退出")
                return

        # ========== Step 2: AI 分析 ==========
        if not skip_ai and topics_file == "":
            safe_print("\n" + "#"*70)
            safe_print("🤖 STEP 2: AI 热点分析")
            safe_print("#"*70 + "\n", flush=True)

            ai = AIEngine(api_key=self.api_key, model=ai_model, enable_thinking=enable_thinking)
            
            # 创建自定义日志回调，支持详细输出
            def verbose_log(msg):
                safe_print(msg, flush=True)
            
            if verbose:
                safe_print("=" * 70)
                safe_print("📋 详细输出模式已开启，将显示完整的API交互内容")
                safe_print("=" * 70 + "\n")
            
            ai_result = ai.analyze_and_create_topics(
                notes=notes, 
                keyword=keyword, 
                top_n=topic_count,
                log_callback=verbose_log
            )
            topics = ai_result["topics"]

            # 保存分析结果到会话目录
            ai_path = data_dir / "ai_result.json"
            print(f"\n💾 正在保存AI分析结果...")
            print(f"   文件路径: {ai_path}")
            
            try:
                with open(ai_path, "w", encoding="utf-8") as f:
                    json.dump(ai_result, f, ensure_ascii=False, indent=2)
                
                # 验证文件是否真的保存了
                if ai_path.exists():
                    file_size = ai_path.stat().st_size / 1024
                    print(f"   ✅ 保存成功: {file_size:.1f} KB")
                else:
                    print(f"   ❌ 保存失败: 文件不存在")
            except Exception as e:
                print(f"   ❌ 保存失败: {e}")
                import traceback
                traceback.print_exc()

            # 打印分析摘要
            print("\n📊 分析摘要:")
            analyze = ai_result["analyze_result"]
            keywords = analyze.get('top_keywords', [])[:5]
            emotions = analyze.get('emotion_points', [])[:3]
            if keywords:
                print(f"   关键词: {', '.join(keywords)}")
            if emotions:
                print(f"   情绪点: {', '.join(emotions)}")

        elif topics_file != "":
            print(f"\n📂 从文件加载话题: {topics_file}")
            with open(topics_file, "r", encoding="utf-8") as f:
                if topics_file.endswith(".json"):
                    data = json.load(f)
                    if "topics" in data:
                        topics = data["topics"]
                    else:
                        topics = data
                else:
                    topics = json.load(f)
            print(f"✅ 已加载 {len(topics)} 个话题")
        else:
            print("⏭️ 跳过AI分析步骤")

        if not topics:
            print("❌ 没有可用的话题数据，退出")
            return

        # ========== Step 3: 文生图 ==========
        if not skip_image:
            safe_print("\n" + "#"*70)
            safe_print("🖼️ STEP 3: 生成配图")
            safe_print("#"*70 + "\n", flush=True)

            img_gen = ImageGenerator(
                api_key=self.api_key,
                save_dir=str(images_dir),  # 使用会话目录下的 images 文件夹
            )
            
            # 创建自定义日志回调
            def verbose_log(msg):
                safe_print(msg, flush=True)

            topics = img_gen.generate_for_topics(
                topics=topics,
                n_per_topic=self.config["content"].get("images_per_topic", 5),
                size=self.config["content"].get("image_size", "768*1152"),
                log_callback=verbose_log
            )

            # 保存带图片路径的话题到会话目录
            topics_img_path = data_dir / "topics_with_images.json"
            print(f"\n💾 正在保存话题数据...")
            print(f"   文件路径: {topics_img_path}")
            print(f"   话题数量: {len(topics)}")
            
            try:
                with open(topics_img_path, "w", encoding="utf-8") as f:
                    json.dump(topics, f, ensure_ascii=False, indent=2)
                
                # 验证文件是否真的保存了
                if topics_img_path.exists():
                    file_size = topics_img_path.stat().st_size / 1024
                    print(f"   ✅ 保存成功: {file_size:.1f} KB")
                else:
                    print(f"   ❌ 保存失败: 文件不存在")
            except Exception as e:
                print(f"   ❌ 保存失败: {e}")
                import traceback
                traceback.print_exc()

        else:
            print("⏭️ 跳过图片生成步骤")

        # ========== Step 4: 发布 ==========
        if not skip_publish:
            safe_print("\n" + "#"*70)
            safe_print("📤 STEP 4: 发布笔记")
            safe_print("#"*70 + "\n", flush=True)

            # 检查是否有图片
            valid_topics = [t for t in topics if t.get("image_paths")]
            if not valid_topics:
                print("⚠️ 没有带图片的话题，跳过发布")
                return

            print(f"📋 准备发布 {len(valid_topics)} 篇笔记\n")

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
            print(f"\n💾 正在保存发布结果...")
            print(f"   文件路径: {publish_path}")
            
            try:
                with open(publish_path, "w", encoding="utf-8") as f:
                    json.dump(publish_result, f, ensure_ascii=False, indent=2)
                
                # 验证文件是否真的保存了
                if publish_path.exists():
                    file_size = publish_path.stat().st_size / 1024
                    print(f"   ✅ 保存成功: {file_size:.1f} KB")
                else:
                    print(f"   ❌ 保存失败: 文件不存在")
            except Exception as e:
                print(f"   ❌ 保存失败: {e}")
                import traceback
                traceback.print_exc()
            
            print(f"\n💾 发布结果已保存: {publish_path}")

        else:
            print("⏭️ 跳过发布步骤")

        print("\n" + "=" * 70)
        print(f"✅ 流程执行完毕！所有文件保存在: {session_dir}")
        print("=" * 70 + "\n")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="小红书自动化工具 - 搜索→分析→生成→发布",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 完整流程（推荐，人工确认发布）
  python main.py --keyword "春日穿搭"

  # 自定义爬取数量和话题数量
  python main.py --keyword "春日穿搭" --max-notes 100 --topics 15
  python main.py --keyword "春日穿搭" -n 100 -t 15  # 简写形式

  # 快速测试（少量数据）
  python main.py --keyword "春日穿搭" -n 20 -t 3

  # 使用快速模型（推荐，响应更快）
  python main.py --keyword "春日穿搭" --ai-model qwen-turbo

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
        """,
    )

    parser.add_argument("--keyword", "-k", required=True, help="搜索关键词")
    parser.add_argument(
        "--max-notes", 
        "-n", 
        type=int, 
        default=50,
        help="爬取笔记数量 (默认: 50，建议 20-100)"
    )
    parser.add_argument(
        "--topics", 
        "-t", 
        type=int, 
        default=10,
        help="AI 智能提取的话题数量 (默认: 10，建议 5-20)"
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
        "--verbose", "-v", action="store_true", help="详细输出模式，显示完整的API输入输出内容"
    )
    
    parser.add_argument(
        "--ai-model", 
        default="qwen-plus", 
        choices=["qwen-plus", "qwen-max", "qwen-turbo", "qwen3-max-2026-01-23"],
        help="AI模型选择 (默认: qwen-plus，推荐使用qwen-plus或qwen-turbo以获得更快响应)"
    )
    parser.add_argument(
        "--enable-thinking",
        action="store_true",
        help="启用思考模式（仅支持qwen3系列，会显著增加响应时间，不推荐）"
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

    try:
        app = XHSAutomation(config_path=args.config)
        app.run(
            keyword=args.keyword,
            max_notes=args.max_notes or 50,
            topic_count=args.topics or 10,
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
            enable_thinking=args.enable_thinking,
        )
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断执行")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ 执行出错: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

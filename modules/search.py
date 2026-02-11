"""
小红书高级搜索模块
使用 DrissionPage 监听搜索接口获取数据
"""

from DrissionPage import ChromiumPage
from urllib.parse import quote
import time
import json
import os
from typing import List, Dict, Callable, Optional
from datetime import datetime
from pathlib import Path


class XHSAdvancedSearch:
    """小红书高级搜索类"""

    def __init__(self, headless: bool = False):
        """
        初始化搜索器

        Args:
            headless: 是否无头模式
        """
        self.page = ChromiumPage()
        self.headless = headless

    def search_with_filter(
        self,
        keyword: str,
        sort: str = "time_descending",
        note_type: int = 51,
        source: str = "web_explore_feed",
        max_notes: int = 50,
        min_likes: int = 0,
        log_callback: Optional[Callable] = None,
        debug: bool = False,
    ) -> List[Dict]:
        """
        高级搜索：带排序 + 类型筛选 + 数据质量过滤

        Args:
            keyword: 搜索关键词
            sort: 排序方式 (time_descending/hot/comprehensive)
            note_type: 笔记类型 (51=图文)
            source: 来源标识
            max_notes: 最大获取笔记数
            min_likes: 最小点赞数过滤
            log_callback: 日志回调函数
            debug: 是否开启调试模式

        Returns:
            筛选后的笔记列表
        """
        if log_callback is None:
            log_callback = print

        # 1. 构造搜索 URL
        encoded_kw = quote(keyword)
        url = (
            f"https://www.xiaohongshu.com/search_result"
            f"?keyword={encoded_kw}&source={source}&type={note_type}"
        )

        log_callback(f"🔍 高级搜索 URL: {url}")
        log_callback(f"📊 排序方式: {sort}, 笔记类型: {note_type}")

        # 2. 启动数据包监听
        self.page.listen.start("web/v1/search/notes")

        # 3. 打开搜索结果页
        self.page.get(url)
        time.sleep(3)

        notes = []
        filtered_count = {
            "low_likes": 0,
            "no_content": 0,
            "duplicate": 0,
            "wrong_type": 0,
            "parse_error": 0,
        }
        seen_ids = set()
        page_no = 1
        max_scroll_attempts = 50
        scroll_attempts = 0

        # 调试：保存完整响应
        debug_responses = []
        logs_dir = Path("logs/debug")
        logs_dir.mkdir(parents=True, exist_ok=True)

        # 4. 滚动加载，直到拿到足够多的笔记
        while len(notes) < max_notes and scroll_attempts < max_scroll_attempts:
            try:
                # 监听结果会自动存入队列
                res = self.page.listen.wait(timeout=5)

                if not res:
                    # 没有新数据，尝试滚动
                    self.page.scroll.down(800)
                    time.sleep(2)
                    scroll_attempts += 1
                    continue

                # 处理可能的列表情况
                if isinstance(res, list):
                    if len(res) == 0:
                        scroll_attempts += 1
                        continue
                    res = res[0]

                # 解析 JSON
                body = res.response.body

                # 调试：保存完整响应
                if debug and len(debug_responses) < 3:
                    debug_responses.append(body)
                    # 保存到文件
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    debug_file = (
                        logs_dir
                        / f"debug_response_{timestamp}_{len(debug_responses)}.json"
                    )
                    with open(debug_file, "w", encoding="utf-8") as f:
                        json.dump(body, f, ensure_ascii=False, indent=2)
                    log_callback(f"💾 调试数据已保存: {debug_file}")

                # 调试：输出数据结构
                if debug and len(debug_responses) <= 1:
                    log_callback("\n📋 调试：响应数据结构")
                    log_callback(f"Body type: {type(body)}")
                    if isinstance(body, dict):
                        log_callback(f"Body keys: {list(body.keys())}")
                        if "data" in body:
                            data = body["data"]
                            log_callback(f"Data type: {type(data)}")
                            if isinstance(data, dict):
                                log_callback(f"Data keys: {list(data.keys())}")
                                if "items" in data:
                                    items_data = data["items"]
                                    log_callback(
                                        f"Items type: {type(items_data)}, count: {len(items_data) if isinstance(items_data, list) else 'N/A'}"
                                    )
                                    if (
                                        isinstance(items_data, list)
                                        and len(items_data) > 0
                                    ):
                                        first_item = items_data[0]
                                        log_callback(
                                            f"First item type: {type(first_item)}"
                                        )
                                        if isinstance(first_item, dict):
                                            log_callback(
                                                f"First item keys: {list(first_item.keys())}"
                                            )
                                            # 输出完整的第一条数据
                                            log_callback("\n📄 第一条数据完整内容:")
                                            log_callback(
                                                json.dumps(
                                                    first_item,
                                                    ensure_ascii=False,
                                                    indent=2,
                                                )[:1000]
                                                + "..."
                                            )

                # 获取 items
                if not isinstance(body, dict):
                    scroll_attempts += 1
                    continue

                data = body.get("data", {})
                if not isinstance(data, dict):
                    scroll_attempts += 1
                    continue

                items = data.get("items", [])
                if not isinstance(items, list):
                    scroll_attempts += 1
                    continue

                if not items:
                    scroll_attempts += 1
                    self.page.scroll.down(800)
                    time.sleep(2)
                    continue

                for item in items:
                    if len(notes) >= max_notes:
                        break

                    if not isinstance(item, dict):
                        filtered_count["parse_error"] += 1
                        continue

                    # 提取字段 - 处理多种可能的数据结构
                    note_id = (
                        item.get("id") or item.get("noteId") or item.get("note_id")
                    )

                    # 获取 noteCard，可能在不同层级（API返回的是 note_card 下划线格式）
                    note_card = item.get("note_card", {}) or item.get("noteCard", {})
                    if not note_card and isinstance(item, dict):
                        # 可能 item 本身就是 noteCard 或者包含其他字段
                        if any(
                            k in item
                            for k in [
                                "title",
                                "display_title",
                                "displayTitle",
                                "desc",
                                "content",
                                "interact_info",
                                "interactInfo",
                            ]
                        ):
                            note_card = item

                    if not isinstance(note_card, dict):
                        note_card = {}

                    # 去重检查
                    if not note_id:
                        # 尝试从其他字段获取ID
                        note_id = note_card.get("noteId") or note_card.get("id")
                        if not note_id:
                            filtered_count["parse_error"] += 1
                            if debug:
                                log_callback(
                                    f"  ⚠️ 无法获取笔记ID，item keys: {list(item.keys())}"
                                )
                            continue

                    if note_id in seen_ids:
                        filtered_count["duplicate"] += 1
                        continue
                    seen_ids.add(note_id)

                    # 提取标题 - 尝试多个可能的字段名（支持下划线格式）
                    title = (
                        note_card.get("display_title")
                        or note_card.get("displayTitle")
                        or note_card.get("title")
                        or item.get("display_title")
                        or item.get("displayTitle")
                        or item.get("title")
                        or note_card.get("name")
                        or item.get("name")
                        or ""
                    )

                    # 提取描述 - 尝试多个可能的字段名
                    desc = (
                        note_card.get("desc")
                        or note_card.get("content")
                        or note_card.get("description")
                        or item.get("desc")
                        or item.get("content")
                        or item.get("description")
                        or ""
                    )

                    # 调试：显示被过滤的笔记信息
                    if debug and not title and not desc:
                        log_callback(f"\n⚠️ 无内容笔记:")
                        log_callback(f"  ID: {note_id}")
                        log_callback(f"  Item keys: {list(item.keys())}")
                        log_callback(
                            f"  NoteCard keys: {list(note_card.keys()) if note_card else 'None'}"
                        )

                    # 内容完整性检查 - 放宽条件，只要有ID就算有效
                    if not title and not desc:
                        # 尝试获取任何文本字段（支持下划线格式）
                        all_text = []
                        for key in [
                            "display_title",
                            "displayTitle",
                            "title",
                            "desc",
                            "content",
                            "description",
                            "name",
                            "text",
                        ]:
                            val = note_card.get(key) or item.get(key)
                            if val and isinstance(val, str):
                                all_text.append(val)

                        if not all_text:
                            filtered_count["no_content"] += 1
                            continue
                        else:
                            # 使用找到的第一个文本作为标题
                            title = all_text[0][:50]

                    # 获取互动数据 - 尝试多个可能的路径（支持下划线格式）
                    interact_info = (
                        note_card.get("interact_info", {})
                        or note_card.get("interactInfo", {})
                        or note_card.get("counts", {})
                        or {}
                    )
                    if not interact_info:
                        # 直接从 note_card 或 item 获取
                        interact_info = {}

                    # 解析数字（处理字符串和数字类型）
                    def parse_num(val):
                        if val is None:
                            return 0
                        if isinstance(val, (int, float)):
                            return int(val)
                        if isinstance(val, str):
                            # 处理 "1.2万" 这样的格式
                            val = val.replace(",", "").replace("+", "").strip()
                            if "万" in val:
                                try:
                                    return int(float(val.replace("万", "")) * 10000)
                                except (ValueError, TypeError) as e:
                                    if debug:
                                        log_callback(f"  ⚠️ 数字解析异常 '{val}': {e}")
                                    return 0
                            try:
                                return int(val)
                            except (ValueError, TypeError) as e:
                                if debug:
                                    log_callback(f"  ⚠️ 数字解析异常 '{val}': {e}")
                                return 0
                        return 0

                    # 获取互动数，尝试多个可能的字段名（支持下划线格式）
                    liked_count = parse_num(
                        interact_info.get("liked_count")
                        or interact_info.get("likedCount")
                        or interact_info.get("likes")
                        or note_card.get("liked_count")
                        or note_card.get("likedCount")
                        or note_card.get("likes")
                        or item.get("liked_count")
                        or item.get("likedCount")
                        or item.get("likes")
                        or 0
                    )

                    collected_count = parse_num(
                        interact_info.get("collected_count")
                        or interact_info.get("collectedCount")
                        or interact_info.get("collects")
                        or note_card.get("collected_count")
                        or note_card.get("collectedCount")
                        or note_card.get("collects")
                        or 0
                    )

                    comment_count = parse_num(
                        interact_info.get("comment_count")
                        or interact_info.get("commentCount")
                        or note_card.get("comment_count")
                        or note_card.get("commentCount")
                        or 0
                    )

                    share_count = parse_num(
                        interact_info.get("shared_count")
                        or interact_info.get("shareCount")
                        or note_card.get("shared_count")
                        or note_card.get("shareCount")
                        or 0
                    )

                    # 点赞数过滤（仅在设置了min_likes时）
                    if min_likes > 0 and liked_count < min_likes:
                        filtered_count["low_likes"] += 1
                        continue

                    # 计算互动率
                    total_interact = (
                        liked_count + collected_count + comment_count + share_count
                    )
                    engagement_rate = total_interact / max(liked_count, 1)

                    # 获取用户信息
                    user_info = note_card.get("user", {}) or item.get("user", {}) or {}
                    if not isinstance(user_info, dict):
                        user_info = {}

                    # 获取标签（支持下划线格式）
                    tags = []
                    tag_list = (
                        note_card.get("tag_list", [])
                        or note_card.get("tagList", [])
                        or note_card.get("tags", [])
                        or []
                    )
                    if isinstance(tag_list, list):
                        for tag in tag_list:
                            if isinstance(tag, dict):
                                tag_name = (
                                    tag.get("name")
                                    or tag.get("tag_name")
                                    or tag.get("tagName")
                                    or tag.get("display_name")
                                    or tag.get("displayName")
                                )
                                if tag_name:
                                    tags.append(tag_name)
                            elif isinstance(tag, str):
                                tags.append(tag)

                    # 获取封面图（支持下划线格式）
                    cover = ""
                    cover_data = note_card.get("cover") or item.get("cover")
                    if cover_data:
                        if isinstance(cover_data, dict):
                            cover = (
                                cover_data.get("url_default")
                                or cover_data.get("url")
                                or cover_data.get("origin")
                                or ""
                            )
                        elif isinstance(cover_data, str):
                            cover = cover_data

                    # 获取笔记类型
                    note_type_val = note_card.get("type") or item.get("type") or ""

                    # 构建笔记数据
                    note_data = {
                        "note_id": note_id,
                        "title": title or "无标题",
                        "desc": desc,
                        "liked_count": liked_count,
                        "collected_count": collected_count,
                        "comment_count": comment_count,
                        "share_count": share_count,
                        "total_interact": total_interact,
                        "engagement_rate": round(engagement_rate, 2),
                        "user": {
                            "user_id": user_info.get("user_id")
                            or user_info.get("userId")
                            or user_info.get("id"),
                            "nickname": user_info.get("nickname")
                            or user_info.get("nick_name")
                            or user_info.get("name")
                            or user_info.get("user_name")
                            or "未知用户",
                        },
                        "tags": tags,
                        "type": note_type_val,
                        "cover": cover,
                        "timestamp": datetime.now().isoformat(),
                        "raw_data": item if debug else None,  # 调试时保存原始数据
                    }

                    notes.append(note_data)

                log_callback(
                    f"📥 已获取 {len(notes)} 条笔记（当前页 {page_no}, "
                    f"过滤: 低赞{filtered_count['low_likes']} 无内容{filtered_count['no_content']} "
                    f"重复{filtered_count['duplicate']} 解析错{filtered_count['parse_error']}）"
                )
                page_no += 1

                # 模拟滚动触发下一页加载
                self.page.scroll.down(800)
                time.sleep(2)
                scroll_attempts += 1

            except Exception as e:
                log_callback(f"⚠️ 数据解析异常: {e}")
                if debug:
                    import traceback

                    log_callback(traceback.format_exc())
                scroll_attempts += 1
                time.sleep(1)
                continue

        # 按点赞数降序排序
        if notes:
            notes.sort(key=lambda x: x["liked_count"], reverse=True)

        log_callback(f"✅ 搜索完成，共获取 {len(notes)} 条高质量笔记")
        if len(notes) > 0:
            total_likes = sum(n["liked_count"] for n in notes)
            log_callback(f"📈 平均点赞数: {total_likes / len(notes):.0f}")
            log_callback(f"📊 最高点赞数: {max(n['liked_count'] for n in notes)}")
        else:
            log_callback("⚠️ 未获取到任何笔记，可能原因：")
            log_callback("  1. 搜索接口未正确监听")
            log_callback("  2. 数据结构不匹配")
            log_callback("  3. 页面加载异常")
            if debug and debug_responses:
                log_callback(
                    f"\n💾 已保存 {len(debug_responses)} 个调试响应文件，请查看 logs/debug/ 目录"
                )

        return notes

    def close(self):
        """关闭浏览器"""
        try:
            self.page.quit()
        except:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class DataQualityFilter:
    """数据质量过滤器"""

    @staticmethod
    def filter_by_interaction(
        notes: List[Dict],
        min_likes: int = 100,
        min_comments: int = 10,
        min_collects: int = 50,
    ) -> List[Dict]:
        """
        按互动数据过滤

        Args:
            notes: 笔记列表
            min_likes: 最小点赞数
            min_comments: 最小评论数
            min_collects: 最小收藏数

        Returns:
            过滤后的笔记列表
        """
        filtered = []
        for note in notes:
            if (
                note.get("liked_count", 0) >= min_likes
                and note.get("comment_count", 0) >= min_comments
                and note.get("collected_count", 0) >= min_collects
            ):
                filtered.append(note)
        return filtered

    @staticmethod
    def filter_by_engagement_rate(
        notes: List[Dict], min_rate: float = 1.2
    ) -> List[Dict]:
        """
        按互动率过滤

        Args:
            notes: 笔记列表
            min_rate: 最小互动率

        Returns:
            过滤后的笔记列表
        """
        return [n for n in notes if n.get("engagement_rate", 0) >= min_rate]

    @staticmethod
    def get_top_notes(
        notes: List[Dict], n: int = 50, sort_by: str = "liked_count"
    ) -> List[Dict]:
        """
        获取 Top N 笔记

        Args:
            notes: 笔记列表
            n: 数量
            sort_by: 排序字段

        Returns:
            Top N 笔记列表
        """
        sorted_notes = sorted(notes, key=lambda x: x.get(sort_by, 0), reverse=True)
        return sorted_notes[:n]

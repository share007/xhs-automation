"""
文生图模块
使用阿里云百炼万相2.6模型生成小红书配图

功能：
- 支持新的 image_prompts 列表格式（每话题统一风格 + 关联配图）
- 兼容旧的 image_prompt 单一格式
- 并发图片生成（ThreadPoolExecutor）
- 自动重试机制（指数退避）
- 图片下载验证

API文档: https://help.aliyun.com/zh/dashscope/developer-reference/tongyi-wanxiang-text-to-image
"""

import dashscope
from dashscope import MultiModalConversation
import requests
import os
import time
import threading
import concurrent.futures
from typing import List, Dict, Optional, Callable, Any, Tuple
from datetime import datetime

from utils.retry import call_with_retry

# 配置 dashscope 基础 URL
dashscope.base_http_api_url = "https://dashscope.aliyuncs.com/api/v1"


class ImageGenerator:
    """图片生成器 - 万相2.6版本（支持并发和重试）"""

    # 小红书风格增强提示词
    XHS_STYLE_ENHANCEMENT = (
        ", xiaohongshu style, lifestyle photography, aesthetic composition,"
        " vibrant colors, soft lighting, clean background, 4k resolution"
    )

    # 差异化视觉风格模板（用于兼容旧的 image_prompt 单一格式）
    VISUAL_STYLES = [
        {
            "name": "扁平插画_孟菲斯",
            "style": (
                "flat illustration, Memphis design style, geometric shapes,"
                " bold colors, clean lines, minimalist"
            ),
            "composition": "centered composition",
            "tone": "vibrant and playful",
        },
        {
            "name": "3D渲染_C4D",
            "style": (
                "3D rendering, C4D style, soft lighting, isometric view,"
                " rounded shapes, pastel colors"
            ),
            "composition": "isometric composition",
            "tone": "soft and dreamy",
        },
        {
            "name": "手绘水彩_日系",
            "style": (
                "watercolor painting, Japanese style, soft textures,"
                " natural elements, delicate brush strokes"
            ),
            "composition": "asymmetrical composition",
            "tone": "soft and natural",
        },
        {
            "name": "复古胶片_港风",
            "style": (
                "vintage film photography, Hong Kong style, film grain,"
                " nostalgic mood, warm lighting"
            ),
            "composition": "rule of thirds",
            "tone": "warm and nostalgic",
        },
        {
            "name": "极简主义_北欧",
            "style": (
                "minimalist design, Scandinavian style, clean background,"
                " negative space, muted colors"
            ),
            "composition": "minimalist composition",
            "tone": "clean and elegant",
        },
        {
            "name": "国潮风_新中式",
            "style": (
                "Chinese trendy style, neo-Chinese design, traditional patterns,"
                " modern interpretation, red and gold accents"
            ),
            "composition": "balanced composition",
            "tone": "festive and cultural",
        },
        {
            "name": "赛博朋克_霓虹",
            "style": (
                "cyberpunk style, neon lights, futuristic, high contrast,"
                " glowing effects, dark background"
            ),
            "composition": "dynamic composition",
            "tone": "cool and techy",
        },
    ]

    # 万相API支持的尺寸
    VALID_SIZES = ["1024*1024", "720*1280", "1280*720", "768*1152", "1280*1280"]

    def __init__(
        self,
        api_key: str,
        save_dir: str = "./images",
        model: str = "wan2.6-t2i",
        max_retries: int = 3,
        max_concurrent: int = 3,
    ):
        """
        初始化图片生成器

        Args:
            api_key: 阿里云百炼 API Key
            save_dir: 图片保存目录
            model: 使用的模型，默认 wan2.6-t2i
            max_retries: API 调用最大重试次数
            max_concurrent: 最大并发请求数
        """
        dashscope.api_key = api_key
        self.model = model
        self.save_dir = save_dir
        self.max_retries = max_retries
        self.max_concurrent = max_concurrent
        os.makedirs(save_dir, exist_ok=True)

    def validate_size(self, size: str) -> str:
        """验证并返回有效的尺寸"""
        if size in self.VALID_SIZES:
            return size
        print(f"⚠️ 尺寸 '{size}' 不支持，使用默认尺寸 '768*1152'")
        print(f"   支持的尺寸: {', '.join(self.VALID_SIZES)}")
        return "768*1152"

    def _prepare_prompts(
        self, topic: Dict, n: int, enhance: bool = True
    ) -> List[Dict]:
        """
        根据话题准备图片提示词列表

        优先使用新格式 image_prompts（列表），
        兼容旧格式 image_prompt（单一字符串，自动生成差异化版本）

        Args:
            topic: 话题字典
            n: 需要的图片数量
            enhance: 是否添加小红书风格增强

        Returns:
            提示词字典列表 [{"prompt": "...", "style_name": "..."}]
        """
        # 新格式：AI 预生成的 per-image prompts
        image_prompts = topic.get("image_prompts", [])
        visual_style = topic.get("visual_style", "")

        if image_prompts and isinstance(image_prompts, list) and len(image_prompts) > 0:
            result = []
            for i, prompt in enumerate(image_prompts[:n]):
                # 如果提示词不含风格增强，添加之
                final_prompt = prompt
                if enhance and "4k resolution" not in prompt.lower():
                    final_prompt = prompt + self.XHS_STYLE_ENHANCEMENT
                result.append({
                    "prompt": " ".join(final_prompt.split()),
                    "style_name": f"scene_{i + 1:02d}",
                    "index": i,
                })

            # 如果提示词数量不够 n，复制最后一个
            while len(result) < n:
                last = result[-1].copy()
                idx = len(result)
                last["style_name"] = f"scene_{idx + 1:02d}"
                last["index"] = idx
                result.append(last)

            return result

        # 旧格式兼容：从单一 image_prompt 生成差异化版本
        base_prompt = topic.get("image_prompt", "")
        if not base_prompt:
            return []

        if enhance:
            base_prompt = base_prompt + self.XHS_STYLE_ENHANCEMENT

        return self._generate_differentiated_prompts(base_prompt, n)

    def _generate_differentiated_prompts(
        self, base_prompt: str, n: int
    ) -> List[Dict]:
        """
        基于基础提示词生成n个差异化的提示词（旧格式兼容）

        Args:
            base_prompt: 基础提示词
            n: 需要生成的数量

        Returns:
            差异化提示词列表
        """
        differentiated_prompts = []

        for i in range(n):
            style_config = self.VISUAL_STYLES[i % len(self.VISUAL_STYLES)]

            style = style_config.get("style", "")
            composition = style_config.get("composition", "")
            tone = style_config.get("tone", "")
            name = style_config.get("name", "")

            differentiated_prompt = (
                f"{base_prompt}, {style}, {composition}, {tone},"
                " high quality, detailed, 4k resolution"
            )

            differentiated_prompt = " ".join(differentiated_prompt.split())
            differentiated_prompts.append({
                "prompt": differentiated_prompt,
                "style_name": name,
                "index": i,
            })

        return differentiated_prompts

    def _generate_single_image(
        self,
        prompt: str,
        size: str,
        log_callback: Optional[Callable] = None,
    ) -> Optional[str]:
        """
        生成单张图片（含重试 + 下载）

        Args:
            prompt: 提示词
            size: 图片尺寸
            log_callback: 日志回调

        Returns:
            图片 URL 或 None
        """
        if log_callback is None:
            log_callback = print

        def _api_call():
            return self._call_wanx_api(prompt, size, log_callback)

        # 带重试的 API 调用
        rsp = call_with_retry(
            _api_call,
            max_retries=self.max_retries,
            base_delay=3.0,
            max_delay=30.0,
            backoff_factor=2.0,
            log_callback=log_callback,
        )

        if not rsp:
            return None

        # 提取图片 URL
        img_url = self._extract_image_url(rsp)
        return img_url

    def generate_images_for_topic(
        self,
        topic: Dict,
        n: int = 5,
        size: str = "768*1152",
        enhance_prompt: bool = True,
        log_callback: Optional[Callable] = None,
    ) -> Dict:
        """
        为话题生成图片（并发模式）

        支持两种模式：
        1. 新模式：使用 topic["image_prompts"] 列表（统一风格，关联内容）
        2. 旧模式：使用 topic["image_prompt"] 单一提示词（自动差异化风格）

        Args:
            topic: 话题字典
            n: 生成图片数量
            size: 图片尺寸
            enhance_prompt: 是否增强提示词
            log_callback: 日志回调

        Returns:
            包含图片路径的话题字典
        """
        if log_callback is None:
            log_callback = print

        # 验证尺寸
        size = self.validate_size(size)

        # 准备提示词
        prompt_list = self._prepare_prompts(topic, n, enhance=enhance_prompt)
        if not prompt_list:
            log_callback("⚠️ 话题缺少图片提示词，跳过图片生成")
            topic["image_paths"] = []
            return topic

        # 显示生成模式
        has_multi_prompts = bool(topic.get("image_prompts"))
        mode = "统一风格" if has_multi_prompts else "差异化风格"
        visual_style = topic.get("visual_style", "自动")
        log_callback(f"   🎨 模式: {mode} | 风格: {visual_style}")

        # 创建话题专属文件夹
        topic_title = topic.get("title", "untitled")
        safe_title = "".join(
            c for c in topic_title if c.isalnum() or c in (" ", "_", "-")
        ).strip()
        safe_title = safe_title[:30] if len(safe_title) > 30 else safe_title
        timestamp_str = datetime.now().strftime("%m%d_%H%M%S")
        topic_folder = f"{timestamp_str}_{safe_title}"
        topic_save_dir = os.path.join(self.save_dir, topic_folder)

        os.makedirs(topic_save_dir, exist_ok=True)
        if not os.path.exists(topic_save_dir):
            log_callback(f"❌ 无法创建目录: {topic_save_dir}")
            topic["image_paths"] = []
            return topic

        # 线程安全的日志锁
        log_lock = threading.Lock()

        def thread_safe_log(msg: str) -> None:
            with log_lock:
                log_callback(msg)

        # ===== 并发图片生成 =====
        img_paths: List[Optional[Tuple[int, str]]] = []

        def _generate_and_save(prompt_info: Dict) -> Optional[Tuple[int, str]]:
            """生成并保存单张图片（在线程中执行）"""
            idx = prompt_info["index"]
            style_name = prompt_info["style_name"]
            prompt = prompt_info["prompt"]

            thread_safe_log(
                f"\n  [{idx + 1}/{len(prompt_list)}] {style_name}"
            )

            try:
                img_url = self._generate_single_image(
                    prompt, size, log_callback=thread_safe_log
                )
                if not img_url:
                    thread_safe_log(f"      ❌ 无法获取图片 URL")
                    return None

                # 下载图片
                img_filename = f"{idx + 1:02d}_{style_name}.png"
                img_path = os.path.join(topic_save_dir, img_filename)

                download_success = self._download_image(
                    img_url, img_path, log_callback=thread_safe_log
                )
                if download_success:
                    return (idx, img_path)
                return None

            except Exception as e:
                thread_safe_log(f"      ⚠️ 异常: {e}")
                return None

        # 使用线程池并发生成
        actual_workers = min(self.max_concurrent, len(prompt_list))
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=actual_workers
        ) as executor:
            # 提交所有任务（带错开延迟避免瞬时并发）
            futures = {}
            for i, prompt_info in enumerate(prompt_list):
                # 错开提交以避免 API 瞬时洪峰
                if i > 0:
                    time.sleep(0.5)
                future = executor.submit(_generate_and_save, prompt_info)
                futures[future] = i

            # 收集结果
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    if result is not None:
                        img_paths.append(result)
                except Exception as e:
                    thread_safe_log(f"      ⚠️ 并发任务异常: {e}")

        # 按顺序排列图片路径
        img_paths.sort(key=lambda x: x[0] if x else 999)
        ordered_paths = [path for _, path in img_paths if path]

        topic["image_paths"] = ordered_paths
        topic["image_count"] = len(ordered_paths)
        topic["image_styles"] = [
            p["style_name"] for p in prompt_list[: len(ordered_paths)]
        ]

        return topic

    def _download_image(
        self,
        url: str,
        save_path: str,
        log_callback: Optional[Callable] = None,
    ) -> bool:
        """
        下载图片（带重试）

        Args:
            url: 图片URL
            save_path: 保存路径
            log_callback: 日志回调

        Returns:
            是否下载成功
        """
        if log_callback is None:
            log_callback = print

        def _do_download():
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            if len(response.content) < 100:
                raise Exception(
                    f"图片数据异常: {len(response.content)} bytes"
                )

            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            with open(save_path, "wb") as f:
                f.write(response.content)

            if not os.path.exists(save_path):
                raise Exception("文件写入后不存在")

            img_size_kb = len(response.content) / 1024
            log_callback(f"      ✅ 已保存 ({img_size_kb:.0f} KB)")
            return True

        try:
            return call_with_retry(
                _do_download,
                max_retries=2,
                base_delay=2.0,
                max_delay=15.0,
                retryable_exceptions=(
                    requests.exceptions.RequestException,
                    Exception,
                ),
                log_callback=log_callback,
            )
        except Exception as e:
            log_callback(f"      ❌ 下载失败: {e}")
            return False

    def _call_wanx_api(
        self, prompt: str, size: str, log_callback: Optional[Callable] = None
    ) -> Optional[Dict]:
        """
        调用万相2.6 API（单次调用，重试由上层处理）

        Args:
            prompt: 提示词
            size: 图片尺寸
            log_callback: 日志回调

        Returns:
            API响应字典
        """
        if log_callback is None:
            log_callback = print

        try:
            log_callback("      🌐 调用 API...")

            start_time = datetime.now()

            messages = [{"role": "user", "content": [{"text": prompt.strip()}]}]

            response: Any = MultiModalConversation.call(
                api_key=dashscope.api_key or "",
                model=self.model,
                messages=messages,
                stream=False,
                prompt_extend=True,
                size=size,
            )

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            if response.status_code != 200:
                log_callback(f"      ❌ HTTP {response.status_code}")
                if hasattr(response, "message"):
                    log_callback(f"      ❌ 错误: {response.message}")

                # 429 = 限流，抛出异常以触发重试
                if response.status_code == 429:
                    raise Exception("触发速率限制，需要重试")

                return None

            result = {
                "output": {
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    response.output.choices[0].message.content
                                )
                            }
                        }
                    ]
                }
            }

            log_callback(f"      ✅ 成功 ({duration:.1f}s)")
            return result

        except Exception as e:
            log_callback(f"      ❌ API调用异常: {str(e)}")
            raise  # 让上层重试处理

    def _extract_image_url(self, rsp: Dict) -> Optional[str]:
        """
        从API响应中提取图片URL

        Args:
            rsp: API响应字典

        Returns:
            图片URL或None
        """
        try:
            if not isinstance(rsp, dict):
                return None

            output = rsp.get("output", {})
            if not output:
                return None

            choices = output.get("choices", [])
            if choices and len(choices) > 0:
                choice = choices[0]
                if isinstance(choice, dict):
                    message = choice.get("message", {})
                    if isinstance(message, dict):
                        content = message.get("content", [])
                        if content and len(content) > 0:
                            content_item = content[0]
                            if isinstance(content_item, dict):
                                image_url = content_item.get("image")
                                if image_url:
                                    return image_url

            return None

        except Exception as e:
            print(f"提取图片URL异常: {e}")
            return None

    def generate_for_topics(
        self,
        topics: List[Dict],
        n_per_topic: int = 5,
        size: str = "768*1152",
        log_callback: Optional[Callable] = None,
    ) -> List[Dict]:
        """
        为多个话题批量生成图片

        Args:
            topics: 话题列表
            n_per_topic: 每个话题生成图片数（仅旧格式时生效）
            size: 图片尺寸
            log_callback: 日志回调

        Returns:
            包含图片路径的话题列表
        """
        if log_callback is None:
            log_callback = print

        start_time = time.time()
        total_images = sum(
            len(t.get("image_prompts", [])) or n_per_topic for t in topics
        )
        generated_count = 0

        log_callback(f"\n{'-' * 70}")
        log_callback("🖼️  开始生成图片（并发模式）")
        log_callback(f"{'-' * 70}")
        log_callback(
            f"📊 话题数: {len(topics)} | 总计: ~{total_images} 张"
        )
        log_callback(
            f"📐 尺寸: {size} | 🤖 模型: {self.model}"
            f" | 并发: {self.max_concurrent} 线程"
        )
        log_callback(
            f"⏱️  预计: {len(topics) * n_per_topic * 8 // 60} 分钟"
            f"（并发加速）"
        )

        for i, topic in enumerate(topics):
            log_callback(f"\n{'·' * 70}")
            log_callback(
                f"🎨 话题 [{i + 1}/{len(topics)}]: "
                f"{topic.get('title', '无标题')[:35]}"
            )
            style = topic.get("visual_style", "自动")
            n_prompts = len(topic.get("image_prompts", []))
            if n_prompts:
                log_callback(
                    f"{'·' * 70}\n"
                    f"   📐 尺寸: {size} | 🖼️ {n_prompts} 张 | 🎨 {style}"
                )
            else:
                log_callback(
                    f"{'·' * 70}\n"
                    f"   📐 尺寸: {size} | 🖼️ {n_per_topic} 张 | 🎨 差异化风格"
                )

            # 对于新格式，n 来自于 image_prompts 的长度
            actual_n = n_prompts if n_prompts > 0 else n_per_topic

            self.generate_images_for_topic(
                topic, n=actual_n, size=size, log_callback=log_callback
            )

            generated_count += len(topic.get("image_paths", []))

            # 进度统计
            elapsed = time.time() - start_time
            avg_time_per_topic = elapsed / (i + 1)
            remaining_topics = len(topics) - (i + 1)
            estimated_remaining = avg_time_per_topic * remaining_topics

            log_callback(
                f"\n✅ 话题完成 | 生成: "
                f"{len(topic.get('image_paths', []))}/{actual_n} 张"
            )
            log_callback(
                f"📊 总进度: {i + 1}/{len(topics)} 话题 | "
                f"{generated_count}/{total_images} 张图片"
            )
            if remaining_topics > 0:
                log_callback(
                    f"⏱️  预计剩余: {int(estimated_remaining // 60)} 分"
                    f" {int(estimated_remaining % 60)} 秒"
                )

            # 话题间间隔（避免限流）
            if i < len(topics) - 1:
                log_callback("⏳ 等待 3 秒...")
                time.sleep(3)

        total_elapsed = time.time() - start_time
        log_callback(f"\n{'-' * 70}")
        log_callback("✅ 图片生成完成")
        log_callback(f"{'-' * 70}")
        log_callback(f"📊 成功: {generated_count}/{total_images} 张")
        log_callback(
            f"⏱️  总耗时: {int(total_elapsed // 60)} 分"
            f" {int(total_elapsed % 60)} 秒"
        )
        log_callback(f"📁 保存位置: {self.save_dir}")
        return topics

    def enhance_prompt_for_xhs(self, base_prompt: str) -> str:
        """
        为小红书风格增强提示词

        Args:
            base_prompt: 基础提示词

        Returns:
            增强后的提示词
        """
        xhs_keywords = [
            "xiaohongshu style",
            "lifestyle photography",
            "aesthetic",
            "high quality",
            "vibrant colors",
            "soft lighting",
            "clean composition",
            "instagram-worthy",
        ]

        enhanced = base_prompt
        for keyword in xhs_keywords:
            if keyword.lower() not in base_prompt.lower():
                enhanced += f", {keyword}"

        return enhanced


class ImageUtils:
    """图片工具类"""

    @staticmethod
    def validate_image(path: str) -> bool:
        """验证图片是否有效"""
        try:
            if not os.path.exists(path):
                return False

            size = os.path.getsize(path)
            if size < 1024:  # 小于1KB可能是损坏文件
                return False

            return True
        except Exception:
            return False

    @staticmethod
    def get_image_info(path: str) -> Dict:
        """获取图片信息"""
        try:
            from PIL import Image

            with Image.open(path) as img:
                return {
                    "path": path,
                    "format": img.format,
                    "mode": img.mode,
                    "size": img.size,
                    "width": img.width,
                    "height": img.height,
                    "file_size": os.path.getsize(path),
                }
        except Exception:
            return {"path": path, "error": "无法读取图片信息"}

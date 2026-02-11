"""
文生图模块
使用阿里云百炼万相2.6模型生成小红书配图
API文档: https://help.aliyun.com/zh/dashscope/developer-reference/tongyi-wanxiang-text-to-image
"""

import dashscope
import requests
import os
import time
from typing import List, Dict, Optional, Callable
from datetime import datetime


class ImageGenerator:
    """图片生成器 - 万相2.6版本"""

    # 小红书风格增强提示词
    XHS_STYLE_ENHANCEMENT = ", xiaohongshu style, lifestyle photography, aesthetic composition, vibrant colors, soft lighting, clean background, 4k resolution"

    # 差异化视觉风格模板
    VISUAL_STYLES = [
        {
            "name": "扁平插画+孟菲斯",
            "style": "flat illustration, Memphis design style, geometric shapes, bold colors, clean lines, minimalist",
            "composition": "centered composition",
            "tone": "vibrant and playful",
        },
        {
            "name": "3D渲染+C4D",
            "style": "3D rendering, C4D style, soft lighting, isometric view, rounded shapes, pastel colors",
            "composition": "isometric composition",
            "tone": "soft and dreamy",
        },
        {
            "name": "手绘水彩+日系",
            "style": "watercolor painting, Japanese style, soft textures, natural elements, delicate brush strokes",
            "composition": "asymmetrical composition",
            "tone": "soft and natural",
        },
        {
            "name": "复古胶片+港风",
            "style": "vintage film photography, Hong Kong style, film grain, nostalgic mood, warm lighting",
            "composition": "rule of thirds",
            "tone": "warm and nostalgic",
        },
        {
            "name": "极简主义+北欧",
            "style": "minimalist design, Scandinavian style, clean background, negative space, muted colors",
            "composition": "minimalist composition",
            "tone": "clean and elegant",
        },
        {
            "name": "国潮风+新中式",
            "style": "Chinese trendy style, neo-Chinese design, traditional patterns, modern interpretation, red and gold accents",
            "composition": "balanced composition",
            "tone": "festive and cultural",
        },
        {
            "name": "赛博朋克+霓虹",
            "style": "cyberpunk style, neon lights, futuristic, high contrast, glowing effects, dark background",
            "composition": "dynamic composition",
            "tone": "cool and techy",
        },
    ]

    # 万相API支持的尺寸（新版）
    VALID_SIZES = ["1024*1024", "720*1280", "1280*720", "768*1152", "1280*1280"]

    def __init__(
        self, api_key: str, save_dir: str = "./images", model: str = "wan2.6-t2i"
    ):
        """
        初始化图片生成器

        Args:
            api_key: 阿里云百炼 API Key
            save_dir: 图片保存目录
            model: 使用的模型，默认 wan2.6-t2i
        """
        dashscope.api_key = api_key
        self.model = model
        self.save_dir = save_dir
        os.makedirs(save_dir, exist_ok=True)

    def validate_size(self, size: str) -> str:
        """验证并返回有效的尺寸"""
        if size in self.VALID_SIZES:
            return size
        # 默认使用适合小红书的尺寸
        print(f"⚠️ 尺寸 '{size}' 不支持，使用默认尺寸 '768*1152'")
        print(f"   支持的尺寸: {', '.join(self.VALID_SIZES)}")
        return "768*1152"

    def _generate_differentiated_prompts(self, base_prompt: str, n: int) -> List[str]:
        """
        基于基础提示词生成n个差异化的提示词

        Args:
            base_prompt: 基础提示词
            n: 需要生成的数量

        Returns:
            差异化提示词列表
        """
        differentiated_prompts = []

        # 循环使用不同的视觉风格
        for i in range(n):
            style_config = self.VISUAL_STYLES[i % len(self.VISUAL_STYLES)]

            # 构建差异化提示词
            style = style_config.get("style", "")
            composition = style_config.get("composition", "")
            tone = style_config.get("tone", "")
            name = style_config.get("name", "")

            differentiated_prompt = f"""{base_prompt}, 
{style}, 
{composition}, 
{tone}, 
high quality, detailed, 4k resolution"""

            # 清理多余空格和换行
            differentiated_prompt = " ".join(differentiated_prompt.split())
            differentiated_prompts.append(
                {"prompt": differentiated_prompt, "style_name": name}
            )

        return differentiated_prompts

    def generate_images_for_topic(
        self,
        topic: Dict,
        n: int = 5,
        size: str = "768*1152",
        enhance_prompt: bool = True,
        log_callback: Optional[Callable] = None,
    ) -> Dict:
        """
        为话题生成图片，每张图片使用差异化的提示词

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

        base_prompt = topic.get("image_prompt", "")
        if not base_prompt:
            log_callback("⚠️ 话题缺少 image_prompt，跳过图片生成")
            topic["image_paths"] = []
            return topic

        # 增强基础提示词
        if enhance_prompt:
            base_prompt = base_prompt + self.XHS_STYLE_ENHANCEMENT

        # 生成n个差异化的提示词
        differentiated_prompts = self._generate_differentiated_prompts(base_prompt, n)

        # 为每个话题创建单独文件夹
        topic_title = topic.get("title", "untitled")
        # 清理文件夹名（移除特殊字符，限制长度）
        safe_title = "".join(
            c for c in topic_title if c.isalnum() or c in (" ", "_", "-")
        ).strip()
        safe_title = safe_title[:30] if len(safe_title) > 30 else safe_title  # 限制长度
        timestamp_str = datetime.now().strftime("%m%d_%H%M%S")
        topic_folder = f"{timestamp_str}_{safe_title}"
        topic_save_dir = os.path.join(self.save_dir, topic_folder)
        
        # 创建目录并验证
        os.makedirs(topic_save_dir, exist_ok=True)
        
        if not os.path.exists(topic_save_dir):
            log_callback(f"❌ 无法创建目录: {topic_save_dir}")
            topic["image_paths"] = []
            return topic

        img_paths = []

        for i, prompt_info in enumerate(differentiated_prompts):
            try:
                log_callback(f"\n  [{i + 1}/{n}] {prompt_info.get('style_name')}")

                # 调用万相2.6 API
                rsp = self._call_wanx_api(prompt_info.get("prompt"), size, log_callback)

                if not rsp:
                    log_callback(f"      ❌ API 调用失败")
                    continue

                # 解析响应获取图片URL
                img_url = self._extract_image_url(rsp)

                if not img_url:
                    log_callback(f"      ❌ 无法提取图片 URL")
                    continue

                # 下载图片到话题专属文件夹
                style_name = prompt_info.get("style_name", "")
                img_filename = f"{i + 1:02d}_{style_name.replace('+', '_')}.png"
                img_path = os.path.join(topic_save_dir, img_filename)

                try:
                    response = requests.get(img_url, timeout=30)
                    response.raise_for_status()

                    img_size_kb = len(response.content) / 1024
                    
                    if len(response.content) < 100:
                        log_callback(f"      ⚠️ 图片数据异常: {len(response.content)} bytes")
                        continue

                    # 确保目录存在
                    os.makedirs(os.path.dirname(img_path), exist_ok=True)
                    
                    with open(img_path, "wb") as f:
                        f.write(response.content)

                    # 验证文件是否真的保存了
                    if os.path.exists(img_path):
                        log_callback(f"      ✅ 已保存 ({img_size_kb:.0f} KB)")
                    else:
                        log_callback(f"      ⚠️ 保存失败")
                        continue

                except requests.exceptions.RequestException as req_err:
                    log_callback(f"      ❌ 下载失败: {req_err}")
                    continue

                img_paths.append(img_path)

                # 避免限流
                if i < n - 1:
                    time.sleep(2)

            except Exception as e:
                log_callback(f"      ⚠️ 异常: {e}")
                continue

        topic["image_paths"] = img_paths
        topic["image_count"] = len(img_paths)

        # 记录使用的风格信息
        topic["image_styles"] = [
            p.get("style_name") for p in differentiated_prompts[: len(img_paths)]
        ]

        return topic

    def _call_wanx_api(
        self, prompt: str, size: str, log_callback: Optional[Callable] = None
    ) -> Optional[Dict]:
        """
        调用万相2.6 API

        Args:
            prompt: 提示词
            size: 图片尺寸
            log_callback: 日志回调

        Returns:
            API响应字典
        """
        if log_callback is None:
            log_callback = print

        import json

        # 构建请求体（根据最新API文档）
        payload = {
            "model": self.model,
            "input": {
                "messages": [{"role": "user", "content": [{"text": prompt.strip()}]}]
            },
            "parameters": {
                "prompt_extend": True,  # 开启智能提示词扩展
                "watermark": False,  # 不添加水印
                "n": 1,  # 生成1张
                "negative_prompt": "",  # 负面提示词（可选）
                "size": size,  # 图片尺寸
            },
        }

        # 直接使用HTTP请求（因为dashscope SDK可能不支持新接口）
        import requests

        url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"

        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {dashscope.api_key}",
            }

            log_callback(f"      🌐 调用 API...")

            start_time = datetime.now()

            response = requests.post(url, headers=headers, json=payload, timeout=60)

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            if response.status_code != 200:
                log_callback(f"      ❌ HTTP {response.status_code}")
                return None

            result = response.json()
            log_callback(f"      ✅ 成功 ({duration:.1f}s)")

            return result

        except Exception as e:
            log_callback(f"      ❌ API调用异常!")
            log_callback(f"         📍 接口地址: {url}")
            log_callback(f"         ❗ 错误: {str(e)}")
            return None

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

            # 实际响应格式: output.choices[0].message.content[0].image
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
                                # 图片URL在 "image" 字段
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
            n_per_topic: 每个话题生成图片数
            size: 图片尺寸
            log_callback: 日志回调

        Returns:
            包含图片路径的话题列表
        """
        if log_callback is None:
            log_callback = print

        # 先计算总数
        start_time = time.time()
        total_images = len(topics) * n_per_topic
        generated_count = 0

        log_callback(f"\n{'-'*70}")
        log_callback(f"🖼️  开始生成图片")
        log_callback(f"{'-'*70}")
        log_callback(f"📊 话题数: {len(topics)} | 每个话题: {n_per_topic} 张 | 总计: {total_images} 张")
        log_callback(f"📐 尺寸: {size} | 🤖 模型: {self.model}")
        log_callback(f"⏱️  预计: {len(topics) * n_per_topic * 10 // 60} 分钟")

        for i, topic in enumerate(topics):
            log_callback(f"\n{'·'*70}")
            log_callback(f"🎨 话题 [{i + 1}/{len(topics)}]: {topic.get('title', '无标题')[:30]}")
            log_callback(f"{'·'*70}")
            log_callback(f"📐 尺寸: {size} | 🖼️  数量: {n_per_topic} 张")
            
            topic_start = time.time()

            self.generate_images_for_topic(
                topic, n=n_per_topic, size=size, log_callback=log_callback
            )

            generated_count += len(topic.get("image_paths", []))

            # 计算进度和预估时间
            elapsed = time.time() - start_time
            avg_time_per_topic = elapsed / (i + 1)
            remaining_topics = len(topics) - (i + 1)
            estimated_remaining = avg_time_per_topic * remaining_topics

            log_callback(f"\n✅ 话题完成 | 生成: {len(topic.get('image_paths', []))}/{n_per_topic} 张")
            log_callback(f"📊 总进度: {i + 1}/{len(topics)} 话题 | {generated_count}/{total_images} 张图片")
            if remaining_topics > 0:
                log_callback(f"⏱️  预计剩余: {int(estimated_remaining // 60)} 分 {int(estimated_remaining % 60)} 秒")

            # 话题间间隔
            if i < len(topics) - 1:
                log_callback(f"⏳ 等待 3 秒...")
                time.sleep(3)

        total_elapsed = time.time() - start_time
        log_callback(f"\n{'-'*70}")
        log_callback(f"✅ 图片生成完成")
        log_callback(f"{'-'*70}")
        log_callback(f"📊 成功: {generated_count}/{total_images} 张")
        log_callback(f"⏱️  总耗时: {int(total_elapsed // 60)} 分 {int(total_elapsed % 60)} 秒")
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

            # 检查文件大小
            size = os.path.getsize(path)
            if size < 1024:  # 小于1KB可能是损坏文件
                return False

            return True
        except:
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
        except:
            return {"path": path, "error": "无法读取图片信息"}

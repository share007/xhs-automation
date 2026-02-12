"""
AI 分析引擎模块
使用阿里云百炼大模型进行热点分析和话题生成
采用 dashscope.Generation API（推荐方式）

功能：
- 爆款笔记趋势分析
- 话题生成（每话题统一视觉风格 + 多张关联图片）
- 图片提示词优化
- 内置指数退避重试机制
"""

import os
import json
import traceback
from dashscope import Generation
import dashscope
from typing import List, Dict, Optional, Callable, Any
from datetime import datetime

from utils.retry import call_with_retry

# 配置 dashscope 基础 URL
dashscope.base_http_api_url = "https://dashscope.aliyuncs.com/api/v1"


class AIEngine:
    """AI 分析引擎 - OpenAI 兼容接口"""

    # 小红书风格提示词模板
    XHS_STYLE_PROMPT = """你是一位专业的小红书爆款内容策划专家，深谙平台算法和用户心理。
你擅长分析爆款内容的底层逻辑，并能创造出具有病毒传播潜力的新内容。

## 重要原则：基于事实，拒绝幻觉

你必须严格遵守以下原则：
1. **只基于提供的原始数据进行分析和创作**，不要编造数据中不存在的信息
2. **不要凭空捏造具体的技术细节、数据、对比结果**
3. **每个观点都必须能在原始笔记中找到依据**
4. 如果原始数据不足以支撑某个话题，就不要生成该话题
5. 宁可话题少一些，也不要编造不存在的内容"""

    def __init__(
        self,
        api_key: str,
        model: str = "qwen3-max-2026-01-23",
        enable_thinking: Optional[bool] = None,
        max_retries: int = 3,
    ):
        """
        初始化 AI 引擎

        Args:
            api_key: 阿里云百炼 API Key
            model: 使用的模型名称，默认 qwen3-max-2026-01-23
            enable_thinking: 是否启用思考模式（None=自动, True=强制启用, False=强制禁用）
            max_retries: API 调用最大重试次数
        """
        self.api_key = api_key
        self.model = model
        self.base_url = (
            "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        )
        self.enable_thinking = enable_thinking
        self.max_retries = max_retries

        # 根据是否启用思考模式设置超时时间
        self.timeout = 600 if enable_thinking else 120

    def validate_api_key(self, log_callback: Optional[Callable] = None) -> bool:
        """
        验证 API Key 是否有效

        Args:
            log_callback: 日志回调

        Returns:
            是否验证通过
        """
        if log_callback is None:
            log_callback = print

        try:
            log_callback("🔍 正在验证 API Key...")

            test_messages = [{"role": "user", "content": "Hello"}]

            response = Generation.call(
                api_key=self.api_key,
                model=self.model,
                messages=test_messages,
                result_format="message",
                max_tokens=10,
            )

            if response.status_code == 200:
                log_callback("✅ API Key 验证通过")
                return True
            else:
                error_code = getattr(response, "code", "unknown")
                error_msg = getattr(response, "message", "未知错误")
                log_callback("❌ API Key 验证失败")
                log_callback(f"   状态码: {response.status_code}")
                log_callback(f"   错误码: {error_code}")
                log_callback(f"   错误信息: {error_msg}")

                if response.status_code == 401:
                    log_callback("💡 提示: API Key 无效或已过期")
                elif response.status_code == 403:
                    log_callback(f"💡 提示: 没有权限访问模型 '{self.model}'")
                    log_callback("   请检查: 1) 账户是否已完成实名认证")
                    log_callback("          2) 是否已开通百炼服务")
                    log_callback("          3) 是否有该模型的访问权限")

                return False

        except Exception as e:
            log_callback(f"❌ API Key 验证出错: {e}")
            return False

    def _call_api_once(
        self,
        messages: List[Dict],
        temperature: float = 0.7,
        enable_thinking: Optional[bool] = None,
        log_callback: Optional[Callable] = None,
    ) -> str:
        """
        单次 API 调用（不含重试，由 _call_api 包装重试逻辑）

        Args:
            messages: 消息列表
            temperature: 温度参数
            enable_thinking: 是否启用思考模式
            log_callback: 日志回调

        Returns:
            模型生成的文本

        Raises:
            Exception: API 调用失败
        """
        if log_callback is None:
            log_callback = print

        if enable_thinking is None:
            enable_thinking = self.enable_thinking

        log_callback("")
        log_callback("🌐 调用 API...")
        log_callback(f"   模型: {self.model} | 温度: {temperature}")
        if enable_thinking and "qwen3" in self.model.lower():
            log_callback("   💭 思考模式已启用")

        start_time = datetime.now()

        # 构建 API 调用参数
        call_params = {
            "api_key": self.api_key,
            "model": self.model,
            "messages": messages,
            "result_format": "message",
            "temperature": temperature,
            "request_timeout": self.timeout,  # dashscope SDK 使用 request_timeout
        }

        if enable_thinking and "qwen3" in self.model.lower():
            call_params["enable_thinking"] = True

        # 调用 API
        response: Any = Generation.call(**call_params)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # 检查响应状态码
        if response.status_code != 200:
            error_msg = f"HTTP {response.status_code}"
            if hasattr(response, "message") and response.message:
                error_msg = f"{error_msg} - {response.message}"
            elif hasattr(response, "code") and response.code:
                error_msg = f"{error_msg} - 错误码: {response.code}"

            log_callback(f"   ❌ API 返回非 200 状态码")
            log_callback(f"      状态码: {response.status_code}")
            if hasattr(response, "code"):
                log_callback(f"      错误码: {response.code}")
            if hasattr(response, "message") and response.message:
                log_callback(f"      错误信息: {response.message}")

            try:
                if hasattr(response, "output") and response.output:
                    log_callback(f"      输出内容: {response.output}")
            except Exception:
                pass

            if response.status_code == 401:
                raise Exception("API Key 无效或已过期。请检查配置。")
            elif response.status_code == 403:
                raise Exception(
                    f"没有权限访问该模型 '{self.model}'。"
                    "请检查 API Key、模型权限、实名认证。"
                )
            elif response.status_code == 429:
                raise Exception("触发速率限制，请稍后重试。")
            elif response.status_code == 400:
                raise Exception(f"请求参数错误: {error_msg}")
            else:
                raise Exception(f"API 请求失败: {error_msg}")

        # 解析响应
        if (
            hasattr(response, "code")
            and response.code
            and str(response.code) not in ["200", "None", "", "0"]
        ):
            error_msg = (
                response.message
                if hasattr(response, "message") and response.message
                else f"错误码: {response.code}"
            )
            raise Exception(f"API 返回错误: {error_msg}")

        if not hasattr(response, "output") or not response.output:
            raise Exception("API 返回空结果（无 output 字段）")

        if (
            not hasattr(response.output, "choices")
            or not response.output.choices
        ):
            raise Exception("API 返回空结果（无 choices 字段）")

        message = response.output.choices[0].message
        response_content = (
            str(message.content) if hasattr(message, "content") else ""
        )

        content_length = len(response_content) if response_content else 0
        log_callback(f"   ✅ 成功 ({duration:.1f}s, {content_length} 字符)")

        if enable_thinking and hasattr(message, "reasoning_content"):
            reasoning = message.reasoning_content
            if reasoning:
                log_callback("   💭 思考过程已生成")

        if not response_content:
            log_callback("   ⚠️  警告: API 返回空内容")

        return response_content

    def _call_api(
        self,
        messages: List[Dict],
        temperature: float = 0.7,
        enable_thinking: Optional[bool] = None,
        log_callback: Optional[Callable] = None,
    ) -> str:
        """
        调用阿里云百炼 API（带自动重试）

        Args:
            messages: 消息列表
            temperature: 温度参数
            enable_thinking: 是否启用思考模式
            log_callback: 日志回调

        Returns:
            模型生成的文本
        """
        if log_callback is None:
            log_callback = print

        return call_with_retry(
            self._call_api_once,
            messages,
            temperature,
            enable_thinking,
            log_callback,
            max_retries=self.max_retries,
            base_delay=3.0,
            max_delay=60.0,
            backoff_factor=2.0,
            log_callback=log_callback,
        )

    def analyze_trends(
        self,
        notes: List[Dict],
        top_n: int = 50,
        log_callback: Optional[Callable] = None,
    ) -> Dict:
        """
        分析热门趋势

        Args:
            notes: 笔记列表
            top_n: 分析前 N 条
            log_callback: 日志回调

        Returns:
            分析结果字典
        """
        if log_callback is None:
            log_callback = print

        log_callback(f"\n{'-' * 70}")
        log_callback("🧠 分析热点趋势")
        log_callback(f"{'-' * 70}")

        # 限制传入LLM的笔记数量，避免prompt过大导致超时
        # 笔记已按质量排序，取前30条足够分析趋势
        max_analyze = min(top_n, len(notes), 30)
        log_callback(f"📊 分析笔记数: {max_analyze} 条（共搜集 {len(notes)} 条）\n")

        # 准备分析数据（保留更多原始信息用于事实溯源）
        analyze_data = []
        for idx, note in enumerate(notes[:max_analyze]):
            analyze_data.append(
                {
                    "index": idx + 1,
                    "note_id": note.get("note_id", ""),
                    "title": note.get("title", ""),
                    "desc": note.get("desc", "")[:300],
                    "liked_count": note.get("liked_count", 0),
                    "collected_count": note.get("collected_count", 0),
                    "comment_count": note.get("comment_count", 0),
                    "share_count": note.get("share_count", 0),
                    "tags": note.get("tags", [])[:5],
                    "user_nickname": note.get("user", {}).get("nickname", ""),
                }
            )

        system_message = {"role": "system", "content": self.XHS_STYLE_PROMPT}

        user_message = {
            "role": "user",
            "content": f"""请基于以下小红书真实笔记数据进行分析。

注意：只分析数据中实际存在的内容，不要编造或推测数据中没有的信息。
如果某个笔记的描述(desc)为空，只能从标题推断大方向，不要脑补具体内容。

原始笔记数据：
{json.dumps(analyze_data, ensure_ascii=False, indent=2)}

请从以下维度分析：

1. **高频关键词**（标题和描述中实际出现3次以上的词）
2. **情绪价值点**（从标题可以判断的情绪触发类型）
3. **爆款标题模式**（引用具体的标题作为例子）
4. **内容类型分布**（教程类/资讯类/评测类/经验分享类等，统计各类占比）
5. **互动数据洞察**（哪类标题获得最高点赞/收藏/分享）
6. **代表性笔记**（列出互动量最高的5条笔记标题和数据）

请以 JSON 格式输出：
{{
  "top_keywords": ["关键词1", "关键词2", ...],
  "emotion_points": ["情绪点1", "情绪点2", ...],
  "title_patterns": [
    {{"pattern": "模式名称", "example": "实际标题原文", "count": 出现次数}}
  ],
  "content_types": [
    {{"type": "类型名", "count": 数量, "examples": ["标题1", "标题2"]}}
  ],
  "top_notes": [
    {{"title": "标题", "liked": 点赞数, "collected": 收藏数, "note_id": "ID"}}
  ],
  "interaction_insight": "互动数据洞察...",
  "viral_logic": "爆款底层逻辑总结"
}}

只返回 JSON，不要其他内容。""",
        }

        try:
            task_enable_thinking = (
                self.enable_thinking if self.enable_thinking is not None else True
            )
            response_text = self._call_api(
                [system_message, user_message],
                temperature=0.3,
                enable_thinking=task_enable_thinking,
                log_callback=log_callback,
            )

            response_text = (
                response_text.replace("```json", "").replace("```", "").strip()
            )

            analyze_result = json.loads(response_text)
            log_callback("✅ 分析完成\n")

            return analyze_result

        except Exception as e:
            log_callback(f"❌ 分析失败: {e}")
            raise

    def generate_topics(
        self,
        analyze_result: Dict,
        keyword: str,
        top_n: int = 10,
        images_per_topic: int = 5,
        log_callback: Optional[Callable] = None,
    ) -> List[Dict]:
        """
        生成新话题，每个话题包含统一视觉风格 + 多张关联图片提示词

        核心策略：
        - 每个话题选择一种统一的视觉风格
        - 同一话题的 N 张图片风格一致、内容不同
        - N 张图片构成视觉叙事（轮播图故事线）
        - 不同话题之间使用不同的视觉风格

        Args:
            analyze_result: 分析结果
            keyword: 原始搜索关键词
            top_n: 生成话题数量
            images_per_topic: 每个话题的图片数量
            log_callback: 日志回调

        Returns:
            话题列表
        """
        if log_callback is None:
            log_callback = print

        log_callback(f"\n{'-' * 70}")
        log_callback("✨ 生成话题（基于事实 + 关联配图）")
        log_callback(f"{'-' * 70}")
        log_callback(
            f"📊 数量: {top_n} 个 | 关键词: {keyword} | "
            f"每话题: {images_per_topic} 张图"
        )
        log_callback(f"⏱️  预计: 15-45 秒\n")

        system_message = {"role": "system", "content": self.XHS_STYLE_PROMPT}

        user_message = {
            "role": "user",
            "content": f"""基于以下爆款内容分析报告和原始笔记数据，创作新话题。

## 分析报告
{json.dumps(analyze_result, ensure_ascii=False, indent=2)}

## 原始搜索关键词
{keyword}

## ⚠️ 反幻觉要求（必须遵守）

1. **话题必须基于分析报告中的真实趋势**，不要凭空创造
2. **正文内容只能包含从分析报告中能推断出的信息**，不要编造具体数据、代码片段、对比结果
3. **如果你不确定某个技术细节是否真实存在，就不要写**
4. 话题内容应该是"引导性+框架性"的，而不是编造假的具体教程
5. 可以用"分享经验"、"避坑指南"等框架，但不要捏造具体的步骤细节

## 话题创作要求

请生成 {top_n} 个话题，每个话题需要 {images_per_topic} 张配图。

### 话题来源
每个话题必须标明灵感来源于哪些原始笔记（用标题引用），确保话题有事实基础。

### 话题差异化
{top_n} 个话题必须从不同角度切入：
- 可参考分析报告中的内容类型分布
- 覆盖不同用户群体（小白/进阶/专业）
- 标题10-20个中文字符，简洁有力，含1-2个emoji

### 正文要求
- 150-250字，分段落，含emoji
- **只写你确信的信息**，用引导框架代替编造细节
- 例如：「✅ 环境配置有坑，评论区分享你的解决方案」而不是编造具体配置步骤
- 可以用「你们觉得呢？」「评论区讨论」等开放式互动

### 图片提示词要求（适配万相2.6模型）

⚠️ 万相2.6模型的能力边界：
- ✅ 擅长：自然场景、人物、物品、抽象概念的视觉化、氛围营造
- ❌ 不擅长：渲染精确文字、复杂UI界面、详细图表、代码截图

因此，图片提示词必须：
1. 使用英文，30-50个词（简洁效果更好）
2. 描述具体的**视觉场景**而非抽象概念
3. **不要要求渲染文字**（如 'LOSS EXPLODED' 这种）
4. **不要描述UI界面、代码编辑器、详细图表**
5. 用具象物品和场景来象征抽象概念
6. 同话题内风格一致、内容不同
7. 末尾添加: high quality, detailed, 4k resolution

**好的提示词示例**：
- "A cozy desk with laptop, warm coffee, scattered notes under soft morning light, minimalist style, clean composition, high quality, detailed, 4k resolution"
- "Abstract 3D geometric shapes floating in soft pastel space, representing AI technology, isometric view, C4D style, high quality, detailed, 4k resolution"

**不要写这种提示词**：
- "Code editor showing Python code with error message" (模型无法渲染文字和代码)
- "Detailed comparison chart with performance metrics" (模型无法画精确图表)

### 可选视觉风格（每话题选一种，不同话题不重复）
- 3D渲染（3D rendering, soft lighting, isometric view, pastel colors）
- 手绘插画（hand drawn illustration, soft watercolor, warm tones）
- 极简摄影（minimalist photography, clean negative space, natural light）
- 扁平插画（flat illustration, geometric shapes, bold colors）
- 氛围感摄影（moody photography, warm lighting, bokeh, lifestyle）
- 科技感（futuristic, glowing elements, dark background, blue tones）

## 输出格式

```json
[
  {{
    "title": "标题（10-20字含emoji）",
    "content": "正文（150-250字，基于事实）",
    "tags": "#标签1 #标签2 #标签3 #标签4 #标签5",
    "source_notes": ["灵感来源的原始笔记标题1", "标题2"],
    "visual_style": "视觉风格名称",
    "color_palette": "色调描述",
    "image_prompts": [
      "简洁英文提示词, 30-50 words, high quality, detailed, 4k resolution",
      "简洁英文提示词, 30-50 words, high quality, detailed, 4k resolution"
    ]
  }}
]
```

**绝对约束**：
- image_prompts 数组长度必须是 {images_per_topic}
- 图片提示词必须简洁（30-50词），不含文字渲染要求
- 每个话题必须有 source_notes 字段引用原始笔记
- 不同话题使用不同视觉风格

只返回 JSON 数组，不要其他内容。""",
        }

        try:
            task_enable_thinking = (
                self.enable_thinking if self.enable_thinking is not None else True
            )
            response_text = self._call_api(
                [system_message, user_message],
                temperature=0.6,
                enable_thinking=task_enable_thinking,
                log_callback=log_callback,
            )

            response_text = (
                response_text.replace("```json", "").replace("```", "").strip()
            )

            topics = json.loads(response_text)

            # 验证话题格式
            for i, topic in enumerate(topics):
                # 必须字段
                for field in ["title", "content", "tags"]:
                    if field not in topic:
                        topic[field] = ""

                # 处理图片提示词格式
                if "image_prompts" not in topic or not isinstance(
                    topic["image_prompts"], list
                ):
                    # 兼容旧格式：将单个 image_prompt 转为列表
                    single_prompt = topic.get("image_prompt", "")
                    if single_prompt:
                        topic["image_prompts"] = [single_prompt] * images_per_topic
                    else:
                        topic["image_prompts"] = []

                # 元数据字段
                if "visual_style" not in topic:
                    topic["visual_style"] = "未标注"
                if "color_palette" not in topic:
                    topic["color_palette"] = "未标注"
                if "source_notes" not in topic:
                    topic["source_notes"] = []

                # 同时保留 image_prompt（兼容旧代码）
                if topic["image_prompts"]:
                    topic["image_prompt"] = topic["image_prompts"][0]

            log_callback(f"\n✅ 成功生成 {len(topics)} 个话题")

            # 打印话题预览
            log_callback(f"\n📋 话题预览:")
            for i, topic in enumerate(topics[:5]):
                title = topic.get("title", "无标题")
                style = topic.get("visual_style", "?")
                n_prompts = len(topic.get("image_prompts", []))
                sources = topic.get("source_notes", [])
                source_str = f" ← {sources[0][:20]}..." if sources else ""
                log_callback(
                    f"   {i + 1}. {title[:35]} "
                    f"[{style}] ({n_prompts}张图){source_str}"
                )
            if len(topics) > 5:
                log_callback(f"   ... 还有 {len(topics) - 5} 个话题")

            return topics

        except Exception as e:
            log_callback(f"❌ 话题生成失败: {e}")
            raise

    def enhance_image_prompts(
        self,
        topics: List[Dict],
        log_callback: Optional[Callable] = None,
    ) -> List[Dict]:
        """
        进一步优化图片提示词（支持新的 image_prompts 列表格式）

        Args:
            topics: 话题列表
            log_callback: 日志回调

        Returns:
            优化后的话题列表
        """
        if log_callback is None:
            log_callback = print

        total_prompts = sum(
            len(t.get("image_prompts", []) or [t.get("image_prompt", "")])
            for t in topics
        )
        log_callback(f"🎨 正在优化 {total_prompts} 个图片提示词...")

        enhanced_count = 0

        for i, topic in enumerate(topics):
            prompts = topic.get("image_prompts", [])
            if not prompts:
                # 兼容旧格式
                single = topic.get("image_prompt", "")
                if single:
                    prompts = [single]
                else:
                    continue

            visual_style = topic.get("visual_style", "mixed style")
            color_palette = topic.get("color_palette", "vibrant colors")

            enhanced_prompts = []
            for j, prompt in enumerate(prompts):
                try:
                    system_message = {
                        "role": "system",
                        "content": (
                            "你是一位专业的AI绘图提示词工程师，"
                            "擅长为万相2.6模型优化英文提示词。"
                        ),
                    }

                    user_message = {
                        "role": "user",
                        "content": f"""请将以下图片提示词优化，使其更适合万相2.6模型生成高质量图片：

原始提示词：{prompt}
视觉风格：{visual_style}
色调：{color_palette}
图片序号：第{j + 1}张（共{len(prompts)}张，需保持风格一致）

优化要求：
1. 使用英文，60-80个词
2. 保持与同系列其他图片一致的视觉风格和色调
3. 使用具体的视觉描述词汇
4. 适合小红书平台的审美
5. 末尾包含: high quality, detailed, 4k resolution

直接返回优化后的英文提示词，不要其他内容。""",
                    }

                    enhanced = self._call_api(
                        [system_message, user_message],
                        temperature=0.5,
                        enable_thinking=False,
                        log_callback=log_callback,
                    )
                    enhanced = enhanced.strip().strip('"').strip("'")
                    enhanced_prompts.append(enhanced)
                    enhanced_count += 1

                except Exception as e:
                    log_callback(f"  ⚠️ 话题{i + 1}图{j + 1} 优化失败: {e}")
                    enhanced_prompts.append(prompt)  # 保留原始版本

            # 保存原始和优化后的提示词
            topic["image_prompts_original"] = prompts
            topic["image_prompts"] = enhanced_prompts
            if enhanced_prompts:
                topic["image_prompt"] = enhanced_prompts[0]

            log_callback(
                f"  ✅ 话题 {i + 1} 提示词已优化"
                f" ({len(enhanced_prompts)}/{len(prompts)})"
            )

        log_callback(f"✅ 成功优化 {enhanced_count}/{total_prompts} 个提示词")
        return topics

    def analyze_and_create_topics(
        self,
        notes: List[Dict],
        keyword: str,
        top_n: int = 10,
        images_per_topic: int = 5,
        enhance_prompts: bool = False,
        log_callback: Optional[Callable] = None,
    ) -> Dict:
        """
        分析并生成话题（组合方法）

        Args:
            notes: 笔记列表
            keyword: 搜索关键词
            top_n: 生成话题数量
            images_per_topic: 每个话题的图片数量
            enhance_prompts: 是否进一步优化图片提示词
                            （新模式下已生成高质量提示词，默认关闭）
            log_callback: 日志回调

        Returns:
            包含分析结果和话题的字典
        """
        # 1. 热点分析
        analyze_result = self.analyze_trends(notes, top_n=50, log_callback=log_callback)

        # 2. 生成话题（统一风格 + 关联配图）
        topics = self.generate_topics(
            analyze_result,
            keyword,
            top_n=top_n,
            images_per_topic=images_per_topic,
            log_callback=log_callback,
        )

        # 3. 可选：进一步优化图片提示词
        # 新模式下 AI 已生成高质量的 per-image prompts，通常不需要额外优化
        if enhance_prompts:
            topics = self.enhance_image_prompts(topics, log_callback=log_callback)

        return {"analyze_result": analyze_result, "topics": topics, "keyword": keyword}

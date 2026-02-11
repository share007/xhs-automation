"""
AI 分析引擎模块
使用阿里云百炼大模型进行热点分析和话题生成
采用 OpenAI 兼容接口（Chat Completions API）
"""

import os
import json
import requests
from typing import List, Dict, Optional, Callable
from datetime import datetime


class AIEngine:
    """AI 分析引擎 - OpenAI 兼容接口"""

    # 小红书风格提示词模板
    XHS_STYLE_PROMPT = """你是一位专业的小红书爆款内容策划专家，深谙平台算法和用户心理。
你擅长分析爆款内容的底层逻辑，并能创造出具有病毒传播潜力的新内容。"""

    def __init__(self, api_key: str, model: str = "qwen-plus", enable_thinking: bool = False):
        """
        初始化 AI 引擎

        Args:
            api_key: 阿里云百炼 API Key
            model: 使用的模型名称，默认 qwen-plus (快速稳定)
                   可选模型：
                   - qwen-plus (推荐，快速稳定)
                   - qwen-max (最强性能，较慢)
                   - qwen-turbo (最快速度)
                   - qwen3-max-2026-01-23 (思考模式，非常慢)
            enable_thinking: 是否启用思考模式（仅支持特定模型，会显著增加响应时间）
        """
        self.api_key = api_key
        self.model = model
        self.base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        self.enable_thinking = enable_thinking

        # 根据是否启用思考模式设置超时时间
        self.timeout = 600 if enable_thinking else 120  # 思考模式需要更长时间

    def _call_api(
        self,
        messages: List[Dict],
        temperature: float = 0.7,
        enable_thinking: bool = None,
        log_callback: Optional[Callable] = None,
    ) -> str:
        """
        调用阿里云百炼 API（使用 requests 直接调用）

        Args:
            messages: 消息列表
            temperature: 温度参数
            enable_thinking: 是否启用思考模式（None表示使用实例默认值）
            log_callback: 日志回调

        Returns:
            模型生成的文本
        """
        if log_callback is None:
            log_callback = print

        # 如果没有指定，使用实例的默认值
        if enable_thinking is None:
            enable_thinking = self.enable_thinking

        try:
            # 获取第一条消息内容长度用于日志
            first_msg_content = ""
            if messages and len(messages) > 0:
                first_msg = messages[0]
                content = first_msg.get("content", "")
                if isinstance(content, str):
                    first_msg_content = content[:50]
                elif isinstance(content, list) and len(content) > 0:
                    first_msg_content = str(content[0])[:50]

            # 使用换行符确保格式正确，避免与之前的输出混在一起
            log_callback("")
            log_callback("🌐 调用 API...")
            log_callback(f"   模型: {self.model} | 温度: {temperature}")
            if enable_thinking and "qwen3" in self.model.lower():
                log_callback("   💭 思考模式已启用")

            start_time = datetime.now()

            # 构建请求头
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            # 构建请求体
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "stream": False,  # 禁用流式响应
            }

            # 只有当支持思考模式且启用时才添加该参数
            if enable_thinking and "qwen3" in self.model.lower():
                payload["enable_thinking"] = True

            # 发送 HTTP 请求
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=(
                    self.timeout,  # 连接超时
                    self.timeout   # 读取超时
                )
            )

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            # 检查响应状态码
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg = error_detail.get("error", {}).get("message", error_msg)
                except:
                    pass

                log_callback(f"   ❌ 失败: {error_msg}")

                # 提供更友好的错误提示
                if response.status_code == 401:
                    raise Exception(f"API Key 无效或已过期。请检查配置。")
                elif response.status_code == 429:
                    raise Exception(f"触发速率限制，请稍后重试。")
                elif response.status_code == 400:
                    raise Exception(f"请求参数错误: {error_msg}")
                else:
                    raise Exception(f"API 请求失败: {error_msg}")

            # 解析响应
            try:
                result = response.json()

                # 检查是否有错误字段
                if "error" in result:
                    error_info = result["error"]
                    error_msg = error_info.get("message", "未知错误")
                    log_callback(f"   ❌ API 错误: {error_msg}")
                    raise Exception(f"API 返回错误: {error_msg}")

                # 获取响应内容
                choices = result.get("choices", [])
                if not choices:
                    raise Exception("API 返回空结果")

                message = choices[0].get("message", {})
                response_content = message.get("content", "")

                content_length = len(response_content) if response_content else 0

                log_callback(f"   ✅ 成功 ({duration:.1f}s, {content_length} 字符)")

                if not response_content:
                    log_callback("   ⚠️  警告: API 返回空内容")

                return response_content

            except json.JSONDecodeError as e:
                log_callback(f"   ⚠️ JSON 解析失败: {e}")
                log_callback(f"   📄 响应内容: {response.text[:500]}")
                raise Exception(f"响应格式错误: {e}")

        except requests.exceptions.Timeout as e:
            log_callback(f"   ❌ 请求超时!")
            log_callback(f"   💡 提示: 当前超时设置为 {self.timeout} 秒")
            if enable_thinking:
                log_callback(f"   💡 思考模式已启用，建议:")
                log_callback(f"      1. 禁用思考模式（初始化时设置 enable_thinking=False）")
                log_callback(f"      2. 使用更快的模型（如 qwen-plus 或 qwen-turbo）")
                log_callback(f"      3. 增加超时时间")
            else:
                log_callback(f"   💡 建议:")
                log_callback(f"      1. 检查网络连接")
                log_callback(f"      2. 使用更快的模型（如 qwen-turbo）")
                log_callback(f"      3. 减少输入内容长度")
            raise Exception(f"API 请求超时 (超过 {self.timeout} 秒): {e}")

        except requests.exceptions.ConnectionError as e:
            log_callback(f"   ❌ 连接错误!")
            log_callback(f"   💡 提示: 请检查网络连接和代理设置")
            raise Exception(f"API 连接失败: {e}")

        except requests.exceptions.RequestException as e:
            log_callback(f"   ❌ 请求异常!")
            log_callback(f"   ❗ 错误类型: {type(e).__name__}")
            log_callback(f"   ❗ 错误信息: {str(e)}")
            raise Exception(f"API 请求异常: {e}")

        except Exception as e:
            log_callback(f"   ❌ 未知错误!")
            log_callback(f"   📍 接口地址: {self.base_url}")
            log_callback(f"   🤖 模型: {self.model}")
            log_callback(f"   ❗ 错误: {str(e)}")
            import traceback
            log_callback(f"   📋 堆栈: {traceback.format_exc()}")
            raise Exception(f"API调用失败: {e}")

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

        log_callback(f"\n{'-'*70}")
        log_callback(f"🧠 分析热点趋势")
        log_callback(f"{'-'*70}")
        log_callback(f"📊 分析笔记数: {min(top_n, len(notes))} 条\n")

        # 准备分析数据
        analyze_data = []
        for note in notes[:top_n]:
            analyze_data.append(
                {
                    "title": note.get("title", ""),
                    "desc": note.get("desc", "")[:200],
                    "liked_count": note.get("liked_count", 0),
                    "comment_count": note.get("comment_count", 0),
                    "collected_count": note.get("collected_count", 0),
                    "tags": note.get("tags", [])[:5],
                }
            )

        # 构建系统消息和用户消息
        system_message = {"role": "system", "content": self.XHS_STYLE_PROMPT}

        user_message = {
            "role": "user",
            "content": f"""请对以下小红书爆款笔记进行深度分析：

{json.dumps(analyze_data, ensure_ascii=False, indent=2)}

请从以下几个维度进行专业分析：

1. **高频关键词**（出现3次以上的关键词和话题标签）
2. **情绪价值点**（内容带给用户的情绪价值，如：缓解焦虑、爽感、干货、种草、省钱、颜值等）
3. **爆款标题模式**（常见的爆款标题结构，如：数字法、对比法、悬念法、痛点法等）
4. **内容结构特点**（开头、中间、结尾的写作套路）
5. **视觉呈现趋势**（封面风格、配色、排版等）
6. **爆款底层逻辑**（一句话总结这类内容爆火的核心原因）

请以 JSON 格式输出：
{{
  "top_keywords": ["关键词1", "关键词2", "关键词3"],
  "emotion_points": ["情绪点1", "情绪点2", "情绪点3"],
  "title_patterns": ["模式1", "模式2", "模式3"],
  "content_structure": "内容结构分析...",
  "visual_trends": "视觉趋势分析...",
  "viral_logic": "爆款底层逻辑总结"
}}

只返回 JSON，不要其他内容。""",
        }

        try:
            response_text = self._call_api(
                [system_message, user_message],
                temperature=0.3,
                log_callback=log_callback,
            )

            # 清理可能的 markdown 代码块
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
        log_callback: Optional[Callable] = None,
    ) -> List[Dict]:
        """
        生成新话题，确保图片提示词差异化

        Args:
            analyze_result: 分析结果
            keyword: 原始搜索关键词
            top_n: 生成话题数量
            log_callback: 日志回调

        Returns:
            话题列表
        """
        if log_callback is None:
            log_callback = print

        log_callback(f"\n{'-'*70}")
        log_callback(f"✨ 生成话题")
        log_callback(f"{'-'*70}")
        log_callback(f"📊 数量: {top_n} 个 | 关键词: {keyword}")
        log_callback(f"⏱️  预计: 10-30 秒\n")

        # 构建系统消息和用户消息
        system_message = {"role": "system", "content": self.XHS_STYLE_PROMPT}

        user_message = {
            "role": "user",
            "content": f"""基于以下爆款内容分析报告：

{json.dumps(analyze_result, ensure_ascii=False, indent=2)}

原始关键词：{keyword}

请生成 {top_n} 个全新的、具有爆款潜质的小红书话题。

## 核心要求

每个话题必须**完全不同**，避免同质化：

1. **主题差异化**：从不同角度切入，覆盖不同场景和人群
2. **视觉差异化**：每个话题的图片必须有独特的视觉风格和构图
3. **情绪差异化**：触发不同的情绪反应（焦虑、喜悦、好奇、怀旧等）
4. **标题控制**：标题必须在10-20个中文字以内，简洁有力

## 图片提示词差异化要求（重点）

每个话题的图片提示词必须包含**独特的视觉元素**：

**视觉风格选项（每个话题选一种不同风格）**：
- 扁平插画 + 孟菲斯风格（几何图形、鲜艳色块）
- 3D渲染 + C4D风格（立体、柔和光影）
- 手绘水彩 + 日系清新（柔和、自然纹理）
- 复古胶片 + 港风（颗粒感、怀旧色调）
- 极简主义 + 北欧风（留白、低饱和）
- 国潮风 + 新中式（传统元素、现代设计）
- 赛博朋克 + 霓虹光效（科技、高对比）

**构图差异（每个话题选一种）**：
- 中心对称构图
- 对角线构图
- 三分法构图
- 框架式构图
- 引导线构图

**色调差异（每个话题选一种）**：
- 暖色调（红、橙、黄）
- 冷色调（蓝、绿、紫）
- 马卡龙色系（柔和、甜美）
- 莫兰迪色系（高级、灰调）
- 高对比撞色（视觉冲击力）

**场景差异**：
- 室内/室外
- 白天/夜晚
- 自然/城市
- 静物/人物
- 宏观/微观

## 输出格式

请以 JSON 数组格式输出，每个话题必须包含：

```json
[
  {{
    "title": "标题（10-20个中文字，含1-2个emoji，简洁有力）",
    "content": "正文（150-250字，分段落，含emoji）",
    "tags": "#标签1 #标签2 #标签3",
    "image_prompt": "英文绘图提示词（必须详细描述：1.主体内容 2.视觉风格 3.构图方式 4.色调 5.光影 6.细节元素，60-100词）",
    "visual_style": "标注使用的视觉风格",
    "composition": "标注构图方式",
    "color_tone": "标注色调"
  }}
]
```

**重要提醒**：
- {top_n}个话题的图片提示词**必须完全不同**
- 不能重复使用相同的视觉风格、构图或色调
- 每个提示词都要描述出**独特的画面感**
- 标题必须控制在20个字以内（中文字符）
- 确保提示词具体、详细，便于AI绘图生成差异化图片

只返回 JSON 数组，不要其他内容。""",
        }

        try:
            response_text = self._call_api(
                [system_message, user_message],
                temperature=0.8,
                log_callback=log_callback,
            )

            # 清理可能的 markdown 代码块
            response_text = (
                response_text.replace("```json", "").replace("```", "").strip()
            )

            topics = json.loads(response_text)

            # 验证话题格式并添加默认值
            for i, topic in enumerate(topics):
                required_fields = ["title", "content", "tags", "image_prompt"]
                for field in required_fields:
                    if field not in topic:
                        topic[field] = ""

                # 添加视觉元数据字段（如果不存在）
                if "visual_style" not in topic:
                    topic["visual_style"] = "未标注"
                if "composition" not in topic:
                    topic["composition"] = "未标注"
                if "color_tone" not in topic:
                    topic["color_tone"] = "未标注"

            log_callback(f"\n✅ 成功生成 {len(topics)} 个话题")

            # 打印话题预览（简化版）
            log_callback(f"\n📋 话题预览:")
            for i, topic in enumerate(topics[:5]):  # 只显示前5个
                title = topic.get("title", "无标题")
                log_callback(f"   {i + 1}. {title[:40]}")
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
        进一步优化图片提示词，确保与万相2.6模型完美兼容

        Args:
            topics: 话题列表
            log_callback: 日志回调

        Returns:
            优化后的话题列表
        """
        if log_callback is None:
            log_callback = print

        log_callback(f"🎨 正在优化 {len(topics)} 个图片提示词...")

        enhanced_count = 0

        for i, topic in enumerate(topics):
            try:
                original_prompt = topic.get("image_prompt", "")
                if not original_prompt:
                    continue

                system_message = {
                    "role": "system",
                    "content": "你是一位专业的AI绘图提示词工程师，擅长为万相2.6模型优化英文提示词。",
                }

                user_message = {
                    "role": "user",
                    "content": f"""请将以下图片提示词优化，使其更适合万相2.6模型生成高质量图片：

原始提示词：{original_prompt}
视觉风格：{topic.get("visual_style", "mixed style")}
构图方式：{topic.get("composition", "balanced composition")}
色调：{topic.get("color_tone", "vibrant colors")}

优化要求：
1. 使用英文，60-80个词
2. 包含：主体 + 风格 + 构图 + 色调 + 光影 + 细节
3. 使用具体的视觉描述词汇
4. 适合小红书平台的审美
5. 确保与万相2.6模型的训练数据匹配

直接返回优化后的英文提示词，不要其他内容。""",
                }

                enhanced_prompt = self._call_api(
                    [system_message, user_message],
                    temperature=0.5,
                    enable_thinking=False,  # 提示词优化不需要思考模式，提高效率
                    log_callback=log_callback,
                )
                enhanced_prompt = enhanced_prompt.strip().strip('"').strip("'")

                # 保存原始和优化后的提示词
                topic["image_prompt_original"] = original_prompt
                topic["image_prompt"] = enhanced_prompt
                enhanced_count += 1

                log_callback(f"  ✅ 话题 {i + 1} 提示词已优化")

            except Exception as e:
                log_callback(f"  ⚠️ 话题 {i + 1} 优化失败: {e}")
                continue

        log_callback(f"✅ 成功优化 {enhanced_count}/{len(topics)} 个提示词")
        return topics

    def analyze_and_create_topics(
        self,
        notes: List[Dict],
        keyword: str,
        top_n: int = 10,
        enhance_prompts: bool = True,
        log_callback: Optional[Callable] = None,
    ) -> Dict:
        """
        分析并生成话题（组合方法）

        Args:
            notes: 笔记列表
            keyword: 搜索关键词
            top_n: 生成话题数量
            enhance_prompts: 是否进一步优化图片提示词
            log_callback: 日志回调

        Returns:
            包含分析结果和话题的字典
        """
        # 1. 热点分析
        analyze_result = self.analyze_trends(notes, top_n=50, log_callback=log_callback)

        # 2. 生成话题（使用差异化策略）
        topics = self.generate_topics(
            analyze_result, keyword, top_n=top_n, log_callback=log_callback
        )

        # 3. 进一步优化图片提示词（可选）
        if enhance_prompts:
            topics = self.enhance_image_prompts(topics, log_callback=log_callback)

        return {"analyze_result": analyze_result, "topics": topics, "keyword": keyword}

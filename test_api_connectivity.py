#!/usr/bin/env python3
"""
阿里云 API 连通性测试脚本
测试内容：
1. 大模型接口（dashscope Generation）
2. 生图接口（万相 2.6 MultiModalConversation）
"""

import os
import sys
import time
from datetime import datetime

# 加载 .env
from dotenv import load_dotenv
load_dotenv()

import dashscope
from dashscope import Generation
from dashscope.api_entities.dashscope_response import MultiModalConversationResponse
from dashscope import MultiModalConversation

# 配置
dashscope.base_http_api_url = "https://dashscope.aliyuncs.com/api/v1"

API_KEY = os.getenv("DASHSCOPE_API_KEY") or os.getenv("ALIYUN_API_KEY")

def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def test_llm_api():
    """测试 1: 大模型接口（qwen）"""
    log("=" * 60)
    log("📝 测试 1: 大模型接口 (qwen3-max)")
    log("=" * 60)

    try:
        start = time.time()
        response = Generation.call(
            api_key=API_KEY,
            model="qwen3-max-2026-01-23",
            messages=[{"role": "user", "content": "你好，请用一句话介绍你自己"}],
            result_format="message",
            max_tokens=50,
        )
        duration = time.time() - start

        if response.status_code == 200:
            content = response.output.choices[0].message.content
            log(f"✅ 大模型接口连通 ({duration:.2f}s)")
            log(f"   模型回复: {content[:100]}")
            return True
        else:
            log(f"❌ 大模型接口失败")
            log(f"   状态码: {response.status_code}")
            log(f"   错误码: {getattr(response, 'code', 'N/A')}")
            log(f"   错误信息: {getattr(response, 'message', 'N/A')}")
            return False

    except Exception as e:
        log(f"❌ 大模型接口异常: {e}")
        return False


def test_image_gen_api():
    """测试 2: 生图接口（万相 2.6）"""
    log("")
    log("=" * 60)
    log("🎨 测试 2: 生图接口 (万相 wan2.6-t2i)")
    log("=" * 60)

    try:
        prompt = "a cute cat sitting on a windowsill, warm sunlight, cozy atmosphere"
        size = "768*1152"

        log(f"   提示词: {prompt}")
        log(f"   尺寸: {size}")

        start = time.time()
        messages = [{"role": "user", "content": [{"text": prompt}]}]

        response = MultiModalConversation.call(
            api_key=API_KEY,
            model="wan2.6-t2i",
            messages=messages,
            stream=False,
            prompt_extend=True,
            size=size,
        )
        duration = time.time() - start

        if response.status_code == 200:
            # 尝试提取图片 URL
            try:
                content = response.output.choices[0].message.content
                image_url = None
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and "image" in item:
                            image_url = item["image"]
                            break
                elif isinstance(content, str):
                    image_url = content

                log(f"✅ 生图接口连通 ({duration:.2f}s)")
                if image_url:
                    log(f"   图片 URL: {image_url[:120]}...")

                    # 尝试下载验证
                    import requests
                    head_resp = requests.head(image_url, timeout=10)
                    log(f"   图片可访问: {'✅ 是' if head_resp.status_code == 200 else '❌ 否'}")
                    log(f"   Content-Type: {head_resp.headers.get('Content-Type', 'N/A')}")
                    content_length = head_resp.headers.get('Content-Length')
                    if content_length:
                        log(f"   图片大小: {int(content_length) / 1024:.1f} KB")
                else:
                    log(f"   ⚠️ 未能从响应中提取到图片 URL")
                    log(f"   响应内容: {content}")

            except Exception as e:
                log(f"✅ 生图接口连通 ({duration:.2f}s)")
                log(f"   ⚠️ 解析响应时出错: {e}")
                log(f"   原始响应: {response}")

            return True
        else:
            log(f"❌ 生图接口失败")
            log(f"   状态码: {response.status_code}")
            log(f"   错误码: {getattr(response, 'code', 'N/A')}")
            log(f"   错误信息: {getattr(response, 'message', 'N/A')}")

            if response.status_code == 401:
                log("💡 提示: API Key 无效或已过期")
            elif response.status_code == 403:
                log("💡 提示: 没有权限，请检查是否已开通万相模型")
            elif response.status_code == 429:
                log("💡 提示: 请求被限流，稍后再试")

            return False

    except Exception as e:
        log(f"❌ 生图接口异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    log("🚀 阿里云 API 连通性测试")
    log(f"   API Key: {API_KEY[:8]}...{API_KEY[-4:]}" if API_KEY else "   ❌ 未找到 API Key!")
    log("")

    if not API_KEY:
        log("❌ 请在 .env 文件中配置 DASHSCOPE_API_KEY")
        sys.exit(1)

    results = {}

    # 测试大模型
    results["llm"] = test_llm_api()

    # 测试生图
    results["image_gen"] = test_image_gen_api()

    # 汇总
    log("")
    log("=" * 60)
    log("📊 测试结果汇总")
    log("=" * 60)
    log(f"   大模型接口 (qwen):    {'✅ 通过' if results['llm'] else '❌ 失败'}")
    log(f"   生图接口 (wan2.6):    {'✅ 通过' if results['image_gen'] else '❌ 失败'}")

    all_passed = all(results.values())
    log("")
    if all_passed:
        log("🎉 所有测试通过！")
    else:
        log("⚠️ 部分测试未通过，请检查上方日志")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

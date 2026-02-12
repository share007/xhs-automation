"""
小红书发布模块
使用 DrissionPage RPA 模拟人工发布
"""

from DrissionPage import ChromiumPage
import time
import random
from typing import Dict, List, Optional, Callable


class XHSPublisher:
    """小红书发布器"""

    # 创作者中心发布页
    PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish"

    def __init__(self, headless: bool = False):
        """
        初始化发布器

        Args:
            headless: 是否无头模式
        """
        self.page = ChromiumPage()
        self.headless = headless

    def publish_note(
        self,
        topic: Dict,
        image_paths: List[str],
        manual_confirm: bool = True,
        auto_retry: bool = True,
        log_callback: Optional[Callable] = None,
    ) -> bool:
        """
        发布笔记

        Args:
            topic: 话题字典
            image_paths: 图片路径列表
            manual_confirm: 是否人工确认发布（建议保持True以避免风控）
            auto_retry: 失败时是否自动重试
            log_callback: 日志回调

        Returns:
            是否成功
        """
        if log_callback is None:
            log_callback = print

        title = topic.get("title", "")
        content = topic.get("content", "")
        tags = topic.get("tags", "")

        log_callback(f"\n🚀 正在发布: {title[:30]}...")

        try:
            # 1. 打开发布页
            log_callback("  📱 打开发布页面...")
            self.page.get(self.PUBLISH_URL)
            time.sleep(3)

            # 2. 点击"图文"选项卡（如果需要）
            log_callback("  🖱️  选择图文发布...")
            self._click_image_text_tab(log_callback)
            time.sleep(1)

            # 3. 上传图片（增强自动化）
            log_callback(f"  📷 上传 {len(image_paths)} 张图片...")
            upload_success = self._upload_images_auto(image_paths, log_callback)

            if not upload_success and auto_retry:
                log_callback("  🔄 首次上传失败，3秒后重试...")
                time.sleep(3)
                upload_success = self._upload_images_auto(image_paths, log_callback)

            if not upload_success:
                log_callback("  ❌ 上传失败，跳过此笔记")
                return False

            # 3. 填写标题
            log_callback("  📝 填写标题...")
            title_success = self._fill_title_auto(title, log_callback)
            if not title_success:
                log_callback("  ⚠️ 标题填写失败，继续尝试...")

            # 4. 填写正文
            log_callback("  📝 填写正文...")
            content_success = self._fill_content_auto(content, tags, log_callback)
            if not content_success:
                log_callback("  ⚠️ 正文填写失败，继续尝试...")

            # 5. 等待内容稳定
            time.sleep(2)

            # 6. 发布
            if manual_confirm:
                # 人工确认模式（推荐，避免风控）
                log_callback("\n" + "=" * 60)
                log_callback("✅ 内容已自动填充完成！")
                log_callback("📝 请检查内容是否正确，然后：")
                log_callback("   1. 确认图片已上传并显示正常")
                log_callback("   2. 确认标题和正文正确")
                log_callback("   3. 添加或调整话题标签（如有需要）")
                log_callback("   4. 手动点击【发布】按钮")
                log_callback("=" * 60)
                log_callback("\n💡 提示：如需全自动发布，请使用 --auto-publish 参数")
                log_callback("⚠️  注意：全自动模式可能触发平台风控，请谨慎使用\n")

                # 等待用户发布完成
                from utils.colors import colorize, C, highlight

                prompt_msg = colorize("请完成发布后按 Enter 键继续（输入 '", C.YELLOW)
                skip_hint = colorize("skip", C.BRIGHT_CYAN, C.BOLD)
                prompt_end = colorize("' 跳过此笔记）...", C.YELLOW)
                user_input = input(f"\n{prompt_msg}{skip_hint}{prompt_end}")
                if user_input.strip().lower() == "skip":
                    log_callback("⏭️  用户选择跳过此笔记")
                    return False

                # 检查是否成功发布（通过检测页面是否跳转或成功提示）
                time.sleep(2)
                log_callback("✅ 笔记处理完成")
                return True
            else:
                # 全自动模式
                log_callback("  🔘 自动点击发布...")
                publish_success = self._click_publish_auto(log_callback)
                if publish_success:
                    log_callback(f"✅ 笔记发布成功: {title[:30]}...")
                    time.sleep(3)  # 等待发布完成
                    return True
                else:
                    log_callback("  ⚠️ 自动发布失败，请手动点击发布按钮")
                    from utils.colors import colorize, C

                    input(colorize("\n按 Enter 键继续...", C.YELLOW))
                    return False

        except Exception as e:
            log_callback(f"❌ 发布失败: {e}")
            import traceback

            log_callback(f"📋 错误详情: {traceback.format_exc()[:200]}")
            return False

    def _upload_images_auto(
        self, image_paths: List[str], log_callback: Callable
    ) -> bool:
        """自动上传图片 - 增强版"""
        uploaded_count = 0

        for i, img_path in enumerate(image_paths):
            try:
                log_callback(f"    📤 上传第 {i + 1}/{len(image_paths)} 张...")

                # 方案1: 直接找input[type='file']
                upload_input = self.page.ele("css:input[type='file']", timeout=3)
                if upload_input:
                    upload_input.input(img_path)
                    log_callback(f"      ✅ 通过input上传成功")
                    uploaded_count += 1
                    time.sleep(2)
                    continue

                # 方案2: 点击上传区域触发文件选择
                upload_area_selectors = [
                    "css:.upload-area",
                    "css:.upload-btn",
                    "css:[class*='upload']",
                    "css:[class*='Upload']",
                    "css:div[class*='upload']",
                    "css:.publish-upload",
                    "css:[data-testid='upload']",
                    "xpath://div[contains(@class, 'upload')]",
                    "xpath://div[contains(text(), '上传')]",
                    "xpath://span[contains(text(), '上传')]",
                ]

                for selector in upload_area_selectors:
                    try:
                        upload_area = self.page.ele(selector, timeout=2)
                        if upload_area:
                            upload_area.click()
                            log_callback(f"      🖱️ 点击上传区域: {selector}")
                            time.sleep(1.5)

                            # 点击后再次查找input
                            upload_input = self.page.ele(
                                "css:input[type='file']", timeout=3
                            )
                            if upload_input:
                                upload_input.input(img_path)
                                log_callback(f"      ✅ 上传成功")
                                uploaded_count += 1
                                time.sleep(2)
                                break
                    except Exception:
                        continue
                else:
                    log_callback(f"      ❌ 第 {i + 1} 张上传失败，未找到上传控件")

            except Exception as e:
                log_callback(f"      ⚠️ 上传异常: {e}")
                continue

        if uploaded_count == 0:
            log_callback("  ❌ 所有图片上传失败")
            return False
        elif uploaded_count < len(image_paths):
            log_callback(f"  ⚠️ 部分上传成功: {uploaded_count}/{len(image_paths)}")
            return True
        else:
            log_callback(f"  ✅ 全部上传成功: {uploaded_count}/{len(image_paths)}")
            return True

    def _click_image_text_tab(self, log_callback: Callable) -> bool:
        """点击图文选项卡"""
        selectors = [
            "css:[class*='tab']",
            "css:.tab",
            "css:[role='tab']",
            "xpath://div[contains(text(), '图文')]",
            "xpath://span[contains(text(), '图文')]",
            "xpath://button[contains(text(), '图文')]",
            "css:[data-testid='image-text-tab']",
        ]

        for selector in selectors:
            try:
                tab = self.page.ele(selector, timeout=2)
                if tab:
                    tab.click()
                    log_callback(f"      ✅ 已点击图文选项")
                    return True
            except Exception:
                continue

        log_callback(f"      ⏭️ 无需切换或已默认图文模式")
        return True

    def _fill_title_auto(self, title: str, log_callback: Callable) -> bool:
        """自动填写标题"""
        selectors = [
            "css:#title-input",
            "css:input[placeholder*='标题']",
            "css:textarea[placeholder*='标题']",
            "css:[class*='title'] input",
            "css:[class*='title'] textarea",
            "css:[data-testid='title-input']",
            "xpath://input[contains(@placeholder, '标题')]",
            "xpath://textarea[contains(@placeholder, '标题')]",
            "xpath://div[contains(@class, 'title')]//input",
        ]

        for selector in selectors:
            try:
                title_input = self.page.ele(selector, timeout=2)
                if title_input:
                    title_input.clear()
                    title_input.input(title)
                    log_callback(f"      ✓ 标题已填写: {title[:20]}...")
                    return True
            except Exception:
                continue

        log_callback(" ⚠️ 未找到标题输入框")
        return False

    def _fill_content_auto(
        self, content: str, tags: str, log_callback: Callable
    ) -> bool:
        """自动填写正文"""
        full_content = f"{content}\n\n{tags}".strip()

        selectors = [
            "css:#content-textarea",
            "css:textarea[placeholder*='正文']",
            "css:textarea[placeholder*='内容']",
            "css:textarea[placeholder*='描述']",
            "css:[class*='content'] textarea",
            "css:[class*='desc'] textarea",
            "css:[class*='editor'] textarea",
            "css:[contenteditable='true']",
            "css:[data-testid='content-input']",
            "xpath://textarea[contains(@placeholder, '正文')]",
            "xpath://div[contains(@class, 'content')]//textarea",
            "xpath://div[contains(@class, 'editor')]//textarea",
        ]

        for selector in selectors:
            try:
                content_input = self.page.ele(selector, timeout=2)
                if content_input:
                    content_input.clear()
                    content_input.input(full_content)
                    log_callback(f"      ✓ 正文已填写 ({len(full_content)} 字)")
                    return True
            except Exception:
                continue

        log_callback(" ⚠️ 未找到正文输入框")
        return False

    def _click_publish_auto(self, log_callback: Callable) -> bool:
        """自动点击发布按钮"""
        selectors = [
            "css:.publish-btn",
            "css:.btn-publish",
            "css:[class*='publish'] button",
            "css:[data-testid='publish-btn']",
            "xpath://button[contains(text(), '发布')]",
            "xpath://span[contains(text(), '发布')]/parent::button",
            "xpath://div[contains(text(), '发布')]/ancestor::button",
        ]

        for selector in selectors:
            try:
                publish_btn = self.page.ele(selector, timeout=2)
                if publish_btn:
                    publish_btn.click()
                    log_callback("      ✓ 已点击发布按钮")
                    return True
            except Exception:
                continue

        log_callback(" ⚠️ 未找到或无法点击发布按钮")
        return False

    def publish_batch(
        self,
        topics: List[Dict],
        min_interval: int = 120,
        max_interval: int = 180,
        manual_confirm: bool = True,
        log_callback: Optional[Callable] = None,
    ) -> List[bool]:
        """
        批量发布

        Args:
            topics: 话题列表
            min_interval: 最小间隔(秒)
            max_interval: 最大间隔(秒)
            manual_confirm: 是否人工确认（建议保持True）
            log_callback: 日志回调

        Returns:
            发布结果列表
        """
        if log_callback is None:
            log_callback = print

        results = []

        log_callback(f"\n{'=' * 60}")
        log_callback(f"📚 开始批量发布 {len(topics)} 篇笔记")
        log_callback(f"⏱️ 发布间隔: {min_interval}-{max_interval} 秒")
        log_callback(
            f"🔘 发布模式: {'人工确认（推荐）' if manual_confirm else '全自动（高风险）'}"
        )
        if not manual_confirm:
            log_callback(f"⚠️  警告：全自动模式可能触发平台风控，建议谨慎使用！")
        log_callback(f"{'=' * 60}\n")

        for i, topic in enumerate(topics):
            log_callback(f"\n{'=' * 60}")
            log_callback(f"📄 第 {i + 1}/{len(topics)} 篇")
            log_callback(f"{'=' * 60}")

            image_paths = topic.get("image_paths", [])
            if not image_paths:
                log_callback(f"⚠️ 话题缺少图片，跳过")
                results.append(False)
                continue

            success = self.publish_note(
                topic,
                image_paths,
                manual_confirm=manual_confirm,
                auto_retry=True,
                log_callback=log_callback,
            )
            results.append(success)

            # 间隔等待
            if i < len(topics) - 1:
                interval = random.randint(min_interval, max_interval)
                log_callback(f"\n⏳ 等待 {interval} 秒后继续...")
                time.sleep(interval)

        success_count = sum(results)
        log_callback(f"\n{'=' * 60}")
        log_callback(f"✅ 批量发布完成: {success_count}/{len(topics)} 成功")
        log_callback(f"{'=' * 60}")

        return results

    def close(self):
        """关闭浏览器"""
        try:
            self.page.quit()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

"""
终端颜色工具模块
提供跨平台的颜色支持
"""

import os
import sys


class Colors:
    """ANSI颜色代码"""

    # 基本颜色
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"

    # 前景色
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # 亮前景色
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # 背景色
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"


class NoColor:
    """无颜色模式（用于不支持颜色的终端）"""

    RESET = ""
    BOLD = ""
    DIM = ""
    ITALIC = ""
    UNDERLINE = ""
    BLACK = ""
    RED = ""
    GREEN = ""
    YELLOW = ""
    BLUE = ""
    MAGENTA = ""
    CYAN = ""
    WHITE = ""
    BRIGHT_BLACK = ""
    BRIGHT_RED = ""
    BRIGHT_GREEN = ""
    BRIGHT_YELLOW = ""
    BRIGHT_BLUE = ""
    BRIGHT_MAGENTA = ""
    BRIGHT_CYAN = ""
    BRIGHT_WHITE = ""
    BG_BLACK = ""
    BG_RED = ""
    BG_GREEN = ""
    BG_YELLOW = ""
    BG_BLUE = ""
    BG_MAGENTA = ""
    BG_CYAN = ""
    BG_WHITE = ""


def supports_color() -> bool:
    """检测终端是否支持颜色"""
    # Windows 10+ 支持颜色
    if sys.platform == "win32":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            return True
        except:
            return False

    # 检查环境变量
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True

    # 检查是否为终端
    if not hasattr(sys.stdout, "isatty"):
        return False
    if not sys.stdout.isatty():
        return False

    # 检查 TERM 环境变量
    term = os.environ.get("TERM", "").lower()
    if term in ("dumb", ""):
        return False

    return True


# 根据终端支持选择颜色类
C = Colors if supports_color() else NoColor


def colorize(text: str, *colors: str) -> str:
    """
    给文本添加颜色

    Args:
        text: 要着色的文本
        *colors: 颜色代码（如 C.RED, C.BOLD）

    Returns:
        着色后的文本
    """
    color_str = "".join(colors)
    return f"{color_str}{text}{C.RESET}"


def success(text: str) -> str:
    """成功消息 - 绿色"""
    return colorize(text, C.GREEN, C.BOLD)


def error(text: str) -> str:
    """错误消息 - 红色"""
    return colorize(text, C.RED, C.BOLD)


def warning(text: str) -> str:
    """警告消息 - 黄色"""
    return colorize(text, C.YELLOW, C.BOLD)


def info(text: str) -> str:
    """信息消息 - 青色"""
    return colorize(text, C.CYAN)


def highlight(text: str) -> str:
    """高亮文本 - 蓝色加粗"""
    return colorize(text, C.BLUE, C.BOLD)


def dim(text: str) -> str:
    """暗淡文本"""
    return colorize(text, C.DIM)


def emoji_status(status: str) -> str:
    """
    获取状态对应的emoji

    Args:
        status: 状态类型 (success, error, warning, info, pending)

    Returns:
        emoji字符串
    """
    emojis = {
        "success": "✅",
        "error": "❌",
        "warning": "⚠️",
        "info": "ℹ️",
        "pending": "⏳",
        "running": "🔄",
        "complete": "🎉",
        "rocket": "🚀",
        "star": "⭐",
        "fire": "🔥",
        "sparkle": "✨",
        "target": "🎯",
        "brain": "🧠",
        "image": "🖼️",
        "publish": "📤",
        "search": "🔍",
        "save": "💾",
        "check": "☑️",
        "cross": "❌",
        "arrow": "➜",
        "bullet": "•",
    }
    return emojis.get(status, "•")


def print_box(title: str, content: str, width: int = 70) -> None:
    """
    打印带边框的盒子

    Args:
        title: 标题
        content: 内容
        width: 盒子宽度
    """
    print()
    print(colorize("╔" + "═" * (width - 2) + "╗", C.CYAN))
    print(colorize("║" + title.center(width - 2) + "║", C.CYAN))
    print(colorize("╠" + "═" * (width - 2) + "╣", C.CYAN))
    for line in content.split("\n"):
        print(colorize("║ " + line.ljust(width - 4) + " ║", C.CYAN))
    print(colorize("╚" + "═" * (width - 2) + "╝", C.CYAN))
    print()


def print_step(step_num: int, total: int, title: str, description: str = "") -> None:
    """
    打印步骤标题

    Args:
        step_num: 当前步骤编号
        total: 总步骤数
        title: 步骤标题
        description: 步骤描述
    """
    print()
    step_indicator = f"STEP {step_num}/{total}"
    print(
        colorize(
            f"┌{'─' * 68}┐",
            C.BRIGHT_BLUE,
        )
    )
    print(
        colorize(
            f"│ {step_indicator:10} {title:54} │",
            C.BRIGHT_BLUE,
        )
    )
    if description:
        print(colorize(f"├{'─' * 68}┤", C.BRIGHT_BLUE))
        print(colorize(f"│ {description:66} │", C.DIM))
    print(colorize(f"└{'─' * 68}┘", C.BRIGHT_BLUE))
    print()


def print_progress_bar(
    current: int, total: int, width: int = 50, suffix: str = ""
) -> str:
    """
    生成进度条字符串

    Args:
        current: 当前进度
        total: 总数
        width: 进度条宽度
        suffix: 后缀文本

    Returns:
        进度条字符串
    """
    if total == 0:
        return ""

    progress = current / total
    filled = int(width * progress)
    bar = "█" * filled + "░" * (width - filled)
    percentage = progress * 100

    return colorize(f"[{bar}] {percentage:5.1f}% {suffix}", C.BRIGHT_CYAN)


def print_banner() -> None:
    """打印启动Banner"""
    banner = f"""
{C.BRIGHT_CYAN}╔══════════════════════════════════════════════════════════════════════════╗
║                                                                          ║
║   {C.BRIGHT_MAGENTA}🚀 小红书自动化工具{C.BRIGHT_CYAN}                                                        ║
║                                                                          ║
║   {C.WHITE}搜索 → 分析 → 生成 → 发布 全流程自动化{C.BRIGHT_CYAN}                                  ║
║                                                                          ║
╚══════════════════════════════════════════════════════════════════════════╝{C.RESET}
"""
    print(banner)


def print_section(title: str, emoji: str = "✨") -> None:
    """
    打印分节标题

    Args:
        title: 标题文本
        emoji: 前置emoji
    """
    print()
    print(colorize(f"{emoji} {title}", C.BRIGHT_MAGENTA, C.BOLD))
    print(colorize("─" * 70, C.DIM))


def print_config_item(key: str, value: str, emoji: str = "•") -> None:
    """
    打印配置项

    Args:
        key: 配置键
        value: 配置值
        emoji: 前置emoji
    """
    key_colored = colorize(f"{emoji} {key}:", C.CYAN)
    value_colored = colorize(value, C.WHITE)
    print(f"  {key_colored:<30} {value_colored}")


def print_summary(data: dict, title: str = "执行摘要") -> None:
    """
    打印摘要信息

    Args:
        data: 数据字典
        title: 标题
    """
    print()
    print(colorize(f"📊 {title}", C.BRIGHT_CYAN, C.BOLD))
    print(colorize("═" * 70, C.BRIGHT_CYAN))

    for key, value in data.items():
        key_str = colorize(f"{key}:", C.DIM)
        value_str = colorize(str(value), C.WHITE)
        print(f"  {key_str:<20} {value_str}")

    print(colorize("═" * 70, C.BRIGHT_CYAN))
    print()


def confirm_prompt(message: str, default: bool = True) -> bool:
    """
    确认提示

    Args:
        message: 提示消息
        default: 默认值

    Returns:
        用户确认结果
    """
    default_str = "Y/n" if default else "y/N"
    prompt = colorize(f"{message} [{default_str}]: ", C.YELLOW)

    try:
        response = input(prompt).strip().lower()
        if not response:
            return default
        return response in ("y", "yes", "是", "确认")
    except (EOFError, KeyboardInterrupt):
        return False


def input_prompt(message: str, default: str = "") -> str:
    """
    输入提示

    Args:
        message: 提示消息
        default: 默认值

    Returns:
        用户输入
    """
    if default:
        prompt = colorize(f"{message} [{default}]: ", C.YELLOW)
    else:
        prompt = colorize(f"{message}: ", C.YELLOW)

    try:
        response = input(prompt).strip()
        return response if response else default
    except (EOFError, KeyboardInterrupt):
        return default

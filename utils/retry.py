"""
重试工具模块
提供指数退避 + 随机抖动的重试机制
"""

import time
import random
import functools
from typing import Optional, Callable, Tuple, Type, Any


def call_with_retry(
    func: Callable,
    *args: Any,
    max_retries: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    log_callback: Optional[Callable] = None,
    **kwargs: Any,
) -> Any:
    """
    调用函数并在失败时自动重试（指数退避 + 随机抖动）

    Args:
        func: 要调用的函数
        *args: 位置参数
        max_retries: 最大重试次数（默认3次）
        base_delay: 基础延迟秒数（默认2秒）
        max_delay: 最大延迟秒数（默认60秒）
        backoff_factor: 退避倍数（默认2倍）
        retryable_exceptions: 可重试的异常类型元组
        log_callback: 日志回调函数
        **kwargs: 关键字参数

    Returns:
        函数返回值

    Raises:
        最后一次重试失败时的异常
    """
    log = log_callback or print
    last_exception: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except retryable_exceptions as e:
            last_exception = e
            if attempt < max_retries:
                delay = min(base_delay * (backoff_factor ** attempt), max_delay)
                jitter = random.uniform(0, delay * 0.3)
                total_delay = delay + jitter
                log(f"   ⚠️ 第 {attempt + 1} 次调用失败: {e}")
                log(
                    f"   🔄 {total_delay:.1f}s 后重试"
                    f" ({attempt + 1}/{max_retries})..."
                )
                time.sleep(total_delay)
            else:
                log(f"   ❌ 已重试 {max_retries} 次，仍然失败: {e}")
                raise

    # 理论上不会到达这里，但为了类型安全
    raise last_exception  # type: ignore[misc]


def retry(
    max_retries: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
) -> Callable:
    """
    重试装饰器

    被装饰的函数如果接受 log_callback 关键字参数，会自动用于日志输出。

    Usage:
        @retry(max_retries=3, base_delay=2.0)
        def my_api_call(data, log_callback=None):
            ...

    Args:
        max_retries: 最大重试次数
        base_delay: 基础延迟秒数
        max_delay: 最大延迟秒数
        backoff_factor: 退避倍数
        retryable_exceptions: 可重试的异常类型

    Returns:
        装饰器
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            log = kwargs.get("log_callback") or print
            last_exception: Optional[Exception] = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = min(
                            base_delay * (backoff_factor ** attempt),
                            max_delay,
                        )
                        jitter = random.uniform(0, delay * 0.3)
                        total_delay = delay + jitter
                        log(f"   ⚠️ 第 {attempt + 1} 次调用失败: {e}")
                        log(
                            f"   🔄 {total_delay:.1f}s 后重试"
                            f" ({attempt + 1}/{max_retries})..."
                        )
                        time.sleep(total_delay)
                    else:
                        log(f"   ❌ 已重试 {max_retries} 次，仍然失败: {e}")
                        raise

            raise last_exception  # type: ignore[misc]

        return wrapper

    return decorator

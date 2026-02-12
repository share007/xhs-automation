"""
配置校验模块
使用 Pydantic 进行配置文件类型校验和默认值管理
"""

from typing import Any, Dict, List, Optional

try:
    from pydantic import BaseModel, Field, field_validator, model_validator

    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False


if PYDANTIC_AVAILABLE:

    class AliyunConfig(BaseModel):
        """阿里云百炼配置"""

        api_key: str = Field(
            default="", description="API Key（推荐使用环境变量 DASHSCOPE_API_KEY）"
        )

    class XiaohongshuConfig(BaseModel):
        """小红书账号配置"""

        cookies: Dict[str, Any] = Field(default_factory=dict, description="登录态 Cookie")

    class SearchConfig(BaseModel):
        """搜索配置"""

        default_sort: str = Field(
            default="time_descending",
            description="排序: time_descending(最新), hot(最热), comprehensive(综合)",
        )
        default_note_type: int = Field(default=51, description="笔记类型: 51=图文")
        page_size: int = Field(default=20, ge=1, le=100, description="每页数量")
        max_notes: int = Field(default=50, ge=1, le=500, description="最大获取笔记数")
        min_likes: int = Field(default=10, ge=0, description="最小点赞数过滤（0=不过滤）")

        @field_validator("default_sort")
        @classmethod
        def validate_sort(cls, v: str) -> str:
            valid = ["time_descending", "hot", "comprehensive"]
            if v not in valid:
                raise ValueError(f"排序方式必须是 {valid} 之一，当前值: '{v}'")
            return v

    class ContentConfig(BaseModel):
        """内容生成配置"""

        topic_count: int = Field(default=10, ge=1, le=50, description="生成话题数量")
        images_per_topic: int = Field(
            default=5, ge=1, le=10, description="每个话题生成图片数"
        )
        image_size: str = Field(default="768*1152", description="图片尺寸")

        @field_validator("image_size")
        @classmethod
        def validate_image_size(cls, v: str) -> str:
            valid = [
                "1024*1024",
                "720*1280",
                "1280*720",
                "768*1152",
                "1280*1280",
            ]
            if v not in valid:
                raise ValueError(f"图片尺寸必须是 {valid} 之一，当前值: '{v}'")
            return v

    class PublishConfig(BaseModel):
        """发布配置"""

        min_interval: int = Field(default=120, ge=10, description="最小发布间隔(秒)")
        max_interval: int = Field(default=180, ge=10, description="最大发布间隔(秒)")
        manual_confirm: bool = Field(default=True, description="人工确认发布")

        @model_validator(mode="after")
        def validate_intervals(self) -> "PublishConfig":
            if self.max_interval < self.min_interval:
                raise ValueError(
                    f"max_interval({self.max_interval}) 必须 >= "
                    f"min_interval({self.min_interval})"
                )
            return self

    class RiskControlConfig(BaseModel):
        """风控配置"""

        search_interval: int = Field(default=300, ge=0, description="搜索间隔(秒)")
        max_daily_publish: int = Field(
            default=10, ge=1, le=50, description="每日最大发布数"
        )
        random_delay: bool = Field(default=True, description="启用随机延迟")

    class AppConfig(BaseModel):
        """应用完整配置（根模型）"""

        aliyun: AliyunConfig = Field(default_factory=AliyunConfig)
        xiaohongshu: XiaohongshuConfig = Field(default_factory=XiaohongshuConfig)
        search: SearchConfig = Field(default_factory=SearchConfig)
        content: ContentConfig = Field(default_factory=ContentConfig)
        publish: PublishConfig = Field(default_factory=PublishConfig)
        risk_control: RiskControlConfig = Field(default_factory=RiskControlConfig)

else:
    # Pydantic 不可用时的降级方案
    class AppConfig:  # type: ignore[no-redef]
        """降级配置（不含校验）"""

        def __init__(self, **kwargs: Any):
            self.aliyun = kwargs.get("aliyun", {"api_key": ""})
            self.xiaohongshu = kwargs.get("xiaohongshu", {"cookies": {}})
            self.search = kwargs.get(
                "search",
                {
                    "default_sort": "time_descending",
                    "default_note_type": 51,
                    "max_notes": 50,
                    "min_likes": 10,
                },
            )
            self.content = kwargs.get(
                "content",
                {
                    "topic_count": 10,
                    "images_per_topic": 5,
                    "image_size": "768*1152",
                },
            )
            self.publish = kwargs.get(
                "publish",
                {
                    "min_interval": 120,
                    "max_interval": 180,
                    "manual_confirm": True,
                },
            )
            self.risk_control = kwargs.get(
                "risk_control",
                {
                    "search_interval": 300,
                    "max_daily_publish": 10,
                    "random_delay": True,
                },
            )

        def model_dump(self) -> Dict[str, Any]:
            return {
                "aliyun": self.aliyun,
                "xiaohongshu": self.xiaohongshu,
                "search": self.search,
                "content": self.content,
                "publish": self.publish,
                "risk_control": self.risk_control,
            }


def validate_config(config_dict: Dict[str, Any]) -> AppConfig:
    """
    校验并标准化配置字典

    Args:
        config_dict: 从 YAML 加载的原始配置字典

    Returns:
        校验后的 AppConfig 实例

    Raises:
        ValidationError (pydantic) 或 ValueError: 配置校验失败
    """
    if not isinstance(config_dict, dict):
        config_dict = {}

    return AppConfig(**config_dict)


def config_to_dict(config: AppConfig) -> Dict[str, Any]:
    """
    将 AppConfig 实例转为普通字典（兼容现有代码）

    Args:
        config: AppConfig 实例

    Returns:
        配置字典
    """
    if PYDANTIC_AVAILABLE:
        return config.model_dump()
    else:
        return config.model_dump()

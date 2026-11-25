"""采集适配器接口定义。

设计原则：平台差异全部关在子类内部，上游只认 RawListing。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RawListing(BaseModel):
    """归一化之前的原始挂单。平台能给多少就填多少，其余留 None。"""

    platform: str                                  # BUFF / YOUPIN / C5
    platform_item_id: str                          # 平台内唯一 ID
    price_amount: int = Field(ge=0, description="标价，单位：分")
    fetched_at: datetime
    currency: str = "CNY"

    market_hash_name: str | None = None            # Steam 市场名，跨平台归一主键
    raw_name: str | None = None                    # 平台原始名称
    float_value: float | None = Field(default=None, ge=0.0, le=1.0)
    paint_seed: int | None = None
    seller_id: str | None = None                   # 存哈希，不存明文 ID
    listed_at: datetime | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class MarketCollector(ABC):
    """一个平台一个实例。所有网络请求都必须经过 ctx 的限速器与熔断器。"""

    platform: str

    @abstractmethod
    async def fetch_listings(
        self, platform_goods_id: str, page: int = 1, size: int = 20
    ) -> list[RawListing]:

        """按平台默认排序（一般上架时间倒序）拉一页在售挂单。

        只拉第一页 + 本地去重，是控制请求量的关键，
        不要为了"完整"去翻全量列表。
        """

    @abstractmethod
    async def fetch_detail(
         self, platform_goods_id: str, platform_item_id: str
    ) -> RawListing | None:
            
        """拉单品详情，补齐磨损、印花、改名等信息。"""
    def health(self) -> dict[str, Any]:
        """健康度快照，给看板和告警用。子类按需覆盖。"""
        return {"platform": self.platform, "status": "unknown"}

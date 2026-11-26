"""网易 BUFF 采集适配器（只读）。

真实接口（网页版，2026-11）：
    GET /api/market/goods              搜索饰品 → goods_id
    GET /api/market/goods/sell_order   某个 goods_id 的在售挂单

登录态：本人账号扫码后的 Cookie，由 CredentialStore 解密注入。
只读：不下单、不加购、不调用任何写接口。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from hashlib import sha256
from typing import Any

from adapters.base import MarketCollector, RawListing
from core.http_client import PlatformClient, looks_like_verification

BUFF_BASE = "https://buff.163.com"
GAME = "csgo"
CN_TZ = timezone(timedelta(hours=8))

class BuffApiError(RuntimeError):
    """BUFF 业务码不是 OK，或页面结构不符合预期。"""


def _to_cents(value: Any) -> int:
    """'772.00' → 77200。全程 Decimal，绝不经过 float。"""
    return int((Decimal(str(value)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _seller_hash(platform: str, nickname: str | None) -> str | None:
    """卖家昵称不落明文，只留 32 位哈希。"""
    if not nickname:
        return None
    return sha256(f"{platform}|{nickname}".encode("utf-8")).hexdigest()[:32]


def _parse_listed_at(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=CN_TZ)
    return parsed


def _parse_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if 0.0 <= number <= 1.0 else None

def _clean_raw(item: dict[str, Any]) -> dict[str, Any]:
    """只保留非个人字段；user_id / user_steamid / 昵称 / 资产 ID 不进 raw。"""
    asset = item.get("asset_info") or {}
    info = asset.get("info") or {}
    return {
        "goods_id": item.get("goods_id"),
        "price": item.get("price"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "state": item.get("state"),
        "state_text": item.get("state_text"),
        "tradable_cooldown": item.get("tradable_cooldown"),
        "allow_bargain": item.get("allow_bargain"),
        "fee": item.get("fee"),
        "income": item.get("income"),
        "recent_average_duration": item.get("recent_average_duration"),
        "recent_deliver_rate": item.get("recent_deliver_rate"),
        "appid": item.get("appid"),
        "game": item.get("game"),
        "mode": item.get("mode"),
        "order_type": item.get("order_type"),
        "sticker_premium": item.get("sticker_premium"),
        "asset_info": {
            "paintwear": asset.get("paintwear"),
            "tradable_unfrozen_time": asset.get("tradable_unfrozen_time"),
            "info": {
                "paintseed": info.get("paintseed"),
                "paintindex": info.get("paintindex"),
                "stickers": info.get("stickers") or [],
                "keychains": info.get("keychains") or [],
                "tournament_tags": info.get("tournament_tags") or [],
                "fraudwarnings": info.get("fraudwarnings") or [],
                "icon_url": info.get("icon_url"),
            },
        },
    }

class BuffCollector(MarketCollector):
    platform = "BUFF"

    def __init__(self, client: PlatformClient) -> None:
        self.client = client

    async def fetch_listings(
        self, platform_goods_id: str, page: int = 1, size: int = 20
    ) -> list[RawListing]:
        resp = await self.client.get(
            "/api/market/goods/sell_order",
            params={
                "game": GAME,
                "goods_id": platform_goods_id,
                "page_num": page,
                "page_size": size,
                "sort_by": "default",
                "mode": "",
                "allow_tradable_cooldown": 1,
            },
        )
        if looks_like_verification(resp):
            await self.client.report_fatal("buff verification page")
            raise BuffApiError("命中 BUFF 验证页，已熔断该平台")

        payload = resp.json()
        code = str(payload.get("code", ""))
        if code != "OK":
            if "login" in code.lower() or "session" in code.lower():
                await self.client.report_fatal(f"buff code={code}")
            raise BuffApiError(f"BUFF 返回 code={code}（goods_id={platform_goods_id}）")

        items = (payload.get("data") or {}).get("items") or []
        return [self._parse_item(item) for item in items]

    def _parse_item(self, item: dict[str, Any]) -> RawListing:
        asset = item.get("asset_info") or {}
        info = asset.get("info") or {}
        paintwear = item.get("paintwear") or asset.get("paintwear")
        return RawListing(
            platform=self.platform,
            platform_item_id=str(item.get("id", "")),
            price_amount=_to_cents(item.get("price", "0")),
            fetched_at=datetime.now(timezone.utc),
            currency="CNY",
            market_hash_name=item.get("market_hash_name"),
            raw_name=item.get("name"),
            float_value=_parse_float(paintwear),
            paint_seed=info.get("paintseed"),
            seller_id=_seller_hash(self.platform, (item.get("user") or {}).get("nickname")),
            listed_at=_parse_listed_at(item.get("created_at")),
            raw=_clean_raw(item),
        )

    async def fetch_detail(
        self, platform_goods_id: str, platform_item_id: str
    ) -> RawListing | None:
        """列表接口已返回磨损 / 图案模板 / 卖家，详情按需再补。

        不要在没抓过详情接口样本前猜路径。
        """
        return None

    async def search_goods(
        self, keyword: str, page: int = 1, page_size: int = 20
    ) -> list[dict[str, Any]]:
        """按名称搜饰品，用来建监控清单（market_hash_name ↔ goods_id）。"""
        resp = await self.client.get(
            "/api/market/goods",
            params={
                "game": GAME,
                "page_num": page,
                "page_size": page_size,
                "search": keyword,
                "sort_by": "default",
            },
        )
        payload = resp.json()
        if payload.get("code") != "OK":
            raise BuffApiError(f"搜索返回 code={payload.get('code')}")
        items = (payload.get("data") or {}).get("items") or []
        return [
            {
                "goods_id": str(it.get("id")),
                "name": it.get("name"),
                "market_hash_name": it.get("market_hash_name"),
                "sell_min_price": it.get("sell_min_price"),
            }
            for it in items
        ]

    def health(self) -> dict[str, Any]:
        return self.client.health

if __name__ == "__main__":
    import asyncio

    import httpx

    from core.circuit_breaker import CircuitBreaker
    from core.credentials import Credential
    from core.rate_limiter import RateLimiter

    SAMPLE = {
        "code": "OK",
        "data": {
            "items": [
                {
                    "id": "1234567890123",
                    "price": "772.00",
                    "paintwear": "0.21431234",
                    "asset_info": {
                        "paintwear": "0.21431234",
                        "info": {"paintseed": 421, "stickers": []},
                    },
                    "user": {"nickname": "seller_a", "level": 6},
                    "created_at": 1764130000,
                },
                {
                    "id": "1234567890124",
                    "price": "780.50",
                    "paintwear": "0.3011",
                    "asset_info": {"paintwear": "0.3011", "info": {"paintseed": 88}},
                    "user": {"nickname": "seller_b", "level": 4},
                    "created_at": "2026-11-25 16:40:12",
                },
            ],
            "total_count": 2,
        },
    }

    async def _demo() -> None:
        calls: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append({"path": request.url.path, "params": dict(request.url.params)})
            if request.url.path == "/api/market/goods/sell_order":
                return httpx.Response(200, json=SAMPLE, request=request)
            if request.url.path == "/api/market/goods":
                return httpx.Response(
                    200,
                    json={
                        "code": "OK",
                        "data": {
                            "items": [
                                {
                                    "id": 12345,
                                    "name": "AWP | 二西莫夫 (久经沙场)",
                                    "market_hash_name": "AWP | Asiimov (Field-Tested)",
                                    "sell_min_price": "772.00",
                                }
                            ]
                        },
                    },
                    request=request,
                )
            return httpx.Response(404, json={"code": "NOT_FOUND"}, request=request)

        client = PlatformClient(
            platform="BUFF",
            base_url=BUFF_BASE,
            limiter=RateLimiter(rate_per_sec=20.0, burst=2, jitter_ms=(0, 0)),
            breaker=CircuitBreaker(platform="BUFF"),
            credential=Credential(platform="BUFF", cookies={"session": "fake"}),
            transport=httpx.MockTransport(handler),
        )
        collector = BuffCollector(client)

        listings = await collector.fetch_listings("12345", page=1, size=20)
        assert len(listings) == 2
        assert listings[0].price_amount == 77200
        assert listings[0].float_value == 0.21431234
        assert listings[0].paint_seed == 421
        assert listings[0].seller_id != "seller_a"
        assert listings[1].listed_at is not None
        assert calls[0]["params"]["goods_id"] == "12345"
        print(
            f"[1] 解析 {len(listings)} 条："
            f"到手价=分 {listings[0].price_amount}，float={listings[0].float_value}"
        )

        goods = await collector.search_goods("AWP 二西莫夫")
        assert goods[0]["goods_id"] == "12345"
        print(f"[2] 搜索可用：{goods[0]['market_hash_name']} → goods_id={goods[0]['goods_id']}")

        await client.aclose()

    asyncio.run(_demo())
    print("[OK] buff 自检通过")


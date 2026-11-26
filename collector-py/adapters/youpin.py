"""悠悠有品采集适配器（只读）。

真实接口（网页版，2026-11 采样）：
    POST /api/homepage/pc/goods/market/queryOnSaleCommodityList
    请求体只要 templateId + 分页，没有签名参数；
    认证靠 authorization JWT + 设备标识，由 CredentialStore 解密注入。

登录态：本人账号网页版导出的请求头，约 10 天过期。
只读：不下单、不加购、不调用任何写接口。
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from hashlib import sha256
from typing import Any

from adapters.base import MarketCollector, RawListing
from core.http_client import PlatformClient, looks_like_verification

YOUPIN_BASE = "https://pc-api.youpin898.com"
LIST_PATH = "/api/homepage/pc/goods/market/queryOnSaleCommodityList"
GAME_ID = "730"


class YoupinApiError(RuntimeError):
    """悠悠有品业务码不是 0，或返回结构不符合预期。"""


def _to_cents(value: Any) -> int:
    """'503.49' → 50349。全程 Decimal，绝不经过 float。"""
    return int((Decimal(str(value)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _seller_hash(user_id: Any) -> str | None:
    """平台 userId 不落明文，只留 32 位哈希。"""
    if not user_id:
        return None
    return sha256(f"YOUPIN|{user_id}".encode("utf-8")).hexdigest()[:32]


def _parse_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if 0.0 <= number <= 1.0 else None


def _parse_publish_time(value: Any) -> datetime | None:
    """悠悠有品的 publishTime 是毫秒时间戳。"""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    return datetime.fromtimestamp(number / 1000, tz=timezone.utc)


def _clean_raw(item: dict[str, Any]) -> dict[str, Any]:
    """只保留非个人字段；userId / userNickName / steamId / actions 不进 raw。"""
    return {
        "templateId": item.get("templateId"),
        "commodityNo": item.get("commodityNo"),
        "typeName": item.get("typeName"),
        "haveSticker": item.get("haveSticker"),
        "haveBuZhang": item.get("haveBuZhang"),
        "haveNameTag": item.get("haveNameTag"),
        "abrade": item.get("abrade"),
        "paintSeed": item.get("paintSeed"),
        "stickers": [
            {
                "name": sticker.get("Name"),
                "price": sticker.get("Price"),
                "abrade": sticker.get("Abrade"),
            }
            for sticker in (item.get("stickers") or [])
        ],
    }


class YoupinCollector(MarketCollector):
    platform = "YOUPIN"

    def __init__(self, client: PlatformClient) -> None:
        self.client = client

    async def fetch_listings(
        self, platform_goods_id: str, page: int = 1, size: int = 20
    ) -> list[RawListing]:
        resp = await self.client.post(
            LIST_PATH,
            json={
                "gameId": GAME_ID,
                "listType": "10",
                "templateId": str(platform_goods_id),
                "listSortType": 1,
                "sortType": 0,
                "pageIndex": page,
                "pageSize": size,
            },
            headers={
                "Origin": "https://www.youpin898.com",
                "Referer": "https://www.youpin898.com/",
                "Accept": "application/json, text/plain, */*",
            },
        )
        if looks_like_verification(resp):
            await self.client.report_fatal("youpin verification page")
            raise YoupinApiError("命中悠悠有品验证页，已熔断该平台")

        try:
            payload = resp.json()
        except ValueError as exc:
            await self.client.report_fatal("youpin non-json response")
            raise YoupinApiError("悠悠有品返回非 JSON，已熔断该平台") from exc

        code = payload.get("Code")
        if code not in (0, "0"):
            message = str(payload.get("Msg") or "")
            lower = message.lower()
            if (
                "token" in lower
                or "login" in lower
                or "auth" in lower
                or str(code) in {"401", "403"}
            ):
                await self.client.report_fatal(f"youpin code={code}")
            raise YoupinApiError(
                f"悠悠有品返回 Code={code} Msg={message}（templateId={platform_goods_id}）"
            )

        items = payload.get("Data") or []
        return [self._parse_item(item) for item in items]

    def _parse_item(self, item: dict[str, Any]) -> RawListing:
        return RawListing(
            platform=self.platform,
            platform_item_id=str(item.get("id") or item.get("commodityNo") or ""),
            price_amount=_to_cents(item.get("price", "0")),
            fetched_at=datetime.now(timezone.utc),
            currency="CNY",
            market_hash_name=item.get("commodityHashName"),
            raw_name=item.get("commodityName"),
            float_value=_parse_float(item.get("abrade")),
            paint_seed=item.get("paintSeed"),
            seller_id=_seller_hash(item.get("userId")),
            listed_at=_parse_publish_time(item.get("publishTime")),
            raw=_clean_raw(item),
        )

    async def fetch_detail(
        self, platform_goods_id: str, platform_item_id: str
    ) -> RawListing | None:
        """列表已经给了磨损、图案模板、印花、改名标记，详情接口没采样前不猜路径。"""
        return None

    def health(self) -> dict[str, Any]:
        return self.client.health


if __name__ == "__main__":
    import asyncio
    import json

    import httpx

    from core.circuit_breaker import CircuitBreaker
    from core.credentials import Credential
    from core.rate_limiter import RateLimiter

    SAMPLE = {
        "Code": 0,
        "Msg": "success",
        "Data": [
            {
                "id": 2106704463,
                "commodityNo": "2106704463",
                "templateId": 407,
                "commodityName": "AWP | 二西莫夫 (久经沙场)",
                "commodityHashName": "AWP | Asiimov (Field-Tested)",
                "price": "503.49",
                "abrade": "0.2978457212448120000",
                "paintSeed": 608,
                "publishTime": 1795650517679,
                "haveSticker": 1,
                "haveNameTag": 0,
                "userId": "u-1001",
                "userNickName": "seller_a",
                "stickers": [
                    {"Name": "印花 | 测试", "Price": "1.44", "Abrade": "0"}
                ],
            },
            {
                "id": 2106704464,
                "commodityNo": "2106704464",
                "templateId": 407,
                "commodityName": "AWP | 二西莫夫 (久经沙场)",
                "commodityHashName": "AWP | Asiimov (Field-Tested)",
                "price": "510.00",
                "abrade": "0.31",
                "paintSeed": 88,
                "publishTime": 1795650617679,
                "haveSticker": 0,
                "haveNameTag": 1,
                "userId": "u-1002",
                "userNickName": "seller_b",
                "stickers": [],
            },
        ],
        "TotalCount": 2,
        "HasNext": False,
    }

    async def _demo() -> None:
        seen: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["method"] = request.method
            seen["path"] = request.url.path
            seen["body"] = json.loads(request.content.decode("utf-8"))
            seen["authorization"] = request.headers.get("authorization")
            seen["deviceid"] = request.headers.get("deviceid")
            seen["origin"] = request.headers.get("origin")
            return httpx.Response(200, json=SAMPLE, request=request)

        client = PlatformClient(
            platform="YOUPIN",
            base_url=YOUPIN_BASE,
            limiter=RateLimiter(rate_per_sec=20.0, burst=2, jitter_ms=(0, 0)),
            breaker=CircuitBreaker(platform="YOUPIN"),
            credential=Credential(
                platform="YOUPIN",
                cookies={},
                headers={"authorization": "Bearer test-token", "deviceid": "dev-test"},
            ),
            transport=httpx.MockTransport(handler),
        )
        collector = YoupinCollector(client)

        listings = await collector.fetch_listings("407", page=1, size=20)

        assert seen["method"] == "POST"
        assert seen["path"] == LIST_PATH
        assert seen["body"]["templateId"] == "407"
        assert seen["body"]["pageIndex"] == 1
        assert seen["body"]["pageSize"] == 20
        assert seen["authorization"] == "Bearer test-token"
        assert seen["deviceid"] == "dev-test"
        assert seen["origin"] == "https://www.youpin898.com"
        print("[1] POST 参数与请求头正确：templateId=407，authorization 已注入")

        assert len(listings) == 2
        first = listings[0]
        assert first.price_amount == 50349
        assert first.float_value is not None
        assert abs(first.float_value - 0.297845721244812) < 1e-12
        assert first.paint_seed == 608
        assert first.market_hash_name == "AWP | Asiimov (Field-Tested)"
        assert first.seller_id is not None and len(first.seller_id) == 32
        assert first.seller_id != "u-1001"
        assert first.listed_at is not None
        assert "userId" not in first.raw and "userNickName" not in first.raw
        print(
            f"[2] 解析 {len(listings)} 条：{first.price_amount} 分，"
            f"float={first.float_value}，paintSeed={first.paint_seed}"
        )
        print("[3] 卖家哈希 32 位，raw 不含个人字段")

        await client.aclose()

    asyncio.run(_demo())
    print("[OK] youpin 自检通过")

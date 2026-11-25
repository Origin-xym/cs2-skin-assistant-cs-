"""快照写入 Redis Stream：去重 + 序列化。

Stream 键来自 settings.stream_key，默认 cs2:listings。
每条记录字段：
    platform / item_id / snapshot_at / payload(JSON) / goods_id(可选)

去重规则：同一挂单（platform + item_id）的（价格，卖家哈希）没变就不写。
去重键 {stream}:seen:{platform}:{item_id}，TTL 24 小时——
即使挂单没变，每天也会重发一次，兼作每日全量快照。

这里只负责写，消费与 ack 由 Java 侧 Consumer Group 负责。
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import orjson
from redis.asyncio import Redis

from adapters.base import RawListing
from config import settings

DEDUP_TTL_SEC = 86400      # 24 小时
STREAM_MAXLEN = 100_000    # 近似裁剪，防止 Stream 无限增长


class SnapshotWriter:
    """把 RawListing 推进 Redis Stream，重复挂单自动跳过。"""

    def __init__(
        self,
        client: Redis | None = None,
        stream_key: str | None = None,
        dedup_ttl_sec: int = DEDUP_TTL_SEC,
        maxlen: int = STREAM_MAXLEN,
    ) -> None:
        self._redis = client or Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True,
        )
        self._stream = stream_key or settings.stream_key
        self._dedup_ttl = dedup_ttl_sec
        self._maxlen = maxlen

    def _dedup_key(self, listing: RawListing) -> str:
        return f"{self._stream}:seen:{listing.platform}:{listing.platform_item_id}"

    def _fingerprint(self, listing: RawListing) -> str:
        return f"{listing.price_amount}:{listing.seller_id or '-'}"

    async def write(self, listing: RawListing, goods_id: str | None = None) -> bool:
        """返回 True 表示真的写入了一条，False 表示被去重跳过。"""
        key = self._dedup_key(listing)
        fingerprint = self._fingerprint(listing)

        if await self._redis.get(key) == fingerprint:
            return False

        entry: dict[str, Any] = {
            "platform": listing.platform,
            "item_id": listing.platform_item_id,
            "snapshot_at": listing.fetched_at.isoformat(),
            "payload": orjson.dumps(listing.model_dump(mode="json")).decode("utf-8"),
        }
        if goods_id:
            entry["goods_id"] = goods_id

        await self._redis.xadd(
            self._stream, entry, maxlen=self._maxlen, approximate=True
        )
        await self._redis.set(key, fingerprint, ex=self._dedup_ttl)
        return True

    async def write_many(
        self, listings: Iterable[RawListing], goods_id: str | None = None
    ) -> dict[str, int]:
        written = skipped = 0
        for listing in listings:
            if await self.write(listing, goods_id=goods_id):
                written += 1
            else:
                skipped += 1
        return {"written": written, "skipped": skipped}

    async def aclose(self) -> None:
        await self._redis.aclose()

if __name__ == "__main__":
    import asyncio
    import uuid
    from datetime import datetime, timezone

    async def _demo() -> None:
        stream = f"cs2:test:{uuid.uuid4().hex[:8]}"
        client = Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True,
        )
        writer = SnapshotWriter(client=client, stream_key=stream, dedup_ttl_sec=60)
        listing = RawListing(
            platform="BUFF",
            platform_item_id="1234567890123",
            price_amount=77200,
            fetched_at=datetime.now(timezone.utc),
            market_hash_name="AWP | Asiimov (Field-Tested)",
            float_value=0.2143,
            seller_id="abc123",
            raw={"id": "1234567890123", "price": "772.00"},
        )

        assert await writer.write(listing, goods_id="12345") is True
        assert await writer.write(listing, goods_id="12345") is False
        print("[1] 同价同卖家的重复挂单被跳过")

        cheaper = listing.model_copy(update={"price_amount": 76000})
        assert await writer.write(cheaper, goods_id="12345") is True
        print("[2] 价格变化会重新落一条")

        length = await client.xlen(stream)
        assert length == 2, length
        entries = await client.xrange(stream, "-", "+")
        fields = entries[-1][1]
        assert fields["platform"] == "BUFF"
        assert fields["goods_id"] == "12345"
        payload = orjson.loads(fields["payload"])
        assert payload["price_amount"] == 76000
        print(f"[3] Stream 共 {length} 条，最后一条 payload 反序列化正常")

        await client.delete(stream, writer._dedup_key(listing))
        await client.aclose()

    asyncio.run(_demo())
    print("[OK] snapshot_writer 自检通过")

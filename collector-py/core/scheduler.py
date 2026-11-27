"""采集调度：每轮把“清单 → 请求 → 快照”串起来。

一轮的流程：
1. 重新加载监控清单（文件坏了保留旧版）；
2. 每个平台独立并发执行，互不拖累；
3. 平台内按标的顺序拉第一页，节奏由 RateLimiter 兜住；
4. CircuitOpenError / PlatformBlockedError → 该平台本轮直接结束；
5. 单条失败只记日志，不影响同平台其他标的。

多进程时用 Redis 锁 collector:lock:{platform} 保证同平台只有一个采集者。
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any
from loguru import logger
from redis.asyncio import Redis

from adapters.base import MarketCollector
from config import settings
from core.circuit_breaker import CircuitOpenError
from core.http_client import PlatformBlockedError
from core.snapshot_writer import SnapshotWriter
from core.watchlist import WatchList, WatchListError

LOCK_PREFIX = "collector:lock"
LOCK_PREFIX = "collector:lock"
HEARTBEAT_PREFIX = "collector:heartbeat"
HEARTBEAT_TTL_SEC = 180


class CollectorScheduler:
    def __init__(
        self,
        watchlist: WatchList,
        collectors: dict[str, MarketCollector],
        writer: SnapshotWriter,
        *,
        poll_interval: int | None = None,
        page_size: int = 20,
        lock_client: Redis | None = None,
        lock_ttl_sec: int = 120,
    ) -> None:
        self._watchlist = watchlist
        self._collectors = collectors
        self._writer = writer
        self._interval = poll_interval or settings.poll_interval
        self._page_size = page_size
        self._lock_client = lock_client
        self._lock_ttl = lock_ttl_sec

    async def run(self, stop_event: asyncio.Event | None = None) -> None:
        stop_event = stop_event or asyncio.Event()
        logger.info(f"采集调度启动：{len(self._collectors)} 个平台，周期 {self._interval}s")
        while not stop_event.is_set():
            started = time.monotonic()
            await self.run_once()
            wait = max(0.0, self._interval - (time.monotonic() - started))
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=wait)
            except asyncio.TimeoutError:
                continue

    async def run_once(self) -> list[dict[str, Any]]:
        try:
            count = self._watchlist.reload()
            logger.info(f"清单已加载：{count} 个标的")
        except WatchListError as exc:
            logger.error(f"清单加载失败，沿用上一版：{exc}")

        tasks = [
            self._collect_platform(platform, self._watchlist.for_platform(platform))
            for platform in self._collectors
        ]
        results = await asyncio.gather(*tasks)
        for stat in results:
            logger.info(f"[{stat['platform']}] {stat['summary']}")
        return results

    async def _collect_platform(self, platform: str, items: list) -> dict[str, Any]:
        stats: dict[str, Any] = {
            "platform": platform,
            "items": len(items),
            "written": 0,
            "skipped": 0,
            "errors": 0,
            "summary": "无标的",
        }
        if not items:
            await self._write_heartbeat(platform, stats)
            return stats

        if not await self._acquire_lock(platform):
            stats["summary"] = "未拿到平台锁，本轮跳过"
            return stats

        try:
            for item in items:
                goods_id = item.goods_id_for(platform)
                try:
                    listings = await self._collectors[platform].fetch_listings(
                        goods_id, page=1, size=self._page_size
                    )
                    if item.market_hash_name:
                        for listing in listings:
                            if not listing.market_hash_name:
                                listing.market_hash_name = item.market_hash_name

                except CircuitOpenError as exc:
                    stats["summary"] = f"熔断中，平台本轮结束：{exc}"
                    return stats
                except PlatformBlockedError as exc:
                    stats["summary"] = f"平台拦截，本轮结束：{exc}"
                    return stats
                except Exception as exc:
                    stats["errors"] += 1
                    logger.exception(f"[{platform}] {item.market_hash_name} 采集失败：{exc}")
                    continue

                try:
                    result = await self._writer.write_many(listings, goods_id=goods_id)
                except Exception as exc:
                    stats["errors"] += 1
                    logger.error(f"[{platform}] 写入 Stream 失败：{exc}")
                    continue

                stats["written"] += result["written"]
                stats["skipped"] += result["skipped"]
                logger.debug(
                    f"[{platform}] {item.market_hash_name}: {len(listings)} 条，"
                    f"新写 {result['written']}，去重 {result['skipped']}"
                )

            stats["summary"] = (
                f"标的 {stats['items']}，新写 {stats['written']}，"
                f"去重 {stats['skipped']}，错误 {stats['errors']}"
            )
            return stats
        finally:
            await self._write_heartbeat(platform, stats)
            await self._release_lock(platform)


    async def _write_heartbeat(self, platform: str, stats: dict[str, Any]) -> None:
        if self._lock_client is None:
            return

        ttl_sec = max(HEARTBEAT_TTL_SEC, int(self._interval * 3))
        payload = {
            "platform": platform,
            "at": datetime.now(timezone.utc).isoformat(),
            "ttl_sec": ttl_sec,
            "items": stats["items"],
            "written": stats["written"],
            "skipped": stats["skipped"],
            "errors": stats["errors"],
            "summary": stats["summary"],
        }
        try:
            await self._lock_client.set(
                f"{HEARTBEAT_PREFIX}:{platform}",
                json.dumps(payload, ensure_ascii=False),
                ex=ttl_sec,
            )
        except Exception as exc:
            logger.warning(f"[{platform}] 写心跳失败：{exc}")


    async def _acquire_lock(self, platform: str) -> bool:
        if self._lock_client is None:
            return True
        try:
            acquired = await self._lock_client.set(
                f"{LOCK_PREFIX}:{platform}", "1", nx=True, ex=self._lock_ttl
            )
            return bool(acquired)
        except Exception as exc:
            logger.error(f"[{platform}] 获取锁失败：{exc}")
            return False

    async def _release_lock(self, platform: str) -> None:
        if self._lock_client is None:
            return
        try:
            await self._lock_client.delete(f"{LOCK_PREFIX}:{platform}")
        except Exception as exc:
            logger.warning(f"[{platform}] 释放锁失败（等 TTL 自动过期）：{exc}")


if __name__ == "__main__":
    import asyncio
    from datetime import datetime, timezone

    from adapters.base import RawListing
    from core.watchlist import WatchItem

    logger.remove()  # 自检时关掉 loguru 输出，只看 print

    class FakeWatchList:
        def __init__(self, items: list[WatchItem]) -> None:
            self._items = items

        def reload(self) -> int:
            return len(self._items)

        def for_platform(self, platform: str) -> list[WatchItem]:
            return [
                item
                for item in self._items
                if item.enabled and item.goods_id_for(platform)
            ]

    class FakeWriter:
        def __init__(self) -> None:
            self.calls: list[tuple[str | None, int]] = []

        async def write_many(self, listings, goods_id=None):
            self.calls.append((goods_id, len(list(listings))))
            return {"written": len(listings), "skipped": 0}

    class FakeCollector(MarketCollector):
        platform = "BUFF"

        def __init__(self, fail_on: str | None = None, error: Exception | None = None) -> None:
            self.fail_on = fail_on
            self.error = error

        async def fetch_listings(self, platform_goods_id, page=1, size=20):
            if self.fail_on and platform_goods_id == self.fail_on:
                raise self.error  # type: ignore[misc]
            return [
                RawListing(
                    platform="BUFF",
                    platform_item_id=f"{platform_goods_id}-1",
                    price_amount=100,
                    fetched_at=datetime.now(timezone.utc),
                )
            ]

        async def fetch_detail(self, platform_goods_id, platform_item_id):
            return None

    class FakeLockClient:
        def __init__(self) -> None:
            self.held: set[str] = set()

        async def set(self, key, value, nx=False, ex=None):
            if key in self.held:
                return None
            self.held.add(key)
            return True

        async def delete(self, key):
            self.held.discard(key)

    def make_items() -> list[WatchItem]:
        return [
            WatchItem("AWP | Asiimov (Field-Tested)", "AWP 二西莫夫", {"BUFF": "111"}),
            WatchItem("AK-47 | Redline (Field-Tested)", "AK 红线", {"BUFF": "222"}),
            WatchItem("M4A1-S | Printstream (Field-Tested)", "M4 印花集", {"YOUPIN": "333"}),
        ]

    async def _demo() -> None:
        writer = FakeWriter()
        scheduler = CollectorScheduler(
            FakeWatchList(make_items()), {"BUFF": FakeCollector()}, writer
        )
        stats = await scheduler.run_once()
        assert len(writer.calls) == 2
        assert stats[0]["written"] == 2
        print(f"[1] 正常轮次：{stats[0]['summary']}")

        writer = FakeWriter()
        scheduler = CollectorScheduler(
            FakeWatchList(make_items()),
            {"BUFF": FakeCollector(fail_on="111", error=RuntimeError("parse failed"))},
            writer,
        )
        stats = await scheduler.run_once()
        assert stats[0]["errors"] == 1
        assert len(writer.calls) == 1
        print(f"[2] 单条失败继续跑：{stats[0]['summary']}")

        writer = FakeWriter()
        scheduler = CollectorScheduler(
            FakeWatchList(make_items()),
            {"BUFF": FakeCollector(fail_on="111", error=CircuitOpenError("BUFF", 30.0, "test"))},
            writer,
        )
        stats = await scheduler.run_once()
        assert writer.calls == []
        assert "熔断" in stats[0]["summary"]
        print(f"[3] 熔断跳过：{stats[0]['summary']}")

        lock = FakeLockClient()
        await lock.set("collector:lock:BUFF", "other", nx=True, ex=60)
        writer = FakeWriter()
        scheduler = CollectorScheduler(
            FakeWatchList(make_items()), {"BUFF": FakeCollector()}, writer, lock_client=lock
        )
        stats = await scheduler.run_once()
        assert "锁" in stats[0]["summary"]
        assert writer.calls == []
        print(f"[4] 锁被占用：{stats[0]['summary']}")

    asyncio.run(_demo())
    print("[OK] scheduler 自检通过")

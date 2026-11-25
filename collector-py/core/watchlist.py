"""监控清单：第一版读本地 JSON，后续可换 Redis / 接口。

清单结构（data/watchlist.json）：

    {
      "version": 1,
      "items": [
        {
          "market_hash_name": "AWP | Asiimov (Field-Tested)",
          "display_name": "AWP | 二西莫夫（久经沙场）",
          "platform_goods_ids": {"BUFF": "12345", "YOUPIN": "67890"},
          "enabled": true
        }
      ]
    }

宁可启动失败，也不要带着一份格式错误的清单去扫。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import settings

SUPPORTED_PLATFORMS = ("BUFF", "YOUPIN", "C5")
FILE_VERSION = 1

class WatchListError(RuntimeError):
    """清单文件格式不对。"""


@dataclass
class WatchItem:
    market_hash_name: str
    display_name: str
    platform_goods_ids: dict[str, str]
    enabled: bool = True

    def goods_id_for(self, platform: str) -> str | None:
        return self.platform_goods_ids.get(platform)

class WatchList:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or (settings.data_dir / "watchlist.json")
        self._items: list[WatchItem] = []
        self.reload()

    def reload(self) -> int:
        """重新读文件。解析失败时保留旧清单，不把运行中的服务带崩。"""
        if not self._path.exists():
            raise WatchListError(f"清单文件不存在：{self._path}")

        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WatchListError(f"读取 {self._path} 失败：{exc}") from exc

        if raw.get("version") != FILE_VERSION:
            raise WatchListError(
                f"{self._path} 版本是 {raw.get('version')}，本代码只认 v{FILE_VERSION}"
            )

        entries = raw.get("items")
        if not isinstance(entries, list):
            raise WatchListError("items 必须是数组")

        parsed: list[WatchItem] = []
        seen: set[str] = set()
        for index, entry in enumerate(entries, start=1):
            item = self._parse_item(index, entry)
            if item.market_hash_name in seen:
                raise WatchListError(
                    f"第 {index} 项 market_hash_name 重复：{item.market_hash_name}"
                )
            seen.add(item.market_hash_name)
            parsed.append(item)

        self._items = parsed
        return len(parsed)

    def _parse_item(self, index: int, entry: Any) -> WatchItem:
        if not isinstance(entry, dict):
            raise WatchListError(f"第 {index} 项必须是对象")

        mhn = str(entry.get("market_hash_name") or "").strip()
        if not mhn:
            raise WatchListError(f"第 {index} 项缺少 market_hash_name")

        ids_raw = entry.get("platform_goods_ids") or {}
        if not isinstance(ids_raw, dict):
            raise WatchListError(f"第 {index} 项 platform_goods_ids 必须是对象")

        ids: dict[str, str] = {}
        for platform, goods_id in ids_raw.items():
            if platform not in SUPPORTED_PLATFORMS:
                raise WatchListError(f"第 {index} 项未知平台：{platform}")
            if goods_id in (None, ""):
                continue
            ids[platform] = str(goods_id)

        if not ids:
            raise WatchListError(f"第 {index} 项没有任何平台的 goods_id，无法监控")

        return WatchItem(
            market_hash_name=mhn,
            display_name=str(entry.get("display_name") or mhn),
            platform_goods_ids=ids,
            enabled=bool(entry.get("enabled", True)),
        )

    # ---- 查询 ----

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self):
        return iter(self._items)

    @property
    def items(self) -> list[WatchItem]:
        return list(self._items)

    def enabled_items(self) -> list[WatchItem]:
        return [item for item in self._items if item.enabled]

    def for_platform(self, platform: str) -> list[WatchItem]:
        return [
            item
            for item in self._items
            if item.enabled and item.goods_id_for(platform)
        ]

if __name__ == "__main__":
    import tempfile

    SAMPLE = {
        "version": 1,
        "items": [
            {
                "market_hash_name": "AWP | Asiimov (Field-Tested)",
                "display_name": "AWP | 二西莫夫（久经沙场）",
                "platform_goods_ids": {"BUFF": "12345", "YOUPIN": "67890"},
                "enabled": True,
            },
            {
                "market_hash_name": "AK-47 | Redline (Field-Tested)",
                "display_name": "AK-47 | 红线（久经沙场）",
                "platform_goods_ids": {"BUFF": "54321"},
                "enabled": False,
            },
        ],
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        path = Path(tmp_dir) / "watchlist.json"
        path.write_text(json.dumps(SAMPLE, ensure_ascii=False), encoding="utf-8")
        wl = WatchList(path=path)

        assert len(wl) == 2
        assert len(wl.for_platform("BUFF")) == 1      # 停用的不返回
        assert len(wl.for_platform("YOUPIN")) == 1
        assert len(wl.for_platform("C5")) == 0        # 没填 id 的平台不返回
        print("[1] 加载 2 项：BUFF 1 项、YOUPIN 1 项、C5 0 项")

        duplicate = dict(SAMPLE)
        duplicate["items"] = [SAMPLE["items"][0], {**SAMPLE["items"][0], "display_name": "重复项"}]
        path.write_text(json.dumps(duplicate, ensure_ascii=False), encoding="utf-8")
        try:
            wl.reload()
        except WatchListError as exc:
            print(f"[2] 重复 mhn 被拦下：{exc}")
        else:
            raise AssertionError("重复 mhn 竟然通过了")
        assert len(wl) == 2                            # 失败后旧清单还在

        unknown = dict(SAMPLE)
        unknown["items"] = [{**SAMPLE["items"][0], "platform_goods_ids": {"STEAM": "1"}}]
        path.write_text(json.dumps(unknown, ensure_ascii=False), encoding="utf-8")
        try:
            wl.reload()
        except WatchListError as exc:
            print(f"[3] 未知平台被拦下：{exc}")
        else:
            raise AssertionError("未知平台竟然通过了")

    print("[OK] watchlist 自检通过")

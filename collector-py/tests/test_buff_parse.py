"""BUFF 解析契约测试：用真实响应回放，盯住字段名。

fixture 来自真实采集（tests/fixtures/buff_sell_order.json）。
平台改字段时这里先炸，而不是等到线上静默返回 0 条。
"""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from adapters.buff import BuffCollector

FIXTURE = Path(__file__).parent / "fixtures" / "buff_sell_order.json"


def test_parse_real_fixture() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    items = payload["data"]["items"]
    assert items, "fixture 里没有挂单，先跑一次 run_collector --once 再导出"

    collector = BuffCollector(client=object())  # _parse_item 不依赖 client
    listings = [collector._parse_item(item) for item in items]

    assert len(listings) == len(items)
    for raw, listing in zip(items, listings):
        assert listing.platform == "BUFF"
        assert listing.platform_item_id
        assert listing.price_amount > 0
        assert listing.price_amount == int(Decimal(str(raw["price"])) * 100)
        assert listing.float_value is None or 0.0 <= listing.float_value <= 1.0
        if listing.seller_id:
            assert len(listing.seller_id) == 32
            assert listing.seller_id != (raw.get("user") or {}).get("nickname")
            assert "user_id" not in listing.raw
            assert "user_steamid" not in listing.raw



if __name__ == "__main__":
    test_parse_real_fixture()
    count = len(json.loads(FIXTURE.read_text(encoding="utf-8"))["data"]["items"])
    print(f"[OK] 回放 {count} 条真实挂单，字段映射正常")

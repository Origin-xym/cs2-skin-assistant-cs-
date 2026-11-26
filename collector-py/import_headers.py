"""从 DevTools 导出的请求文本里提取指定请求头，加密写入 credentials.json。

用法：
    .venv\\Scripts\\python.exe import_headers.py --platform YOUPIN --file "C:\\...\\请求导出.txt"

只导入白名单内的头。导入完成后请删除源文件：它包含仍然有效的 token。
"""
from __future__ import annotations

import argparse
import base64
import json
from datetime import datetime, timezone
from pathlib import Path

from core.credentials import Credential, CredentialError, CredentialStore

SUPPORTED_PLATFORMS = {"BUFF", "YOUPIN", "C5"}
IMPORT_HEADERS = (
    "authorization",
    "app-version",
    "apptype",
    "appversion",
    "platform",
    "secret-v",
    "deviceid",
    "deviceuk",
    "uk",
    "user-agent",
)


def parse_headers(text: str) -> dict[str, str]:
    """兼容两种 DevTools 导出格式：`name: value` 单行，以及 name/value 各占一行。"""
    lines = [line.strip() for line in text.splitlines()]
    found: dict[str, str] = {}
    for index, line in enumerate(lines):
        lower = line.lower()
        for name in IMPORT_HEADERS:
            if name in found:
                continue
            if lower.startswith(f"{name}:"):
                value = line.split(":", 1)[1].strip()
                if value:
                    found[name] = value
            elif lower == name:
                for follow in lines[index + 1:]:
                    if follow:
                        found[name] = follow
                        break
    return found


def jwt_expiry(token: str) -> datetime | None:
    """只解 payload 取 exp，不校验签名；用于 --list 展示到期时间。"""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload))
        exp = int(data["exp"])
    except (IndexError, ValueError, KeyError, json.JSONDecodeError):
        return None
    return datetime.fromtimestamp(exp, tz=timezone.utc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="导入 DevTools 请求头到加密登录态")
    parser.add_argument("--platform", required=True, help="BUFF / YOUPIN / C5")
    parser.add_argument("--file", required=True, help="DevTools 导出的文本文件路径")
    args = parser.parse_args(argv)

    platform = args.platform.upper()
    if platform not in SUPPORTED_PLATFORMS:
        print(f"[FAIL] 不支持的平台 {platform}")
        return 1

    path = Path(args.file)
    if not path.exists():
        print(f"[FAIL] 文件不存在：{path}")
        return 1

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"[FAIL] 读取失败：{exc}")
        return 1

    found = parse_headers(text)
    if "authorization" not in found:
        print("[FAIL] 没找到 authorization，确认导出的是请求头而不是响应头")
        return 1

    try:
        store = CredentialStore()
        existing = store.load(platform)
    except CredentialError as exc:
        print(f"[FAIL] 登录态存储异常：{exc}")
        return 1

    expires_at = jwt_expiry(found["authorization"])
    credential = Credential(
        platform=platform,
        cookies=existing.cookies if existing else {},
        headers=found,
        expires_at=expires_at or (existing.expires_at if existing else None),
    )
    try:
        store.save(credential)
    except CredentialError as exc:
        print(f"[FAIL] 保存失败：{exc}")
        return 1

    expires_text = expires_at.isoformat() if expires_at else "未识别"
    print(f"[OK] {platform} 已导入 {len(found)} 个请求头：{', '.join(sorted(found))}")
    print(f"     JWT 过期时间：{expires_text}")
    print("     下一步：删除源文件，然后运行 save_cookie.py --list 核对")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

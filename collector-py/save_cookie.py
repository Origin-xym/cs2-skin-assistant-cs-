"""把浏览器里的 Cookie 加密存进 data/credentials.json。

用法：
    # 保存（整段 Cookie 从浏览器开发者工具复制）
    .venv\\Scripts\\python.exe save_cookie.py --platform BUFF --cookie 'session=...; csrf_token=...'

    # 查看已保存的平台（只显示项数，不打印值）
    .venv\\Scripts\\python.exe save_cookie.py --list

    # 删除
    .venv\\Scripts\\python.exe save_cookie.py --platform BUFF --delete
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

from core.credentials import Credential, CredentialError, CredentialStore

SUPPORTED_PLATFORMS = {"BUFF", "YOUPIN", "C5"}


def parse_cookie(raw: str) -> dict[str, str]:
    """'session=abc; csrf=xyz' → {'session': 'abc', 'csrf': 'xyz'}"""
    cookies: dict[str, str] = {}
    for part in raw.split(";"):
        part = part.strip()
        if not part:
            continue
        name, sep, value = part.partition("=")
        if not sep:
            continue
        name = name.strip()
        if not name:
            continue
        cookies[name] = value.strip()
    return cookies

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="保存 / 查看 / 删除平台登录态")
    parser.add_argument("--platform", help="BUFF / YOUPIN / C5")
    parser.add_argument("--cookie", help="整段 Cookie，例如 'session=xxx; csrf_token=yyy'")
    parser.add_argument("--expires", help="可选，ISO8601 过期时间")
    parser.add_argument("--list", action="store_true", help="列出已保存的平台")
    parser.add_argument("--delete", action="store_true", help="删除指定平台的登录态")
    args = parser.parse_args(argv)

    try:
        store = CredentialStore()
    except CredentialError as exc:
        print(f"[FAIL] {exc}")
        return 1

    if args.list:
        platforms = store.list_platforms()
        if not platforms:
            print("（还没有保存任何登录态）")
            return 0
        for platform in platforms:
            try:
                cred = store.load(platform)
            except CredentialError as exc:
                print(f"{platform}: 解不开（{exc}）")
                continue
            if cred is None:
                continue
            expires = cred.expires_at.isoformat() if cred.expires_at else "未设置"
            print(
                f"{platform}: cookies {len(cred.cookies)} 项，headers {len(cred.headers)} 项，"
                f"保存于 {cred.saved_at.isoformat()}，过期 {expires}"
            )

        return 0

    platform = (args.platform or "").upper()
    if not platform:
        print("[FAIL] 需要 --platform")
        return 1
    if platform not in SUPPORTED_PLATFORMS:
        print(f"[FAIL] 不支持的平台 {platform}，只认 {sorted(SUPPORTED_PLATFORMS)}")
        return 1

    if args.delete:
        existed = store.delete(platform)
        print(f"{platform}: {'已删除' if existed else '本来就没有'}")
        return 0

    if not args.cookie:
        print("[FAIL] 需要 --cookie（或改用 --list / --delete）")
        return 1

    cookies = parse_cookie(args.cookie)
    if not cookies:
        print("[FAIL] Cookie 解析为空，检查格式是否为 name=value; name2=value2")
        return 1

    expires_at = None
    if args.expires:
        try:
            expires_at = datetime.fromisoformat(args.expires)
        except ValueError:
            print("[FAIL] --expires 不是合法 ISO8601 时间")
            return 1
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

    try:
        store.save(
            Credential(
                platform=platform,
                cookies=cookies,
                expires_at=expires_at,
            )
        )
    except CredentialError as exc:
        print(f"[FAIL] 保存失败：{exc}")
        return 1

    print(f"[OK] {platform} 登录态已加密保存：{len(cookies)} 项（{', '.join(sorted(cookies))}）")
    print("     核对：.venv\\Scripts\\python.exe save_cookie.py --list")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""登录态加解密：AES-256-GCM，密钥只从环境变量 CS2_CRED_KEY 读。

落盘位置：data/credentials.json（已被 .gitignore 忽略），结构：

    {
      "version": 1,
      "platforms": {
        "BUFF": {"nonce": "<b64>", "data": "<b64>", "saved_at": "<iso>"}
      }
    }

每个平台一个密文块，AAD 绑定平台名，防止密文跨平台挪用。
Cookie 只在采集进程内存里出现，日志里永远打不出明文。
"""
from __future__ import annotations

import base64
import json
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from config import settings

KEY_ENV = "CS2_CRED_KEY"
FILE_VERSION = 1


class CredentialError(RuntimeError):
    """登录态相关的统一异常基类。"""


class CredentialKeyMissing(CredentialError):
    """没有配置 CS2_CRED_KEY，或格式不对。"""


class CredentialDecryptError(CredentialError):
    """密钥错误、密文被篡改，或文件损坏。密钥丢了只能重新扫码。"""


def generate_key() -> str:
    """生成一把 32 字节的 base64url 密钥，写进系统环境变量用。"""
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


def load_key() -> bytes:
    raw = os.getenv(KEY_ENV, "").strip()
    if not raw:
        raise CredentialKeyMissing(
            f"缺少环境变量 {KEY_ENV}，先生成一把并写进系统环境变量"
        )
    try:
        key = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    except Exception as exc:
        raise CredentialKeyMissing(f"{KEY_ENV} 不是合法的 base64url：{exc}") from exc
    if len(key) != 32:
        raise CredentialKeyMissing(f"{KEY_ENV} 解码后是 {len(key)} 字节，AES-256 需要 32 字节")
    return key


@dataclass
class Credential:
    """一个平台的本人登录态。cookies 用 dict，httpx 可直接吃。"""

    platform: str
    cookies: dict[str, str]
    headers: dict[str, str] = field(default_factory=dict)
    saved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None

    def __repr__(self) -> str:
        return (
            f"Credential(platform={self.platform!r}, cookies={len(self.cookies)} 项, "
            f"headers={len(self.headers)} 项, expires_at={self.expires_at!r})"
        )

    def is_expired(self, now: datetime | None = None) -> bool:
        if self.expires_at is None:
            return False
        return (now or datetime.now(timezone.utc)) >= self.expires_at

    def to_payload(self) -> bytes:
        return json.dumps(
            {
                "cookies": self.cookies,
                "headers": self.headers,
                "saved_at": self.saved_at.isoformat(),
                "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")


class CredentialStore:
    """读写 data/credentials.json。单进程内用，低频调用，同步 IO 足够。"""

    def __init__(self, path: Path | None = None, key: bytes | None = None) -> None:
        self._path = path or (settings.data_dir / "credentials.json")
        self._key = key or load_key()
        self._lock = threading.Lock()

    # ---- 对外四个方法 ----

    def save(self, credential: Credential) -> None:
        with self._lock:
            store = self._read_store()
            nonce = os.urandom(12)
            ciphertext = AESGCM(self._key).encrypt(
                nonce, credential.to_payload(), self._aad(credential.platform)
            )
            store["platforms"][credential.platform] = {
                "nonce": base64.urlsafe_b64encode(nonce).decode(),
                "data": base64.urlsafe_b64encode(ciphertext).decode(),
                "saved_at": credential.saved_at.isoformat(),
            }
            self._write_store(store)

    def load(self, platform: str) -> Credential | None:
        with self._lock:
            entry = self._read_store()["platforms"].get(platform)
        if entry is None:
            return None
        try:
            nonce = base64.urlsafe_b64decode(entry["nonce"])
            ciphertext = base64.urlsafe_b64decode(entry["data"])
            plaintext = AESGCM(self._key).decrypt(nonce, ciphertext, self._aad(platform))
            payload = json.loads(plaintext)
        except Exception as exc:
            raise CredentialDecryptError(
                f"[{platform}] 登录态解不开（密钥换了或文件被改过），请重新扫码登录"
            ) from exc
        return Credential(
            platform=platform,
            cookies=payload["cookies"],
            headers=payload.get("headers") or {},
            saved_at=datetime.fromisoformat(payload["saved_at"]),
            expires_at=datetime.fromisoformat(payload["expires_at"]) if payload.get("expires_at") else None,
        )

    def delete(self, platform: str) -> bool:
        with self._lock:
            store = self._read_store()
            existed = store["platforms"].pop(platform, None) is not None
            if existed:
                self._write_store(store)
            return existed

    def list_platforms(self) -> list[str]:
        with self._lock:
            return sorted(self._read_store()["platforms"].keys())

    # ---- 内部 ----

    def _aad(self, platform: str) -> bytes:
        return f"v{FILE_VERSION}|{platform}".encode()

    def _read_store(self) -> dict:
        if not self._path.exists():
            return {"version": FILE_VERSION, "platforms": {}}
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CredentialError(f"读取 {self._path} 失败：{exc}") from exc
        if raw.get("version") != FILE_VERSION:
            raise CredentialError(f"{self._path} 版本是 {raw.get('version')}，本代码只认 v{FILE_VERSION}")
        raw.setdefault("platforms", {})
        return raw

    def _write_store(self, store: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_name(self._path.name + ".tmp")
        tmp.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self._path)


if __name__ == "__main__":
    import tempfile

    os.environ[KEY_ENV] = generate_key()
    with tempfile.TemporaryDirectory() as tmp_dir:
        path = Path(tmp_dir) / "credentials.json"
        store = CredentialStore(path=path)
        cred = Credential(
            platform="BUFF",
            cookies={"session": "abc123", "csrf_token": "xyz"},
            headers={"x-client": "pc"},
        )
        store.save(cred)

        loaded = store.load("BUFF")
        assert loaded is not None and loaded.cookies["session"] == "abc123"
        assert store.list_platforms() == ["BUFF"]
        print("[1] 加密写入 → 解密读取 OK")

        # 篡改密文，必须解不开
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["platforms"]["BUFF"]["data"] = base64.urlsafe_b64encode(b"tampered").decode()
        path.write_text(json.dumps(raw), encoding="utf-8")
        try:
            store.load("BUFF")
        except CredentialDecryptError:
            print("[2] 篡改检测 OK")
        else:
            raise AssertionError("篡改的密文竟然解开了")

        # 换一把密钥，旧密文必须解不开
        store.save(cred)
        os.environ[KEY_ENV] = generate_key()
        wrong_key_store = CredentialStore(path=path)
        try:
            wrong_key_store.load("BUFF")
        except CredentialDecryptError:
            print("[3] 错误密钥拒绝 OK")
        else:
            raise AssertionError("换了密钥还能解开，AES-GCM 白装了")

    print("[OK] credentials 自检通过")

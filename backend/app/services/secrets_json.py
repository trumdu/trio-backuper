from __future__ import annotations

import json
from typing import Any, Iterable

from backend.app.core.security import secrets_cipher


def dumps_with_encrypted_fields(obj: dict[str, Any], secret_fields: Iterable[str]) -> str:
    secret_fields = set(secret_fields)
    out: dict[str, Any] = {}
    for k, v in obj.items():
        if v is None:
            out[k] = None
            continue
        if k in secret_fields and isinstance(v, str) and v != "":
            out[k] = {"__enc__": secrets_cipher.encrypt_str(v)}
        elif k in secret_fields and (v == "" or v is None):
            # empty means "do not overwrite" at update time; caller decides
            out[k] = None
        else:
            out[k] = v
    return json.dumps(out, ensure_ascii=False)


def loads_with_decrypted_fields(payload_json: str | None, secret_fields: Iterable[str]) -> dict[str, Any] | None:
    if not payload_json:
        return None
    secret_fields = set(secret_fields)
    raw = json.loads(payload_json)
    out: dict[str, Any] = {}
    for k, v in raw.items():
        if k in secret_fields and isinstance(v, dict) and "__enc__" in v:
            out[k] = secrets_cipher.decrypt_str(v["__enc__"])
        else:
            out[k] = v
    return out


def loads_masked(payload_json: str | None, secret_fields: Iterable[str]) -> dict[str, Any] | None:
    if not payload_json:
        return None
    secret_fields = set(secret_fields)
    raw = json.loads(payload_json)
    for k in secret_fields:
        if k in raw and raw[k] is not None:
            raw[k] = "********"
    return raw

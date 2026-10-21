import os

from fastapi import HTTPException, Request, WebSocket


def demo_token() -> str:
    return os.getenv("API_TOKEN", "").strip()


def auth_required() -> bool:
    return bool(demo_token())


def check_http(request: Request) -> None:
    expected = demo_token()
    if not expected:
        return
    got = request.headers.get("X-Demo-Token", "")
    if got != expected:
        raise HTTPException(401, "認証トークンが必要です")


def check_ws(ws: WebSocket) -> bool:
    expected = demo_token()
    if not expected:
        return True
    return ws.query_params.get("token", "") == expected

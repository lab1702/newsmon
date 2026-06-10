from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


class _FakeStreamResponse:
    def __init__(self, body: bytes, status: int, encoding: str, chunk_size: int):
        self._body = body
        self.status_code = status
        self.encoding = encoding
        self._chunk_size = chunk_size

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    async def aiter_bytes(self):
        for i in range(0, len(self._body), self._chunk_size):
            yield self._body[i : i + self._chunk_size]


class _FakeStreamContext:
    def __init__(self, response: _FakeStreamResponse):
        self._response = response

    async def __aenter__(self) -> _FakeStreamResponse:
        return self._response

    async def __aexit__(self, *exc) -> bool:
        return False


class FakeStreamClient:
    """Minimal stand-in for httpx.AsyncClient.stream used by source fetch tests.

    Records each call as (method, url, kwargs) and streams a canned body so the
    base.fetch_text helper (raise_for_status + size cap + decode) is exercised.
    """

    def __init__(
        self,
        text: str = "",
        *,
        status: int = 200,
        encoding: str = "utf-8",
        chunk_size: int = 8192,
    ) -> None:
        self._body = text.encode(encoding)
        self._status = status
        self._encoding = encoding
        self._chunk_size = chunk_size
        self.calls: list[tuple[str, str, dict]] = []

    def stream(self, method: str, url: str, **kwargs):
        self.calls.append((method, url, kwargs))
        return _FakeStreamContext(
            _FakeStreamResponse(self._body, self._status, self._encoding, self._chunk_size)
        )

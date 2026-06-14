"""LLM 원시 응답 record/replay 캐시 — 측정 무결성.

LLM 호출만 비결정적이고 그 이후(파싱·검증·채점)는 결정적이다. 따라서 원시 응답을
스냅샷해두면 파서·검증·채점 수정의 효과를 재추출(LLM 호출) 없이 결정적·무료로 측정할 수 있다.

모드 (env LLM_CACHE_MODE):
  off (기본) — 캐시 미사용, 항상 실제 호출
  record     — 실제 호출 후 응답을 캐시에 저장 (스냅샷 생성). 비용 발생.
  replay     — 캐시 히트 시 저장된 응답 반환 (LLM 호출 0, 결정적). 미스 시 실제 호출.

캐시 키에 프롬프트 해시가 포함되므로:
  - 파서/검증/채점 변경 → 키 동일 → 히트 → 결정적 재측정
  - 프롬프트 변경(예: 업종 over-extraction 네거티브) → 키 변경 → 미스 → record 필요(올바름)
"""
import hashlib
import json
import os
import threading
from pathlib import Path

_DEFAULT_PATH = "/evaluation/results/_llm_raw_cache.json"
_lock = threading.Lock()
_cache: dict | None = None
_loaded_from: str | None = None


def mode() -> str:
    return os.environ.get("LLM_CACHE_MODE", "off").strip().lower()


def _cache_path() -> Path:
    return Path(os.environ.get("LLM_CACHE_PATH", _DEFAULT_PATH))


def _load() -> dict:
    global _cache, _loaded_from
    path = str(_cache_path())
    if _cache is None or _loaded_from != path:
        p = Path(path)
        try:
            _cache = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        except Exception:
            _cache = {}
        _loaded_from = path
    return _cache


def _key(kind: str, model: str, prompt: str, content: str) -> str:
    prompt_h = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    content_h = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return hashlib.sha256(f"{kind}\x00{model}\x00{prompt_h}\x00{content_h}".encode("utf-8")).hexdigest()


def get(kind: str, model: str, prompt: str, content: str) -> str | None:
    """replay 모드일 때만 캐시 조회. 그 외엔 None(=실제 호출 유도)."""
    if mode() != "replay":
        return None
    return _load().get(_key(kind, model, prompt, content))


def put(kind: str, model: str, prompt: str, content: str, response: str) -> None:
    """record 모드일 때만 저장. crash 내성을 위해 매 put마다 파일 기록."""
    if mode() != "record":
        return
    with _lock:
        c = _load()
        c[_key(kind, model, prompt, content)] = response
        path = _cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")

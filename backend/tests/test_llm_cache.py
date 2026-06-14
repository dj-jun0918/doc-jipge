"""llm_cache record/replay 단위 테스트 — 측정 무결성 인프라."""
from app.extractor import llm_cache


def _set(monkeypatch, mode, path):
    monkeypatch.setenv("LLM_CACHE_MODE", mode)
    monkeypatch.setenv("LLM_CACHE_PATH", str(path))
    llm_cache._cache = None  # 모듈 캐시 상태 리셋
    llm_cache._loaded_from = None


def test_off_모드는_캐시_미사용(monkeypatch, tmp_path):
    path = tmp_path / "c.json"
    _set(monkeypatch, "off", path)
    assert llm_cache.get("text", "m", "p", "in") is None
    llm_cache.put("text", "m", "p", "in", "resp")  # no-op
    assert not path.exists()


def test_record_후_replay_히트(monkeypatch, tmp_path):
    path = tmp_path / "c.json"
    _set(monkeypatch, "record", path)
    llm_cache.put("text", "m", "p", "in", "RESP")
    assert path.exists()
    _set(monkeypatch, "replay", path)
    assert llm_cache.get("text", "m", "p", "in") == "RESP"


def test_replay_미스는_None(monkeypatch, tmp_path):
    path = tmp_path / "c.json"
    _set(monkeypatch, "record", path)
    llm_cache.put("text", "m", "p", "in", "RESP")
    _set(monkeypatch, "replay", path)
    assert llm_cache.get("text", "m", "p", "DIFFERENT_INPUT") is None


def test_프롬프트_변경시_캐시_무효화(monkeypatch, tmp_path):
    # 핵심: 프롬프트가 바뀌면 키가 바뀌어 미스 (LLM-레벨 변경은 재record 필요)
    path = tmp_path / "c.json"
    _set(monkeypatch, "record", path)
    llm_cache.put("text", "m", "PROMPT_A", "in", "RESP")
    _set(monkeypatch, "replay", path)
    assert llm_cache.get("text", "m", "PROMPT_A", "in") == "RESP"  # 동일 프롬프트 → 히트
    assert llm_cache.get("text", "m", "PROMPT_B", "in") is None     # 변경 프롬프트 → 미스


def test_동일_입력프롬프트는_히트_파서변경_무관(monkeypatch, tmp_path):
    # 파서가 바뀌어도 (input/prompt 동일) 키 동일 → 히트 → 결정적 재측정의 핵심
    path = tmp_path / "c.json"
    _set(monkeypatch, "record", path)
    llm_cache.put("vision", "gpt-4o", "VP", "imgdata", "VRESP")
    _set(monkeypatch, "replay", path)
    assert llm_cache.get("vision", "gpt-4o", "VP", "imgdata") == "VRESP"


def test_kind_분리(monkeypatch, tmp_path):
    # text와 vision은 같은 입력이어도 키가 다름
    path = tmp_path / "c.json"
    _set(monkeypatch, "record", path)
    llm_cache.put("text", "m", "p", "x", "T")
    _set(monkeypatch, "replay", path)
    assert llm_cache.get("text", "m", "p", "x") == "T"
    assert llm_cache.get("vision", "m", "p", "x") is None

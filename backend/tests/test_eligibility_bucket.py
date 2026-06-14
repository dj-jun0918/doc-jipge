"""적합도 버킷 파생 — 필드 status를 공고 단위 신청가능/조건확인/자격미달로 묶기."""
from app.matcher.matcher import derive_eligibility_bucket


def _f(*statuses):
    # (field_name, status, score) 튜플 리스트 — bucket은 status만 본다
    return [(f"f{i}", s, None) for i, s in enumerate(statuses)]


def test_미충족_있으면_자격미달():
    assert derive_eligibility_bucket(_f("충족", "미충족", "확인필요")) == "자격미달"
    assert derive_eligibility_bucket(_f("미충족")) == "자격미달"


def test_미충족없고_확인필요있으면_조건확인():
    assert derive_eligibility_bucket(_f("충족", "확인필요")) == "조건확인"
    assert derive_eligibility_bucket(_f("확인필요")) == "조건확인"


def test_전부_충족이면_신청가능():
    assert derive_eligibility_bucket(_f("충족", "충족")) == "신청가능"


def test_해당없음은_카운트_제외():
    # 해당없음만 있으면 판단 근거 없음 → 조건확인
    assert derive_eligibility_bucket(_f("해당없음", "해당없음")) == "조건확인"
    # 충족 + 해당없음 → 해당없음 무시하고 신청가능
    assert derive_eligibility_bucket(_f("충족", "해당없음")) == "신청가능"
    # 미충족 + 해당없음 → 자격미달
    assert derive_eligibility_bucket(_f("미충족", "해당없음")) == "자격미달"


def test_빈입력_조건확인():
    assert derive_eligibility_bucket([]) == "조건확인"


def test_미충족이_확인필요보다_우선():
    # 미충족과 확인필요가 같이 있어도 미충족이 있으면 자격미달
    assert derive_eligibility_bucket(_f("확인필요", "미충족", "충족")) == "자격미달"

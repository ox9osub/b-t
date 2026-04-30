"""트윗 본문 조립 + 글자수 계산 + 스레드 분할.

twitter-text 규칙 (가중 카운트):
- ASCII 일반 문자: 1 weight
- CJK / 이모지 / 기타: 2 weight
- URL: 항상 23 weight (실제 길이 무관, t.co로 단축됨)
- 최대: 280 weight
"""
from __future__ import annotations
import re

# URL detection: https?://... (간단한 휴리스틱; 트위터 자체 단축 규칙과 동일하게 동작)
_URL_RE = re.compile(r"https?://\S+")
URL_WEIGHT = 23

# weight=1 ranges per twitter-text spec
_WEIGHT_ONE_RANGES = (
    (0x0000, 0x10FF),
    (0x2000, 0x200D),
    (0x2010, 0x201F),
    (0x2032, 0x2037),
)


def _char_weight(ch: str) -> int:
    cp = ord(ch)
    for lo, hi in _WEIGHT_ONE_RANGES:
        if lo <= cp <= hi:
            return 1
    return 2


def weighted_count(text: str) -> int:
    """트위터의 weighted character count 규칙 적용."""
    # URL은 23 weight로 치환한 뒤 카운트
    total = 0
    last = 0
    for m in _URL_RE.finditer(text):
        # URL 앞쪽 일반 텍스트
        for ch in text[last:m.start()]:
            total += _char_weight(ch)
        total += URL_WEIGHT
        last = m.end()
    # 마지막 URL 이후 텍스트
    for ch in text[last:]:
        total += _char_weight(ch)
    return total


def render_template(template: str, entry) -> str:
    """템플릿에 entry 필드를 채워 넣음. 리터럴 '\\n' 도 줄바꿈으로 변환."""
    # 리터럴 백슬래시-n을 진짜 줄바꿈으로 (Sheets 셀에서 입력된 경우)
    real_template = template.replace("\\n", "\n")
    return real_template.format(
        bible_text=entry.bible_text,
        bible_ref=entry.bible_ref,
        youtube_url=entry.youtube_url,
        label=entry.label,
    )


def build_single(entry, template: str) -> str:
    """단일 트윗 텍스트를 만든다 (길이 검증은 caller가)."""
    return render_template(template, entry)

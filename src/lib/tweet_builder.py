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
# "\n\n(99/99)" worst-case 스레드 마커 weight: 2(개행) + 7(괄호+숫자) = 9
THREAD_MARKER_MAX_WEIGHT = 9

# weight=1 ranges per twitter-text spec.
# Note: Korean Hangul Syllables (U+AC00–U+D7A3) are far above 0x10FF,
# so they correctly receive weight=2 via the fall-through in _char_weight.
# Hangul Jamo (U+1100–U+11FF) would also fall above this range, which is
# the desired behavior since those are still CJK characters.
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


def _render_with_bible_text(template: str, entry, bible_text: str) -> str:
    """템플릿의 {bible_text}를 임의 값으로 치환해 렌더링. 스레드 분할 시 사용."""
    # 리터럴 백슬래시-n을 진짜 줄바꿈으로 (Sheets 셀에서 입력된 경우)
    real_template = template.replace("\\n", "\n")
    return real_template.format(
        bible_text=bible_text,
        bible_ref=entry.bible_ref,
        youtube_url=entry.youtube_url,
        label=entry.label,
    )


def render_template(template: str, entry) -> str:
    """템플릿에 entry 필드를 채워 넣음. 리터럴 '\\n' 도 줄바꿈으로 변환."""
    return _render_with_bible_text(template, entry, entry.bible_text)


def build_single(entry, template: str) -> str:
    """단일 트윗 텍스트를 만든다 (길이 검증은 caller가)."""
    return render_template(template, entry)


def _split_text_into_chunks(text: str, max_weight: int) -> list[str]:
    """본문을 절(개행) → 문장(. ! ?) → 어절(공백) 순으로 분할."""
    if weighted_count(text) <= max_weight:
        return [text]

    # 1차: 줄바꿈(절) 단위
    lines = text.split("\n")
    chunks: list[str] = []
    current = ""
    for line in lines:
        candidate = current + ("\n" if current else "") + line
        if weighted_count(candidate) <= max_weight:
            current = candidate
        else:
            if current:
                chunks.append(current)
            # 한 줄 자체가 너무 긴 경우 → 문장 단위로 더 분할
            if weighted_count(line) > max_weight:
                chunks.extend(_split_by_sentences(line, max_weight))
                current = ""
            else:
                current = line
    if current:
        chunks.append(current)
    return chunks


def _split_by_sentences(line: str, max_weight: int) -> list[str]:
    """문장 부호(. ! ?) 기준 분할. 그래도 길면 어절."""
    parts = re.split(r"(?<=[.!?。！？])\s+", line)
    chunks: list[str] = []
    current = ""
    for p in parts:
        candidate = (current + " " + p).strip() if current else p
        if weighted_count(candidate) <= max_weight:
            current = candidate
        else:
            if current:
                chunks.append(current)
            if weighted_count(p) > max_weight:
                chunks.extend(_split_by_words(p, max_weight))
                current = ""
            else:
                current = p
    if current:
        chunks.append(current)
    return chunks


def _split_by_words(text: str, max_weight: int) -> list[str]:
    """공백 기준 분할. 마지막 수단."""
    words = text.split()
    chunks: list[str] = []
    current = ""
    for w in words:
        candidate = (current + " " + w).strip() if current else w
        if weighted_count(candidate) <= max_weight:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = w  # Single word may exceed limit but we accept (rare in Korean)
    if current:
        chunks.append(current)
    return chunks


def _force_split_by_chars(text: str, max_weight: int) -> list[str]:
    """문자 단위 강제 분할. 공백/구두점 없는 텍스트의 마지막 안전망."""
    chunks: list[str] = []
    current = ""
    for ch in text:
        candidate = current + ch
        if weighted_count(candidate) <= max_weight:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = ch  # 단일 문자가 max_weight 초과해도 그대로 (실무상 드묾)
    if current:
        chunks.append(current)
    return chunks


def build_thread(entry, template: str, max_weight: int = 270) -> list[str]:
    """단일 또는 복수 트윗으로 조립. 첫 트윗은 템플릿 그대로(해시태그 포함) +
    번호 표기, 이어지는 트윗은 본문 chunk + 번호 표기.
    """
    single = render_template(template, entry)
    if weighted_count(single) <= max_weight:
        return [single]

    # 스레드 모드: bible_text를 분할, 각 chunk를 별도 트윗으로
    budget = _budget_for_text(entry, template, max_weight)
    chunks = _split_text_into_chunks(entry.bible_text, budget)

    # 분할 알고리즘이 실패해 chunks=1 인데 그 chunk가 budget 초과 → 문자 단위 강제 분할
    if len(chunks) == 1 and weighted_count(chunks[0]) > budget:
        chunks = _force_split_by_chars(chunks[0], budget)

    if len(chunks) < 2:
        # budget floor(50) 발동 또는 bible_text 자체가 너무 짧은 케이스. 분할 불가 →
        # single 그대로 (over-limit일 수 있지만 더 쪼갤 수 없음).
        return [single]

    parts: list[str] = []
    total = len(chunks)
    for i, chunk in enumerate(chunks, start=1):
        suffix = f"\n\n({i}/{total})"
        if i == 1:
            # 첫 트윗: 템플릿 그대로 사용 (해시태그 등 포함). bible_text 자리에 chunk 치환.
            body = _render_with_bible_text(template, entry, chunk) + suffix
        else:
            # 이어지는 트윗: 본문 + 번호만
            body = f"{chunk}{suffix}"
        parts.append(body)
    return parts


def _overhead_weight(entry, template: str) -> int:
    """템플릿 렌더링 결과에서 bible_text 부분을 뺀 weight.

    해시태그, ref, URL, 이모지, 줄바꿈 등 본문 외 모든 요소의 가중 합계.
    weighted_count는 URL을 23으로 고정 카운트하므로 단순 차감이 정확.
    """
    full = render_template(template, entry)
    bt_weight = weighted_count(entry.bible_text) if entry.bible_text else 0
    return weighted_count(full) - bt_weight


def _budget_for_text(entry, template: str, max_weight: int) -> int:
    """첫 트윗에서 bible_text(또는 chunk)에 쓸 수 있는 최대 weight.

    overhead(템플릿 본문 외 전체) + 스레드 마커 (\\n\\n(99/99)) 를 차감.
    """
    overhead = _overhead_weight(entry, template) + THREAD_MARKER_MAX_WEIGHT
    return max(50, max_weight - overhead)


def build(entry, template: str, max_weight: int = 270) -> list[str]:
    """공개 API. 단일 또는 스레드 트윗 리스트 반환."""
    return build_thread(entry, template, max_weight)

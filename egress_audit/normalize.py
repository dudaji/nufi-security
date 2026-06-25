"""한국어/혼용 텍스트 정규화 (SPEC_M4 §2.2).

기밀 키워드·표식·EDM 매칭 정확도를 위해 매칭 전에 통과시키는 정규화 파이프.
순수 stdlib (NFR4). 외부 호출 0 (NFR1).

설계 메모: 정규화는 매칭용 *뷰*를 만든다. 정규화 후 좌표(span)는 원문과 다를 수 있으나,
기밀 finding 은 본문 치환(redact) 대상이 아니라(block=요청 전면 차단, warn=무편집)
span 은 감사 참고용으로만 쓰인다(§4.2: 매치 위치만, 원문 비기록).
"""
from __future__ import annotations

import re
import unicodedata

# 제로폭/서식 문자 (조사·자모 변형 회피용 삽입 흔히 사용)
_ZERO_WIDTH = "".join([
    "​",  # ZERO WIDTH SPACE
    "‌",  # ZERO WIDTH NON-JOINER
    "‍",  # ZERO WIDTH JOINER
    "﻿",  # ZERO WIDTH NO-BREAK SPACE
    "­",  # SOFT HYPHEN
])
_ZERO_WIDTH_RE = re.compile("[" + re.escape(_ZERO_WIDTH) + "]")

# 중점/유사 구분기호 → 통일 제거 대상 (예: "대·외·비")
_MIDDOT_RE = re.compile(r"[·•‧・･]")
# 다양한 하이픈/대시 → ASCII '-'
_HYPHEN_RE = re.compile(r"[‐‑‒–—―−－]")
# 연속 공백류 → 단일 공백
_WS_RE = re.compile(r"\s+")

# 한글 음절 + 영숫자 = '단어 문자'(경계 판정용)
_WORDCHAR_RE = re.compile(r"[0-9A-Za-z가-힣]")
_HANGUL_RE = re.compile(r"[가-힣]")


def normalize(text: str, *, collapse_ws: bool = True, drop_middot: bool = True) -> str:
    """매칭용 정규화 뷰를 만든다.

    NFC 결합 → 제로폭 제거 → 하이픈/중점 통일 → (선택) 공백 정리.
    drop_middot=True 면 중점을 제거해 "대·외·비"→"대외비" 흡수.
    """
    if not text:
        return ""
    t = unicodedata.normalize("NFC", text)
    t = _ZERO_WIDTH_RE.sub("", t)
    t = _HYPHEN_RE.sub("-", t)
    if drop_middot:
        t = _MIDDOT_RE.sub("", t)
    else:
        t = _MIDDOT_RE.sub("·", t)
    if collapse_ws:
        t = _WS_RE.sub(" ", t).strip()
    return t


def normalize_token(value: str) -> str:
    """EDM 셀/토큰 정규화 — 내부 공백까지 제거하고 casefold.

    "강 남 구"·"강남구"·"강남 구" 를 동일 키로 만든다. 영문은 casefold.
    """
    if value is None:
        return ""
    t = normalize(value, collapse_ws=True, drop_middot=True)
    t = t.replace(" ", "")
    return t.casefold()


def is_wordchar(ch: str) -> bool:
    return bool(_WORDCHAR_RE.match(ch))


def find_word(text: str, term: str, *, case_sensitive: bool = False,
              max_josa: int = 3):
    """정규화된 text 에서 term 의 한국어 단어경계 매치 위치를 yield.

    - 좌경계: 앞 문자가 단어문자가 아니어야 함(부분어 충돌 방지).
    - 우경계(한글 term): 등록어 뒤 0~max_josa 음절의 조사 후보 허용,
      그 다음이 단어문자가 아니면 매치(예: "오로라는/오로라의" → "오로라").
    - 우경계(영문 term): 바로 뒤가 영숫자가 아니어야 매치(부분어 회피).
    yield (start, end) — end 는 등록어 끝(조사 미포함).
    """
    if not term:
        return
    hay = text if case_sensitive else text.casefold()
    needle = term if case_sensitive else term.casefold()
    has_hangul = bool(_HANGUL_RE.search(term))
    n = len(needle)
    i = 0
    while True:
        idx = hay.find(needle, i)
        if idx < 0:
            return
        i = idx + 1
        # 좌경계
        if idx > 0 and is_wordchar(text[idx - 1]):
            continue
        end = idx + n
        if has_hangul:
            # 조사 후보(한글) 최대 max_josa 음절 소비 후 경계 확인
            j = end
            josa = 0
            while j < len(text) and josa < max_josa and _HANGUL_RE.match(text[j]):
                j += 1
                josa += 1
            # 조사 소비 뒤가 여전히 단어문자(영숫자/추가 한글)면 부분어 → 거름
            if j < len(text) and is_wordchar(text[j]):
                # 단, 모두 한글이고 max_josa 도달이면 조사로 간주하고 통과시키지 않음(보수적)
                continue
            yield (idx, end)
        else:
            if end < len(text) and (text[end].isalnum()):
                continue
            yield (idx, end)

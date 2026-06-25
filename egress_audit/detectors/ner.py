"""한국어 인명/지명 NER 탐지기 (SPEC M2 수용기준 2).

정규식이 못 잡는 인명/지명을 보완한다.

백엔드 2종 (런타임에 자동 선택):
  1. transformers/ONNX 백엔드 — `Leo97/KoELECTRA-small-v3-modu-ner` (권장, 프로덕션).
     모델 가중치 다운로드(최초 1회)·onnxruntime 또는 torch 필요.
  2. gazetteer 백엔드 (기본/폴백) — 한국 성씨 사전 + 경칭/직함/문맥 게이팅 + 행정구역 접미사.
     순수 stdlib, 에어갭 동작(NFR1). PoC·CI 검증용으로 항상 동작.

gazetteer 백엔드는 호모그래프 오탐을 줄이기 위해 인명은 경칭/직함/문맥으로 게이팅한다.
프로덕션 한국어 PII recall ≥ 0.9 목표는 transformers/ONNX 백엔드로 달성한다(SPEC KR 목표).
"""
from __future__ import annotations

import re
from typing import Iterator, List, Optional

from .korean_pii import RawSpan

# 빈도 높은 한국 성씨(상위 ~60). gazetteer 백엔드용.
_SURNAMES = (
    "김|이|박|최|정|강|조|윤|장|임|한|오|서|신|권|황|안|송|전|홍|유|고|문|양|손|"
    "배|백|허|노|심|하|곽|성|차|주|우|구|민|류|나|진|지|엄|채|원|천|방|공|현|함|"
    "변|염|여|추|도|소|석|선|설|마|길|연|위|표|명|기|반|라|왕"
)

# 인명 게이팅: 뒤따르는 경칭/직함, 또는 앞서는 문맥 명사.
_HONORIFICS = "님|씨|군|양"
_TITLES = ("부장|과장|차장|대리|팀장|사원|대표|이사|사장|회장|부사장|상무|전무|"
           "선생|셰프|교수|박사|원장|의원|판사|검사|변호사|기자|감독|선수|작가|"
           "대리님|기사|간호사|약사|의사")
_CONTEXT = ("고객|환자|담당자|직원|대표|발신|수신|성함|이름|사용자|회원|가입자|"
            "신청자|지원자|보호자|의뢰인|수취인|예금주|명의자")

# 인명 후보: (성)(이름 1~2자). 게이팅 방식 3종.
#  - 경칭이 바로 붙은 경우 (님/씨/군/양) — 뒤 조사 허용
#  - 공백 뒤 직함이 오는 경우 — 뒤 조사 허용
#  - 앞에 문맥 명사(고객/환자/담당자 등)가 오는 경우 — 일반 후보
_NAME = rf"(?:{_SURNAMES})[가-힣]{{1,2}}"
_PERSON_HONOR_RE = re.compile(rf"(?<![가-힣])(?P<name>{_NAME})(?:{_HONORIFICS})")
_PERSON_TITLE_RE = re.compile(rf"(?<![가-힣])(?P<name>{_NAME})\s(?:{_TITLES})")
_PERSON_CAND_RE = re.compile(rf"(?<![가-힣])(?P<name>{_NAME})(?![가-힣])")
_CONTEXT_RE = re.compile(rf"(?:{_CONTEXT})\s*$")

_PLACE_SUFFIX_RE = re.compile(r"(?<![가-힣])([가-힣]{2,4}(?:특별시|광역시|특별자치시|특별자치도))")
_PLACE_UNIT_RE = re.compile(r"(?<![가-힣])([가-힣]{1,4}(?:시|도|군|구|읍|면|동|리))(?![가-힣])")

_KNOWN_PLACES = set(
    "서울 부산 대구 인천 광주 대전 울산 세종 경기 강원 충북 충남 전북 전남 "
    "경북 경남 제주 수원 성남 용인 고양 창원 청주 천안 전주 포항 김해 평택".split()
)

# 행정 접미사를 가진 비(非)지명 호모그래프(오탐 억제). 운영자가 확장 가능.
_PLACE_STOPWORDS = set(
    "복잡도 정확도 만족도 난이도 신뢰도 자유도 밀도 빈도 강도 농도 온도 속도 각도 "
    "제도 태도 정도 용도 척도 한도 빈도 회의시 도구 연구 요구 지구 인구 가구 기구 "
    "욕구 무시 즉시 동시 임시 항시 일시 운동 활동 행동 작동 자동 수동 이동 부동 "
    "처리 연동 관리 정리 거리 수리 분리 원리 권리 유리 협동 공동 노동 변동 진동 감동 "
    "출동 은행 부서 본부 지사 지부".split()
)


class _GazetteerBackend:
    name = "gazetteer"

    def detect(self, text: str) -> Iterator[RawSpan]:
        # 인명: 성씨 + 1~2자, 경칭/직함/선행 문맥으로 게이팅(호모그래프 오탐 억제)
        seen: set[tuple[int, int]] = set()

        def emit_person(start, end, name):
            if (start, end) in seen:
                return None
            seen.add((start, end))
            return RawSpan("KR_PERSON", name, start, end, 0.75, source="ner:gazetteer")

        for rx in (_PERSON_HONOR_RE, _PERSON_TITLE_RE):
            for m in rx.finditer(text):
                span = emit_person(m.start("name"), m.end("name"), m.group("name"))
                if span:
                    yield span
        for m in _PERSON_CAND_RE.finditer(text):
            if not _CONTEXT_RE.search(text[max(0, m.start() - 8):m.start()]):
                continue
            span = emit_person(m.start("name"), m.end("name"), m.group("name"))
            if span:
                yield span
        # 지명: 광역 접미사(특별시/광역시 등)
        for m in _PLACE_SUFFIX_RE.finditer(text):
            yield RawSpan("KR_LOCATION", m.group(1), m.start(1), m.end(1), 0.85, source="ner:gazetteer")
        # 지명: 행정단위 접미사 (호모그래프 제외)
        for m in _PLACE_UNIT_RE.finditer(text):
            if m.group(1) in _PLACE_STOPWORDS:
                continue
            yield RawSpan("KR_LOCATION", m.group(1), m.start(1), m.end(1), 0.65, source="ner:gazetteer")
        # 지명: 알려진 광역/축약 지명
        for place in _KNOWN_PLACES:
            start = 0
            while True:
                idx = text.find(place, start)
                if idx < 0:
                    break
                yield RawSpan("KR_LOCATION", place, idx, idx + len(place), 0.7, source="ner:gazetteer")
                start = idx + len(place)


class _PipelineBackend:
    """transformers token-classification 파이프라인 공통 채점 로직.

    하위 클래스가 `self._pipe`(HF token-classification 파이프라인)와
    `name`/`source` 만 구성하면 detect() 가 공유된다. FP32(torch)·INT8(ONNX) 동일.
    """

    name = "pipeline"
    source = "ner:koelectra"
    _LABEL_MAP = {"PS": "KR_PERSON", "PER": "KR_PERSON", "LC": "KR_LOCATION", "LOC": "KR_LOCATION"}

    def detect(self, text: str) -> Iterator[RawSpan]:
        for ent in self._pipe(text):
            grp = str(ent.get("entity_group", "")).upper()
            mapped = next((v for k, v in self._LABEL_MAP.items() if grp.startswith(k)), None)
            if not mapped:
                continue
            yield RawSpan(mapped, ent["word"], int(ent["start"]), int(ent["end"]),
                          float(ent["score"]), source=self.source)


class _TransformersBackend(_PipelineBackend):
    """transformers token-classification 파이프라인 (KoELECTRA FP32, torch)."""

    name = "transformers"
    source = "ner:koelectra"

    def __init__(self, model_id: str = "Leo97/KoELECTRA-small-v3-modu-ner"):
        from transformers import pipeline  # type: ignore
        self._pipe = pipeline("token-classification", model=model_id,
                              aggregation_strategy="simple")


class _OnnxInt8Backend(_PipelineBackend):
    """ONNX 동적 INT8 런타임 백엔드 (optimum onnxruntime).

    `scripts/export_onnx_int8.py` 가 산출한 INT8 ONNX 디렉터리를 로드한다.
    경로는 `model_id`(디렉터리) 또는 env `M5_ONNX_DIR/int8` 로 지정.
    """

    name = "onnx-int8"
    source = "ner:koelectra-onnx-int8"

    def __init__(self, model_id: Optional[str] = None):
        import os
        from optimum.onnxruntime import ORTModelForTokenClassification  # type: ignore
        from transformers import AutoTokenizer, pipeline  # type: ignore

        model_dir = model_id or os.environ.get("M5_ONNX_DIR")
        if model_dir and not str(model_dir).rstrip("/").endswith("int8"):
            cand = os.path.join(model_dir, "int8")
            if os.path.isdir(cand):
                model_dir = cand
        if not model_dir:
            model_dir = os.path.join(os.path.expanduser("~/.cache/m5_onnx_int8"), "int8")
        if not os.path.isdir(model_dir):
            raise FileNotFoundError(
                f"INT8 ONNX 디렉터리 없음: {model_dir} — 먼저 `python3 scripts/export_onnx_int8.py`")
        model = ORTModelForTokenClassification.from_pretrained(model_dir)
        tok = AutoTokenizer.from_pretrained(model_dir)
        self._pipe = pipeline("token-classification", model=model, tokenizer=tok,
                              aggregation_strategy="simple")


class KoreanNerDetector:
    """가능하면 transformers 백엔드, 아니면 gazetteer 폴백."""

    def __init__(self, backend: str = "auto", model_id: Optional[str] = None):
        self.backend = self._build_backend(backend, model_id)

    @staticmethod
    def _build_backend(backend: str, model_id: Optional[str]):
        if backend == "onnx-int8":
            return _OnnxInt8Backend(model_id=model_id)  # 미가용 시 예외 전파(폴백 금지: 명시 측정용)
        if backend in ("auto", "transformers"):
            try:
                kwargs = {"model_id": model_id} if model_id else {}
                return _TransformersBackend(**kwargs)
            except Exception:
                if backend == "transformers":
                    raise
        return _GazetteerBackend()

    @property
    def backend_name(self) -> str:
        return getattr(self.backend, "name", "unknown")

    def detect(self, text: str) -> Iterator[RawSpan]:
        yield from self.backend.detect(text)

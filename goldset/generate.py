"""M5 산출물 A — 한국어 PII 골드셋 생성기 (합성).

설계: docs/design/gateway/m5-bench-hardening-spec.md §1 (CMP-78).
구현·측정: CMP-99 (Engineer, 보안 상시승인 CMP-96).

원칙
-----
- **실고객 데이터 0** — 전량 합성. 체크섬이 필요한 식별번호(RRN/BRN/카드)는 유효 검증숫자로 생성해
  탐지기 선필터→체크섬 경로를 실제로 통과시킨다(과적합 아닌 진짜 탐지 측정).
- **누수 방지 핵심:** KR_PERSON 표본의 ≥ 50% 는 gazetteer 성씨 사전(`detectors/ner.py:_SURNAMES`)에
  **미수록 성씨**(희귀 단성·복성)로 구성한다. gazetteer 백엔드는 이들을 구조적으로 못 잡으므로,
  M2 PoC 의 recall 1.000 이 사전 과적합이었음을 드러내고 KoELECTRA 의 필요를 실측으로 정당화한다.
- **결정성:** 고정 시드. 동일 실행 → 동일 골드셋(§4.3 재현성).
- **스키마:** `{"id","prompt","expect":[type...],"spans":[[start,end,type]...],"source":"synth"}`.
- **분할:** 클래스별 층화 dev 40% / test 60%. test 는 튜닝 중 열람 금지(누수 방지).

실행: python3 goldset/generate.py  →  samples/gold/{dev,test}.jsonl + manifest.json
"""
from __future__ import annotations

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "samples" / "gold"

import sys
sys.path.insert(0, str(ROOT))
from egress_audit import checksums as ck  # noqa: E402
from egress_audit.detectors.ner import _SURNAMES  # noqa: E402

SEED = 20260625
GAZ_SURNAMES = set(_SURNAMES.split("|"))

# gazetteer 사전에 수록된(=폴백이 잡을 수 있는) 흔한 성씨 일부.
LISTED_SURNAMES = ["김", "이", "박", "최", "정", "강", "조", "윤", "장", "한", "오", "서", "신"]
# gazetteer 미수록 — 희귀 단성 + 복성. 폴백 백엔드는 구조적으로 탐지 불가(누수 방지 핵심).
UNLISTED_SURNAMES = ["옥", "음", "동", "경", "사", "호", "모", "봉", "갈", "좌", "어",
                     "탁", "피", "빈", "단", "견", "범", "복", "승", "화", "선", "옹",
                     "남궁", "황보", "제갈", "선우", "독고", "사공", "서문", "동방"]
GIVEN = ["민수", "지훈", "서연", "예준", "도윤", "하준", "지우", "서준", "주원", "은지",
         "현우", "수빈", "유진", "지원", "다은", "준호", "예린", "시우", "하은", "태윤"]

# gazetteer 가 잡는 지명(광역/행정접미사/알려진지명) + 못 잡는 신규지명·건물명 혼합.
GAZ_LOCATIONS = ["서울특별시", "부산광역시", "세종특별자치시", "제주특별자치도",
                 "수원시", "성남시 분당구", "강남구 역삼동", "용인시 기흥구", "청주시", "포항시"]
NONGAZ_LOCATIONS = ["판교테크노밸리", "마곡지구", "송도국제도시", "광교호수공원",
                    "롯데월드타워", "코엑스몰", "여의도 IFC", "동대문디자인플라자",
                    "스타필드 하남", "센텀시티"]

PERSON_CTX = [
    "고객 {name}님의 계정 본인확인을 진행해 주세요.",
    "{name} 부장 보고서 검토 부탁드립니다.",
    "환자 {name}님 진료 예약을 변경하고 싶습니다.",
    "수신자 {name} 앞으로 등기우편 발송했습니다.",
    "담당자 {name}에게 견적서를 전달했어요.",
    "가입 신청자 {name}님 서류 누락 안내 바랍니다.",
    "예금주 {name} 명의로 이체 처리되었습니다.",
    "{name} 선생님 강의 자료 공유드립니다.",
]
LOC_CTX = [
    "이번 워크숍은 {loc}에서 진행됩니다.",
    "{loc} 인근 맛집 추천해줘.",
    "배송지를 {loc}로 변경해 주세요.",
    "{loc} 지점 오픈 일정 알려줘.",
]


def _span(prompt: str, needle: str, etype: str):
    i = prompt.find(needle)
    assert i >= 0, f"needle {needle!r} not in {prompt!r}"
    return [i, i + len(needle), etype]


# --------------------------------------------------------------------------- 식별번호 생성기 (유효 체크섬)
def make_rrn(rng, gender):  # gender 1-4 내국인 / 5-8 외국인
    body = [rng.randint(0, 9) for _ in range(12)]
    body[6] = gender
    w = [2, 3, 4, 5, 6, 7, 8, 9, 2, 3, 4, 5]
    check = (11 - (sum(body[i] * w[i] for i in range(12)) % 11)) % 10
    d = "".join(map(str, body + [check]))
    assert ck.validate_rrn(d)
    return d[:6] + "-" + d[6:]


def make_brn(rng):
    body = [rng.randint(0, 9) for _ in range(9)]
    w = [1, 3, 7, 1, 3, 7, 1, 3, 5]
    total = sum(body[i] * w[i] for i in range(9)) + (body[8] * 5) // 10
    check = (10 - (total % 10)) % 10
    d = "".join(map(str, body + [check]))
    assert ck.validate_brn(d)
    return d[:3] + "-" + d[3:5] + "-" + d[5:]


def make_card(rng):
    bins = ["4", "51", "52", "53", "54", "55", "37"]
    pre = rng.choice(bins)
    body = [int(c) for c in pre] + [rng.randint(0, 9) for _ in range(15 - len(pre))]
    for c in range(10):
        d = "".join(map(str, body + [c]))
        if ck.validate_luhn(d):
            return d[:4] + "-" + d[4:8] + "-" + d[8:12] + "-" + d[12:]
    raise RuntimeError("luhn")


def make_phone(rng):
    head = rng.choice(["010", "011", "016", "02", "031", "051", "064"])
    mid = "".join(str(rng.randint(0, 9)) for _ in range(4 if head.startswith("01") else 3))
    tail = "".join(str(rng.randint(0, 9)) for _ in range(4))
    sep = rng.choice(["-", "-", " "])
    return f"{head}{sep}{mid}{sep}{tail}"


def make_passport(rng):
    return rng.choice("MSRODP") + "".join(str(rng.randint(0, 9)) for _ in range(8))


def make_license(rng):
    g = lambda n: "".join(str(rng.randint(0, 9)) for _ in range(n))
    return f"{g(2)}-{g(2)}-{g(6)}-{g(2)}"


def make_email(rng):
    u = "".join(rng.choice("abcdefghijklmnopqrstuvwxyz0123456789._") for _ in range(rng.randint(4, 10)))
    dom = rng.choice(["naver.com", "gmail.com", "kakao.com", "company.co.kr", "daum.net"])
    return f"{u.strip('._')}@{dom}"


def make_account(rng):
    g = lambda n: "".join(str(rng.randint(0, 9)) for _ in range(n))
    return rng.choice([f"{g(3)}-{g(6)}-{g(5)}", f"{g(6)}-{g(2)}-{g(6)}", f"{g(4)}-{g(4)}-{g(4)}"])


# --------------------------------------------------------------------------- SECRET 생성기 (패턴 매칭)
def make_secret(rng):
    b62 = lambda n: "".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789") for _ in range(n))
    up = lambda n: "".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") for _ in range(n))
    kind = rng.choice(["aws", "aws_secret", "google", "slack", "github", "openai", "anthropic", "jwt", "generic"])
    if kind == "aws":
        return f"AKIA{up(16)}", "배포 키 {v} 검토 바랍니다."
    if kind == "aws_secret":
        return f"aws_secret_access_key={b62(40)}", "{v}"
    if kind == "google":
        return f"AIza{b62(35)}", "지도 API 키 {v} 노출됐어."
    if kind == "slack":
        return f"xoxb-{b62(24)}", "슬랙 토큰 {v} 회수 필요."
    if kind == "github":
        return f"ghp_{b62(36)}", "깃헙 PAT {v} 가 코드에 남아있음."
    if kind == "openai":
        return f"sk-{b62(32)}", "오픈AI 키 {v} 확인."
    if kind == "anthropic":
        return f"sk-ant-{b62(28)}", "앤트로픽 키 {v} 점검."
    if kind == "jwt":
        return f"eyJ{b62(16)}.eyJ{b62(20)}.{b62(24)}", "세션 JWT {v} 디코딩해줘."
    return f'api_key="{b62(20)}"', "설정파일에 {v} 박혀있음."


# --------------------------------------------------------------------------- benign / hard negatives
HARD_NEG = [
    "송장번호 123456-789 로 배송 추적해줘.",
    "상품코드 900101-XL 재고 확인 부탁해.",
    "주문 수량 12345개 단가 6789원 견적 부탁.",
    "버전 2.0.1-rc 빌드 결과 공유합니다.",
    "이 함수의 시간 복잡도는 O(n log n) 입니다.",
    "회의록 초안 v3 검토해 주세요.",
    "분기 매출은 전년 대비 12.5% 증가했습니다.",
    "운송장 1234-5678-9012 배송 조회.",  # 카드처럼 보이나 Luhn 불통과 의도
    "사번 EMP-2026-0417 인사발령 확인.",
    "주차 구역 B2-104 에 차를 세웠어요.",
    "에러 코드 0x1A2B3C 디버깅 중입니다.",
    "도서 ISBN 978-89-12345-67-8 주문.",
    "택배 박스 규격 350x250x120 으로 포장해줘.",
    "포인트 적립 9001011234560 조회 (영수증 번호).",  # RRN 자리수지만 체크섬 무효(검증)
    "프로젝트 마일스톤 M5 일정 공유.",
]
BENIGN_TOPICS = [
    "파이썬에서 리스트를 정렬하는 가장 빠른 방법이 뭐야?",
    "오늘 회의는 3시에 시작합니다. 안건은 분기 리뷰입니다.",
    "제품 출시일은 다음 달 셋째 주로 확정되었습니다.",
    "신규 기능 배포 전 QA 체크리스트를 정리해줘.",
    "Docker 컨테이너 메모리 제한을 거는 방법 알려줘.",
    "주간 보고서 양식을 템플릿으로 만들어줘.",
    "고객 만족도 설문 문항을 다섯 개 제안해줘.",
    "리액트에서 상태관리 라이브러리 비교해줘.",
    "내일 점심 메뉴 추천 좀 해줄래?",
    "이번 스프린트 회고 안건을 정리하고 싶어.",
    "마케팅 캠페인 KPI 지표를 설명해줘.",
    "SQL 인덱스 튜닝 기본 원칙이 궁금해.",
    "온보딩 문서 목차를 잡아줘.",
    "깃 브랜치 전략(trunk-based) 장단점 알려줘.",
    "회사 워크숍 아이스브레이킹 게임 추천.",
]


def build():
    rng = random.Random(SEED)
    rows = []
    n = [0]

    def add(prompt, expect, spans, cls):
        n[0] += 1
        rows.append({"id": f"{cls}-{n[0]:04d}", "prompt": prompt, "expect": expect,
                     "spans": spans, "source": "synth", "_cls": cls})

    # --- 강한/약한 PII (단일 엔티티/프롬프트, 깨끗한 채점) ---
    def pii_block(cls, n_count, gen, template):
        for _ in range(n_count):
            v = gen(rng)
            p = template.format(v=v)
            add(p, [cls], [_span(p, v, cls)], cls)

    pii_block("KR_RRN", 30, lambda r: make_rrn(r, r.randint(1, 4)), "주민등록번호 {v} 본인확인 처리 바랍니다.")
    pii_block("KR_FOREIGNER_REG", 20, lambda r: make_rrn(r, r.randint(5, 8)), "외국인등록번호 {v} 비자 연장 건입니다.")
    pii_block("KR_BRN", 20, make_brn, "사업자등록번호 {v} 세금계산서 발행 요청.")
    pii_block("KR_PASSPORT", 15, make_passport, "여권번호 {v} 항공권 발권 부탁드립니다.")
    pii_block("KR_DRIVER_LICENSE", 15, make_license, "운전면허번호 {v} 렌터카 예약 진행.")
    pii_block("CREDIT_CARD", 20, make_card, "결제 카드번호 {v} 승인 요청합니다.")
    pii_block("KR_ACCOUNT", 20, make_account, "환불 계좌 {v} 로 입금 부탁드립니다.")
    pii_block("KR_PHONE", 25, make_phone, "연락처 {v} 로 안내 문자 보내주세요.")
    pii_block("EMAIL", 15, make_email, "회신은 {v} 메일로 부탁드립니다.")

    # --- KR_PERSON 80: 미수록 성씨 ≥ 50% 강제 ---
    n_person = 80
    n_unlisted = n_person // 2 + 5  # 45/80 = 56% > 50%
    persons = []
    for i in range(n_person):
        unlisted = i < n_unlisted
        sur = rng.choice(UNLISTED_SURNAMES if unlisted else LISTED_SURNAMES)
        name = sur + rng.choice(GIVEN)
        persons.append((name, unlisted))
    rng.shuffle(persons)
    for name, unlisted in persons:
        p = rng.choice(PERSON_CTX).format(name=name)
        r = {"id": f"KR_PERSON-{n[0]+1:04d}", "prompt": p, "expect": ["KR_PERSON"],
             "spans": [_span(p, name, "KR_PERSON")], "source": "synth", "_cls": "KR_PERSON",
             "_gazetteer_unlisted": unlisted}
        n[0] += 1
        rows.append(r)

    # --- KR_LOCATION 40 (gazetteer 가용 20 + 미수록 20) ---
    for i in range(40):
        loc = rng.choice(GAZ_LOCATIONS if i < 20 else NONGAZ_LOCATIONS)
        p = rng.choice(LOC_CTX).format(loc=loc)
        r = {"id": f"KR_LOCATION-{n[0]+1:04d}", "prompt": p, "expect": ["KR_LOCATION"],
             "spans": [_span(p, loc, "KR_LOCATION")], "source": "synth", "_cls": "KR_LOCATION",
             "_gazetteer_unlisted": i >= 20}
        n[0] += 1
        rows.append(r)

    # --- SECRET 40 ---
    for _ in range(40):
        v, tmpl = make_secret(rng)
        p = tmpl.format(v=v)
        add(p, ["SECRET"], [_span(p, v, "SECRET")], "SECRET")

    # --- benign 150 (음성; FP/precision 분모) — 하드네거티브 포함 ---
    bn = 0
    while bn < 150:
        if bn % 5 == 0:
            p = HARD_NEG[bn // 5 % len(HARD_NEG)]
            tag = "benign_hard"
        else:
            base = BENIGN_TOPICS[bn % len(BENIGN_TOPICS)]
            p = base if bn < len(BENIGN_TOPICS) else f"{base} (#{bn})"
            tag = "benign"
        add(p, [], [], tag)
        bn += 1

    return rows


def split_and_write(rows):
    rng = random.Random(SEED + 1)
    by_cls = {}
    for r in rows:
        by_cls.setdefault(r["_cls"], []).append(r)
    dev, test = [], []
    for cls, items in sorted(by_cls.items()):
        idx = list(range(len(items)))
        rng.shuffle(idx)
        cut = int(len(items) * 0.4)  # 40% dev / 60% test
        for j, k in enumerate(idx):
            (dev if j < cut else test).append(items[k])
    for split in (dev, test):
        split.sort(key=lambda r: r["id"])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, split in (("dev", dev), ("test", test)):
        with open(OUT_DIR / f"{name}.jsonl", "w", encoding="utf-8") as f:
            for r in split:
                out = {k: v for k, v in r.items() if not k.startswith("_")}
                # 메타는 별도 키로 보존(채점 슬라이스용)
                if "_gazetteer_unlisted" in r:
                    out["gazetteer_unlisted"] = r["_gazetteer_unlisted"]
                f.write(json.dumps(out, ensure_ascii=False) + "\n")

    # 매니페스트(규모·구성 검증 + 누수방지 비율 기록)
    pos = [r for r in rows if r["expect"]]
    neg = [r for r in rows if not r["expect"]]
    persons = [r for r in rows if r["_cls"] == "KR_PERSON"]
    unlisted_persons = [r for r in persons if r.get("_gazetteer_unlisted")]
    counts = {}
    for r in rows:
        counts[r["_cls"]] = counts.get(r["_cls"], 0) + 1
    manifest = {
        "seed": SEED,
        "total": len(rows),
        "positives": len(pos),
        "negatives": len(neg),
        "class_counts": counts,
        "dev_size": int(len(rows) * 0.4),
        "person_unlisted_ratio": round(len(unlisted_persons) / len(persons), 3),
        "person_unlisted_n": len(unlisted_persons),
        "split": {"dev_pct": 0.4, "test_pct": 0.6, "stratified": True},
        "note": "test 셋은 튜닝 중 열람 금지(누수 방지). person_unlisted_ratio ≥ 0.5 보장.",
    }
    with open(OUT_DIR / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return manifest


if __name__ == "__main__":
    rows = build()
    m = split_and_write(rows)
    print(json.dumps(m, ensure_ascii=False, indent=2))

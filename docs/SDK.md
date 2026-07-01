# NuFi Python SDK 표면 — 라이브러리 임포트 API (설계 스펙)

> 상태: **설계 확정 대기** (2026-06-29). 본 문서는 v0.1.0 의 Python SDK 표면을
> 정의하는 설계 스펙이다. 구현(파사드 모듈·테스트)은 별도 구현 작업으로 인계한다.
> 방향 근거: [ROADMAP.md](ROADMAP.md) P2 — "CLI 외에 라이브러리로 직접 사용".

NuFi 의 네 가지 기능 — **탐지·가명화·정책 평가·증빙 리포트** — 를 코드에서 한 줄로
임포트해 쓰는 경량 파이썬 SDK 표면을 정의한다. CLI(`nufi-egress`)와 **동일 기능을
라이브러리로** 노출한다. 프론트엔드는 만들지 않는다.

---

## 0. 문제 — 표면이 흩어져 있다

기능은 이미 동작하는 코드로 존재하지만, 공개 표면이 세 곳에 분산돼 있어 라이브러리
사용자가 무엇을 임포트해야 하는지 한눈에 알 수 없다.

| 기능 | 현재 임포트 경로 | 비고 |
|---|---|---|
| 탐지 | `egress_audit.DetectionPipeline`, `Finding` | 한국어 PII·비밀·기밀 통합 |
| 가명화(비가역) | `egress_audit.pseudonymize` 모듈 함수 | 패키지 `__all__` 에 미노출 |
| 가명화(가역) | `egress_audit.ReversibleEgress`, `SurrogateMinter`, `MappingVault` | 노출됨 |
| 정책 평가 | `egress_audit.PolicyEngine`, `Decision`, `EgressGuard`, `GuardResult` | 노출됨 |
| 증빙 리포트 | `enforcement.report` 모듈 함수 | 패키지 표면 아님 |

추가로 `nufi_client` 패키지가 따로 있으나, 이는 **게이트웨이 HTTP/in-process 클라이언트**
(서빙빌더가 앞단에 끼우는 얇은 심)로 본 SDK 표면과 **목적이 다르다**. 본 문서가 정의하는
것은 게이트웨이를 거치지 않고 엔진을 직접 임포트하는 **인프로세스 라이브러리 API** 다.

---

## 1. 설계 원칙

1. **단일 진입점.** 신규 최상위 파사드 패키지 `nufi` 를 만들어 네 기능의 큐레이트된
   심볼을 한 곳에서 재노출한다. 사용자는 `from nufi import ...` 한 줄로 시작한다.
2. **CLI 동등.** SDK 로 할 수 있는 일과 CLI 로 할 수 있는 일을 1:1 로 맞춘다(§3 매핑표).
3. **안정성 계층 분리.** 공개(stable)·고급(advanced)·내부(internal)를 명시한다(§4).
   내부 심볼은 파사드가 재노출하지 않으며, 호환성 약속 대상이 아니다.
4. **경량·무상태 우선.** 가장 흔한 작업(탐지·가명화 한 줄)은 객체 수명관리 없이
   모듈 함수로 끝낼 수 있게 한다. 무거운 객체(모델 로딩)는 명시 생성으로 남긴다.
5. **부수효과 없는 임포트.** `import nufi` 가 모델·config 를 로딩하지 않는다(지연 로딩).
   온프렘·에어갭 제약(외부 호출 0)을 깨지 않는다.

---

## 2. 제안 표면 — `nufi` 파사드

### 2.1 최상위 네임스페이스

```python
import nufi

nufi.__version__          # 루트 VERSION 과 동기화
```

### 2.2 탐지 (Detection)

```python
from nufi import detect, Detector, Finding

# 한 줄 — 기본 설정으로 즉시 탐지
findings = detect("홍길동 주민번호 900101-1234567")
#   -> list[Finding]  (entity_type, text, start, end, score, source, ...)

# 재사용 — 모델을 한 번만 로딩해 반복 탐지
det = Detector(ner_backend="auto", enable_confidential=True)
findings = det.analyze(text)
```

- `Detector` = 현행 `DetectionPipeline` 의 공개 별칭. 생성자 인자 그대로 유지.
- `detect(text, **kwargs)` = 프로세스 캐시된 기본 `Detector` 로 위임하는 편의 함수.
- `Finding` = 현행 dataclass 그대로 재노출.

### 2.3 가명화 (Pseudonymization)

```python
from nufi import pseudonymize, mask, redact, ReversibleEgress

# 비가역 — 결정적 토큰(같은 값 → 같은 토큰), 마스킹, 레닥션
token = pseudonymize("KR_PERSON", "홍길동")     # <KR_PERSON_a1b2c3d4e5>
masked = mask("900101-1234567", keep_tail=4)    # ******-***4567
tag    = redact("RRN")                          # <RRN_REDACTED>

# 가역 — 세션 단위 가명화 후 응답에서 원복
rev = ReversibleEgress()
out = rev.pseudonymize(text, session_id="sess-1")   # RevResult
restored = rev.deanonymize(out.text, session_id="sess-1")
```

- `pseudonymize` = 현행 `pseudonymize.pseudo_token` 의 공개 이름(동사형으로 정렬).
- `mask`, `redact` = 현행 함수 그대로.
- 가역 경로는 현행 `ReversibleEgress`/`SurrogateMinter`/`MappingVault` 를 그대로 노출.
  키 주입(KEK/Vault)은 현행 환경변수·`load_kek` 규약을 유지한다.

### 2.4 정책 평가 (Policy evaluation)

```python
from nufi import Guard, GuardResult, PolicyEngine, Decision

# 탐지 + 정책을 한 번에 — 가장 흔한 사용
guard = Guard()                       # 기본 patterns/policy config
result = guard.inspect(text)          # GuardResult(blocked, decision, findings)
if result.blocked:
    ...

# 정책만 따로 — 이미 가진 findings 에 정책 적용
policy = PolicyEngine(policy_path="config/policy.yaml")
decision = policy.apply(text, findings)   # Decision(blocked, actions, redacted_text)
```

- `Guard` = 현행 `EgressGuard` 의 공개 별칭(탐지+정책 결합 진입점).
- `PolicyEngine`, `Decision`, `GuardResult` = 그대로 재노출.

### 2.5 증빙 리포트 (Compliance / evidence report)

```python
from nufi import compliance_report, render_report, load_catalog

# 모델 구성(전부 read-only 재사용) — 변경감사 + 차단/가명화/우회 요약 + 통제 커버리지
model = compliance_report(
    audit_path="logs/decisions.jsonl",
    change_log_path="logs/policy_changes.jsonl",
    flow_dir="logs/flows",
    controls=True,                    # 점검항목 커버리지 섹션 포함
    catalog_path=None,                # None=기본 통제 카탈로그
)
md = render_report(model, fmt="md")   # "md" | "html" | "json"

# 무결성 게이트는 모델에 담긴다(0=정상 / 1=변조). 커버리지는 정보성.
assert model["integrity"]["ok"] is True
```

- `compliance_report` = 현행 `enforcement.report.build_compliance_report` 의 공개 이름.
- `render_report` = 현행 `enforcement.report.render`.
- `load_catalog` = 통제 카탈로그 로더.
- **종료코드 의미 보존:** 무결성 게이트(0 정상 / 1 변조)는 CLI 와 동일하게 모델 안에
  표현하며, 커버리지는 정보성으로 비-0 을 만들지 않는다([REPORTING.md](REPORTING.md) §3 권위).

### 2.6 벤치마크 재현 (Accuracy + Pseudonymization benchmark)

> §2.1–2.5 는 `nufi` 파사드 **설계**(미구현)지만, 본 벤치마크 표면은 **이미 구현·출하**되어
> 있다(`enforcement.benchmark`, advanced 계층). 파사드가 나중에 재노출할 수 있다.

정확도 게이트(봉인 골드셋 측정 산출물 대조, 모델 재실행 없음)와 가명화 품질 하니스(라이브,
결정적)를 **한 함수**로 재현한다. CLI `nufi-egress benchmark` 와 동일 결과를 반환한다.

```python
from enforcement.benchmark import (run_benchmarks, evaluate_accuracy_gate,
                                   run_pseudonymize_benchmark)

# 한 번에 — 정확도 게이트 + 가명화 품질(전부 결정적, 외부호출 0)
report = run_benchmarks()                 # only=None → 둘 다
assert report["overall_pass"] is True     # 게이트 판정(CLI exit 0 과 동치)

# 축 선택
acc = run_benchmarks(only="accuracy")     # 커밋 측정 JSON → 게이트 대조(모델 불필요)
ps  = run_benchmarks(only="pseudonymize") # 가역/비가역 하니스 라이브 재실행

# 저수준 — 게이트/하니스 개별 호출
gate = evaluate_accuracy_gate()           # {gates:[...], baseline_informational, pass}
quality = run_pseudonymize_benchmark()    # {scores, acceptance, acceptance_pass}
```

- `run_benchmarks(only=None)` = 정확도(`evaluate_accuracy_gate`) + 가명화
  (`run_pseudonymize_benchmark`) 통합 리포트. `overall_pass` 는 CLI 종료코드(0/1)와 동치.
- **정확도 게이트**: KR_PERSON Wilson CI 하한 ≥ 0.85, 온프렘 p95(c≤2) ≤ 목표. I1 공개
  골드셋 baseline 은 정보성(게이트 미산입). 산출물 누락 시 해당 게이트 fail + `missing` 기록.
- **가명화 하니스**: `scripts/bench_pseudonymize.run_all()` 재사용 — 충돌율 0·결정성·원복
  정확·차단 유지 불변식. 실고객 데이터 0(전량 합성).
- 실제 정확도 **재측정**(모델 스택 필요)은 `scripts/export_onnx_int8.py` +
  `scripts/bench_m5.py` 경로(벤치마크 진입점은 커밋된 측정 증거를 대조만 한다).

---

## 3. CLI ↔ SDK 동등 매핑

| CLI | SDK 호출 | 기능 |
|---|---|---|
| (탐지는 CLI 내부 단계) | `detect(text)` / `Detector().analyze(text)` | 탐지 |
| (가명화는 가드 내부 단계) | `pseudonymize/mask/redact`, `ReversibleEgress` | 가명화 |
| `nufi-egress` 집행 결정 | `Guard().inspect(text)` | 탐지+정책 평가 |
| `nufi-egress report compliance` | `compliance_report(...)` + `render_report(...)` | 증빙 리포트 |
| `nufi-egress report sla` | `build_sla_report(...)` (advanced 계층) | 운영 리포트 |
| `nufi-egress benchmark` | `run_benchmarks(only=None)` (구현·출하) | 정확도+가명화 벤치마크 재현 |

> 운영(SLA/대시보드/멀티테넌시)은 ROADMAP §3 에서 제외 대상이다. SDK 는 해당 함수를
> **advanced 계층**으로 남겨 두되 신규 표면을 추가하지 않는다.

---

## 4. 안정성 계층

| 계층 | 의미 | 호환성 약속 | 포함 |
|---|---|---|---|
| **stable** | `from nufi import ...` 최상위 파사드 | 마이너 버전 내 시그니처 유지 | §2.2–2.5 의 굵은 심볼 |
| **advanced** | 하위 패키지 직접 임포트(`egress_audit.*`) | 변경 가능, CHANGELOG 고지 | SLA·가역 내부·풀 설정 |
| **internal** | `_` 접두 또는 미문서 심볼 | 약속 없음 | `_infer_pool`, `_merge` 등 |

파사드 `nufi.__all__` 에는 **stable 만** 담는다. advanced/internal 은 파사드가
재노출하지 않으며, 필요한 사용자는 하위 패키지를 직접 임포트한다.

---

## 5. 구현 인계 — 작업 명세

> 본 절은 사람 개발자(또는 구현 담당)에게 인계할 구현 작업의 수용기준이다.
> 본 SDK 표면 설계는 코드를 새로 구현하지 않으며, 기존 심볼의 **재노출·이름 정렬·
> 문서화**가 핵심이다(신규 알고리즘 없음).

**범위(IN):**
1. 신규 패키지 `nufi/__init__.py` — §2 의 stable 심볼을 기존 모듈에서 재노출(별칭 포함:
   `Detector`=`DetectionPipeline`, `Guard`=`EgressGuard`, `pseudonymize`=`pseudo_token`,
   `compliance_report`=`build_compliance_report`, `render_report`=`render`).
2. 편의 함수 `detect(text, **kw)` — 프로세스 캐시된 기본 `Detector` 위임(지연 로딩).
3. `nufi.__version__` — 루트 `VERSION` 동기화(`pyproject` dynamic version 규약과 일치).
4. `pyproject.toml` `[tool.setuptools] packages` 에 `nufi` 추가.
5. 임포트 부수효과 0 보장(모델/config 지연 로딩) 회귀 테스트.
6. CLI↔SDK 동등 스모크 테스트: `Guard().inspect` 결과가 동일 입력에 대해 CLI 집행
   결정과 일치, `compliance_report` 모델의 무결성 게이트(0/1) 보존.
7. README 진입점에 "라이브러리로 쓰기" 5줄 퀵스타트 링크, HANDS_ON 실습 1개.

**범위(OUT):**
- 새 탐지/가명화/정책 알고리즘. (재노출만)
- 운영(SLA/대시보드/멀티테넌시) 신규 표면.
- 게이트웨이 HTTP 클라이언트 변경(`nufi_client` 는 별개 트랙).
- 프론트엔드.

**수용기준(DoD):**
- `from nufi import detect, Detector, Finding, pseudonymize, mask, redact,
  ReversibleEgress, Guard, GuardResult, PolicyEngine, Decision, compliance_report,
  render_report, load_catalog` 가 모두 성공.
- `import nufi` 가 외부 네트워크 호출 0·모델 로딩 0(지연).
- 문서 가드(`check_doc_style`)·문서 정합 가드(`check_docs`) rc=0.
- 신규 스모크 테스트 통과, 기존 테스트 회귀 없음.
- CHANGELOG `[Unreleased]` 에 SDK 표면 항목 기재.

---

## 6. 미해결·후속

- **OKR 연결:** 본 SDK 표면 → 회사 Objective/KR 매핑(goalId)은 리더십 정합 필요.
- **버전 라인:** v0.1.0 포함 여부·릴리스 시점은 보드 명령 사항(예약 매터).
- **고급 계층 정리:** advanced 로 분류한 SLA 함수의 장기 폐기 여부는 차기 결정.

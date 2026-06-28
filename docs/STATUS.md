# 🧭 STATUS — 내부 진척 & 보드 리뷰 (Internal)

> **이 문서는 내부 거버넌스용입니다.** 공개 제품 개요·설치·사용은 [`../README.md`](../README.md), 문서 지도는 [`README.md`](README.md), 단일 권위 아키텍처는 [`ARCHITECTURE.md`](ARCHITECTURE.md) 를 보세요.
> 여기에는 보드 리뷰 대시보드(마일스톤·이슈별 상태·증거), 오너십/승인 근거를 모읍니다. README 에서 분리해 이동했습니다(소실 없음).

---

## v0.0.3 트랙 — Operate 호라이즌 · 보드 승인·분해 (2026-06-27, CMP-132)

테마 **Operate(관측·보증·운영)**. 보드가 **모든 v0.0.3 개발 작업을 블랭킷 승인**(CMP-132, 2026-06-27) → CPO 가 권장 Must+Should 세트를 자식 이슈로 분해. 제안서: [`PROPOSAL_v0.0.3.md`](PROPOSAL_v0.0.3.md).

| 마일스톤 | 자식 | 트랙 | 오너 | 상태 |
|---|---|---|---|---|
| **M0 선행** | (O5) | v0.0.2 릴리스 태그 컷(VERSION/CHANGELOG 0.0.2 + tag) | **사람 릴리스 오너(미지정)** | blocked — CEO 지명 |
| **M1 Observe+Assure** | CMP-133 | O2 상시 커버리지 보증 + 우회 모니터링/알림 | Engineer (CMP-96) | 승인됨→todo |
| **M1 Observe+Assure** | (O1) | 감사 가시성 대시보드(read-only, Langfuse 기본) | Engineer (CMP-96) | todo |
| **M2 Operate-at-Scale** | (O3) | 정책 운영 규모화(멀티프로파일·롤백) | Engineer (CMP-96) | backlog |

> 거버넌스: 빌드 트랙=CMP-96 상시승인 카브아웃(+보드 v0.0.3 승인). 릴리스 권한(O5)=CMP-60 사람 게이트. OKR: `goalId`=null → CEO 링크 대기.
> 조건부: O4 IDM 문서지문(디자인파트너 수요 신호 시 당김). Won't(이번): 멀티테넌시·RBAC·TLS MITM·임베딩 분류기 → v0.1.0 Scale.

---

## v0.0.2 트랙 — 보드 승인·분해 완료 (2026-06-27, CMP-118)

테마 **Adopt(채택 마찰 해소)**. 보드가 체크박스로 트랙 **D1·D2(배포)·D3·D2(운영)** 채택 → CPO 가 자식 이슈로 분해, 오너=Engineer(보안 상시 승인 CMP-96). 제안서: [`PROPOSAL_v0.0.2.md`](PROPOSAL_v0.0.2.md).

| 마일스톤 | 자식 이슈 | 내용 |
|---|---|---|
| **M1 Adopt** | CMP-119 | thin client SDK(Python, OpenAI 호환 base_url 심) |
| **M1 Adopt** | CMP-120 | `nufi doctor` 진단 CLI(하이브리드 배선·카나리 PII E2E) |
| **M1 Adopt** | CMP-121 | 파이프라인 프리셋(strict-kr-pii/audit-only/pseudonymize-roundtrip) + init |
| **M1 Adopt** | CMP-122 | 단일명령 배포(Compose + 에어갭 번들 + Helm 스텁) |
| **M1 Adopt** | CMP-125 | 서빙빌더 통합/사용 가이드 (capstone, CMP-119~122 blockedBy) |
| **M2 Hardening** | CMP-123 | NER base 격상(KR_PERSON CI 0.85↑) + 동시성/부하 p95 재측정 |
| **M2 Hardening** | CMP-124 | 정책 핫리로드+드라이런 + retain_raw/키 회전 하드닝 |

> Won't(이번): D4 IDM/임베딩 분류기 · 멀티테넌시 · TLS MITM(수요/범위/리스크).

---

## 보드 리뷰 — 전체 진척 한눈에 (2026-06-27)

| 트랙 | 산출물 | 이슈 | 상태 | 핵심 증거 |
|---|---|---|---|---|
| **M1** 게이트웨이 PoC | private 기본 + public 폴백 + public 100% 감사로깅 | CMP-72 | ✅ **검수합격·종결** | `tests/run_acceptance.py` 10/10 |
| **M2** 탐지 파이프라인 | 한국 PII 정규식·체크섬 + NER + 비밀 + 정책 | CMP-72 | ✅ **검수합격·종결** | 동상(M1+M2 합산) |
| **CMP-85** 차등감사·패킷·봇 | P0 메시지스토어 / P1 패킷캡처·우회탐지 / P2 비동기 감사봇 / P3 통합데모 | CMP-85 | ✅ 완료 | P0 4/4·P1 5/5·P2 6/6·데모 6/6 |
| **Enforcement** 우회 차단 | 탐지→실제 차단(nftables 허용목록) | CMP-93→94 | ✅ 빌드·보드 approved | `ENFORCEMENT_BUILD_CMP94.md` |
| **M3** 가역 가명화 | 가명화·원복 + 매핑 Vault | CMP-97 | ✅ 완료 | `egress_audit/pseudonymize.py` |
| **M4** 기밀 1차 탐지 | 키워드/표식 + EDM(구조화·비구조화) | CMP-98 | ✅ 완료 | `IMPL_M4.md` |
| **M5** 벤치·하드닝 | 골드셋 확대·채점 하니스·fail-closed·감사 해시체인 | CMP-99 | ✅ 완료 | 하드닝 12/12 |
| **M5** 실측(KoELECTRA/INT8) | recall·지연 실측 + 잔여게이트 종결 | CMP-100/103/104 | ✅ 완료 | **PII recall 0.946 · INT8 p95 38ms** |

**M5 게이트 최종 판정(CPO CMP-101):** §1.3 7개 게이트 전항 점추정 PASS — PII recall(전체) **0.946**(≥0.90),
강한PII/Secret **1.000**, precision **0.985**, KR_PERSON **0.897**(표본 48→126 확대, CI 절반 축소), benign-FP **0/90**(CMP-103).
잔여 단 1건(INT8 Wilson CI 하한 0.832가 0.85를 ~1.8%p 하회 = 소표본 양자화 노이즈, FP32는 CI 하한까지 PASS)은
**Should 등급으로 종결**, base 모델 격상(option b)은 **M6 이연**. 상세: [`M5_MEASUREMENT_REPORT.md`](M5_MEASUREMENT_REPORT.md).

---

## 마일스톤 트래킹 (전 트랙 ✅ — M6 ① 종결, ② 온프렘 p95만 분리추적)

- **M1** 게이트웨이 PoC (private 기본 + public 폴백 + public 100% 로깅) — ✅ 검수합격·종결 (CMP-72)
- **M2** 탐지 파이프라인 (PII 체크섬 + KoELECTRA/gazetteer NER + 비밀정보 + 정책) — ✅ 검수합격·종결 (CMP-72)
- **CMP-85 P0** 메시지 스토어 분리(private/public in·out) — ✅ / **P1** 패킷 레이어 캡처(content dump + flow tap)·게이트웨이 우회 탐지 — ✅ / **P2** 비동기 감사 봇(producer/consumer·차등 프로파일·우회 상관·준실시간) — ✅ / **P3** 통합 데모(`scripts/demo_cmp85.sh` + `DEMO_CMP85.md`, 6/6 PASS) — ✅
- **Enforcement** 우회 차단 — ✅ 설계(CMP-93) → nftables 허용목록 MVP 빌드(CMP-94, 보드 approved)
- **M3** 가역 가명화/원복 + 매핑 Vault — ✅ (CMP-97)
- **M4** 기밀 1차 탐지(키워드/표식 + EDM) — ✅ (CMP-98, [`IMPL_M4.md`](IMPL_M4.md))
- **M5** 벤치·하드닝 + KoELECTRA/INT8 실측 — ✅ (CMP-99/100/103/104, 게이트 최종판정 CPO CMP-101)
- **M6** 정확도 숙제 — ① **종결** (CMP-145, [`CMP-145-accuracy-debt.md`](reports/CMP-145-accuracy-debt.md)): per-channel 재양자화로 INT8 KR_PERSON CI 하한 **0.832→0.850 (≥0.85)** + 재양자화 정합성 테스트. ② 프로덕션 온프렘 p95 — **분리추적**(온프렘 하드웨어 의존, 보드/CEO 환경 제공 필요)

```
M1 게이트웨이 + M2 PII/비밀 탐지  ──✅ PoC 검수합격·종결 (SPEC.md / DEMO.md)
   └ CMP-85: Public/Private 차등감사 + 패킷레이어 + 비동기 감사봇 ──✅ (SPEC_CMP85 / DEMO_CMP85)
        └ Enforcement: 우회 차단(nftables) ──✅ 설계(CMP-93)→빌드(CMP-94)
M3 가역 가명화/원복 + 매핑 Vault ──✅ (CMP-97, egress_audit/pseudonymize.py)
M4 기밀 1차 탐지(키워드/표식 + EDM) ──✅ (CMP-98, IMPL_M4.md)
M5 벤치·하드닝 + KoELECTRA/INT8 실측 ──✅ (CMP-99/100/103/104, M5_MEASUREMENT_REPORT.md)
   · PII recall 0.946 ≥ 0.90 · INT8 512자 p95 38ms · 하드닝 12/12 · 게이트 최종판정 CPO(CMP-101)
M6 정확도 숙제 ──① ✅ per-channel INT8 KR_PERSON CI 하한 0.832→0.850 (CMP-145) · ② 🔜 온프렘 p95(분리추적)
```

---

## 검증 결과 (재현 가능)

**M1+M2 (현재 저장소, gazetteer 백엔드):** `python3 tests/run_acceptance.py` → **10/10 PASS** (M1 3 + M2 7). `python3 tests/test_cmp85_p0.py` → **4/4 PASS** (P0) · `tests/test_cmp85_p1.py` → **5/5 PASS** (P1) · `tests/test_cmp85_p2.py` → **6/6 PASS** (P2). `scripts/bench.py` → PII recall 1.000(샘플셋), 지연 p95 ≈ 0.06ms.

**M5 실측 (확대 골드셋, KoELECTRA ONNX-INT8 = 프로덕션 목표 백엔드):** `scripts/bench_m5.py --backend onnx-int8 --split test` →
PII recall(전체) **0.946** [CI 0.906–0.970] ≥ 0.90 ✅ · 강한PII/Secret **1.000** · precision **0.985** · KR_PERSON **0.897**(n=126) · benign-FP **0/90** · 512자 p95 **38ms** ≤ 150ms ✅. 하드닝 `tests/test_m5_hardening.py` → **12/12 PASS**(fail-closed·감사 해시체인·원문 미저장). 상세: [`M5_MEASUREMENT_REPORT.md`](M5_MEASUREMENT_REPORT.md).

> ⚠️ **M2 PoC 의 gazetteer recall 1.000 은 사전 과적합**으로 확증됨 — 누수 통제 확대 골드셋(미수록 인명 56%)에선 gazetteer 인명 recall이 0.375로 붕괴. 한국어 PII recall ≥ 0.9 목표는 **KoELECTRA 백엔드로만 달성**(0.809→0.946). gazetteer 는 에어갭 최소보장 라인.

---

## 핵심 결정 (CEO 정렬 완료, 2026-06-24)

| 항목 | 결정 |
|---|---|
| 인터셉션 방식 | **게이트웨이 먼저(LiteLLM/FastAPI), 네트워크 탭은 후속** |
| 구현 리소스 | Engineer 에이전트, 본 `security/` 저장소 |
| KR 목표 | 한국어 PII recall ≥ 0.9 / 인라인 지연 p95 ≤ 150ms(CPU) |
| 라이선스 | 상업 사용 가능만 (NFR4) |

---

## 오너십 / 승인 근거 (거버넌스)

- **상위 이슈:** CMP-71 (설계/제안, CPO) · **구현 이슈:** CMP-72 (Engineer)
- **구현 오너:** Engineer 에이전트. 본 저장소(보안 도메인) 구현은 **상시 승인** 적용 — Engineer 가 건별 보드승인 없이 착수 가능([`../../GOVERNANCE.md`](../../GOVERNANCE.md) 규칙 3, CMP-96). M1/M2 당시엔 CMP-58 건별 승인이었음.
- **설계 근거:** [`PROPOSAL.md`](PROPOSAL.md) · **구현 명세:** [`SPEC.md`](SPEC.md). 설계 문서는 CPO 산출, 코드는 Engineer 구현.
- **게이트 판정:** M5 §1.3 게이트 최종판정은 CPO(CMP-101). Enforcement(CMP-94)는 보드 approved.

*최종 갱신: 2026-06-27 (CMP-114, Engineer) — README 에서 보드 리뷰 대시보드·거버넌스 표기를 분리해 이동(소실 없음).*

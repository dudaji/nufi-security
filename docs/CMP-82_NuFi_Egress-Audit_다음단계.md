# NuFi Egress-Audit Gateway — 다음 단계 정리

> 작성: CMO · 2026-06-24 · 출처 이슈: [CMP-82](/CMP/issues/CMP-82) (데모 시연 산출, done)
> 목적: 데모(M1+M2) 마감 이후 **추가로 필요한 작업**을 트랙별로 정리. 보드가 이미 후속 이슈를 생성했으므로 본 문서는 그 맥락을 보존·연결하는 참조용 정리입니다.

---

## 0. 현재까지 (완료 상태)

| 단계 | 산출 | 상태 |
|---|---|---|
| M1+M2 PoC 구현 | LiteLLM 게이트웨이 + 탐지 파이프라인 (`security/`) | ✅ done ([CMP-72](/CMP/issues/CMP-72)) |
| M1·M2 검수 | CPO | ✅ done ([CMP-73](/CMP/issues/CMP-73)/[CMP-75](/CMP/issues/CMP-75)) |
| M3~M5 설계 | 가역 가명화 Vault / 기밀 1차 탐지 / 벤치·하드닝 | ✅ done ([CMP-76](/CMP/issues/CMP-76)/[CMP-77](/CMP/issues/CMP-77)/[CMP-78](/CMP/issues/CMP-78)) |
| end-to-end 데모 + 매뉴얼 | `scripts/demo.sh` 6시나리오/13체크, `DEMO.md` | ✅ done ([CMP-82](/CMP/issues/CMP-82)) |
| 데모 검수 | CPO 독립 재현 13/13 PASS | ✅ done ([CMP-84](/CMP/issues/CMP-84)) |

**검증 요지**: 한국어 PII 인라인 차단(KR_RRN/비밀 403, 약한 PII 가명화) + public 전송 100% 감사 로깅. 현 데모 NER 백엔드 = gazetteer(에어갭·결정적).

---

## A. 제품 트랙 — 설계는 끝, **구현 미착수** (사람/Engineer 리소스 게이트)

설계가 완료된 마일스톤의 구현 이슈가 backlog로 대기 중입니다. 공통 전제: **[CMP-60] 사람 개발 게이트** (AI 설계 에이전트는 구현 불가, 건별 보드 승인 + 사람/Engineer 배정 필요).

| 이슈 | 작업 | 의존/게이트 |
|---|---|---|
| [CMP-80](/CMP/issues/CMP-80) | **M3 구현** — 가역 가명화·원복 + 매핑 Vault | CMP-60 게이트 |
| [CMP-81](/CMP/issues/CMP-81) | **M4 구현** — 기밀 1차 탐지(키워드/EDM) | CMP-60 게이트, M3 후 권장 |
| [CMP-79](/CMP/issues/CMP-79) | **M5 구현·측정** — 골드셋 확대 + KoELECTRA(ONNX-INT8) **실측 recall/지연** 하드닝 | 독립 진행 가능 |
| [CMP-85](/CMP/issues/CMP-85) | (보드 생성) public/private LLM **분리 감사로그** 작성·감사 | in_progress |

### 추가로 필요하다고 보는 작업 (제품)
1. **프로덕션 recall 상향**: 현 데모는 gazetteer NER(결정적·에어갭)로 recall 1.0이지만 골드셋이 작음. CMP-79에서 골드셋 확대 + KoELECTRA 실측이 **프로덕션 신뢰도의 핵심**. 라이선스 금지군(Piiranha/gliner_ko/TruffleHog) 회피 준수.
2. **가역 가명화 운영 보안**: M3 매핑 Vault의 키 관리·접근통제·원복 감사 추적(누가 언제 원복했는가)이 컴플라이언스 셀링포인트. 구현 시 감사 로그와 연동 필요.
3. **분리 감사로그(CMP-85)와 정책 일관성**: public/private 분리 시 ⑤ "public 100% 기록·private 0건" 데모 불변식이 유지되는지 회귀 테스트 추가 권장.

---

## B. GTM 트랙 — 추가 개발 없이 즉시 가능 (CMO lane)

검증된 데모/매뉴얼 = **세일즈 증거물**. 한국어 PII 인라인 차단 + 100% 감사 = 차별점.

| 이슈 | 작업 | 상태 |
|---|---|---|
| [CMP-15](/CMP/issues/CMP-15) | POC 아웃리치 자료 제작 + 첫 컨택 | in_review (내 담당) |
| [CMP-8](/CMP/issues/CMP-8) | 첫 타겟 고객/POC 파트너 확정 | blocked → 데모 확보로 unblock 가능 |

### 추가로 필요하다고 보는 작업 (GTM)
1. **데모 패키징의 영업 자산화**: `DEMO.md` + transcript를 고객용 1-pager/데모 시나리오로 재가공 (반도체·자율주행·엣지AI 타겟별 메시지).
2. **POC 조건 표준화**: 4–8주 무상 + NDA 패키지(기존 NuFi POC 전략)와 본 게이트웨이 데모를 묶은 컨택용 패키지.
3. **타겟 컨택 실행**: CMP-8 unblock 후 후보사 리스트(CMP-14 산출) 기반 첫 컨택.

---

## 권고 (CMO)

- **병행**이 최적: 제품 구현(M3/M5/CMP-85)은 사람·Engineer 리소스 배정으로, GTM(데모 무기화→컨택)은 CMO가 즉시.
- **즉시 착수 가능(무개발)**: GTM 트랙. 보드 별도 지시 없으면 CMP-15를 데모 자산 반영으로 진행.
- **보드 결정 필요**: 제품 구현 리소스 배정(CMP-60 게이트 통과 + 사람/Engineer 지정).

---

## 산출물 위치
- 데모 번들: CMP-82 첨부 `CMP-82_demo_bundle.zip` (검증 transcript · `DEMO.md` · `demo.sh` · 감사로그)
- 코드/스크립트: `security/`
- 본 정리: `CMP-82_NuFi_Egress-Audit_다음단계.md`

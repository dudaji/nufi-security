# 규정준수 리포트
**고객:** Acme Corp  
**해시체인 무결성:** ✅ 무결성 정상

> 기존 감사 로그·변경 감사·flow tap 재사용 — 새 측정 없음(read-only).

## 1. 정책 변경 감사 (누가·언제·무엇)
로그: `/mnt/c/Users/shhon/Desktop/Dudaji-pc-home/security/samples/sla/policy_changes.jsonl`  ·  총 5건  ·  체인: **OK** (5건)

| 시각 | 주체 | 동작 | 프로파일 | 버전 | 메모 |
|---|---|---|---|---|---|
| 2026-06-28T06:36:29+0000 | alice | register | strict-kr-pii | — | 초기 strict 프로파일 등록 |
| 2026-06-28T06:36:29+0000 | alice | snapshot | strict-kr-pii | v1 | v1 적재 |
| 2026-06-28T06:36:30+0000 | bob | bind | strict-kr-pii | — | acme 테넌트 묶기 |
| 2026-06-28T06:36:30+0000 | alice | snapshot | strict-kr-pii | v1→v2 | 규정 업데이트 반영 |
| 2026-06-28T06:36:30+0000 | carol | rollback | strict-kr-pii | v2→v1 | 오탐 급증 — 무재기동 되돌리기 |

## 2. 차단·가명화 집계
감사 행 5건  ·  감사 해시체인: **OK**

| 항목 | 건수 |
|---|---|
| outcome:blocked | 3 |
| outcome:allowed | 1 |
| outcome:pseudonymized | 1 |
| action:pseudonymize | 4 |
| action:block | 3 |

**차단 엔티티별:** KR_RRN=2, KR_PERSON=2, KR_PHONE=1, SECRET=1

## 3. 우회 탐지 요약
관측 flow 3건  ·  **우회 1건**

| 시각 | 목적지 | 프로세스 | 심각도 |
|---|---|---|---|
| 2026-06-23T11:30:00+0900 | api.anthropic.com | rogue_script | high |


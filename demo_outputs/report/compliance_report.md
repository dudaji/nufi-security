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

## 4. 점검항목 커버리지 (control coverage)
카탈로그 v1.0  ·  **직접 8**(충족 8/미충족 0)  ·  **부분 6**  ·  **범위밖 5**

> 금융보안원 안내서 점검항목 + 망분리 평가기준 대비 NuFi 통제 충족 — 위 증빙에서 자동 산출(정보성; 종료코드 미반영).

| 항목 | 출처 | 요구사항 | NuFi 통제 | 충족 | 증빙/보강 |
|---|---|---|---|---|---|
| C-07 | 안내서 점검 ⑦ | 입출력 고유식별정보·개인신용정보 탐지/마스킹 | 한국어 PII 탐지·차단·가명화 | ✅ 충족 | action_counts[mask=0, block=3, pseudonymize=4]; decisions.blocked_by_entity#=4 |
| C-26 | 안내서 점검 26 | 데이터 국외이전 차단 | egress 차단(국외 목적지) — 차단 결정으로 증빙 | ✅ 충족 | action_counts[block=3] |
| C-24 | 안내서 점검 24 | 자동화 접근 모니터링 + 최소권한 | 감사 결정 로깅 + 세션 RBAC(viewer/operator) | ✅ 충족 | decisions.total=5 |
| M-1.2 | 망분리 1.2 | 입출력 로그 보존 | 감사 해시체인 로그(보존 + 무결성) | ✅ 충족 | decisions.total=5; decisions.chain.ok=True |
| M-2.4 | 망분리 2.4 | 중요정보 입력 방지 | 입력측 PII 차단/마스킹 결정 | ✅ 충족 | action_counts[mask=0, block=3] |
| M-2.5 | 망분리 2.5 | 출력/모델정보 노출 방지 | 출력측 필터(마스킹·가명화·차단) 결정 | ✅ 충족 | action_counts[mask=0, block=3, pseudonymize=4] |
| M-3.1 | 망분리 3.1 | 중요정보 업로드 차단 | egress 업로드 차단 결정 | ✅ 충족 | action_counts[block=3] |
| M-2.7 | 망분리 2.7 | 위변조 방지 형상관리 | 감사·변경 해시체인 무결성(audit_chain + change_chain) | ✅ 충족 | integrity_ok=True |
| C-06/09 | 안내서 점검 ⑥·⑨ | 회피공격(프롬프트 인젝션·탈옥) 탐지 | 입출력 필터(룰) — 가드모델 미연동 | 🟡 부분충족 | P2 — 생성형 회피공격 인라인 가드모델 |
| C-12 | 안내서 점검 ⑫·망 2.6 | 사용자별 요청 횟수 제한 | (미구현) | 🟡 부분충족 | P1 — 테넌트/사용자별 rate limit |
| C-11 | 안내서 점검 ⑪·32~35 | 실시간 모니터링·정기점검·보고 | SLA/리포트(수동 산출) | 🟡 부분충족 | P1+ — 모니터링·보고 자동화 |
| C-14/17 | 안내서 점검 ⑭·⑰ | 자산·모델 파일 해시 인벤토리 | 감사 무결성(부분) — 자산 해시 인벤토리 미구현 | 🟡 부분충족 | P3 — 자산 무결성 인벤토리 |
| C-25 | 안내서 점검 25 | 킬스위치 | bypass 차단·전 규칙 제거(부분) — 명시적 킬스위치 미정의 | 🟡 부분충족 | P3 — 명시적 킬스위치 |
| C-23 | 안내서 점검 23 | 모델·학습데이터 접근통제(RBAC) | 리포트 RBAC(부분) — 자산 RBAC 미구현 | 🟡 부분충족 | P1+ — 자산 RBAC |
| OOS-ROBUST | 안내서 7.6 | 판단형 적대적 robustness 검증 | 범위밖 — 파트너/이연 | ⛔ 범위밖 | — |
| OOS-POISON | 안내서 7.3 | 데이터·모델 오염 공격 방어 | 범위밖 — 파트너/이연 | ⛔ 범위밖 | — |
| OOS-SBOM | 안내서 7.4 | 공급망 SBOM | 범위밖 — 파트너/이연 | ⛔ 범위밖 | — |
| OOS-EDU | 안내서 일반 | AI 보안 교육 | 범위밖 — 파트너/이연 | ⛔ 범위밖 | — |
| OOS-3RDPARTY | 안내서 7.6 | 제3자 검증 프로세스 | 범위밖 — 파트너/이연 | ⛔ 범위밖 | — |


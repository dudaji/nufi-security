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
카탈로그 v1.1  ·  **직접 23**(충족 23/미충족 0)  ·  **부분 9**  ·  **범위밖 8**

> 한국 규제(금융 AI 안내서·망분리·개인정보보호법·신용정보법·ISMS-P) 대비 NuFi 통제 충족 — 위 증빙에서 자동 산출(정보성; 종료코드 미반영). 동일 통제가 여러 규제를 충족(maps_to)함을 규제별 행으로 투명하게 보인다.

### 프레임워크별 소계
| 규제 | 직접(충족/미충족) | 부분 | 범위밖 |
|---|---|---|---|
| 금융분야 AI 보안 안내서 (fsec-ai) | 3 (3/0) | 6 | 5 |
| 망분리 보안대책 (net-sep) | 5 (5/0) | 0 | 0 |
| 개인정보보호법 (pipa) | 6 (6/0) | 1 | 1 |
| 신용정보법 (cia) | 4 (4/0) | 1 | 0 |
| ISMS-P 인증기준 (isms-p) | 5 (5/0) | 1 | 2 |

### 금융분야 AI 보안 안내서 (fsec-ai) — 직접 3(충족 3/미충족 0)·부분 6·범위밖 5
| 항목 | 출처 | 요구사항 | NuFi 통제 | 충족 | 증빙/보강 |
|---|---|---|---|---|---|
| C-07 | 안내서 점검 ⑦ | 입출력 고유식별정보·개인신용정보 탐지/마스킹 | 한국어 PII 탐지·차단·가명화 | ✅ 충족 | action_counts[mask=0, block=3, pseudonymize=4]; decisions.blocked_by_entity#=4 |
| C-26 | 안내서 점검 26 | 데이터 국외이전 차단 | egress 차단(국외 목적지) — 차단 결정으로 증빙 | ✅ 충족 | action_counts[block=3] |
| C-24 | 안내서 점검 24 | 자동화 접근 모니터링 + 최소권한 | 감사 결정 로깅 + 세션 RBAC(viewer/operator) | ✅ 충족 | decisions.total=5 |
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

### 망분리 보안대책 (net-sep) — 직접 5(충족 5/미충족 0)·부분 0·범위밖 0
| 항목 | 출처 | 요구사항 | NuFi 통제 | 충족 | 증빙/보강 |
|---|---|---|---|---|---|
| M-1.2 | 망분리 1.2 | 입출력 로그 보존 | 감사 해시체인 로그(보존 + 무결성) | ✅ 충족 | decisions.total=5; decisions.chain.ok=True |
| M-2.4 | 망분리 2.4 | 중요정보 입력 방지 | 입력측 PII 차단/마스킹 결정 | ✅ 충족 | action_counts[mask=0, block=3] |
| M-2.5 | 망분리 2.5 | 출력/모델정보 노출 방지 | 출력측 필터(마스킹·가명화·차단) 결정 | ✅ 충족 | action_counts[mask=0, block=3, pseudonymize=4] |
| M-3.1 | 망분리 3.1 | 중요정보 업로드 차단 | egress 업로드 차단 결정 | ✅ 충족 | action_counts[block=3] |
| M-2.7 | 망분리 2.7 | 위변조 방지 형상관리 | 감사·변경 해시체인 무결성(audit_chain + change_chain) | ✅ 충족 | integrity_ok=True |

### 개인정보보호법 (pipa) — 직접 6(충족 6/미충족 0)·부분 1·범위밖 1
| 항목 | 출처 | 요구사항 | NuFi 통제 | 충족 | 증빙/보강 |
|---|---|---|---|---|---|
| PIPA-23 (←C-07) | 개인정보보호법 §23(민감정보) | 민감정보 처리제한 | 한국어 민감정보 탐지·마스킹·차단 | ✅ 충족 | action_counts[mask=0, block=3]; decisions.blocked_by_entity#=4 |
| PIPA-24 | 개인정보보호법 §24(고유식별정보) | 고유식별정보(주민·외국인등록·여권·운전면허) 처리제한 | 고유식별정보 탐지·차단·가명화 | ✅ 충족 | action_counts[mask=0, block=3, pseudonymize=4] |
| PIPA-28-2 | 개인정보보호법 §28-2(가명정보) | 가명정보 처리 | 가명화(pseudonymize) 결정 | ✅ 충족 | action_counts[pseudonymize=4] |
| PIPA-29-LOG (←M-1.2) | 개인정보보호법 §29(안전조치) | 접속기록 보관 | 감사 해시체인 로그(보존) | ✅ 충족 | decisions.total=5; decisions.chain.ok=True |
| PIPA-29-INTEG (←M-2.7) | 개인정보보호법 §29(안전조치) | 위변조 방지 | 감사·변경 해시체인 무결성 | ✅ 충족 | integrity_ok=True |
| PIPA-17-18 (←C-26) | 개인정보보호법 §17·§18 | 국외이전·제3자 제공 제한 | egress 국외 차단 결정 | ✅ 충족 | action_counts[block=3] |
| PIPA-29-AC | 개인정보보호법 §29(안전조치) | 접근통제 최소권한 | 리포트 RBAC(부분) — 자산 RBAC 미구현 | 🟡 부분충족 | P1+ — 자산 RBAC |
| PIPA-21 | 개인정보보호법 §21(파기) | 개인정보 파기 | 범위밖 — 게이트웨이는 처리시점 통제(파기 라이프사이클 비범위) | ⛔ 범위밖 | — |

### 신용정보법 (cia) — 직접 4(충족 4/미충족 0)·부분 1·범위밖 0
| 항목 | 출처 | 요구사항 | NuFi 통제 | 충족 | 증빙/보강 |
|---|---|---|---|---|---|
| CIA-PII (←C-07) | 신용정보법(개인신용정보 보호) | 개인신용정보(계좌·카드·신용) 탐지·마스킹 | 개인신용정보 탐지·차단·마스킹 | ✅ 충족 | action_counts[mask=0, block=3]; decisions.blocked_by_entity#=4 |
| CIA-17-2 | 신용정보법 §17-2(가명처리) | 개인신용정보 가명처리 | 가명화(pseudonymize) 결정 | ✅ 충족 | action_counts[pseudonymize=4] |
| CIA-20 (←M-1.2) | 신용정보법 §20(이용·제공 기록) | 신용정보 이용·제공 내역 기록 보존 | 감사로그 보존(해시체인) | ✅ 충족 | decisions.total=5; decisions.chain.ok=True |
| CIA-XBORDER (←C-26) | 신용정보법(국외이전·제공) | 신용정보 국외이전·제공 제한 | egress 차단 결정 | ✅ 충족 | action_counts[block=3] |
| CIA-19 | 신용정보법 §19(전산시스템 안전보호) | 신용정보전산시스템 안전보호(접근통제·침입탐지·위변조방지) | 무결성+RBAC(부분) — 침입탐지(IDS) 미구현 | 🟡 부분충족 | P3 — 침입탐지·자산 RBAC |

### ISMS-P 인증기준 (isms-p) — 직접 5(충족 5/미충족 0)·부분 1·범위밖 2
| 항목 | 출처 | 요구사항 | NuFi 통제 | 충족 | 증빙/보강 |
|---|---|---|---|---|---|
| ISMS-2.9.4 (←M-1.2) | ISMS-P 2.9.4 | 로그 및 접속기록 관리 | 감사 해시체인 로그 | ✅ 충족 | decisions.total=5; decisions.chain.ok=True |
| ISMS-2.9.1 (←M-2.7) | ISMS-P 2.9.1 | 변경관리 위변조방지 | 변경 해시체인 무결성 | ✅ 충족 | integrity_ok=True |
| ISMS-2.6 | ISMS-P 2.6 | 접근통제 | 세션 RBAC(viewer/operator) — 자산 RBAC 미구현 | 🟡 부분충족 | P1+ — 자산 RBAC |
| ISMS-3.1 (←M-2.4) | ISMS-P 3.1 | 개인정보 수집 시 보호조치(입력측) | 입력측 PII 차단/마스킹 결정 | ✅ 충족 | action_counts[mask=0, block=3] |
| ISMS-3.2 (←M-2.5) | ISMS-P 3.2 | 개인정보 이용·보유 보호조치 | 마스킹·가명화 결정 | ✅ 충족 | action_counts[mask=0, block=3, pseudonymize=4] |
| ISMS-3.3 (←C-26) | ISMS-P 3.3 | 개인정보 제공 보호조치(국외이전 포함) | egress 차단 결정 | ✅ 충족 | action_counts[block=3] |
| ISMS-3.4 | ISMS-P 3.4 | 개인정보 파기 | 범위밖 — 파기 라이프사이클 비범위 | ⛔ 범위밖 | — |
| ISMS-2.11/2.12 | ISMS-P 2.11·2.12 | 사고 예방·대응 / 재해복구 | 범위밖 — 파트너/이연 | ⛔ 범위밖 | — |


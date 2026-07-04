# 프로젝트 현재 상태 & 남은 일 (Project State) — 인수인계용

> 이어받는 사람/AI가 "무엇이 되어 있고, 무엇이 남았고, 어디를 조심해야 하나"를 파악하도록
> 정리했습니다. 수치의 권위는 `docs/reports/*.json`, 변경 이력의 권위는 `CHANGELOG.md` 입니다.

*작성 시점: 2026-07-03 · 최종 갱신: 2026-07-04 · 대상: v0.4.16-patch47 (main, origin 동기화됨)*

---

## 1. 버전 이력 요약

| 버전 | 테마 | 핵심 내용 |
|---|---|---|
| **v0.4.16-patch47** | MANUAL §9 용어집 확장 | Wilson CI·강한/약한 PII·가역성·PII 라우팅 등 7개 항목 추가 |
| **v0.4.16-patch46** | RELEASE_NOTES 성과 요약 표 | 패치 시리즈 8개 지표 패치 이전/이후 비교 표 추가 |
| **v0.4.16-patch45** | MANUAL 부록 문서 지도 완성 | SDK·PII_ROUTING·RELEASE_NOTES·DOC_STYLE 링크 추가, 잔재 XML 태그 제거, 내부 링크 145개 |
| **v0.4.16-patch44** | SDK Finding 필드 표 | Finding dataclass 7개 필드 타입·설명 표 추가 |
| **v0.4.16-patch43** | MANUAL §3 PII 클래스 표 | 탐지 대상 PII 12종 표 추가(클래스·설명·방식·강한/약한 구분) |
| **v0.4.16-patch42** | REPORTING 커버리지 수치 표 | 5종 규제 프레임워크별 direct/partial/oos 항목 수 표 추가 |
| **v0.4.16-patch41** | reports/README JSON 키 구조 | recall-int8.json Python 접근 예시·키 구조 안내 추가 |
| **v0.4.16-patch40** | PROJECT_STATE 이력 현행화 | §4 갭 점검에 patch14~39 교차링크 보강 이력 16항목 추가 |
| **v0.4.16-patch39** | docs/README 관련 문서 | docs/README.md 관련 문서 섹션 신설 |
| **v0.4.16-patch38** | reports/README 관련 문서 | docs/reports/README.md 관련 문서 섹션 신설 |
| **v0.4.16-patch37** | RELEASE_CHECKLIST 관련 문서 | RELEASE_CHECKLIST.md 관련 문서 섹션 신설 |
| **v0.4.16-patch36** | HANDOVER·DOC_STYLE 관련 문서 | AGENT_OPERATING_MODEL·ENGINEERING_CONVENTIONS·DOC_STYLE 관련 문서 섹션 신설 |
| **v0.4.16-patch35** | CLI·HANDS_ON 관련 문서 | CLI.md·HANDS_ON.md 관련 문서 섹션 신설 |
| **v0.4.16-patch34** | CHANGELOG·HANDOVER 현행화 | patch33~34 이력 기록, RELEASE_NOTES 확장 |
| **v0.4.16-patch33** | research/ 전략 문서 관련 문서 | FSEC·SOLUTION_FOCUS·CHARTER 관련 문서 표 신설 |
| **v0.4.16-patch32** | CHANGELOG·HANDOVER 현행화 | patch30~32 이력 기록, RELEASE_NOTES 확장 |
| **v0.4.16-patch31** | goldset README 관련 문서 | reports/README·HANDS_ON·kr-person-error-analysis 교차링크 |
| **v0.4.16-patch30** | nufi_client README 보강 | 통합 가이드 링크 확정, SDK·INTEGRATION_GUIDE·examples 교차링크 |
| **v0.4.16-patch29** | CHANGELOG·HANDOVER 현행화 | patch26~29 이력 기록, RELEASE_NOTES 확장 |
| **v0.4.16-patch28** | INTEGRATION_GUIDE 관련 문서 | PRESETS·CLI·SDK·HANDS_ON·PII_ROUTING·OPS_RULE_RELOAD 교차링크 |
| **v0.4.16-patch27** | docs/README 진입점 링크 | history/README·research/README 진입점 추가 |
| **v0.4.16-patch26** | examples/README 관련 문서 | SDK·HANDS_ON·REPORTING·DEMO 교차링크 |
| **v0.4.16-patch25** | CHANGELOG·HANDOVER 현행화 | patch23~25 이력 기록, RELEASE_NOTES 확장 |
| **v0.4.16-patch24** | DEMO·ROADMAP 관련 문서 | HANDS_ON·examples·CLI·INTEGRATION_GUIDE·REPORTING·PII_ROUTING 교차링크 |
| **v0.4.16-patch23** | REPORTING 관련 문서 | SDK·CLI·examples·OPS·SECURITY·research 교차링크 |
| **v0.4.16-patch22** | CHANGELOG·HANDOVER 현행화 | patch20~22 이력 기록, RELEASE_NOTES 확장 |
| **v0.4.16-patch21** | PII_ROUTING 관련 문서 | INTEGRATION_GUIDE·SDK·ARCHITECTURE·ROADMAP 교차링크 |
| **v0.4.16-patch20** | SDK 관련 문서 | examples·HANDS_ON·INTEGRATION_GUIDE·REPORTING·PII_ROUTING·CLI 교차링크 |
| **v0.4.16-patch19** | history/README 신설 | 역사적 스냅샷 6종 인덱스·열람 가이드 |
| **v0.4.16-patch18** | research/README 신설 | 조사·전략 문서 3종 인덱스·배경 설명 |
| **v0.4.16-patch17** | SECURITY_RETAIN_RAW 링크 | 관련 문서 섹션(OPS_RULE_RELOAD·PRESETS·REPORTING) 신설 |
| **v0.4.16-patch16** | OPS 관련 문서 섹션 | OPS_RULE_RELOAD·OPS_POLICY_AT_SCALE 관련 문서 표 신설 |
| **v0.4.16-patch15** | 교차링크 보강 | INTEGRATION_GUIDE §5 PII_ROUTING 링크, PRESETS 관련 문서 섹션 신설 |
| **v0.4.16-patch14** | MANUAL SDK 링크 | MANUAL.md SDK 예시 examples/README.md(7종) 인덱스 링크 |
| **v0.4.16-patch13** | MANUAL 정확도 정정 | MANUAL.md §3 0.977→0.9908 현행화, RELEASE_NOTES 패치 시리즈 확장 |
| **v0.4.16-patch12** | HANDOVER·research 인덱스 | HANDOVER README 버전 갱신, docs/README research 섹션, patch11 이력 |
| **v0.4.16-patch10** | 문서 풍부화 4차 | docs/README research 섹션, ARCHITECTURE §8 링크, REPORTING SDK §4, test docstring 7종, HANDOVER 버전 갱신 |
| **v0.4.16-patch09** | 문서 풍부화 3차 | RELEASE_NOTES 패치 시리즈 요약, ROADMAP P1·P2 완료, SDK Finding 메서드 설명, 교차링크 보강 |
| **v0.4.16-patch08** | CLI·goldset 문서 | CLI.md SDK 예시 표, goldset README 프로그래밍 가이드 |
| **v0.4.16-patch07** | HANDOVER 현행화 | PROJECT_STATE patch06 기준 버전 이력·갭 점검 |
| **v0.4.16-patch06** | Finding.__repr__ + examples/README | Finding repr 개선(None 필드 제거·score 포맷), examples/ 인덱스 README 신설 |
| **v0.4.16-patch05** | 문서 풍부화 | ARCHITECTURE 컴포넌트 표, DEMO SDK 섹션, SDK/MANUAL/INTEGRATION_GUIDE 교차링크, FN §7.6 분석 |
| **v0.4.16-patch04** | examples 확장 + 문서 보강 | examples 7종 스모크(sdk_file_scan·sdk_compliance_report 추가), 307 테스트, 보고서 인덱스, 잔여 FN §7.6 |
| **v0.4.16** | KR_PERSON CI 하한 달성 | UNLISTED_SURNAMES 재설계 → person_recall 0.9799, CI 하한 0.9591 ≥ 0.93 ✅ (n=854) |
| **v0.4.15** | 골드셋 정합 복원 | 미수록 성씨 목록 정합, 전체 테스트 통과 복원 |
| **v0.4.14** | 확장 골드셋 확정 | 극희성 54건 추가(n=818), recall-int8.json 갱신 |
| **v0.4.13** | 체크섬 골드셋 + CI 강화 | KR_PERSON test 258건, person_recall_ci_low ≥ 0.93 게이트 상향 |
| **v0.4.12** | KR_ACCOUNT·SECRET CI 마감 | CI 하한 ≥0.90 달성, 전체 골드셋 1,144건 |
| **v0.4.11** | 문서 풍부화 + 골드셋 확대 | RELEASE_NOTES 5버전 추가, goldset README 현행화 |
| **v0.4.6** | SDK 편의 함수 | `scan_file`·`guard_file`·`batch_detect` 편의 함수 추가 |
| **v0.4.1** | Python SDK 파사드 | `nufi/` 패키지 — `from nufi import detect, Guard, pseudonymize` |
| **v0.4.0** | 규제 증빙 48통제 + PII 라우팅 | 컴플라이언스 매핑 48개 통제 완성 + PII 기반 하이브리드 LLM 라우팅 Phase 1 |
| **v0.3.0** | 인명 정확도 달성 | KR_PERSON 재현율 0.9516(Wilson 하한 0.91+), 전체 PII 재현율 0.977 |
| **v0.2.x** | 주소·수치 무결성 | KR_LOCATION 유니온 0.79→1.0 + 공개 수치 드리프트 교정 + 인명 오차 분석 |
| **v0.1.0** | 방향 재설정 | 경량 CLI/SDK·한국 규제 증빙 특화 재정의, 골드셋 정식화·baseline·가명화 벤치 |
| v0.0.x | 기반 구축 | 게이트웨이·탐지·가명화·기밀 탐지·우회 차단·비동기 감사·정책 운영·매뉴얼 |

- 상세 내러티브: [`../docs/RELEASE_NOTES.md`](../docs/RELEASE_NOTES.md), 전체 변경: [`../CHANGELOG.md`](../CHANGELOG.md).
- **로드맵/방향:** [`../docs/ROADMAP.md`](../docs/ROADMAP.md) — 한국어 PII·규제 증빙 우선,
  CLI/SDK 경량, **운영(멀티테넌시/SLA/대시보드) 레이어는 의도적으로 강등**. 게이트웨이 코어는
  데모·검증·"직접 구현" 차별점 근거로 유지.

## 2. 알려진 한계 (Known Limitations)

- **외부 원문 보존:** 켜면 외부로 나간 원문(개인정보 포함 가능)이 디스크에 남습니다(기본 꺼짐).
  켤 때는 접근 제어·보존기간·파기 절차를 반드시 정의(README 설정 주의 참조).
- **라이브 패킷 캡처:** 관리자 권한(root/CAP_NET_RAW) 필요. 에어갭·CI 는 `--simulate` 리플레이.
- **프로덕션 온프렘 지연:** 일부 유니온/onnx-int8 실측이 미프로비저닝 환경에서 skip 됨
  (정직하게 skip 리포트로 기록). → 후속: 프로덕션 온프렘 지연 재측정.

## 3. 열린 후속 과제 (Open Follow-ups)

| 과제 | 상태 | 다음 행동 |
|---|---|---|
| 프로덕션 온프렘 지연 재측정 | 하드웨어 대기 | 온프렘 환경 확보 시 실측 |
| 한국어 생성형 가드레일(프롬프트 인젝션·탈옥) | 차기 옵션(L) | 로드맵 P차기 |

### 완료된 과제 (v0.3.0~v0.4.16 에서 해소)

| 과제 | 해소 버전 |
|---|---|
| 인명(KR_PERSON) Wilson CI 하한 ≥ 0.93 달성 | v0.4.16 (UNLISTED_SURNAMES 재설계 + n=854, CI 하한 0.9591) |
| 12개 엔터티 클래스 전부 Wilson CI95 하한 ≥ 0.90 | v0.4.12~v0.4.13 (골드셋 확장·게이트 상향) |
| KR_PERSON 골드셋 표본 186→348 (Wilson CI 좁힘) | v0.4.12~v0.4.16 |
| Python SDK 파사드(`nufi`) 구현 | v0.4.1 (파사드) + v0.4.6 (편의 함수) |
| PII 기반 하이브리드 LLM 라우팅 | v0.4.0 Phase 1 |
| 한국 규제 증빙 팩 48개 통제 완성 | v0.4.0 (카탈로그 v1.2) |

> **OKR 연결:** 다수 트랙이 내부 OKR 목표에 아직 연결(goalId)되지 않은 상태로 진행되어
> 왔습니다. 새 작업은 활성 NuFi 목표에 연결하는 것이 기본값입니다(릴리스 체크리스트 참조).

## 4. 문서화 갭 점검 결과 (이 인수인계에서 수행)

이 저장소를 팀에 공유하기 전 **최근 작업 중 문서화가 덜 된 부분**을 전수 점검했습니다.
찾은 갭과 조치:

| 갭 | 심각도 | 조치 |
|---|---|---|
| `nufi-egress benchmark` 서브커맨드가 CLI 레퍼런스에 없음 | 높음 | ✅ `docs/CLI.md` 에 `benchmark` 섹션 추가 |
| `report sla` 알림·다테넌트 플래그(`--alert`/`--webhook`/`--all-tenants`)가 CLI 레퍼런스에 없음 | 중간 | ✅ `docs/CLI.md` §report 에 추가 |
| `report compliance` 통제 커버리지·규제 필터(`--controls`/`--framework` 등)가 CLI 레퍼런스에 없음 | 중간 | ✅ `docs/CLI.md` §report 에 추가 |
| `demo_sla_alert.sh` 가 데모 카탈로그·전체 러너에 없음 | 낮음 | ✅ `docs/DEMO.md` 카탈로그 + `scripts/demo_all.sh` 러너에 추가(6/6 PASS 확인) |
| README 정확도 표 각주가 주소(KR_LOCATION) 수치 출처를 recall-int8.json 로 뭉뚱그림 | 낮음 | ✅ README 각주를 kr-location-gate.json(유니온) 출처로 정밀화 |

> **참고 — 의도된 비대칭:** `report sla`/`dashboard`/멀티테넌시 플래그는 README 에서
> "운영 레이어 제외" 방침에 따라 **의도적으로 전면에 두지 않습니다**. 전체 레퍼런스인
> `docs/CLI.md` 에는 기술되어야 하므로 위와 같이 CLI.md 에만 보강했습니다.

### patch05~patch06 추가 보강 (2026-07-04)

| 갭 | 심각도 | 조치 |
|---|---|---|
| Python SDK 파사드(`nufi/`) 가 ARCHITECTURE.md 컴포넌트 표에 없음 | 낮음 | ✅ ARCHITECTURE.md 컴포넌트 표에 SDK 파사드 행 추가 |
| DEMO.md 에 `examples/` Python SDK 예시 섹션 없음 | 낮음 | ✅ DEMO.md 에 SDK 예시 7종 + 스모크 실행법 섹션 신설 |
| INTEGRATION_GUIDE.md 경로 D 실행 예시가 1종뿐 | 낮음 | ✅ 실행 예시 3종으로 확장(library_detect·sdk_file_scan·sdk_compliance_report) |
| kr-person-error-analysis.md 에 v0.4.16 잔여 FN 분석 없음 | 낮음 | ✅ §7.6 추가 — FN 7건 구조(희귀 단성 ~5, 문맥 미탐지 ~2) |
| `examples/` 디렉터리에 인덱스 README 없음 | 낮음 | ✅ `examples/README.md` 신설 — 7종 예시 목적·API·실행법·백엔드 설명 |
| `Finding.__repr__` 가 None 필드 전부 노출해 개발자 가독성 저하 | 낮음 | ✅ 커스텀 `__repr__` 추가 — None 필드 생략, score 2자리, gazetteer 소스 기본 생략 |
| ROADMAP.md 깨진 링크 2건 | 낮음 | ✅ 수정 — 존재하지 않는 파일→텍스트, 잘못된 보고서 파일명 수정 |
| docs/reports/README.md 에서 5개 보고서 파일 누락 | 낮음 | ✅ baseline-int8.json, CMP-199, fn-dumps 2종, location-union-skip 인덱스 추가 |

### patch14~patch39 교차링크 전반 보강 (2026-07-04)

| 보강 항목 | 조치 |
|---|---|
| 전체 `docs/*.md` 관련 문서 섹션 누락 | ✅ INTEGRATION_GUIDE·PRESETS·OPS_RULE_RELOAD·OPS_POLICY_AT_SCALE·SECURITY_RETAIN_RAW·SDK·PII_ROUTING·REPORTING·DEMO·ROADMAP·CLI·HANDS_ON·DOC_STYLE·RELEASE_CHECKLIST 에 관련 문서 표 신설 |
| `docs/research/` 3종 관련 문서 누락 | ✅ FSEC_AI_GUIDE_2026·SOLUTION_FOCUS_OPTIONS·NUFI_SECURITY_PLANE_CHARTER 에 관련 문서 표 신설 |
| `HANDOVER/` 관련 문서 누락 | ✅ AGENT_OPERATING_MODEL·ENGINEERING_CONVENTIONS 에 관련 문서 표 신설 |
| `docs/history/README.md` · `docs/research/README.md` 진입점 부재 | ✅ 디렉터리 README 신설 · `docs/README.md` 에 링크 |
| `docs/reports/README.md` 관련 문서 누락 | ✅ REPORTING·SDK·HANDS_ON·goldset 교차링크 신설 |
| `docs/README.md` 관련 문서 누락 | ✅ ROOT_README·MANUAL·HANDS_ON·CHANGELOG·HANDOVER 교차링크 신설 |

### patch40~patch45 내용 보강 (2026-07-04)

| 보강 항목 | 조치 |
|---|---|
| `docs/reports/README.md` Python 접근 예시 없음 | ✅ recall-int8.json 키 구조 + Python 코드 스니펫 추가 (patch41) |
| `REPORTING.md` 프레임워크별 커버리지 수치 표 없음 | ✅ 5종 규제(fsec-ai/net-sep/pipa/cia/isms-p) direct·partial·oos 항목 수 표 추가 (patch42) |
| `MANUAL.md` §3 에 PII 클래스 목록 없음 | ✅ 탐지 대상 PII 12종 표(클래스명·설명·탐지 방식·강한/약한 구분) 추가 (patch43) |
| `SDK.md` Finding dataclass 필드 명세 없음 | ✅ entity_type·text·start·end·score·source·context 7개 필드 타입·설명 표 추가 (patch44) |
| `MANUAL.md` 부록 문서 지도 불완전 + 잔재 XML 태그 | ✅ SDK·PII_ROUTING·RELEASE_NOTES·DOC_STYLE 4개 링크 추가, `</content></invoke>` 태그 제거 (patch45) |

### 점검 결과 양호(gap 없음)

모든 공개 정확도·지연 수치 (v0.4.16: pii_recall=0.9908, KR_PERSON 0.9799/CI하한 0.9591,
KR_LOCATION 1.0/CI하한 0.9417, p95 41ms, benign_fp=0) 가 커밋된 리포트 JSON 과 일치하며,
`scripts/check_docs.py` 회귀 가드가 향후 드리프트를 기계로 막습니다. 307 테스트 · 11/11 데모 PASS.
내부 링크 수: **145개** (v0.4.16-patch45 기준). 문서 교차링크 체계 완성.

## 5. 이어받는 사람이 가장 먼저 볼 것

1. 제품이 뭔지·코드 지도 → [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md)
2. 어떻게 일하나(거버넌스·이슈 흐름) → [`AGENT_OPERATING_MODEL.md`](AGENT_OPERATING_MODEL.md)
3. 커밋·문서·릴리스 관례 → [`ENGINEERING_CONVENTIONS.md`](ENGINEERING_CONVENTIONS.md)
4. 직접 돌려 보기 → [`../docs/HANDS_ON.md`](../docs/HANDS_ON.md)

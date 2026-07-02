# 프로젝트 현재 상태 & 남은 일 (Project State) — 인수인계용

> 이어받는 사람/AI가 "무엇이 되어 있고, 무엇이 남았고, 어디를 조심해야 하나"를 파악하도록
> 정리했습니다. 수치의 권위는 `docs/reports/*.json`, 변경 이력의 권위는 `CHANGELOG.md` 입니다.

*작성 시점: 2026-07-02 · 대상: v0.2.2 (main, origin 동기화됨)*

---

## 1. 버전 이력 요약

| 버전 | 테마 | 핵심 내용 |
|---|---|---|
| **v0.2.2** | 공개 수치 무결성 | README 정확도·성능 수치 드리프트 3건 교정 + 수치↔리포트 JSON 회귀 가드(`scripts/check_docs.py`) |
| **v0.2.1** | 인명 오차 분석 | KR_PERSON 재현율 FN 전량 덤프·클래스 분류(사전 미수록 인명에 집중) |
| **v0.2.0** | 주소 정확도 본편 | KR_LOCATION 재현율 0.79→1.000(Wilson 하한 0.9417): 규칙 사전 확장(시군구·랜드마크·도로명·상세주소 28→206항) + 모델∪규칙 유니온, 무해 입력 오탐 0 |
| **v0.1.0** | 방향 재설정 첫 마이너 | 한국어 PII·한국 규제 증빙 특화 경량 CLI/SDK 로 재정의. 골드셋 공개 배포 정식화·baseline 측정·개인신용정보 커버리지·가명화 벤치·단일 벤치 진입점·규제 증빙 팩 |
| v0.0.x | 기반 구축 | 게이트웨이·탐지·가명화·기밀 탐지·우회 차단·비동기 감사·대시보드·정책 운영·컴플라이언스 리포트·운영자 매뉴얼 |

- 상세 내러티브: [`../docs/RELEASE_NOTES.md`](../docs/RELEASE_NOTES.md), 전체 변경: [`../CHANGELOG.md`](../CHANGELOG.md).
- **로드맵/방향:** [`../docs/ROADMAP.md`](../docs/ROADMAP.md) — 한국어 PII·규제 증빙 우선,
  CLI/SDK 경량, **운영(멀티테넌시/SLA/대시보드) 레이어는 의도적으로 강등**. 게이트웨이 코어는
  데모·검증·"직접 구현" 차별점 근거로 유지.

## 2. 알려진 한계 (Known Limitations)

- **인명(KR_PERSON) INT8 재현율:** 0.9127(Wilson 신뢰구간 하한 0.8504)로 목표선 0.90 을
  신뢰구간 하한 기준 소폭 하회(FP32 는 충족). 오차는 **사전 미수록 인명(희성·복성)**에 집중.
  분석: [`../docs/reports/kr-person-error-analysis.md`](../docs/reports/kr-person-error-analysis.md).
  → 후속: NER 베이스 모델 격상.
- **외부 원문 보존:** 켜면 외부로 나간 원문(개인정보 포함 가능)이 디스크에 남습니다(기본 꺼짐).
  켤 때는 접근 제어·보존기간·파기 절차를 반드시 정의(README 설정 주의 참조).
- **라이브 패킷 캡처:** 관리자 권한(root/CAP_NET_RAW) 필요. 에어갭·CI 는 `--simulate` 리플레이.
- **프로덕션 온프렘 지연:** 일부 유니온/onnx-int8 실측이 미프로비저닝 환경에서 skip 됨
  (정직하게 skip 리포트로 기록). → 후속: 프로덕션 온프렘 지연 재측정.

## 3. 열린 후속 과제 (Open Follow-ups)

| 과제 | 상태 | 다음 행동 |
|---|---|---|
| NER 베이스 모델 격상(인명 정확도 여유) | 백로그 | v0.3.0 후보 — 인명 본편 |
| Python SDK 파사드(`nufi`) 구현 | 설계 완료(스펙 `docs/SDK.md`) | 구현 착수(경량 임포트 API, CLI 동등) |
| 프로덕션 온프렘 지연 재측정 | 하드웨어 대기 | 온프렘 환경 확보 시 실측 |
| 한국어 생성형 가드레일(프롬프트 인젝션·탈옥) | 차기 옵션(L) | 로드맵 P차기 |

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

### 점검 결과 양호(gap 없음)

모든 공개 정확도·지연 수치(재현율 0.9433, 정밀도 0.9925, p95 41ms, KR_LOCATION Wilson 하한
0.9417, KR_PERSON 0.9127/0.8504)가 커밋된 리포트 JSON 과 일치하며, `scripts/check_docs.py`
회귀 가드가 향후 드리프트를 기계로 막습니다. RBAC/테넌트·환경변수는 문서화되어 있습니다.

## 5. 이어받는 사람이 가장 먼저 볼 것

1. 제품이 뭔지·코드 지도 → [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md)
2. 어떻게 일하나(거버넌스·이슈 흐름) → [`AGENT_OPERATING_MODEL.md`](AGENT_OPERATING_MODEL.md)
3. 커밋·문서·릴리스 관례 → [`ENGINEERING_CONVENTIONS.md`](ENGINEERING_CONVENTIONS.md)
4. 직접 돌려 보기 → [`../docs/HANDS_ON.md`](../docs/HANDS_ON.md)

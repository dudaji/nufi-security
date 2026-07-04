# docs/reports — 측정·분석 보고서 인덱스

이 폴더는 정확도 측정·갭 분석·릴리스 게이트·오차 분석 보고서를 담습니다.

## 현행 권위 데이터

| 파일 | 내용 | 상태 |
|---|---|---|
| [`recall-int8.json`](recall-int8.json) | 전체 정확도 기준 리포트 (onnx-int8, split=test, **n=854, v0.4.16**) | ✅ **현행 권위** |
| [`kr-location-gate.json`](kr-location-gate.json) | KR_LOCATION 유니온 게이트 판정 (recall=1.0, CI 하한 0.9417) | ✅ 현행 |
| [`kr-location-union.json`](kr-location-union.json) | KR_LOCATION 모델∪규칙 유니온 상세 (live onnx-int8, n=62) | ✅ 현행 |
| [`pseudonymize-quality.json`](pseudonymize-quality.json) | 가명화 품질 하니스 결과 | ✅ 현행 |
| [`load-p95.json`](load-p95.json) | 온프렘 부하 p95 (c=1: 41ms, c=2: 67ms) | ✅ 현행 |

## 분석 보고서

| 파일 | 내용 | 시점 |
|---|---|---|
| [`CMP-172-pii-accuracy-gap-analysis.md`](CMP-172-pii-accuracy-gap-analysis.md) | 엔터티별 정확도 갭 분석 + 연동 구조 (v0.4.16 현행화) | 현행 |
| [`kr-person-error-analysis.md`](kr-person-error-analysis.md) | KR_PERSON FN 분석 + v0.4.16 결과 추적 §7 | 현행 |
| [`kr-location-gate.md`](kr-location-gate.md) | KR_LOCATION v0.2.0 릴리스 게이트 판정 보고서 | v0.2.0 완료 |
| [`kr-location-ci-narrowing.md`](kr-location-ci-narrowing.md) | KR_LOCATION Wilson CI 좁히기 (P6, n 24→62) | v0.2.0 완료 |
| [`kr-location-error-analysis.md`](kr-location-error-analysis.md) | KR_LOCATION FN 분류·우선순위 (P2/P3 완료) | 역사적 ✅ |
| [`accuracy-integrity-audit.md`](accuracy-integrity-audit.md) | 공개 수치 무결성 감사 (v0.2.2, 드리프트 해소됨) | 역사적 ✅ |
| [`CMP-238-llm-routing-research.md`](CMP-238-llm-routing-research.md) | LLM 라우팅 솔루션 조사 | 조사 |
| [`CMP-246-llm-routing-market-research.md`](CMP-246-llm-routing-market-research.md) | LLM 라우팅 시장 조사 | 조사 |
| [`CMP-252-productivity-review.md`](CMP-252-productivity-review.md) | 생산성 검토 (완료) | 완료 |

## v0.4.16 핵심 수치 요약

`recall-int8.json` 기준 (onnx-int8, split=test, n=854):

| 지표 | 값 |
|---|---|
| 전체 PII 재현율 | **0.9908** |
| KR_PERSON 재현율 | **0.9799** (Wilson CI 하한 **0.9591** ✅ ≥0.93) |
| KR_LOCATION 재현율 | **1.0000** (Wilson CI 하한 0.9417 ✅ ≥0.90) |
| 12개 클래스 전부 CI95 하한 | **≥ 0.90** ✅ |
| benign_false_block | **0.0** |
| 온프렘 지연 p95 (512자, c=1) | **41 ms** |

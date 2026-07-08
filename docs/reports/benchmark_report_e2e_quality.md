# E2E 가명화 품질 벤치마크 리포트

**Date**: 2026-07-08
**Issue**: CMP-352 (parent: CMP-346)
**Pipeline**: `scripts/bench_pseudonymize_e2e.py` (CMP-351)
**LLM Backend**: mock (ANTHROPIC_API_KEY 미설정 — mock 모드 대체)

## 개요

원문→LLM→원문응답 vs 가명화→LLM→원복응답을 자동 비교하는 E2E 벤치마크.
CMP-350 한국어 PII QA 평가셋(170건: PII 150건 + Control 20건)을 입력으로 사용.

## 종합 결과

| 지표 | 달성값 | 목표 | 판정 |
|------|--------|------|------|
| Utility Retention (ROUGE-L) | **0.9820** | ≥ 0.90 | **PASS** ✅ |
| Exact Match Rate | **0.8294** (141/170) | — | — |
| PII Protection Rate | **0.9138** (265/290) | == 1.00 | FAIL ❌ |
| Roundtrip Fidelity | **0.8966** (260/290) | ≥ 0.95 | FAIL ❌ |

**종합: FAIL** — Utility 목표 달성, PII 보호율·원복 충실도 미달.

## 타입별 분석

| PII 타입 | 건수 | 보호율 | 원복 충실도 | 비고 |
|----------|------|--------|-------------|------|
| EMAIL | 50 | **1.0000** ✅ | 0.9000 | 원복 일부 미달 |
| KR_BRN | 25 | **1.0000** ✅ | **1.0000** ✅ | 완벽 |
| KR_LOCATION | 25 | **1.0000** ✅ | 0.8400 | 원복 저하 |
| KR_PERSON | 135 | 0.8148 ❌ | 0.8444 | **주요 실패 원인** |
| KR_PHONE | 55 | **1.0000** ✅ | **1.0000** ✅ | 완벽 |

### 핵심 발견

1. **KR_PERSON이 주요 병목** — 135건 중 25건(18.5%)에서 원본 인명이 가명화 텍스트에 잔존. 복합 성씨(제갈, 사공, 동방 등) 및 단음절 이름이 탐지 누락의 주 원인.
2. **EMAIL, KR_BRN, KR_PHONE은 완벽한 보호율** — 정규식 기반 탐지가 안정적.
3. **KR_LOCATION 원복 저하** — 보호는 100%이나 LLM 응답에서 surrogate→원본 역치환 시 위치 정보 일부 미복원 (21/25).

## 카테고리별 분석

| 카테고리 | 샘플 수 | Exact Match | 평균 ROUGE-L |
|----------|---------|-------------|--------------|
| payment | 28 | **28 (100%)** | 1.0000 |
| hr | 28 | 23 (82.1%) | 0.9786 |
| legal | 28 | 23 (82.1%) | 0.9779 |
| customer_service | 29 | 23 (79.3%) | 0.9838 |
| document_summary | 29 | 23 (79.3%) | 0.9772 |
| medical | 28 | 21 (75.0%) | 0.9746 |

- **payment**: PII 미포함 control 샘플 → 100% 일치.
- **medical**: 가장 낮은 EM rate — 의료 용어 + 인명 조합에서 품질 저하.

## 실패 케이스 분석

총 15건의 품질 저하(ROUGE-L < 0.90) 샘플 발생.

| 원인 카테고리 | 건수 | 설명 |
|---------------|------|------|
| 복합 성씨 미탐지 | 7 | 제갈, 사공, 동방, 몽, 좌, 절, 경 등 희귀 성씨가 KR_PERSON으로 탐지 안 됨 |
| 단음절 이름 미탐지 | 5 | 일반적인 2글자 이름이지만 문맥상 탐지 누락 |
| 복합 원인 | 3 | 인명 미탐지 + 위치 정보 원복 실패 결합 |

## 레이턴시 오버헤드

| 단계 | p50 | p95 | p99 |
|------|-----|-----|-----|
| 가명화 | 0.4ms | 0.5ms | 0.7ms |
| 원복 | 0.0ms | 0.0ms | 0.1ms |

가명화/원복 처리 레이턴시는 sub-millisecond 수준으로 LLM 호출 대비 무시 가능.

## 개선 방향

1. **KR_PERSON 탐지 강화** — 복합 성씨 사전 확장, NER 모델 fine-tuning 데이터 보강.
2. **KR_LOCATION 원복 개선** — surrogate 매핑 테이블 정확도 향상.
3. **실제 LLM 벤치마크** — ANTHROPIC_API_KEY 확보 후 Claude API로 재실행하여 실제 LLM 응답 기반 품질 검증 필요.

## 산출물

- 벤치마크 JSON: `docs/reports/pseudonymize-e2e-quality.json`
- 평가셋: `data/pii_qa_eval.jsonl` (170건)
- 평가셋 설명: `data/pii_qa_eval_README.md`
- 파이프라인: `scripts/bench_pseudonymize_e2e.py`

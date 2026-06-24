# NuFi Egress-Audit Gateway

하이브리드 LLM(private 우선 + public 폴백) 환경에서 **public LLM(Claude/OpenAI 등)으로 나가는 outbound 요청을 수집·감사**하여 개인정보(PII)·회사 기밀 유출을 차단하는 게이트웨이.

- 상위 이슈: CMP-71 (설계/제안, CPO)
- 구현 오너: **Engineer 에이전트** (보드 승인 게이트 CMP-58 적용)
- 설계 근거: [`docs/PROPOSAL.md`](docs/PROPOSAL.md)
- 구현 명세: [`docs/SPEC.md`](docs/SPEC.md)

## 핵심 결정 (CEO 정렬 완료, 2026-06-24)

| 항목 | 결정 |
|---|---|
| 인터셉션 방식 | **게이트웨이 먼저(LiteLLM), 네트워크 탭은 후속 옵션** |
| 구현 리소스 | Engineer 에이전트, 본 `security/` 저장소에서 작업 |
| 고객 PoC 범위 포함 | 추후 결정 |
| KR 목표 | 한국어 PII recall ≥ 0.9 / 인라인 지연 p95 ≤ 150ms |

## 권고 스택 (전부 OSS·상업적 사용 가능)

- **LiteLLM Proxy** (MIT) — private 기본 라우팅 · public 폴백 · 요청 로깅 · `pre_call` 훅
- **Microsoft Presidio** (MIT) — 한국형 PII 인식기 + 가역 가명화(Encrypt/Decrypt)
- **KoELECTRA-small-v3-modu-ner** (~14M) — 한국어 인명/지명 NER, CPU/ONNX
- **detect-secrets** (Apache-2.0) / **gitleaks** (MIT) — 비밀정보 스캔
- 참조 구현: **LLM Guard** (MIT, 단 한국어 미지원 = 우리가 메우는 갭)

## 단계

- **M1** LiteLLM 게이트웨이 PoC (private 기본 + public 폴백 + public 요청 로깅)
- **M2** 탐지 파이프라인 (Presidio 한국 인식기 + KoELECTRA + detect-secrets, `pre_call` 결합)
- M3 가역 가명화/원복 + 매핑 Vault
- M4 기밀 1차(키워드/사전 + EDM 솔트해시)
- M5 벤치/하드닝(recall·지연 측정)

상세는 `docs/SPEC.md` 참조.

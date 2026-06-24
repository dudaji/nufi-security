# NuFi Egress-Audit Gateway — 데모 (M1 + M2)

실행 일자: 2026-06-24 · 검증: CPO (NuFi) · 구현: Engineer (CMP-72) · 저장소: `security/`

하이브리드 LLM 환경에서 **public LLM으로 나가는 요청을 게이트웨이가 가로채 PII/비밀을 인라인 탐지·차단·가명화**하고 **public 전송을 100% 감사 로깅**하는 동작을 시연한다.

## 재현 방법

```bash
cd security
python3 -m pip install -r requirements.txt   # PyYAML·fastapi·uvicorn·httpx (코어는 stdlib+PyYAML만으로도 동작)

python3 tests/run_acceptance.py              # 수용기준 10/10
python3 tests/test_unit.py                   # 단위 8/8
python3 scripts/bench.py --ner gazetteer     # recall/지연
PORT=4000 ./scripts/run_gateway.sh           # 게이트웨이 기동 (OpenAI 호환 /v1/chat/completions)
```

## 1. 자동 검증 결과

| 항목 | 결과 |
|---|---|
| 수용기준 (M1 3 + M2 7) | **10 / 10 PASS** |
| 단위 테스트 | **8 / 8 PASS** |
| 한국어 PII recall | **1.000 (23/23)** — 목표 ≥ 0.9 |
| 비밀정보 recall | 1.000 (9/9) |
| benign 오탐 차단 | 0 / 5 |
| 인라인 지연(CPU) | p50 0.06ms · **p95 0.15ms** — 목표 ≤ 150ms |

> gazetteer NER 백엔드 기준(에어갭·외부의존 0). 프로덕션 recall 목표는 KoELECTRA(transformers/ONNX) 백엔드로 상향.

## 2. 라이브 게이트웨이 시연

### A. private 기본 라우팅 — 외부 미전송
```
$ curl localhost:4000/v1/chat/completions -d '{"model":"nufi-default","messages":[{"role":"user","content":"내부 회의록 요약해줘"}]}'
→ model: private-llm | content: [private-llm stub response]
→ 감사 로그(외부전송 기록) 건수: 0   ← private 경로는 외부로 안 나가므로 기록 없음
```

### B. public 폴백 + 주민등록번호(강한 PII) → **차단(403)**
```
$ EGRESS_PRIVATE_DOWN=1 curl -w "HTTP %{http_code}" .../v1/chat/completions \
    -d '{"model":"nufi-default","messages":[{"role":"user","content":"김민수님 주민번호 900101-1234568 으로 신청서 작성해줘"}]}'
HTTP 403
{"error":{"type":"egress_blocked","message":"민감정보 탐지로 public LLM 전송이 차단되었습니다.",
          "decision":{"blocked":true,"action_counts":{"pseudonymize":1,"block":1},"finding_count":2},
          "entities":["KR_RRN"]}}
```
→ 인명(김민수)은 가명화 대상, 주민번호(KR_RRN)는 차단 → 요청 전체 public 전송 차단.

### C. public 폴백 + API 키(비밀) → **차단(403)**
```
$ EGRESS_PRIVATE_DOWN=1 curl -w "HTTP %{http_code}" .../v1/chat/completions \
    -d '{...content":"이 키로 배포해줘 sk-ant-api03-AbCdEf...01"}]}'
HTTP 403
{"error":{"type":"egress_blocked","decision":{"action_counts":{"block":1},"finding_count":1},"entities":["SECRET"]}}
```

### D. public 폴백 + 약한 PII(전화/이메일) → 가명화 후 전송(200)
```
$ EGRESS_PRIVATE_DOWN=1 curl -w "HTTP %{http_code}" .../v1/chat/completions \
    -d '{...content":"연락처 정리: 010-1234-5678, hong@dudaji.com 으로 회신"}]}'
HTTP 200   ← 전화/이메일은 pseudonymize(비차단) 정책 → 본문 가명화 후 public 전송
```

### 감사 로그 (`logs/egress_audit.jsonl`) — public 전송 100% 기록
```json
{"ts":"2026-06-24T15:10:27+0900","model":"claude-3-5-sonnet","is_public":true,"outcome":"forwarded"}
{"ts":"2026-06-24T15:10:27+0900","model":"claude-3-5-sonnet","is_public":true,"outcome":"blocked"}
{"ts":"2026-06-24T15:10:27+0900","model":"claude-3-5-sonnet","is_public":true,"outcome":"blocked"}
```

## 3. 정책 (운영자 갱신 가능 — `config/policy.yaml`)

- 강한 PII(주민번호·외국인등록·여권·면허·카드·계좌)·비밀정보 = **block**
- 약한 PII(사업자번호·전화·이메일·인명) = **pseudonymize**, 지명 = **warn**
- 차단 동작이 하나라도 결정되면 요청 전체를 public 전송 차단

## 4. 데모 요지

1. **민감하면 private, 어쩔 수 없으면 public** — 기본 private 라우팅, 폴백/명시 시에만 public.
2. **public 직전 인라인 감사** — 정규식+체크섬(강한 PII·비밀) + 경량 NER(한국어 인명/지명).
3. **유출 차단** — 강한 PII/비밀은 403 차단, 약한 PII는 가명화 후 전송.
4. **전량 감사 로깅** — public 전송은 결정과 함께 100% 기록.
5. **에어갭/저지연** — 외부 의존 0, p95 0.15ms.

후속(M3~M5): 가역 가명화·원복(매핑 Vault), 회사 기밀(키워드/EDM), 프로덕션 KoELECTRA 백엔드 벤치·하드닝.

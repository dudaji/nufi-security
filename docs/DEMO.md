# NuFi 데모 카탈로그

이 저장소의 모든 데모를 한 곳에 모았다. 각 데모는 **이름만 보고 무엇을 시연하는지**
알 수 있도록 기능 이름(`demo_<feature>.sh`)을 쓰며, 실행하면 시나리오별 PASS/FAIL 을
자동 집계한다. 별도 표기가 없으면 **root 불필요 · 외부 네트워크 호출 0**(stub 백엔드 +
gazetteer NER + 임시 픽스처)으로 에어갭/CI 에서 결정적으로 재현된다.

## 한 번에 전부 실행

```bash
cd security
python3 -m pip install -r requirements.txt   # PyYAML·fastapi·uvicorn·httpx
./scripts/demo_all.sh                         # 모든 기능 데모를 차례로 실행 → 집계 PASS/FAIL
```

`demo_all.sh` 는 아래 카탈로그의 데모를 순서대로 돌리고 마지막에 PASS/FAIL/SKIP 을
집계한다. 사전조건(모델 측정 산출물·root)이 없는 데모는 **SKIP**(실패 아님)으로
분류한다.

## 카탈로그

| 데모 | 한 줄 목적 | 시나리오 | 실행법 | 매뉴얼 |
|---|---|---|---|---|
| [`demo.sh`](../scripts/demo.sh) | 게이트웨이 e2e — private 라우팅 · 강한 PII/비밀 차단(403) · 약한 PII 가명화 · 감사 로깅 | 6 | `./scripts/demo.sh` | 본 문서 §부록 |
| [`demo_coverage.sh`](../scripts/demo_coverage.sh) | 감사 커버리지 — "내 트래픽 중 몇 %가 게이트웨이를 통과했나" + 우회 알림 | 3 | `./scripts/demo_coverage.sh` | [`CLI.md#coverage`](CLI.md) |
| [`demo_dashboards.sh`](../scripts/demo_dashboards.sh) | 감사 대시보드 — 결정/무결성/우회/추이 4개 패널 어댑터(읽기 전용) | 6 | `./scripts/demo_dashboards.sh` | [`dashboards/README.md`](../dashboards/README.md) |
| [`demo_report.sh`](../scripts/demo_report.sh) | SLA·규정준수 리포트 — 기간별 충족/위반 판정 + 해시체인 무결성 게이트 + 점검항목 커버리지 | 7 | `./scripts/demo_report.sh` | [`REPORTING.md`](REPORTING.md) |
| [`demo_compliance_mapping.sh`](../scripts/demo_compliance_mapping.sh) | 컴플라이언스 매핑 — 한국 규제팩(금융 AI 안내서·망분리·개인정보보호법·신용정보법·ISMS-P) 대비 NuFi 통제 커버리지(직접/부분/범위밖) 자동 산출 + 프레임워크별 소계·`--framework` 필터 + 무결성 게이트 0/1 유지 | 7 | `./scripts/demo_compliance_mapping.sh` | [`REPORTING.md`](REPORTING.md) |
| [`demo_policy_ops.sh`](../scripts/demo_policy_ops.sh) | 정책 운영 — 다중 프로파일 · 경로별 바인딩 · 무재기동 롤백 · 변경 감사 | 4 | `./scripts/demo_policy_ops.sh` | [`OPS_POLICY_AT_SCALE.md`](OPS_POLICY_AT_SCALE.md) |
| [`demo_multitenancy.sh`](../scripts/demo_multitenancy.sh) | 멀티테넌시·RBAC — 테넌트 읽기 경계 + viewer/operator 읽기전용 역할 | 6 | `./scripts/demo_multitenancy.sh` | [`MULTITENANCY.md`](MULTITENANCY.md) |
| [`demo_pseudonymize.sh`](../scripts/demo_pseudonymize.sh) | 가명화 품질 벤치마크 — 가역(원복 정확도·스트리밍 경계·충돌율 0·결정성)/비가역(원복불가·구조보존·일관 치환) 지표 + 강한 식별자·비밀 차단 유지 | 2 | `./scripts/demo_pseudonymize.sh` | [`PRESETS.md`](PRESETS.md) |
| [`demo_audit_separation.sh`](../scripts/demo_audit_separation.sh) | 차등 감사 — public/private 분리 저장 + 패킷 레이어 우회 탭 + 비동기 감사봇 | 6 | `./scripts/demo_audit_separation.sh` | [`history/DEMO_v0.0.5.md`](history/DEMO_v0.0.5.md) |
| [`demo_accuracy.sh`](../scripts/demo_accuracy.sh) | 정확도 재현 — KR_PERSON INT8 Wilson CI 하한 ≥ 0.85 + 온프렘 p95 표 *(측정 산출물 필요)* | 2 | `./scripts/demo_accuracy.sh` | [`history/DEMO_v0.0.5.md`](history/DEMO_v0.0.5.md) |
| [`demo_bypass_enforcement.sh`](../scripts/demo_bypass_enforcement.sh) | 우회 차단(ENFORCED) — 격리 netns 에서 실제 egress drop *(root/nft 필요)* | 3 | `sudo bash scripts/demo_bypass_enforcement.sh` | [`history/DEMO_v0.0.5.md`](history/DEMO_v0.0.5.md) |
| [`demo_all.sh`](../scripts/demo_all.sh) | 전체 데모 러너 — 위 데모를 차례로 실행하고 집계 PASS/FAIL 출력 | — | `./scripts/demo_all.sh` | 본 문서 |

> `demo_bypass_enforcement.sh` 는 `demo_audit_separation.sh --enforce` 경로가 root/nft 가
> 있을 때 호출하는 하위 데모다. 권한이 없으면 차등 감사 데모가 정직하게 SIMULATED 로
> 폴백하므로, 일반 실행에는 추가 권한이 필요 없다.

---

## 부록 — 게이트웨이 e2e 상세(`demo.sh`)

하이브리드 LLM 환경에서 **public LLM으로 나가는 요청을 게이트웨이가 가로채 PII/비밀을
인라인 탐지·차단·가명화**하고 **public 전송을 100% 감사 로깅**하는 동작을 시연한다.

수동 단계별 재현:

```bash
cd security
python3 -m pip install -r requirements.txt   # 코어는 stdlib+PyYAML만으로도 동작

python3 tests/run_acceptance.py              # 수용기준 10/10
python3 tests/test_unit.py                   # 단위 8/8
python3 scripts/bench.py --ner gazetteer     # recall/지연
PORT=4000 ./scripts/run_gateway.sh           # 게이트웨이 기동 (OpenAI 호환 /v1/chat/completions)
```

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
{"ts":"...","model":"claude-3-5-sonnet","is_public":true,"outcome":"forwarded"}
{"ts":"...","model":"claude-3-5-sonnet","is_public":true,"outcome":"blocked"}
```

### 정책 (운영자 갱신 가능 — `config/policy.yaml`)

- 강한 PII(주민번호·외국인등록·여권·면허·카드·계좌)·비밀정보 = **block**
- 약한 PII(사업자번호·전화·이메일·인명) = **pseudonymize**, 지명 = **warn**
- 차단 동작이 하나라도 결정되면 요청 전체를 public 전송 차단

### 요지

1. **민감하면 private, 어쩔 수 없으면 public** — 기본 private 라우팅, 폴백/명시 시에만 public.
2. **public 직전 인라인 감사** — 정규식+체크섬(강한 PII·비밀) + 경량 NER(한국어 인명/지명).
3. **유출 차단** — 강한 PII/비밀은 403 차단, 약한 PII는 가명화 후 전송.
4. **전량 감사 로깅** — public 전송은 결정과 함께 100% 기록.
5. **에어갭/저지연** — 외부 의존 0, p95 < 1ms(gazetteer 백엔드 기준).

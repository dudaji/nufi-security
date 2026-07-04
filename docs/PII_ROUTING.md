# PII 기반 하이브리드 LLM 라우팅 (Phase 1)

> NuFi PII 감지 엔진을 라우팅 최우선 레이어로 활용하여,
> PII 포함 요청은 로컬 모델로, PII 없는 요청은 클라우드 모델로 자동 분배한다.

## 아키텍처

```
요청 → [PII 감지] → PII 있음 → 로컬 모델 (강제)
                 → PII 없음 → [기존 라우팅] → private/public 결정
```

PII 감지가 기존 egress 감사(block/pseudonymize)보다 **먼저** 실행된다.
PII가 포함된 요청은 클라우드로 나가기 전에 로컬 모델로 강제 라우팅되므로,
egress 감사 단계에 도달하지 않는다.

## 구성 요소

| 파일 | 역할 |
|------|------|
| `config/routing.yaml` | PII 라우팅 설정 (`pii_routing` 섹션) |
| `config/litellm_config.yaml` | LiteLLM 프록시 모델 등록 + PII 라우팅 |
| `gateway/router.py` | `Router.resolve_for_pii()` — PII 라우팅 결정 |
| `gateway/pii_router.py` | `PiiRouter` — LiteLLM 훅용 PII 라우터 + 비용 추적 |
| `gateway/litellm_hook.py` | `EgressAuditHook` — LiteLLM pre_call에서 PII 라우팅 실행 |
| `gateway/core.py` | `Gateway._try_pii_route()` — FastAPI PoC 경로 PII 라우팅 |

## 설정

### routing.yaml (FastAPI PoC 경로)

```yaml
pii_routing:
  enabled: true
  local_backend: private-llm      # PII 요청을 보낼 로컬 백엔드
  entity_types: []                 # 빈 리스트 = 모든 PII 엔티티 대상
```

`entity_types`에 특정 엔티티만 지정하면 해당 엔티티가 감지될 때만 로컬로 라우팅한다:

```yaml
pii_routing:
  enabled: true
  local_backend: private-llm
  entity_types:
    - KR_RRN           # 주민등록번호만 로컬 강제
    - CREDIT_CARD      # 신용카드번호만 로컬 강제
```

### litellm_config.yaml (LiteLLM 프록시 경로)

```yaml
model_list:
  - model_name: nufi-local
    litellm_params:
      model: openai/local-llm
      api_base: http://localhost:8000/v1
      api_key: "sk-local-noauth"
    model_info:
      egress_class: private

  - model_name: nufi-cloud
    litellm_params:
      model: anthropic/claude-3-5-sonnet-20241022
      api_key: os.environ/ANTHROPIC_API_KEY
    model_info:
      egress_class: public
```

환경 변수로 모델 오버라이드:

```bash
export NUFI_LOCAL_MODEL=nufi-local      # PII 요청용 로컬 모델
export NUFI_CLOUD_MODEL=nufi-cloud      # 클린 요청용 클라우드 모델
export NUFI_FAIL_CLOSED=1               # 감지 오류 시 로컬 폴백 (기본 활성)
```

## 실행

### FastAPI PoC 게이트웨이

```bash
uvicorn gateway.app:app --port 4000
```

```bash
# PII 포함 → 로컬 라우팅
curl -X POST http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"nufi-default","messages":[{"role":"user","content":"주민번호 900101-1234568 조회"}]}'

# PII 없음 → 기존 라우팅
curl -X POST http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"nufi-default","messages":[{"role":"user","content":"오늘 날씨가 좋습니다"}]}'
```

### LiteLLM 프록시

```bash
litellm --config config/litellm_config.yaml --port 4000
```

### 데모

```bash
python scripts/demo_pii_routing.py
```

## 테스트

```bash
python tests/test_cmp247_pii_routing.py
# 또는
pytest tests/test_cmp247_pii_routing.py -v
```

검증 항목 (34건):
- `Router.resolve_for_pii`: PII 엔티티 → 로컬, 엔티티 필터링, 비활성 시 동작
- `PiiRouter.route`: PII/클린 텍스트 라우팅, 직렬화, 비용 추적
- `Gateway` 통합: end-to-end PII 라우팅, 비활성 시 기존 동작

## 라우팅 흐름 상세

### 1. PII 감지 (최우선)

NuFi의 `DetectionPipeline`이 요청 텍스트에서 PII 엔티티를 탐지한다.
감지 대상: KR_RRN, KR_PHONE, EMAIL, CREDIT_CARD, KR_ACCOUNT, KR_PERSON 등.

### 2. 라우팅 결정

- **PII 감지됨** → 로컬 모델로 강제 라우팅. 원문 그대로 전달.
- **PII 없음** → 기존 라우팅 흐름 (routing.yaml의 routes 규칙).
- **감지 오류** → fail-closed: 로컬 모델로 안전 폴백.

### 3. 감사 로깅

PII 라우팅 결정은 감사 로그에 기록된다:
- `outcome: pii_routed` — PII 감지로 로컬 라우팅됨
- `entity_types` — 감지된 엔티티 타입 목록
- PII 원문은 마스킹 처리 (길이+해시만 보존)

## 비용 추적

`PiiRouter` 는 라우팅 결정에 따른 추정 비용을 누적 추적한다.

### DEFAULT_COST_TABLE

모델별 토큰당 비용(USD) 근사치. `PiiRouter(cost_table=...)` 로 오버라이드 가능.

```python
DEFAULT_COST_TABLE = {
    "gpt-4o":            {"input": 2.50/1M, "output": 10.00/1M},
    "gpt-4o-mini":       {"input": 0.15/1M, "output":  0.60/1M},
    "gpt-3.5-turbo":     {"input": 0.50/1M, "output":  1.50/1M},
    "claude-3-5-sonnet": {"input": 3.00/1M, "output": 15.00/1M},
    "claude-3-haiku":    {"input": 0.25/1M, "output":  1.25/1M},
    "local":             {"input": 0.0,      "output":  0.0},
}
```

로컬 모델은 토큰 비용 0 으로 계산한다(인프라 비용은 별도 산정).

### cost_summary()

`PiiRouter.cost_summary()` 는 누적된 `record_cost()` 호출을 집계한 딕셔너리를 반환한다:

```python
router = PiiRouter()
# ... route() + record_cost() 호출 후 ...
summary = router.cost_summary()
# {
#   "total_requests": 150,
#   "local_requests": 90,
#   "cloud_requests": 60,
#   "total_cost_usd": 0.042,
#   "local_cost_usd": 0.0,
#   "cloud_cost_usd": 0.042,
#   "by_model": {"gpt-4o": 0.035, "claude-3-haiku": 0.007}
# }
```

| 필드 | 설명 |
|------|------|
| `total_requests` | 전체 기록된 요청 수 |
| `local_requests` / `cloud_requests` | 로컬/클라우드 분배 수 |
| `total_cost_usd` | 전체 추정 비용 |
| `local_cost_usd` / `cloud_cost_usd` | 로컬/클라우드 각 비용 |
| `by_model` | 모델별 비용 분해 |

PII 라우팅이 활성화되면 민감 요청이 로컬로 분배되어 `cloud_cost_usd` 가 절감된다.
절감 효과는 `(cloud_requests / total_requests)` 비율과 `by_model` 분포로 확인할 수 있다.

---

## Phase 2+ 로드맵

- RouteLLM 분류기 도입 (비용-품질 최적화)
- 한국어 프롬프트 복잡도 분류
- 실시간 비용/품질 모니터링 대시보드

---

## 관련 문서

| 문서 | 역할 |
|---|---|
| [`INTEGRATION_GUIDE.md`](INTEGRATION_GUIDE.md) | §5 하이브리드 결정트리 — PII 라우팅이 egress 정책 결정과 어떻게 맞물리나 |
| [`SDK.md`](SDK.md) | PiiRouter·DEFAULT_COST_TABLE advanced 심볼 위치 |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | §8 관련 문서 링크 — 전체 컴포넌트 흐름에서 라우팅 위치 |
| [`ROADMAP.md`](ROADMAP.md) | P3: PII 라우팅 Phase 2 로드맵(RouteLLM·비용 최적화) |

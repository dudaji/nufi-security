# 감사 가시성 대시보드 (read-only) — v0.0.3 O1

온프렘에 **이미 100% 적재되는** 감사를 보안팀이 *읽는* 화면. 프로덕션 무변경·쓰기 권한 없음.
설계 근거: [`../docs/PROPOSAL_v0.0.3.md`](../docs/PROPOSAL_v0.0.3.md) §1 O1 / §3.

## 패널 4종
| # | 패널 | 소스 | 엔드포인트 |
|---|------|------|-----------|
| ① | 결정 뷰어 (차단/가명화/경고) | `logs/egress_audit.jsonl` | `/api/decisions` |
| ② | 감사 해시체인 무결성 | 동일(체인 부착 시) | `/api/chain` |
| ③ | 우회 탐지 이벤트 타임라인 | `logs/packets/public/flow-*.jsonl` | `/api/bypass` |
| ④ | 카테고리별 탐지량 추이 | `logs/egress_audit.jsonl` | `/api/trend` |

## 구성요소
- **`adapter.py`** — read-only 데이터소스 어댑터(코어). 감사·flow 로그를 `'r'` 로만 읽어
  4 패널 모델로 변환. 파일/디렉터리 생성 등 부수효과 없음.
- **`server.py`** — stdlib HTTP 데이터소스. **GET/HEAD 만** 허용(쓰기 메서드 405).
- **`viewer.html`** — 의존성 0 정적 뷰어(오프라인 검증용).
- **`grafana_dashboard.json`** — 프로덕션 배포용 Grafana 대시보드(Infinity 데이터소스).
- **`sample/`** — 데모 픽스처(체인 부착 감사 3건 + 우회 flow 1건). 합성·비-PII.

## 빠른 시작 (오프라인 검증)
```bash
# 1) 데모 픽스처로 데이터소스 기동(또는 --audit/--flow-dir 로 실제 로그 지정)
python3 -m dashboards.server --port 8099 \
  --audit dashboards/sample/audit_chain.jsonl \
  --flow-dir dashboards/sample

# 2) 브라우저로 read-only 뷰어 열기
#    http://127.0.0.1:8099/viewer
#    → 결정 1건 + "해시체인 무결성 OK" 가 보이면 수용 기준(binary) 충족.

# 실제 운영 로그로:
python3 -m dashboards.server --port 8099    # 기본 logs/egress_audit.jsonl, logs/packets/public/
```
모델만 미리 보려면: `python3 dashboards/adapter.py --audit dashboards/sample/audit_chain.jsonl`.

## Grafana 연결 (프로덕션)
1. `dashboards/server.py` 를 보안 네트워크 내부에서 기동(read-only).
2. Grafana 에 [Infinity 데이터소스](https://grafana.com/grafana/plugins/yesoreyeram-infinity-datasource/) 설치.
3. **Dashboards → Import → Upload JSON** 으로 `grafana_dashboard.json` 업로드.
4. 대시보드 변수 `$base` 를 데이터소스 URL(예: `http://127.0.0.1:8099`)로 설정.

## 스택 결정 — Grafana(채택) vs Langfuse(대안)
기본 권장값은 **Langfuse**(LLM 친화)이며, Grafana 도 동등한 대안이다.
본 구현은 **read-only 화면**의 데이터 원천이 *게이트웨이가 이미 적재한 추가전용 JSONL 감사 로그*라는
점을 근거로 **Grafana(+ 파일/JSON 데이터소스)** 를 채택했다:
- Langfuse 는 *trace 를 푸시*해 적재하는 모델 — 게이트웨이 재계측(쓰기 경로)이 필요해
  "프로덕션 무변경·쓰기 권한 없음" 제약과 마찰. 기존 JSONL 을 *읽기만* 하는 데는 부적합.
- Grafana(Infinity) 는 기존 파일을 **읽기 전용**으로 패널화 — 제약과 정합.
- 어댑터(`adapter.py`)는 **백엔드 중립** — Langfuse 채택이 필요하면 이 read-only 모델을
  Langfuse ingestion(별도 사이드카, 별도 이슈+범위)으로 흘리는 어댑터를 추가하면 된다.

→ 기본 권장값을 배제한 것이 아니라, **O1 의 무변경 제약에 부합하는 구현을 먼저 제공**하고
Langfuse 경로는 후속(수요 시)으로 연다. 다른 선택이 필요하면 이슈로 논의한다.

## 보안 — 재유출 방지
감사 레코드의 `request_body`·finding `text` 에는 PII 평문이 있을 수 있다. 관측 패널은 기본값
`redact=True` 로 원문을 **마스킹**(`«N자»`)하고 메타(entity_type/score/source/카운트)만 노출한다.
`--no-redact`(어댑터) 는 운영자 명시 옵션이며 화면 한정 — 감사 원본은 항상 그대로 보존된다.

## 해시체인 무결성
체인 부착 적재(`EGRESS_AUDIT_HASH_CHAIN=1`) 시 `/api/chain` 이 `verify_chain_records`
([`../egress_audit/audit.py`](../egress_audit/audit.py))로 수정·삭제·재배열·시계역행을 검증한다.
미부착 로그는 `status=unchained` 로 안전하게 구분한다.

## 수용 기준(binary) 검증
```bash
python3 -m pytest tests/test_cmp134_dashboards.py -q
```
`test_binary_done_criterion` 이 대시보드 모델에서 **결정 1건 + 해시체인 무결성 1건**을
read-only 로 조회함을 증명한다.

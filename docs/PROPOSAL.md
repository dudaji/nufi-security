# NuFi 하이브리드 LLM 게이트웨이 + 외부 패킷 감사(Egress Audit) 제안서

- **이슈:** CMP-71 — NuFi 로드맵에 하이브리드 LLM 및 외부 패킷 감사 기능 설계
- **작성:** CPO (NuFi)
- **일자:** 2026-06-24
- **상위 목표:** GPU→NPU migration 툴 및 MLOps, NPUOps 솔루션 개발·판매업 (company goal)
- **프로젝트:** korea
- **문서 성격:** 리서치 + 제안(Proposal). **본 문서는 설계/전략 산출물이며, 실제 구현은 사람 개발자 백로그로 인계한다(거버넌스 CMP-58/CMP-60 준수).**

---

## 0. TL;DR (경영 요약)

고객은 **private LLM(내부/온프렘) 우선 + public LLM(Claude/OpenAI 등) 폴백**의 하이브리드 구성을 원한다. 핵심 리스크는 **public LLM으로 나가는 outbound 트래픽에 개인정보(PII)·회사 기밀이 섞여 유출되는 것**이다. 요구사항은 (1) public LLM 행 패킷의 수집/로깅, (2) **정규식 + 경량 AI 모델**로 PII·기밀을 탐지/가명화/차단하는 감사 기능이다.

**권고 프로토타입 스택(전부 OSS, 상업적 사용 가능 라이선스):**

| 레이어 | 선정 | 라이선스 | 역할 |
|---|---|---|---|
| 게이트웨이/라우팅 | **LiteLLM Proxy** | MIT | private 기본 라우팅·public 폴백·요청 로깅·`pre_call` 훅 |
| 탐지 코어 | **Microsoft Presidio** | MIT | 한국형 PII 인식기(RRN/사업자번호 등) + 가역 가명화(Encrypt/Decrypt) |
| 한국어 인명 NER | **KoELECTRA-small-v3-modu-ner (14M)** | Apache 계열 | 정규식이 못 잡는 한국어 인명/지명 탐지, CPU/ONNX 추론 |
| 비밀정보 탐지 | **detect-secrets / gitleaks** | Apache-2.0 / MIT | API 키·자격증명 인라인 스캔 |
| 참조 구현 | **LLM Guard (Protect AI)** | MIT | Presidio+detect-secrets를 이미 결합한 스캐너 파이프라인(포크/벤치 기준) |

**전략적 차별점:** 기성 LLM 가드레일(LLM Guard, Guardrails AI, NeMo)과 HuggingFace PII 모델은 **사실상 전부 영어 중심**이며 **한국어 PII(주민등록번호, 한국어 인명 NER)·온프렘/에어갭 CPU 동작을 기본 지원하지 않는다.** Presidio + KoELECTRA 조합이 유일한 "바로 되는" 한국어 경로다. **이를 턴키 한국어 Egress-Audit 게이트웨이로 패키징하는 것이 NuFi의 방어 가능한 포지셔닝이다.**

---

## 1. 배경 및 문제 정의

- 고객은 보안·개인정보 이슈가 있는 작업은 **private LLM**으로, 불가피한 경우만 **public LLM**으로 처리하는 하이브리드 운영을 결정.
- 따라서 **외부로 나가는 트래픽 중 public LLM 대상 요청**을 수집·감사해야 함. 유출되면 안 되는 두 부류:
  1. **개인정보(PII)** — 가명화/마스킹이 핵심.
  2. **회사 기밀** — 키·자격증명, 내부 코드네임, 기밀 문서 파생 텍스트 등.
- 처리 방식 요구: **정규식 + 경량 AI 모델**. 직접 개발은 부담 → **오픈소스 코드/기술/모델로 프로토타이핑**.

### 적용 렌즈 — OKR 정렬
본 기능은 company goal "NPUOps/MLOps 솔루션 개발·판매업"의 NuFi 제품 라인에 직결된다. KR 후보: *(a) Egress-Audit PoC 1건을 실고객 트래픽에 적용해 PII 유출 0건 검증, (b) 한국어 PII 탐지 재현율(recall) ≥ 0.9 / 인라인 추가 지연 ≤ 150ms.* → **KR 수치는 CEO 정렬 필요(8장 결정사항).**

---

## 2. 목표 / 비목표

**목표(Goals)**
- public LLM 대상 outbound 요청의 **수집·로깅·감사** 파이프라인 설계.
- **정규식 + 경량 AI 모델** 기반 PII·기밀 탐지 및 **가명화/마스킹/차단**.
- **온프렘·에어갭 CPU**에서 동작(데이터가 밖으로 안 나가야 하므로 탐지 자체가 외부 호출 없어야 함).
- 기존 OSS로 **수 주 내 PoC**.

**비목표(Non-goals, 이번 단계)**
- private LLM 자체 서빙 성능/모델 선택(별도 NuFi Serve 트랙 — [CMP-52](/CMP/issues/CMP-52) 계열).
- 완전한 엔터프라이즈 DLP(문서 지문/EDM 풀스택) — PoC 이후 단계.
- TLS 종단 가로채기형 네트워크 탭(법무/운영 리스크) — 아래 "인터셉션 방식 결정" 참조.

---

## 3. 요구사항

**기능 요구(FR)**
- FR1: 요청을 private/public으로 **라우팅**하고 public 행 요청을 식별.
- FR2: public 행 요청/응답을 **감사 로그**로 적재(원문은 보관정책에 따름).
- FR3: 전송 **직전(pre-call)** 프롬프트를 스캔해 PII/기밀 탐지.
- FR4: 정책에 따라 **가명화(가역/비가역) · 마스킹 · 차단(block) · 경고(allow+log)** 중 동작 수행.
- FR5: 가역 가명화 시 응답 수신 후 **원복(de-anonymize)** 지원.
- FR6: 한국어 PII(주민등록번호·사업자등록번호·전화·계좌·카드·여권 + 한국어 인명) 지원.

**비기능 요구(NFR)**
- NFR1: 탐지 추론은 **외부 네트워크 호출 0** (온프렘/에어갭).
- NFR2: 인라인 추가 지연 목표 **≤ 150ms (p95, CPU)** — 경량 모델 + 정규식 우선.
- NFR3: 정책/사전(dictionary)·정규식 룰을 **운영자가 갱신** 가능.
- NFR4: 라이선스 **상업적 사용 가능**(비상업/no-derivatives 모델 배제).

---

## 4. 아키텍처 설계

```
            ┌──────────────┐   기본          ┌─────────────────────┐
앱/사용자 → │  LiteLLM      │ ───────────────▶│ private LLM (온프렘) │
            │  Proxy        │                 │ vLLM/Ollama/NPU     │
            │  (MIT)        │   폴백/명시 요청  └─────────────────────┘
            │              │
            │  pre_call 훅 │── 감사 파이프라인 PASS/REDACT ──┐
            └──────────────┘                                 ▼
                    │ public 행만                   ┌────────────────────┐
                    │  (가명화/차단 후)             │ Audit Pipeline     │
                    ▼                               │ 1) 정규식+체크섬    │
            ┌──────────────┐                        │ 2) 한국어 NER(경량) │
            │ public LLM   │◀── 정제된 프롬프트 ────│ 3) 비밀정보 스캐너  │
            │ Claude/OpenAI│                        │ 4) 가명화/마스킹/   │
            └──────────────┘                        │    차단 + 매핑 Vault│
                    │ 응답                           └────────────────────┘
                    ▼ de-anonymize(가역 시)                 │
            감사 로그(Langfuse 등) ◀──────────────────────┘
```

**4.1 인터셉션/라우팅 레이어 — LiteLLM Proxy (MIT)**
- private 기본 라우팅 + public 폴백, 요청 로깅, **`pre_call` 가드레일 훅** 내장(Presidio MASK/BLOCK 연동 공식 지원).
- 대안: **Kong AI Gateway(Apache-2.0)** — AI Prompt Guard(정규식 allow/deny) + PII Sanitizer 내장. 운영팀이 Kong 친숙하면 유력.
- **Cloudflare AI Gateway는 배제** — SaaS 전용, 온프렘 불가(NFR1 위반).
- 감사 로깅 보강: **Langfuse(MIT)** 또는 **Helicone**을 로깅 사이드카로(차단은 LiteLLM이 담당).

> **인터셉션 방식 결정(중요):** "패킷 dump" 요구는 두 가지로 구현 가능.
> - **(권장) 애플리케이션 게이트웨이 방식** — 앱이 LiteLLM Proxy를 LLM 엔드포인트로 사용. TLS 평문 접근이 자연스럽고 가명화 후 재전송 가능. 구현·법무 리스크 최소.
> - (대안) **네트워크 탭/포워드 프록시 + TLS MITM** — 앱 변경 없이 전 트래픽 감시하나, 인증서 주입·암호화 트래픽 복호화로 운영/법무 부담 큼. PoC 범위에서 **비권장**.
> → PoC는 게이트웨이 방식으로 진행하고, 네트워크 탭은 후속 옵션으로 명시.

**4.2 탐지 코어 — Microsoft Presidio (MIT)**
- 내장 **한국형 인식기**(KR_RRN/KR_FRN/KR_BRN/여권/면허, 체크섬 포함) — 기본 OFF이므로 활성화.
- 한국어 전화/계좌 등은 **커스텀 정규식 인식기** 추가.
- **가역 가명화**: Presidio `Encrypt`(AES)로 치환 → 응답 후 `Decrypt`로 원복. 이 네이티브 가역 기능은 OSS 중 Presidio가 유일.
- 인스턴스 보존 치환(`<PERSON_1>` vs `<PERSON_2>`)은 **커스텀 operator** 필요(업스트림 FR 존재) — 설계에 반영.

**4.3 한국어 인명 NER(정규식이 못 잡는 부분) — KoELECTRA-small-v3-modu-ner (~14M)**
- F1 ≈ 0.834, 15개 엔티티(인명/지명/기관 등), **최소 크기로 CPU 친화적**. Presidio NlpEngine에 플러그인.
- **ONNX + INT8 양자화**로 인라인 지연 목표 달성.
- 런타임 확장형 카테고리가 필요하면 **GLiNER multi-v2.1(Apache-2.0)** 보조(지연↑ 수용 시).
- **라이선스 주의:** `gliner_ko`(CC-BY-NC), `Piiranha`(CC-BY-NC-ND)는 **상업 배제**.

**4.4 비밀정보(자격증명/키) — detect-secrets(Apache-2.0) / gitleaks(MIT)**
- detect-secrets `--string`으로 단일 문자열 인프로세스 스캔(임베드 최적). gitleaks는 ~160 룰 stdin 지원.
- **TruffleHog(AGPL)** 는 활성검증이 외부 호출을 유발 → **인라인 배제, 오프라인 감사 전용**.

**4.5 회사 기밀(비정형 비즈니스 데이터) — 턴키 OSS 없음, 계층 방어 설계**
1. **키워드/사전 매칭**(코드네임, "대외비/CONFIDENTIAL" 배너) — 저비용, 오탐 높음.
2. **EDM(Exact Data Match)** — 기밀 DB 레코드의 솔트 해시 매칭, 정밀도 높음(축자 일치).
3. **문서 지문(IDM)** — 알려진 기밀 문서 해시로 파생본 탐지.
4. **임베딩/분류기** — 패러프레이즈까지 일반화, 라벨 데이터 필요(후속 단계).
- PoC는 1)+2) 우선, 3)4)는 로드맵 후속.

**4.6 참조 구현 — LLM Guard(MIT) / skan0779-korean-pii(Apache-2.0)**
- LLM Guard는 Anonymize(Presidio)+Secrets(detect-secrets)+Deanonymize(Vault) 파이프라인을 **이미 결합** → 스캐너 파이프라인 패턴의 포크/벤치 기준.
- 단, LLM Guard는 **한국어 미지원(영/중만)** → 우리가 메우는 갭.
- `skan0779/korean-pii`는 RRN/인명/전화/계좌/카드/사업자번호를 정규식+체크섬+KoELECTRA+Presidio로 **에어갭 CPU Docker**로 이미 구성 → 한국어 스택의 직접 참조.

---

## 5. 정책 모델(감사 동작)

| 분류 | 예시 | 기본 동작 | 가역성 |
|---|---|---|---|
| 강한 PII | 주민번호·카드·계좌·여권 | **차단** 또는 비가역 마스킹 | 비가역 권장 |
| 약한 PII | 인명·전화·이메일·주소 | **가역 가명화** 후 전송 | 가역(응답 원복) |
| 비밀정보 | API키·토큰·비밀번호 | **차단** | — |
| 회사 기밀 | 코드네임·기밀문서 파생 | **차단 + 경고** | — |
| 일반 | — | allow + 로그 | — |

- 모드: `block` / `redact(비가역)` / `pseudonymize(가역)` / `warn(allow+log)` — 분류별·테넌트별 설정.
- 모든 결정은 **감사 로그**에 기록(무엇을, 왜, 어떤 룰로).

---

## 6. 단계별 프로토타이핑 계획 (실행은 사람 개발자)

> 거버넌스 CMP-58/60: 아래 구현 작업의 **오너는 사람 개발자**다. CPO는 설계/명세까지 담당하고, 구현 자식 이슈는 **사람 백로그**로 생성한다.

| 단계 | 내용 | 산출물 | Effort | 오너 |
|---|---|---|---|---|
| **M0 설계 확정** | 본 제안 검토·라우팅/정책 확정·KR 수치 합의 | 승인된 설계 | S | CPO + CEO |
| **M1 게이트웨이 PoC** | LiteLLM Proxy로 private 기본+public 폴백, public 요청 로깅 | 동작하는 프록시 | S | 사람 개발자 |
| **M2 탐지 파이프라인** | Presidio(한국 인식기)+KoELECTRA(ONNX)+detect-secrets `pre_call` 결합 | 인라인 스캐너 | M | 사람 개발자 |
| **M3 가명화/원복** | 가역 가명화 + 응답 de-anonymize + 매핑 Vault | 라운드트립 데모 | M | 사람 개발자 |
| **M4 기밀 1차** | 키워드/사전 + EDM 솔트해시 | 기밀 탐지 v1 | M | 사람 개발자 |
| **M5 벤치/하드닝** | 한국어 PII recall/precision·지연 측정, 정책 UI 룰갱신 | 벤치 리포트 | M | 사람 개발자 |

**완료 기준(마일스톤 위생, binary):** M1=public 요청 100% 로깅 확인 / M2=샘플셋 PII 탐지 동작 / M3=가명화→원복 무손실 / M5=한국어 PII recall≥0.9 & p95 지연≤150ms(목표, M0에서 확정).

---

## 7. 리스크 & 완화 (리스크 가시성 렌즈)

| 리스크 | 가능성 | 영향 | 완화 |
|---|---|---|---|
| 한국어 PII 재현율 부족(인명 변형) | 중 | 높음(유출) | NER+정규식 이중화, 임계 보수 설정, 강한 PII는 차단 기본 |
| 인라인 지연으로 UX 저하 | 중 | 중 | ONNX/INT8, 정규식 선필터, 비동기 로깅 |
| TLS MITM 운영/법무 부담 | 높음 | 높음 | 게이트웨이 방식 채택(앱 통합), 네트워크 탭은 후속 옵션 |
| 기밀(비정형) 탐지 한계 | 높음 | 중 | 계층 방어(키워드→EDM→지문→분류기) 단계 도입 |
| OSS 라이선스 오염 | 낮음 | 높음 | NC/ND 모델·AGPL 인라인 배제(본문 명시) |
| 사람 개발자 미배치로 PoC 정체 | 중 | 높음 | M1 구현 이슈를 **사람 백로그**로 생성, CEO에 리소스 요청 |

## 적용 렌즈 — MoSCoW (PoC 범위 압박 시)
- **Must:** LiteLLM 라우팅·public 로깅(M1), Presidio 한국 PII + 정규식(M2), 강한 PII 차단.
- **Should:** KoELECTRA 인명 NER(M2), 가역 가명화/원복(M3), detect-secrets(M2).
- **Could:** 기밀 EDM/지문(M4), 정책 UI.
- **Won't(이번):** TLS MITM 네트워크 탭, 임베딩 기밀 분류기, 완전 DLP.

---

## 8. CEO 정렬 필요 결정사항

1. **KR 수치 확정** — 한국어 PII recall 목표·인라인 지연 목표(2/6장 후보값 승인).
2. **인터셉션 방식** — 게이트웨이(권장) vs 네트워크 탭. PoC는 게이트웨이로 가정.
3. **사람 개발자 배치** — M1~M5 구현 오너(현재 NuFi 구현트랙은 사람 백로그). 6월 백엔드 0.5는 AI바우처 전용([nufi_studio_s0] 메모) → **별도 리소스 필요**.
4. **고객 PoC 연계** — 본 기능을 NuFi POC 파트너 전략([nufi_poc_strategy])의 무상 PoC 범위에 포함할지.
5. **로드맵 배치** — NuFi Serve/Studio 트랙과의 우선순위(포트폴리오 로드 렌즈).

---

## 9. 출처(주요)

- LiteLLM: github.com/BerriAI/litellm · docs.litellm.ai/docs/proxy/guardrails/quick_start
- Kong AI Gateway: developer.konghq.com/ai-gateway/ · Apache APISIX: apisix.apache.org/ai-gateway/
- Presidio: github.com/microsoft/presidio · microsoft.github.io/presidio/supported_entities · /anonymizer
- KoELECTRA NER: huggingface.co/Leo97/KoELECTRA-small-v3-modu-ner · github.com/monologg/KoELECTRA
- 한국어 PII 참조: github.com/skan0779/korean-pii
- 비밀정보: github.com/Yelp/detect-secrets · github.com/gitleaks/gitleaks · github.com/trufflesecurity/trufflehog(AGPL)
- LLM Guard: github.com/protectai/llm-guard · protectai.github.io/llm-guard
- GLiNER: github.com/urchade/GLiNER · huggingface.co/urchade/gliner_multi-v2.1
- 프라이어 아트: Lakera, Nightfall, WhyLabs LangKit, NeMo Guardrails, Guardrails AI

---

## 10. 다음 액션

- [ ] CEO: 8장 결정사항 검토(특히 KR 수치·인터셉션 방식·사람 개발자 배치).
- [ ] CPO: 승인 시 M1~M2 구현 명세를 사람 개발자 백로그 자식 이슈로 분해(거버넌스: 오너=사람).
- [ ] CPO: NuFi 로드맵에 "Egress-Audit 게이트웨이" 트랙 등재(POC 파트너 전략과 연계).

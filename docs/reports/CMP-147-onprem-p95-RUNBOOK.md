# CMP-147 — 온프렘 p95 재측정 런북 (per-channel INT8 NER)

- **이슈:** CMP-147 [CMP-145 후속] 온프렘 p95 재측정 · **등급:** Should
- **상위:** CMP-145 ② (승인 `6e02b6aa` 리스크경로: 온프렘 환경 미확보 시 ②를 별도 추적)
- **상태:** **blocked** — 프로덕션 사양 온프렘 하드웨어 미확보. 측정 하니스·러너는 **준비 완료**.

> **요약:** 측정 코드는 끝났다. 남은 것은 **하드웨어 한 대**뿐이다. 프로덕션 사양 박스에서
> 아래 1-명령을 실행하면 host provenance 가 박힌 측정표가 산출되고 CMP-147 은 종결된다.

---

## 블로커 / 언블록 (first-class)

- **블로커:** 실제 온프렘(프로덕션 사양) 하드웨어 미확보. 현재 측정 박스는 **비프로덕션**
  (WSL2 / i7-1360P 모바일 4코어 / 7.6GB) → 진짜 운영 p95 를 낼 수 없다.
- **언블록 오너:** **보드 / CEO** — 온프렘 측정 환경(또는 대표 사양 인스턴스) 제공.
- **언블록 액션:** 환경 제공 시 그 박스에서 아래 1-명령 실행 → `docs/reports/CMP-147-onprem-p95.md` commit.
- **대안(보드 선택지):** 운영 인프라 확보 전까지 **dev-env 인터림을 v0.0.5 참고치로 수용**하고
  프로덕션 측정을 **v0.1.0(인프라 가용 시)으로 이연**. ① (CI ≥0.85) 은 CMP-145 에서 이미 종결됐고
  ②는 Should 등급이라 릴리스를 막지 않는다.

---

## 1-명령 재실행 (프로덕션 박스)

```bash
# 모델 스택(transformers/torch/onnxruntime/optimum + INT8 ONNX)이 동일 경로에 있어야 함:
#   ~/.cache/m5_libs (PYTHONPATH) · ~/.cache/m5_onnx_int8/int8 (per-channel)
HOST_CLASS=production PYTHONPATH=~/.cache/m5_libs bash scripts/measure_onprem_p95.sh
```

러너(`scripts/measure_onprem_p95.sh`)가 하는 일:
1. **host provenance 채집** — CPU 모델/코어/거버너/RAM/커널을 산출물에 박아 넣는다.
   (dev-env 수치로 오인되는 것을 구조적으로 차단. 비프로덕션 박스면 `host_class=non-production`
   경고 + 표 헤더에 ⚠️ 자동 기입.) `HOST_CLASS=production` 으로 대표 사양 라벨을 확정한다.
2. **무부하 버킷** — `bench_m5.py --backend onnx-int8` (≤128 / 512(NFR2) / 2048자).
3. **동시성·지속부하** — `bench_load.py --backend onnx-int8 --concurrency 1,2,4,8 --chars 512`.
4. **측정표 생성** — `docs/reports/CMP-147-onprem-p95.md` (provenance 헤더 포함).

산출물: `CMP-147-onprem-p95.md`(표) · `CMP-147-onprem-int8-noload.json` ·
`CMP-147-onprem-load.json` · `CMP-147-onprem-host.json`(provenance).

---

## 인터림 (비프로덕션 박스, dev-env 참고치 — 운영 용량 산정 근거 아님)

신(per-channel) INT8 을 본 박스(WSL2 / i7-1360P 4코어)에서 측정한 **참고치**.
CMP-145 리포트의 75ms 와 동일 정성(per-channel 은 per-tensor 대비 스케일 연산 가산).

### 무부하 버킷 p95

| 입력 | p50 | **p95** | p99 | req/s |
|---|---|---|---|---|
| ≤128자 | 11.7ms | **13.2ms** | 14.6ms | 84.6 |
| **512자(NFR2)** | 44.7ms | **54.0ms** | 72.3ms | 22.1 |
| 2048자 | 148.9ms | **220.7ms** | 263.2ms | 6.5 |

- 512자 무부하 p95 **54ms ≤ 150ms PASS** (참고치).

### 동시성·지속부하 (512자) — CMP-123 §3 envelope 재확인

| 동시성 C | lat p95 | ≤150ms |
|---|---|---|
| 1 | 68.4ms | ✅ |
| 2 | 56.7ms | ✅ |
| 4 | 313.6ms | ❌ |
| 8 | 568.5ms | ❌ |

- **≤150ms 는 C≤2 한정** (모바일 4코어 과구독에서 C≥4 포화). CMP-123 §3 정성과 동일.
- 백프레셔: 안정 도착률 λ ≤ μ≈19 req/s (mean service ~52ms). λ>μ 면 감사 큐 무한 증가.
- **비프로덕션 4코어 수치** — 프로덕션 코어수·클럭·거버너에서 C 포화점이 달라진다.
  운영 용량은 반드시 프로덕션 박스 재측정으로 확정할 것.

---

## 종결 조건
`host_class=production` 으로 위 1-명령 실행 → `CMP-147-onprem-p95.md` commit → CMP-147 done.
그 전까지는 본 런북이 인터림 근거이며, 이슈는 **보드/CEO 환경 제공 대기로 blocked**.

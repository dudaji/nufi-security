# CMP-147 — 온프렘 p95 측정표 (per-channel INT8 NER)

- **host_class:** `non-production`  ·  **CPU:** 13th Gen Intel(R) Core(TM) i7-1360P (4 cores, governor=unknown, 7.6GB)
- **kernel:** Linux 6.6.87.2-microsoft-standard-WSL2 x86_64
- **backend:** onnx-int8  ·  **stack:** PYTHONPATH=/home/shhon/.cache/m5_libs ; INT8 ONNX ~/.cache/m5_onnx_int8/int8 (per-channel) ; Leo97/KoELECTRA-small-v3-modu-ner

> ⚠️ **host_class=non-production — 이 표는 프로덕션 측정이 아니다.** 운영 용량 산정 근거로 인용 금지. 프로덕션 사양에서 `HOST_CLASS=production` 으로 재실행 필요.

## 무부하 버킷 p95

| 입력 | p50 | **p95** | p99 | req/s |
|---|---|---|---|---|
| ≤128자 | 11.69 | **13.15** | 14.59 | 84.6 |
| **512자(NFR2)** | 44.72 | **53.99** | 72.3 | 22.1 |
| 2048자 | 148.89 | **220.65** | 263.24 | 6.5 |

## 동시성·지속부하 (512자)

```json
{
  "backend": "onnx-int8",
  "chars": 512,
  "p95_target_ms": 150.0,
  "ner_backend_active": "onnx-int8",
  "ner_pool_config": {
    "intra_op_threads": 1,
    "infer_workers": 4,
    "cpu_count": 4
  },
  "concurrency_sweep": {
    "1": {
      "concurrency": 1,
      "requests": 200,
      "lat_p50_ms": 44.94,
      "lat_p95_ms": 68.355,
      "lat_p99_ms": 81.7,
      "lat_max_ms": 84.581,
      "queue_delay_p95_ms": 9322.061,
      "throughput_req_s": 20.5,
      "wall_s": 9.737,
      "p95_le_150ms": true
    },
    "2": {
      "concurrency": 2,
      "requests": 200,
      "lat_p50_ms": 47.777,
      "lat_p95_ms": 56.651,
      "lat_p99_ms": 80.441,
      "lat_max_ms": 86.105,
      "queue_delay_p95_ms": 4626.358,
      "throughput_req_s": 40.7,
      "wall_s": 4.91,
      "p95_le_150ms": true
    },
    "4": {
      "concurrency": 4,
      "requests": 200,
      "lat_p50_ms": 71.333,
      "lat_p95_ms": 313.573,
      "lat_p99_ms": 353.935,
      "lat_max_ms": 364.953,
      "queue_delay_p95_ms": 5192.553,
      "throughput_req_s": 36.1,
      "wall_s": 5.54,
      "p95_le_150ms": false
    },
    "8": {
      "concurrency": 8,
      "requests": 200,
      "lat_p50_ms": 160.931,
      "lat_p95_ms": 568.523,
      "lat_p99_ms": 893.406,
      "lat_max_ms": 1016.856,
      "queue_delay_p95_ms": 5236.486,
      "throughput_req_s": 35.5,
      "wall_s": 5.642,
      "p95_le_150ms": false
    }
  },
  "sustained": {
    "concurrency": 4,
    "duration_s": 10.11,
    "total_requests": 287,
    "throughput_req_s": 28.4,
    "lat_p50_ms": 102.762,
    "lat_p95_ms": 324.661,
    "lat_p99_ms": 355.172,
    "interval_p95_min_ms": 174.899,
    "interval_p95_max_ms": 345.077,
    "p95_le_150ms": false
  },
  "backpressure": {
    "service_rate_mu_req_s": 19.2,
    "mean_service_ms": 52.006,
    "p95_service_ms": 76.932,
    "lambda_safe_req_s": 19.2,
    "note": "도착률 λ ≤ μ 이면 감사 큐 안정(유한 대기). λ>μ 면 큐 무한 증가→백프레셔."
  },
  "all_concurrency_p95_le_150ms": false
}
```


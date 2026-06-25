"""KoELECTRA NER → ONNX FP32 내보내기 + 동적 INT8 양자화.

설계: docs/design/gateway/m5-bench-hardening-spec.md §2.2 (CMP-78). 이슈: CMP-100.
거버넌스: 보안 도메인 상시 승인(GOVERNANCE.md 규칙3, CMP-96).

`Leo97/KoELECTRA-small-v3-modu-ner` 를 optimum(ORT)로 ONNX 내보내기 후
동적 양자화(QInt8, 가중치 INT8)로 변환한다. 산출물 디렉터리는 기본적으로
저장소 밖(`~/.cache/m5_onnx_int8`)에 둬 대용량 바이너리 커밋을 피한다.

  python3 scripts/export_onnx_int8.py            # 기본 경로로 내보내기+양자화
  M5_ONNX_DIR=/path python3 scripts/export_onnx_int8.py

런타임 의존: transformers, onnx, onnxruntime, optimum[onnxruntime]. 에어갭(NFR1)
프로덕션에서는 사전 산출된 INT8 ONNX 를 반입해 동일 경로에 배치한다.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

MODEL_ID = "Leo97/KoELECTRA-small-v3-modu-ner"
DEFAULT_DIR = Path(os.environ.get("M5_ONNX_DIR", Path.home() / ".cache" / "m5_onnx_int8"))


def main():
    out = DEFAULT_DIR
    fp32_dir = out / "fp32"
    int8_dir = out / "int8"
    fp32_dir.mkdir(parents=True, exist_ok=True)
    int8_dir.mkdir(parents=True, exist_ok=True)

    from optimum.onnxruntime import ORTModelForTokenClassification, ORTQuantizer
    from optimum.onnxruntime.configuration import AutoQuantizationConfig
    from transformers import AutoTokenizer

    print(f"[1/3] FP32 ONNX 내보내기: {MODEL_ID} → {fp32_dir}", flush=True)
    model = ORTModelForTokenClassification.from_pretrained(MODEL_ID, export=True)
    model.save_pretrained(fp32_dir)
    AutoTokenizer.from_pretrained(MODEL_ID).save_pretrained(fp32_dir)

    print(f"[2/3] 동적 INT8 양자화(avx512_vnni, QInt8) → {int8_dir}", flush=True)
    quantizer = ORTQuantizer.from_pretrained(fp32_dir)
    # CPU 동적 양자화: 가중치 INT8. AVX512-VNNI 미지원 CPU 도 동적 경로는 동작.
    qconfig = AutoQuantizationConfig.avx512_vnni(is_static=False, per_channel=False)
    quantizer.quantize(save_dir=int8_dir, quantization_config=qconfig)
    AutoTokenizer.from_pretrained(MODEL_ID).save_pretrained(int8_dir)

    # 산출물 크기 보고(FP32 대비 INT8 축소 확인)
    def dir_mb(p):
        return round(sum(f.stat().st_size for f in p.glob("*.onnx")) / 1e6, 1)

    print(f"[3/3] 완료. FP32 onnx={dir_mb(fp32_dir)}MB  INT8 onnx={dir_mb(int8_dir)}MB", flush=True)
    print(f"INT8_DIR={int8_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

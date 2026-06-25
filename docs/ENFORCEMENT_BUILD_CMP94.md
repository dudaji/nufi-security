# Egress Enforcement MVP — 빌드 문서 (CMP-94 트랙 B)

> 설계 스펙: `docs/SPEC_EGRESS_ENFORCEMENT.md` (CMP-93, 보드 확정)
> 거버넌스: 신규 CMP-58 승인 `43dd134b` (트랙 A 감사 승인 `3053e076` 과 별개) — **보드 approved**
> 모델: (a) nftables egress 허용목록 = MVP. 게이트웨이 출처(uid/cgroup)만 public 허용, 그 외 drop.

## 1. 무엇이 빌드됐나 (스펙 §8.1)

| # | 산출물 | 모듈 |
|---|---|---|
| 1 | rule_builder — routing.yaml/policy.yaml → nftables 규칙(화이트리스트 선적용 + public_dst drop) | `enforcement/rule_builder.py` |
| 2 | applier — 원자 commit/rollback, fail_mode(open\|closed), 킬스위치, CAP_NET_ADMIN 분리 | `enforcement/applier.py` |
| 3 | 결정 로그 승격 — 트랙 A SIMULATED → `mode=ENFORCED` + `rule_id`(nft 핸들/동적 set) | `enforcement/decision.py` |
| 4 | drop 피드백 — 커널 drop 로그 → P1/P2 재유입 + `blocked_attempts` 카운터 | `enforcement/feedback.py` |
| 5 | 킬스위치 CLI — `nufi-egress disable` 즉시 전 규칙 제거 | `enforcement/cli.py` |

**정책 단일 출처(A7):** public 목적지는 `capture.targets.derive_targets`(routing.yaml `egress_class: public`)를 재사용한다. 정책 사본 없음. enforcement 토글은 `config/policy.yaml` 의 `enforcement:` 섹션.

## 2. CLI

```bash
python3 -m enforcement.cli status                 # 집행 상태(JSON)
python3 -m enforcement.cli render                 # 규칙 셋 텍스트(적용 안 함·비특권)
sudo python3 -m enforcement.cli apply             # 정적 사전 차단(원자 적용)
sudo python3 -m enforcement.cli apply --fail-mode closed
sudo python3 -m enforcement.cli disable           # 킬스위치(A8)
journalctl -k | python3 -m enforcement.cli feedback   # drop → blocked_attempts + flow 재유입
```

`nft`/권한이 없으면 `apply`/`disable` 는 자동으로 **dry-run**(텍스트만, 안전 degrade). 게이트웨이 uid/cgroup 이 policy.yaml 에 없으면 applier 가 routing.yaml `gateway.process_names` → 실행 중 프로세스 uid 로 런타임 해석한다.

## 3. 안전 설계 (스펙 §2·§5)

- **화이트리스트 선적용(A6):** accept 규칙이 drop 보다 항상 먼저. 전체 셋을 `nft -f` 한 트랜잭션으로 원자 로드 → "게이트웨이 자살"(drop 만 들어간 중간 상태) 불가. 셀렉터(uid/cgroup)가 하나도 없으면 `render_ruleset` 이 `ValueError` 로 거부.
- **fail-open 기본(A4):** 적용 실패 시 차단 규칙 미적용(관찰만, 탐지는 유지). `fail-closed`(A5)는 `policy.yaml enforcement.fail_mode: closed` 옵트인 — 실패 시 패닉 전면 차단.
- **킬스위치(A8):** `disable` = 테이블 제거. 규칙 0, 트래픽 전면 통과.

## 4. 수용 기준 매핑 (스펙 §8.2)

| 기준 | 검증 위치 |
|---|---|
| A1 게이트웨이 public 통과 | 통합(`scripts/enforcement_integration.sh`, netns) |
| A2 비-게이트웨이 직결 drop | 통합 |
| A3 drop 감사 증적 | 유닛(`test_feedback_*`, `blocked_attempts`) + 통합(커널 로그) |
| A4 fail-open | 유닛(`test_fail_open_*`) + 통합 |
| A5 fail-closed(옵트인) | 유닛(`test_fail_closed_*`) + 통합 |
| A6 원자성·화이트리스트 선commit | 유닛(`test_whitelist_precedes_drop`, `test_atomic_recreate_idiom`, `test_missing_gateway_selector_rejected`) + 통합 |
| A7 정책 단일 출처 | 유닛(`test_single_source_new_backend`, 골든) |
| A8 킬스위치 | 유닛(`test_killswitch_teardown_text`) + 통합 |
| A9 nft·iptables-nft 호환 | 통합(매트릭스 2종 환경) |

## 5. 검증 절차 (스펙 §8.3)

```bash
# 유닛/CI (root 불요): 골든 텍스트 + 결정 스키마 + 피드백 파싱
python3 tests/test_enforcement.py        # 또는: pytest tests/test_enforcement.py

# 통합 (root/CAP_NET_ADMIN, 격리 netns): A1~A9 실집행·실 drop
sudo bash scripts/enforcement_integration.sh
```

골든 픽스처: `tests/golden/egress_ruleset.nft` (+ panic/teardown). rule_builder 출력이 바뀌면 골든 갱신 후 리뷰.

## 6. S4 데모 승격 (스펙 §9 — 후속)

S4 데모 스크립트에 `--enforce` 플래그를 추가하면 트랙 A `mode=SIMULATED`(root 불요·CI 안전) ↔ 트랙 B `mode=ENFORCED`(격리 netns 실 drop)를 한 화면에서 대비할 수 있다. 본 빌드가 그 ENFORCED 경로(applier + decision 승격)를 제공한다.

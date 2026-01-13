# Phase 6: k6 부하 테스트 및 안정성 검증

## 개요

Phase 5에서 확인된 PostgreSQL과 HDFS의 단일 쿼리 성능을 기반으로, k6를 활용하여 동시 사용자 부하 테스트 및 시스템 안정성을 검증한다.

## 테스트 목표

1. **동시 사용자 처리 능력**: VU(Virtual Users) 증가에 따른 응답 시간 변화
2. **오류 발생률**: 부하 증가 시 에러율 측정
3. **시스템 안정성**: 지속적인 부하에서의 안정성 확인
4. **PostgreSQL vs HDFS 비교**: 부하 상황에서의 성능 차이

## 테스트 환경

### 데이터 규모
- PostgreSQL: 121,670,000건
- HDFS: 121,619,878건 (100개 Parquet 파일)

### 타임아웃 설정
- PostgreSQL 쿼리: 120초
- HDFS 쿼리: 300초

## 테스트 시나리오

### Scenario 1: PostgreSQL 단순 조회 부하 테스트
- 목적: PostgreSQL의 동시 조회 처리 능력 측정
- VU: 1 → 10 → 30 → 50 → 30 → 0 (점진적 증가/감소)
- 쿼리: `/api/query/postgres/logs?limit=100`

### Scenario 2: PostgreSQL 집계 쿼리 부하 테스트
- 목적: 복잡한 집계 쿼리의 동시 처리 능력
- VU: 1 → 5 → 10 → 20 → 10 → 0
- 쿼리: `/api/query/postgres/logs/aggregate?group_by=service`

### Scenario 3: HDFS 단순 조회 부하 테스트
- 목적: HDFS + Spark의 동시 조회 처리 능력
- VU: 1 → 3 → 5 → 10 → 5 → 0 (HDFS는 리소스 많이 사용)
- 쿼리: `/api/query/hdfs/logs?limit=100`

### Scenario 4: HDFS 집계 쿼리 부하 테스트
- 목적: Spark 분산 집계의 동시 처리 능력
- VU: 1 → 3 → 5 → 10 → 5 → 0
- 쿼리: `/api/query/hdfs/logs/aggregate?group_by=service`

### Scenario 5: 혼합 워크로드 테스트
- 목적: 실제 사용 패턴 시뮬레이션
- PostgreSQL 70% + HDFS 30% 비율
- VU: 1 → 10 → 20 → 30 → 20 → 0

### Scenario 6: PostgreSQL vs HDFS 직접 비교
- 목적: 동일 조건에서 두 시스템 비교
- 동일 쿼리를 순차적으로 실행하여 비교

## 성공 기준

| 메트릭 | PostgreSQL | HDFS |
|--------|-----------|------|
| 에러율 | < 5% | < 10% |
| P95 응답시간 | < 30초 | < 60초 |
| 처리량 (req/s) | > 1 | > 0.3 |

## 실행 방법
```bash
# Scenario 1: PostgreSQL 단순 조회
k6 run k6/phase6/pg_simple_load.js

# Scenario 2: PostgreSQL 집계
k6 run k6/phase6/pg_aggregate_load.js

# Scenario 3: HDFS 단순 조회
k6 run k6/phase6/hdfs_simple_load.js

# Scenario 4: HDFS 집계
k6 run k6/phase6/hdfs_aggregate_load.js

# Scenario 5: 혼합 워크로드
k6 run k6/phase6/mixed_workload.js

# Scenario 6: 직접 비교
k6 run k6/phase6/direct_comparison.js
```

## 결과 저장

각 테스트 결과는 JSON 형식으로 저장:
- `k6/phase6/results/pg_simple_result.json`
- `k6/phase6/results/pg_aggregate_result.json`
- `k6/phase6/results/hdfs_simple_result.json`
- `k6/phase6/results/hdfs_aggregate_result.json`
- `k6/phase6/results/mixed_result.json`
- `k6/phase6/results/comparison_result.json`
# Phase 7: 적정 부하 계산 및 재테스트

## 개요

Phase 6에서 과도한 VU 설정으로 인한 테스트 실패를 분석하고, 현재 리소스 기반으로 적정 VU를 계산하여 재테스트를 진행한다.

## 적정 VU 계산

### 1. 리소스 기반 계산

#### PostgreSQL 환경
```
할당 리소스:
- CPU: 2 cores
- Memory: 2 GB

단일 쿼리 성능:
- 단순 조회: 3.8초 (k6 측정 평균)
- 집계 쿼리: 17.8초 (k6 측정 평균)
```

#### 계산 공식
```
최대 동시 처리량 = 가용 리소스 / 요청당 리소스 사용량

적정 VU = (테스트 시간 / 요청당 소요 시간) × 안전 계수
```

### 2. PostgreSQL 적정 VU 계산

#### 단순 조회 쿼리
```
요청당 소요 시간: 3.8초
sleep 시간: 1초
1 VU의 요청 주기: 3.8 + 1 = 4.8초

CPU 2코어 기준:
- PostgreSQL 쿼리는 단일 스레드
- 동시 쿼리 처리: ~2개 (CPU 바운드)

Memory 2GB 기준:
- 연결당 메모리: ~50MB
- 최대 연결: 2048 / 50 = ~40개 (이론상)
- 실제 안전 연결: ~10개 (버퍼 고려)

병목: CPU (2개 동시 처리)

적정 VU 계산:
- 이론적 최대: 2 × (4.8 / 3.8) = 2.5
- 안전 계수 적용 (0.7): 2.5 × 0.7 ≈ 2
- 버퍼 포함 권장: 3~5 VU
```

#### 집계 쿼리
```
요청당 소요 시간: 17.8초
sleep 시간: 2초
1 VU의 요청 주기: 17.8 + 2 = 19.8초

집계 쿼리 특성:
- Full Table Scan 필요
- CPU 집약적 (GROUP BY 연산)
- 메모리 집약적 (집계 결과 저장)

적정 VU 계산:
- 이론적 최대: 2 × (19.8 / 17.8) = 2.2
- 안전 계수 적용 (0.7): 2.2 × 0.7 ≈ 1.5
- 권장: 2~3 VU
```

### 3. HDFS + Spark 적정 VU 계산

#### 리소스 현황
```
Spark Worker x2:
- 각 Worker: CPU 3코어, Memory 2GB
- 총: CPU 6코어, Memory 4GB

DataNode x2:
- 각 DataNode: Memory 4GB limit
- 현재 사용: datanode-1이 2.7GB 사용 중 (위험)

Query API:
- Spark 세션 1개 공유 (병목)
```

#### 단순 조회 쿼리
```
요청당 소요 시간: 12초
sleep 시간: 3초
1 VU의 요청 주기: 12 + 3 = 15초

Spark 특성:
- 단일 Spark 세션에서 순차 처리
- 동시 쿼리 시 큐잉 발생

DataNode 메모리 제약:
- 현재 2.7GB / 4GB 사용 중
- 추가 요청 시 OOM 위험

적정 VU 계산:
- Spark 세션 1개 = 동시 처리 1개
- 안전 계수 적용: 1 × 0.7 ≈ 1
- 권장: 1~2 VU
```

#### 집계 쿼리
```
요청당 소요 시간: 12초 (Compaction 후)
sleep 시간: 5초
1 VU의 요청 주기: 12 + 5 = 17초

적정 VU 계산:
- Spark 세션 제약으로 동시 처리 제한
- 권장: 1~2 VU
```

### 4. 계산 결과 요약

| 테스트 | Phase 6 VU | 적정 VU | 계산 근거 |
|--------|-----------|---------|-----------|
| PG 단순 조회 | 50 | **5** | CPU 2코어 × 안전계수 |
| PG 집계 | 20 | **3** | CPU 바운드 + 메모리 |
| HDFS 단순 | 10 | **2** | Spark 세션 제약 |
| HDFS 집계 | 10 | **2** | Spark 세션 + DataNode 메모리 |

### 5. 처리량 예측

#### PostgreSQL
```
단순 조회 (VU=5):
- 요청 주기: 4.8초
- 분당 요청: 5 × (60 / 4.8) = 62.5 req/min
- 시간당: ~3,750 req/hour

집계 쿼리 (VU=3):
- 요청 주기: 19.8초
- 분당 요청: 3 × (60 / 19.8) = 9.1 req/min
- 시간당: ~545 req/hour
```

#### HDFS
```
단순 조회 (VU=2):
- 요청 주기: 15초
- 분당 요청: 2 × (60 / 15) = 8 req/min
- 시간당: ~480 req/hour

집계 쿼리 (VU=2):
- 요청 주기: 17초
- 분당 요청: 2 × (60 / 17) = 7.1 req/min
- 시간당: ~425 req/hour
```

## 수정된 테스트 계획

### 테스트 목표

1. 에러율 5% 미만 달성
2. P95 응답시간 threshold 충족
3. 시스템 안정성 확인 (메모리, CPU 모니터링)

### 성공 기준

| 테스트 | 에러율 | P95 응답시간 |
|--------|--------|--------------|
| PG 단순 조회 | < 5% | < 10초 |
| PG 집계 | < 5% | < 30초 |
| HDFS 단순 | < 10% | < 30초 |
| HDFS 집계 | < 10% | < 30초 |

## 테스트 시나리오

### Scenario 1: PostgreSQL 단순 조회 (VU 1→5)
```javascript
stages: [
  { duration: '30s', target: 2 },   // 웜업
  { duration: '1m', target: 5 },    // 목표
  { duration: '2m', target: 5 },    // 유지
  { duration: '30s', target: 0 },   // 종료
]
// 총 4분
```

### Scenario 2: PostgreSQL 집계 쿼리 (VU 1→3)
```javascript
stages: [
  { duration: '30s', target: 1 },
  { duration: '1m', target: 3 },
  { duration: '2m', target: 3 },
  { duration: '30s', target: 0 },
]
// 총 4분
```

### Scenario 3: HDFS 단순 조회 (VU 1→2)
```javascript
stages: [
  { duration: '30s', target: 1 },
  { duration: '1m', target: 2 },
  { duration: '2m', target: 2 },
  { duration: '30s', target: 0 },
]
// 총 4분
```

### Scenario 4: HDFS 집계 쿼리 (VU 1→2)
```javascript
stages: [
  { duration: '30s', target: 1 },
  { duration: '1m', target: 2 },
  { duration: '2m', target: 2 },
  { duration: '30s', target: 0 },
]
// 총 4분
```

## 실행 방법
```bash
# 결과 디렉토리 생성
mkdir -p k6/phase7/results

# 테스트 실행
k6 run k6/phase7/pg_simple_load.js
k6 run k6/phase7/pg_aggregate_load.js
k6 run k6/phase7/hdfs_simple_load.js
k6 run k6/phase7/hdfs_aggregate_load.js
```

## 모니터링

테스트 중 별도 터미널에서:
```bash
# 리소스 모니터링
watch -n 5 "kubectl top pods -n log-pipeline"

# API 로그
kubectl logs -f deployment/query-api -n log-pipeline
```

## 예상 결과

| 테스트 | VU | 예상 요청 수 | 예상 에러율 | 예상 P95 |
|--------|-----|-------------|------------|----------|
| PG 단순 | 5 | ~250 | < 5% | ~5초 |
| PG 집계 | 3 | ~35 | < 5% | ~20초 |
| HDFS 단순 | 2 | ~30 | < 10% | ~15초 |
| HDFS 집계 | 2 | ~25 | < 10% | ~15초 |
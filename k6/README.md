# k6 부하 테스트 가이드

## 📋 개요

PostgreSQL과 HDFS/Spark 조회 API의 성능을 비교하는 k6 부하 테스트 스크립트입니다.

---

## 🔧 k6 설치

### Ubuntu/Debian

```bash
sudo gpg -k
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update
sudo apt-get install k6
```

### Docker

```bash
docker pull grafana/k6
```

---

## 📁 테스트 스크립트

| 파일 | 설명 | 대상 |
|------|------|------|
| `postgres_simple_query.js` | PostgreSQL 단순 조회 | PostgreSQL |
| `postgres_aggregate_query.js` | PostgreSQL 집계 조회 | PostgreSQL |
| `hdfs_query.js` | HDFS/Spark 조회 | HDFS |
| `comparison_test.js` | PostgreSQL vs HDFS 비교 | 둘 다 |
| `mixed_workload.js` | 혼합 워크로드 | PostgreSQL |

---

## 🚀 실행 방법

### 개별 테스트

```bash
# PostgreSQL 단순 조회 테스트
k6 run postgres_simple_query.js

# PostgreSQL 집계 조회 테스트
k6 run postgres_aggregate_query.js

# HDFS 조회 테스트
k6 run hdfs_query.js

# 비교 테스트
k6 run comparison_test.js

# 혼합 워크로드 테스트
k6 run mixed_workload.js
```

### 스크립트 사용

```bash
chmod +x run_tests.sh

# 특정 테스트 실행
./run_tests.sh postgres_simple

# 전체 테스트 실행
./run_tests.sh all
```

### Docker 사용

```bash
docker run -i grafana/k6 run - < postgres_simple_query.js
```

---

## 📊 테스트 시나리오

### 1. PostgreSQL 단순 조회

```
부하 패턴:
1 → 10 VUs (30s)
10 → 50 VUs (1m)
50 → 100 VUs (30s)
100 VUs 유지 (1m)
100 → 0 VUs (30s)

성공 기준:
- P95 응답 시간 < 500ms
- 에러율 < 10%
```

### 2. PostgreSQL 집계 조회

```
부하 패턴:
1 → 10 VUs (30s)
10 → 30 VUs (1m)
30 → 50 VUs (30s)
50 VUs 유지 (1m)
50 → 0 VUs (30s)

성공 기준:
- P95 응답 시간 < 1000ms
- 에러율 < 10%
```

### 3. HDFS/Spark 조회

```
부하 패턴:
1 → 5 VUs (30s)
5 → 10 VUs (1m)
10 → 20 VUs (30s)
20 VUs 유지 (1m)
20 → 0 VUs (30s)

성공 기준:
- P95 응답 시간 < 30000ms (30초)
- 에러율 < 20%
```

### 4. 혼합 워크로드

```
워크로드 비율:
- 단순 조회: 40%
- 조건 조회: 30%
- 집계 조회: 20%
- 통계 조회: 10%

부하 패턴:
1 → 20 → 50 → 100 VUs

성공 기준:
- P95 응답 시간 < 1000ms
- 에러율 < 10%
```

---

## 📈 결과 분석

### 콘솔 출력 예시

```
================================================================================
PostgreSQL 단순 조회 테스트 결과
================================================================================
총 요청 수: 5000
성공률: 99.8%
평균 응답 시간: 15.32ms
P95 응답 시간: 45.67ms
P99 응답 시간: 78.23ms
================================================================================
```

### JSON 결과

각 테스트는 `{테스트명}.json` 파일로 상세 결과를 저장합니다.

---

## ⚠️ 주의사항

1. **네트워크**: Worker 노드에서 Master API에 접근 가능해야 함
2. **HDFS 테스트**: 응답 시간이 길어 타임아웃 설정 필요
3. **리소스**: 높은 부하 시 서버 리소스 모니터링 필요
4. **데이터량**: 테스트 전 충분한 데이터 적재 권장

---

## 🔗 API 엔드포인트

```
Base URL: http://192.168.55.114:30801

PostgreSQL:
  GET /api/query/postgres/logs
  GET /api/query/postgres/logs/aggregate
  GET /api/query/postgres/stats

HDFS:
  GET /api/query/hdfs/logs
  GET /api/query/hdfs/logs/aggregate
  GET /api/query/hdfs/stats

비교:
  GET /api/query/compare
```
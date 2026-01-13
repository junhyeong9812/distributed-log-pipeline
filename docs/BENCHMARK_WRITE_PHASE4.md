# Phase 4: 1.2억건 대용량 데이터 벤치마크

## 개요

Phase 3에서 확장된 클러스터 환경에서 1.2억건 로그 데이터를 적재하고, PostgreSQL과 HDFS+Spark의 조회 성능을 비교한다.

## 테스트 환경

### 하드웨어
| 노드 | 역할 | CPU | RAM |
|------|------|-----|-----|
| Master | NameNode, Spark Master, PostgreSQL | 8 cores | 16GB |
| Worker1 | DataNode, Spark Worker | 8 cores | 16GB |
| Worker2 | DataNode, Spark Worker | 8 cores | 16GB |

### 리소스 할당
| 컴포넌트 | 메모리 | CPU |
|----------|--------|-----|
| PostgreSQL | 2GB | 2 cores |
| Spark Master | 2GB | 2 cores |
| Spark Worker (x2) | 2GB each | 3 cores each |
| DataNode (x2) | 4GB each | 3 cores each |

### 데이터 규모
- **PostgreSQL logs 테이블**: 121,670,000건
- **PostgreSQL events 테이블**: 64,250,000건
- **HDFS Parquet**: 121,619,878건

## 테스트 쿼리

### Query 1: 단순 COUNT
전체 로그 수를 카운트하는 기본 쿼리
```sql
-- PostgreSQL
SELECT COUNT(*) FROM logs;

-- HDFS (Spark SQL)
SELECT COUNT(*) FROM parquet.`/data/logs/raw`
```

### Query 2: GROUP BY 단일 컬럼
서비스별 로그 수 집계
```sql
-- PostgreSQL
SELECT service, COUNT(*) FROM logs GROUP BY service;

-- HDFS (Spark SQL)
SELECT service, COUNT(*) FROM parquet.`/data/logs/raw` GROUP BY service
```

### Query 3: WHERE + GROUP BY
ERROR 레벨 로그만 필터링 후 서비스별 집계
```sql
-- PostgreSQL
SELECT service, COUNT(*) FROM logs WHERE level = 'ERROR' GROUP BY service;

-- HDFS (Spark SQL)
SELECT service, COUNT(*) FROM parquet.`/data/logs/raw` WHERE level = 'ERROR' GROUP BY service
```

### Query 4: 다중 GROUP BY
레벨과 서비스 복합 집계 (Phase 5에서 진행 예정)
```sql
-- PostgreSQL
SELECT level, service, COUNT(*) FROM logs GROUP BY level, service;

-- HDFS (Spark SQL)
SELECT level, service, COUNT(*) FROM parquet.`/data/logs/raw` GROUP BY level, service
```

## 테스트 방법

1. API 서버 재시작하여 캐시 초기화
2. 각 쿼리를 curl로 실행 (타임아웃 600초)
3. query_time_ms 값 기록
4. 3회 반복 후 평균값 산출 (본 테스트는 1회 실행)

## 예상 결과

- 단순 쿼리: PostgreSQL 우세 (인덱스 활용)
- 복잡한 집계: HDFS+Spark 분산처리 효과로 경쟁력 있을 것으로 예상
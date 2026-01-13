# Phase 5: Parquet Compaction 결과

## 개요

Phase 4에서 발견된 Small File Problem (30,803개 Parquet 파일)을 해결하기 위해 파일 Compaction을 수행하고, 동일한 쿼리로 성능을 재측정했다.

## 테스트 일시
- 2026년 1월 13일

## Compaction 실행

### 실행 방법
```python
# Spark coalesce를 사용한 파일 병합
df = spark.read.parquet("hdfs://.../data/logs/raw")
df.coalesce(100).write.mode("overwrite").parquet("hdfs://.../data/logs/raw_compacted")
```

### Compaction 결과

| 항목 | Before | After | 변화 |
|------|--------|-------|------|
| 파일 수 | 30,803개 | 100개 | **99.7% 감소** |
| 총 용량 | 6.4 GB | 5.8 GB | 9.4% 감소 |
| 파일당 크기 | ~200 KB | ~58 MB | **290배 증가** |
| 레코드 수 | 121,619,878 | 121,619,878 | 동일 (무결성 확인) |

## 성능 비교 결과

### HDFS 쿼리 성능 개선 (Compaction 전후)

| 쿼리 | Before (30,803 파일) | After (100 파일) | 개선율 |
|------|---------------------|------------------|--------|
| COUNT(*) | 112,396 ms (112초) | 11,936 ms (12초) | **9.4x 빠름** |
| GROUP BY service | 245,145 ms (245초) | 12,063 ms (12초) | **20.3x 빠름** |
| WHERE + GROUP BY | 235,937 ms (236초) | 8,606 ms (8.6초) | **27.4x 빠름** |

### PostgreSQL vs HDFS 최종 비교

| 쿼리 | PostgreSQL | HDFS (Compacted) | 승자 | 배율 |
|------|-----------|------------------|------|------|
| COUNT(*) | 6,769 ms | 11,936 ms | PostgreSQL | 1.8x |
| GROUP BY service | 15,657 ms | 12,063 ms | **HDFS** | **1.3x** |
| WHERE level='ERROR' + GROUP BY | 20,500 ms | 8,606 ms | **HDFS** | **2.4x** |

## 상세 결과

### Query 1: COUNT(*) - 전체 로그 수 카운트

**PostgreSQL**
```json
{
  "source": "postgresql",
  "query_time_ms": 6769.31,
  "logs_count": 121670000,
  "events_count": 64250000
}
```

**HDFS (Compacted)**
```json
{
  "source": "hdfs",
  "logs_count": 121619878,
  "query_time_ms": 11936.04
}
```

### Query 2: GROUP BY service - 서비스별 집계

**PostgreSQL**: 15,657 ms
**HDFS (Compacted)**: 12,063 ms

### Query 3: WHERE + GROUP BY - 조건부 집계

**PostgreSQL**: 20,500 ms
**HDFS (Compacted)**: 8,606 ms

## 핵심 발견

### 1. Small File Problem의 심각성

파일 수가 성능에 미치는 영향:
- 30,803개 → 100개로 줄이자 **최대 27배 성능 향상**
- 파일 메타데이터 처리, Task 스케줄링 오버헤드가 핵심 병목

### 2. 쿼리 복잡도에 따른 성능 특성

| 쿼리 유형 | 유리한 시스템 | 이유 |
|-----------|--------------|------|
| 단순 COUNT | PostgreSQL | 인덱스/통계 활용 |
| 단일 GROUP BY | HDFS (근소) | 분산 집계 효과 |
| 조건 + GROUP BY | **HDFS (확실)** | 필터링 + 분산 집계 시너지 |

### 3. HDFS + Spark의 강점 조건

1. **적절한 파일 크기**: 50MB ~ 500MB
2. **복잡한 집계 쿼리**: GROUP BY, 다중 조건
3. **대용량 스캔**: Full Table Scan이 필요한 경우

## 결론

### Compaction의 중요성

- HDFS 성능의 **가장 큰 병목은 Small File Problem**
- 정기적인 Compaction이 필수 (Airflow 등으로 자동화 권장)
- 파일당 크기 50MB ~ 500MB 유지 권장

## 실제 로그
```azure
(base) jun@jun-Victus-by-HP-Gaming-Laptop-16-r0xxx:~$ time curl -s --max-time 600 "http://192.168.55.114:30801/api/query/hdfs/stats" | jq .
{
  "source": "hdfs",
  "logs_count": 121619878,
  "query_time_ms": 11936.04
}

real	0m11.944s
user	0m0.019s
sys	0m0.008s
(base) jun@jun-Victus-by-HP-Gaming-Laptop-16-r0xxx:~$ time curl -s --max-time 600 "http://192.168.55.114:30801/api/query/hdfs/logs/aggregate?group_by=service" | jq '.query_time_ms'
12063.4

real	0m14.050s
user	0m0.023s
sys	0m0.007s
(base) jun@jun-Victus-by-HP-Gaming-Laptop-16-r0xxx:~$ time curl -s --max-time 600 "http://192.168.55.114:30801/api/query/hdfs/logs/aggregate?group_by=service&level=ERROR" | jq '.query_time_ms'
8605.82

real	0m8.612s
user	0m0.022s
sys	0m0.007s
(base) jun@jun-Victus-by-HP-Gaming-Laptop-16-r0xxx:~$ `

```

### PostgreSQL vs HDFS 선택 기준

| 상황 | 권장 시스템 |
|------|------------|
| 단순 조회, 인덱스 활용 가능 | PostgreSQL |
| 실시간 트랜잭션 | PostgreSQL |
| 대용량 집계/분석 | HDFS + Spark |
| 조건부 복잡 집계 | HDFS + Spark |
| PB 규모 데이터 | HDFS + Spark |

## 다음 단계

Phase 6에서 k6를 활용한 부하 테스트 진행:
1. 동시 사용자 증가에 따른 성능 변화
2. 오류 발생률 측정
3. 시스템 안정성 검증
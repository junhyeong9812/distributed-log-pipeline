# Phase 5: Parquet Compaction 및 재벤치마크

## 개요

Phase 4에서 발견된 **Small File Problem** (30,803개 Parquet 파일)을 해결하기 위해 파일 Compaction을 수행하고, 동일한 쿼리로 성능을 재측정한다.

## 배경

### Phase 4에서 발견된 문제
```bash
$ kubectl exec -it deployment/namenode -n log-pipeline -- hdfs dfs -ls -R /data/logs/raw | grep ".parquet" | wc -l
30803
```

| 항목 | 권장 구조 | Phase 4 현재 |
|------|-----------|--------------|
| 파일 수 | 수백 개 | 30,803개 |
| 파일당 크기 | 100MB ~ 1GB | 수 KB ~ 수 MB |
| Spark Task 수 | 수백 개 | 30,000+ 개 |

### Small File Problem이 성능에 미치는 영향

1. **NameNode 메모리 부담**: 각 파일당 ~150 bytes 메타데이터
2. **파일 열기/닫기 오버헤드**: 30,803회 I/O 작업
3. **Spark Task 스케줄링**: Task 생성/분배/결과수집 오버헤드
4. **네트워크 트래픽**: 수만 개 Task 결과 전송

## Compaction 계획

### 목표

| 항목 | Before | After |
|------|--------|-------|
| 파일 수 | 30,803개 | ~100개 |
| 파일당 크기 | 수 KB~MB | ~500MB |
| 예상 Task 수 | 30,000+ | ~100 |

### Compaction 방법

#### 방법 1: Spark를 이용한 Compaction
```python
# compaction_job.py
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .appName("ParquetCompaction") \
    .config("spark.sql.shuffle.partitions", "100") \
    .getOrCreate()

# 기존 데이터 읽기
df = spark.read.parquet("hdfs://namenode:9000/data/logs/raw")

# 파티션 수 조정하여 다시 쓰기 (100개 파일로)
df.repartition(100) \
    .write \
    .mode("overwrite") \
    .partitionBy("year", "month", "day") \
    .parquet("hdfs://namenode:9000/data/logs/raw_compacted")
```

#### 방법 2: coalesce 사용 (셔플 최소화)
```python
# 셔플 없이 파티션 합치기 (더 빠름)
df.coalesce(100) \
    .write \
    .mode("overwrite") \
    .parquet("hdfs://namenode:9000/data/logs/raw_compacted")
```

### 실행 명령어
```bash
# 1. Compaction 스크립트 생성
cat > /tmp/compaction.py << 'EOF'
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .appName("ParquetCompaction") \
    .master("spark://spark-master-svc:7077") \
    .config("spark.hadoop.fs.defaultFS", "hdfs://namenode.log-pipeline.svc.cluster.local:9000") \
    .config("spark.executor.memory", "2g") \
    .config("spark.driver.memory", "2g") \
    .getOrCreate()

print("Reading original data...")
df = spark.read.parquet("hdfs://namenode.log-pipeline.svc.cluster.local:9000/data/logs/raw")

original_count = df.count()
print(f"Original count: {original_count}")

print("Compacting to 100 partitions...")
df.coalesce(100) \
    .write \
    .mode("overwrite") \
    .parquet("hdfs://namenode.log-pipeline.svc.cluster.local:9000/data/logs/raw_compacted")

print("Verifying...")
df_new = spark.read.parquet("hdfs://namenode.log-pipeline.svc.cluster.local:9000/data/logs/raw_compacted")
new_count = df_new.count()
print(f"Compacted count: {new_count}")

print("Compaction complete!")
spark.stop()
EOF

# 2. ConfigMap에 추가
kubectl create configmap compaction-job \
  --from-file=compaction.py=/tmp/compaction.py \
  -n log-pipeline

# 3. Spark Submit으로 실행
kubectl exec -it deployment/spark-master -n log-pipeline -- \
  /spark/bin/spark-submit \
  --master spark://spark-master-svc:7077 \
  --executor-memory 2g \
  --driver-memory 2g \
  /tmp/compaction.py
```

## 테스트 쿼리 (Phase 4와 동일)

### Query 1: COUNT(*)
```sql
SELECT COUNT(*) FROM parquet.`/data/logs/raw_compacted`
```

### Query 2: GROUP BY service
```sql
SELECT service, COUNT(*) FROM parquet.`/data/logs/raw_compacted` GROUP BY service
```

### Query 3: WHERE + GROUP BY
```sql
SELECT service, COUNT(*) FROM parquet.`/data/logs/raw_compacted` 
WHERE level = 'ERROR' GROUP BY service
```

### Query 4: 다중 GROUP BY
```sql
SELECT level, service, COUNT(*) FROM parquet.`/data/logs/raw_compacted` 
GROUP BY level, service
```

## 예상 결과

### Compaction 전후 비교 예상

| 쿼리 | Phase 4 (30,803 파일) | Phase 5 (100 파일) | 개선율 |
|------|----------------------|-------------------|--------|
| COUNT(*) | 112초 | ~20초 | 5x |
| GROUP BY | 245초 | ~50초 | 5x |
| WHERE + GROUP BY | 236초 | ~45초 | 5x |

### PostgreSQL vs HDFS (Compaction 후) 예상

| 쿼리 | PostgreSQL | HDFS (Compacted) | 예상 비율 |
|------|-----------|------------------|-----------|
| COUNT(*) | 6.7초 | ~20초 | PG 3x |
| GROUP BY | 15.6초 | ~50초 | PG 3x |
| WHERE + GROUP BY | 20.5초 | ~45초 | PG 2x |

## 성공 기준

1. Parquet 파일 수: 30,803개 → 100개 이하
2. HDFS 쿼리 성능: 5배 이상 개선
3. 데이터 무결성: Compaction 전후 레코드 수 동일

## 진행 순서

1. [ ] 현재 HDFS 데이터 백업 확인
2. [ ] Compaction 스크립트 실행
3. [ ] 파일 수 및 데이터 건수 검증
4. [ ] 4개 쿼리 재실행 및 성능 측정
5. [ ] 결과 문서화 (BENCHMARK_PHASE5_RESULT.md)

## 참고사항

### Compaction 시 주의사항

1. **디스크 공간**: 일시적으로 2배 공간 필요 (원본 + 신규)
2. **실행 시간**: 1.2억건 기준 10~30분 소요 예상
3. **파티셔닝 전략**: 시간 기반 파티션 유지 여부 결정 필요

### 향후 개선 방향

1. **자동 Compaction**: Airflow DAG으로 주기적 실행
2. **적정 파일 크기**: 128MB ~ 1GB 권장
3. **Streaming 설정 조정**: `maxRecordsPerFile` 옵션 활용
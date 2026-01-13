# HDFS Parquet 파일 Compaction 가이드

## 개요

HDFS에서 Spark Streaming으로 데이터를 적재하면 배치마다 작은 파일이 생성되어 "Small File Problem"이 발생한다. 이 문서는 파편화된 파일을 합치는 Compaction 과정을 설명한다.

## Small File Problem이란?

### 문제 상황

Spark Streaming이 60초마다 배치를 실행하면:
- 8시간 적재 = 480개 배치
- 각 배치당 ~64개 파일 생성
- 총 30,803개의 작은 파일 발생

### 성능 영향

| 항목 | 영향 |
|------|------|
| NameNode 메모리 | 파일당 ~150 bytes 메타데이터 부담 |
| Task 오버헤드 | 파일당 1개 Task → 30,000+ Task 생성 |
| I/O 오버헤드 | 파일 열기/닫기 30,000회 반복 |
| 네트워크 | Task 스케줄링/결과 수집 트래픽 증가 |

## Compaction 원리

### 데이터 흐름
```
┌─────────────────────────────────────────────────────────────────┐
│                      BEFORE (30,803 파일)                        │
├─────────────────────────────────────────────────────────────────┤
│  Worker1 (DataNode)          │  Worker2 (DataNode)              │
│  ┌──────────────────────┐    │  ┌──────────────────────┐       │
│  │ part-00001.parquet   │    │  │ part-00002.parquet   │       │
│  │ (200KB)              │    │  │ (200KB)              │       │
│  ├──────────────────────┤    │  ├──────────────────────┤       │
│  │ part-00003.parquet   │    │  │ part-00004.parquet   │       │
│  │ (200KB)              │    │  │ (200KB)              │       │
│  ├──────────────────────┤    │  ├──────────────────────┤       │
│  │ ...                  │    │  │ ...                  │       │
│  │ (약 15,000개 파일)    │    │  │ (약 15,803개 파일)    │       │
│  └──────────────────────┘    │  └──────────────────────┘       │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │   Spark Compaction    │
                    │   (coalesce(100))     │
                    └───────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      AFTER (100 파일)                            │
├─────────────────────────────────────────────────────────────────┤
│  Worker1 (DataNode)          │  Worker2 (DataNode)              │
│  ┌──────────────────────┐    │  ┌──────────────────────┐       │
│  │ part-00000.parquet   │    │  │ part-00000.parquet   │       │
│  │ (58MB) [replica]     │    │  │ (58MB) [primary]     │       │
│  ├──────────────────────┤    │  ├──────────────────────┤       │
│  │ part-00001.parquet   │    │  │ part-00001.parquet   │       │
│  │ (55MB) [primary]     │    │  │ (55MB) [replica]     │       │
│  ├──────────────────────┤    │  ├──────────────────────┤       │
│  │ ...                  │    │  │ ...                  │       │
│  │ (50개 파일)           │    │  │ (50개 파일)           │       │
│  └──────────────────────┘    │  └──────────────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

### Compaction 단계별 과정
```
Step 1: 파일 스캔
┌────────────────────────────────────────┐
│ NameNode가 30,803개 파일 위치 정보 제공  │
│ → Spark Driver가 Task 계획 수립         │
└────────────────────────────────────────┘
                    │
                    ▼
Step 2: 분산 읽기
┌────────────────────────────────────────┐
│ Spark Worker1: 파일 15,000개 읽기       │
│ Spark Worker2: 파일 15,803개 읽기       │
│ → 각 Worker 메모리에 데이터 로드         │
└────────────────────────────────────────┘
                    │
                    ▼
Step 3: Coalesce (파티션 병합)
┌────────────────────────────────────────┐
│ 30,803개 파티션 → 100개 파티션으로 병합  │
│ → 셔플 없이 로컬에서 파티션 합치기       │
│ → 메모리 효율적 처리                    │
└────────────────────────────────────────┘
                    │
                    ▼
Step 4: 분산 쓰기
┌────────────────────────────────────────┐
│ 100개의 새 Parquet 파일 생성            │
│ → HDFS replication=2로 양쪽 노드에 복제 │
│ → 각 파일 약 58MB 크기                  │
└────────────────────────────────────────┘
                    │
                    ▼
Step 5: 검증
┌────────────────────────────────────────┐
│ 원본 레코드 수: 121,619,878             │
│ 병합 후 레코드 수: 121,619,878          │
│ → Data Integrity 확인                  │
└────────────────────────────────────────┘
```

## Compaction 방법

### 방법 1: coalesce (권장)

셔플 없이 파티션 병합. 빠르고 리소스 효율적.
```python
df = spark.read.parquet("hdfs://.../raw")
df.coalesce(100).write.mode("overwrite").parquet("hdfs://.../raw_compacted")
```

### 방법 2: repartition

셔플을 통해 균등 분배. 데이터 편향 해결에 유용.
```python
df = spark.read.parquet("hdfs://.../raw")
df.repartition(100).write.mode("overwrite").parquet("hdfs://.../raw_compacted")
```

### 차이점

| 항목 | coalesce | repartition |
|------|----------|-------------|
| 셔플 | 없음 | 있음 |
| 속도 | 빠름 | 느림 |
| 파일 크기 | 불균등할 수 있음 | 균등 |
| 사용 상황 | 단순 병합 | 데이터 재분배 |

## 실행 스크립트
```python
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .appName("ParquetCompaction") \
    .config("spark.hadoop.fs.defaultFS", "hdfs://namenode:9000") \
    .getOrCreate()

# 원본 읽기
df = spark.read.parquet("/data/logs/raw")
original_count = df.count()
print(f"Original: {original_count} records")

# Compaction (100개 파일로)
df.coalesce(100).write.mode("overwrite").parquet("/data/logs/raw_compacted")

# 검증
df_new = spark.read.parquet("/data/logs/raw_compacted")
new_count = df_new.count()
print(f"Compacted: {new_count} records")
print(f"Integrity: {original_count == new_count}")

spark.stop()
```

## 결과 비교

### 파일 구조

| 항목 | Before | After |
|------|--------|-------|
| 파일 수 | 30,803개 | 100개 |
| 총 용량 | 6.4 GB | 5.8 GB |
| 파일당 크기 | ~200 KB | ~58 MB |

### 쿼리 성능

| 쿼리 | Before | After | 개선율 |
|------|--------|-------|--------|
| COUNT(*) | 112초 | 12초 | 9.4x |
| GROUP BY | 245초 | 12초 | 20x |
| WHERE + GROUP BY | 236초 | 8.6초 | 27x |

## 권장 사항

### 적정 파일 크기

- **최소**: 50 MB
- **권장**: 100 MB ~ 500 MB
- **최대**: 1 GB

### Compaction 주기

| 데이터 적재량 | 권장 주기 |
|--------------|----------|
| < 100만건/일 | 주 1회 |
| 100만~1000만건/일 | 일 1회 |
| > 1000만건/일 | 일 2회 이상 |

### 자동화 (Airflow 예시)
```python
from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

dag = DAG(
    'hdfs_compaction',
    schedule_interval='0 2 * * *',  # 매일 새벽 2시
    start_date=datetime(2026, 1, 1),
)

compaction_task = BashOperator(
    task_id='run_compaction',
    bash_command='spark-submit /opt/spark-jobs/compaction.py',
    dag=dag,
)
```

## 주의사항

1. **디스크 공간**: Compaction 시 일시적으로 2배 공간 필요
2. **원본 백업**: 검증 후 원본 삭제 권장
3. **운영 시간**: 트래픽 적은 시간에 실행
4. **모니터링**: Compaction 전후 레코드 수 검증 필수
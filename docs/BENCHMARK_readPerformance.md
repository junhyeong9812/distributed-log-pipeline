# PostgreSQL vs Spark/HDFS 성능 비교 실험

> 단일 DB(PostgreSQL)와 분산 처리 시스템(Spark/HDFS)의 성능을 비교하는 벤치마크 실험입니다.

---

## 📋 실험 목적

1. **저장 성능 비교**: PostgreSQL vs HDFS 데이터 저장 속도
2. **조회 성능 비교**: PostgreSQL vs Spark/HDFS 데이터 조회 속도
3. **확장성 검증**: 데이터량 증가에 따른 성능 변화
4. **트레이드오프 분석**: 언제 어떤 시스템을 선택해야 하는가?

---

## 🎯 가설

### 메인 가설

> **소량 데이터에서는 PostgreSQL이 빠르지만, 대용량 데이터에서는 Spark/HDFS가 우세할 것이다.**

### 세부 가설

| 데이터 규모 | PostgreSQL | Spark/HDFS | 예상 |
|------------|------------|------------|------|
| 소량 (1만건 이하) | ✅ 빠름 | ❌ 오버헤드 | PostgreSQL 압승 |
| 중량 (10만~100만건) | ⚠️ 느려짐 | ⚠️ 비슷 | 교차점 |
| 대량 (100만건 이상) | ❌ 한계 | ✅ 병렬 처리 | Spark/HDFS 우세 |

---

## 🖥️ 실험 환경

### 하드웨어 구성

| 노드 | IP | CPU | RAM | 역할 |
|------|-----|-----|-----|------|
| Master | 192.168.55.114 | 8코어 | 16GB | K8s Master, PostgreSQL, Kafka, HDFS NameNode, Spark Master |
| Worker 1 | 192.168.55.158 | 6코어 | 16GB | K8s Worker, HDFS DataNode, Spark Worker, k6 부하 테스트 |
| Worker 2 | 192.168.55.9 | 8코어 | 16GB | K8s Worker, HDFS DataNode, Spark Worker |

### 소프트웨어 버전

| 컴포넌트 | 버전 |
|----------|------|
| Kubernetes | k3s v1.34.3 |
| PostgreSQL | 15 |
| Kafka | 3.7.0 |
| Spark | 3.3.0 |
| PySpark (Query API) | 3.5.0 |
| Hadoop | 3.2.1 |
| k6 | latest |

---

## 📊 1차 테스트 결과

### 테스트 환경
- 테스트 일시: 2026-01-12
- PostgreSQL 데이터: 18,600 로그 / 9,200 이벤트
- HDFS 데이터: 29,600 로그

### 단건 조회 성능 비교

| 쿼리 유형 | PostgreSQL | HDFS/Spark | 배수 차이 |
|-----------|------------|------------|----------|
| 통계 조회 (COUNT) | 13.67ms | 1,851.70ms | **135x** |
| 조건 조회 (level=ERROR, LIMIT 100) | 16.68ms | 5,899.03ms | **354x** |
| 집계 조회 (GROUP BY level) | 8.84ms | 2,313.51ms | **262x** |

### PostgreSQL 상세 결과

```json
{
  "source": "postgresql",
  "query_time_ms": 13.67,
  "logs_count": 18300,
  "events_count": 9200
}
```

| 쿼리 | 응답 시간 | 결과 |
|------|----------|------|
| 전체 조회 (LIMIT 5) | 7.77ms | 5건 |
| 조건 조회 (level=ERROR) | 11.01ms | 329건 중 5건 |
| 집계 (GROUP BY level) | 8.84ms | 4개 그룹 |
| 통계 (COUNT) | 13.67ms | 18,300 로그 |

### HDFS/Spark 상세 결과

```json
{
  "source": "hdfs",
  "logs_count": 29600,
  "query_time_ms": 1851.7
}
```

| 쿼리 | 응답 시간 | 결과 |
|------|----------|------|
| 전체 조회 (LIMIT 5) | 18,362ms | 5건 |
| 조건 조회 (level=ERROR) | 5,899ms | 1,426건 중 100건 |
| 집계 (GROUP BY level) | 2,313ms | 4개 그룹 |
| 통계 (COUNT) | 1,851ms | 29,600 로그 |

### 집계 결과 비교

| Level | PostgreSQL | HDFS |
|-------|------------|------|
| WARN | 5,948 | 9,504 |
| INFO | 5,920 | 9,417 |
| DEBUG | 5,843 | 9,242 |
| ERROR | 889 | 1,437 |

### 성능 비교 요약

```
┌─────────────────────────────────────────────────────────────────────┐
│              PostgreSQL vs HDFS/Spark 성능 비교                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  응답 시간 (ms)                                                      │
│                                                                      │
│  PostgreSQL  ████ 16.68ms                                           │
│  HDFS/Spark  ████████████████████████████████████████ 5,899ms       │
│                                                                      │
│  PostgreSQL이 약 350배 빠름 (소량 데이터 기준)                        │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📈 분석

### PostgreSQL 강점 (현재 데이터 규모)

1. **즉각적인 응답**: 평균 10-15ms
2. **인덱스 활용**: 조건 검색 최적화
3. **낮은 오버헤드**: 단일 노드, 직접 쿼리
4. **트랜잭션 지원**: ACID 보장

### HDFS/Spark 약점 (현재 데이터 규모)

1. **높은 초기화 오버헤드**: SparkSession 생성 시간
2. **분산 처리 비용**: 작은 데이터에서 비효율
3. **파일 스캔**: 전체 Parquet 파일 읽기 필요
4. **네트워크 지연**: 분산 노드 간 통신

### HDFS/Spark 예상 강점 (대용량 데이터)

1. **병렬 처리**: 여러 노드에서 동시 처리
2. **수평 확장**: 노드 추가로 성능 향상
3. **대용량 집계**: 분산 MapReduce
4. **비용 효율**: 저렴한 스토리지 확장

---

## 🔧 트러블슈팅

### 문제: PySpark + Java 21 호환성

**증상:**
```
java.lang.NoSuchMethodException: java.nio.DirectByteBuffer.<init>(long,int)
```

**원인:**
- PySpark 3.3.0은 Java 21 미지원
- Query API 컨테이너에 Java 21 설치됨

**해결:**
- PySpark 3.5.0으로 업그레이드 (Java 21 지원)

```txt
# requirements.txt
pyspark==3.5.0
```

---

## 📋 다음 테스트 계획

### Phase 2: 대용량 데이터 테스트

| 단계 | 데이터량 | 목표 |
|------|---------|------|
| 2-1 | 10만건 | 성능 변화 측정 |
| 2-2 | 50만건 | 교차점 확인 |
| 2-3 | 100만건 | Spark 병렬 처리 효과 |

### Phase 3: k6 부하 테스트

| 시나리오 | 동시 사용자 | 목표 |
|---------|-----------|------|
| 단순 조회 | 10 → 100 | 응답 시간 변화 |
| 집계 쿼리 | 10 → 50 | 서버 부하 측정 |
| 혼합 워크로드 | 10 → 100 | 실제 사용 시뮬레이션 |

---

## 🎯 1차 결론

### 현재 데이터 규모 (약 2만건)에서

| 항목 | 권장 시스템 | 이유 |
|------|-------------|------|
| 실시간 조회 | **PostgreSQL** | 350배 빠름 |
| 조건 검색 | **PostgreSQL** | 인덱스 활용 |
| 집계 쿼리 | **PostgreSQL** | 260배 빠름 |
| 데이터 저장 | **PostgreSQL + HDFS** | 이중 저장 |

### 가설 검증 (1차)

> ✅ **소량 데이터에서 PostgreSQL이 압도적으로 빠름** - 가설 일치

### 다음 검증 필요

> ⬜ **대용량 데이터에서 Spark/HDFS가 우세한가?** - Phase 2에서 검증

---

## 📚 API 엔드포인트

### PostgreSQL 조회

```bash
# 로그 조회
GET /api/query/postgres/logs?level=ERROR&limit=100

# 집계 조회
GET /api/query/postgres/logs/aggregate?group_by=level

# 통계
GET /api/query/postgres/stats
```

### HDFS/Spark 조회

```bash
# 로그 조회
GET /api/query/hdfs/logs?level=ERROR&limit=100

# 집계 조회
GET /api/query/hdfs/logs/aggregate?group_by=level

# 통계
GET /api/query/hdfs/stats
```

### 비교

```bash
# PostgreSQL vs HDFS 성능 비교
GET /api/query/compare?level=ERROR&limit=100
```
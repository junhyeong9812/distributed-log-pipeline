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

### 가설 근거

```
┌─────────────────────────────────────────────────────────────────────┐
│                     시스템 특성 비교                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  PostgreSQL (단일 DB)                                               │
│  ├── 장점                                                           │
│  │   ├── 단일 트랜잭션으로 빠른 저장                                │
│  │   ├── 인덱스를 통한 빠른 조회                                    │
│  │   ├── SQL 최적화                                                 │
│  │   └── 낮은 오버헤드                                              │
│  └── 단점                                                           │
│      ├── 단일 노드 메모리/디스크 한계                               │
│      ├── 수직 확장 비용 증가                                        │
│      └── 대용량 집계 시 느려짐                                      │
│                                                                      │
│  Spark/HDFS (분산 처리)                                             │
│  ├── 장점                                                           │
│  │   ├── 수평 확장 용이 (노드 추가)                                │
│  │   ├── 대용량 병렬 처리                                          │
│  │   ├── 장애 내성 (복제)                                          │
│  │   └── 대용량 집계에 강함                                        │
│  └── 단점                                                           │
│      ├── 분산 저장 오버헤드                                        │
│      ├── 작업 스케줄링 지연                                        │
│      ├── 소량 데이터에서 비효율                                    │
│      └── 설정 복잡성                                               │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

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
| Hadoop | 3.2.1 |
| k6 | latest |

### 네트워크

- 내부 네트워크: 192.168.55.0/24
- K8s Pod Network: 10.42.0.0/16
- K8s Service Network: 10.43.0.0/16

---

## 🏗️ 실험 아키텍처

```
┌─────────────────────────────────────────────────────────────────────┐
│                       실험 아키텍처                                  │
└─────────────────────────────────────────────────────────────────────┘

                         ┌─────────────────┐
                         │   Generator     │
                         │  (데이터 생성)   │
                         └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │    Backend      │
                         │  (데이터 수신)   │
                         └────────┬────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
                    ▼                           ▼
           ┌─────────────────┐         ┌─────────────────┐
           │   PostgreSQL    │         │     Kafka       │
           │   (즉시 저장)    │         │   (메시지 큐)   │
           └────────┬────────┘         └────────┬────────┘
                    │                           │
                    │                           ▼
                    │                  ┌─────────────────┐
                    │                  │ Spark Streaming │
                    │                  │   (배치 처리)   │
                    │                  └────────┬────────┘
                    │                           │
                    │                           ▼
                    │                  ┌─────────────────┐
                    │                  │     HDFS       │
                    │                  │  (분산 저장)    │
                    │                  └────────┬────────┘
                    │                           │
                    ▼                           ▼
           ┌─────────────────┐         ┌─────────────────┐
           │  Query Server   │         │  Query Server   │
           │ (PostgreSQL 조회)│         │ (Spark 조회)    │
           └────────┬────────┘         └────────┬────────┘
                    │                           │
                    └─────────────┬─────────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │       k6        │
                         │   (부하 테스트)  │
                         └─────────────────┘
```

---

## 📊 테스트 시나리오

### Phase 1: 소량 데이터 테스트 (1만건)

```
목표: PostgreSQL의 소량 데이터 처리 우위 확인

Generator 설정:
- batch_size: 100
- 총 데이터: 10,000건

테스트 항목:
1. 저장 시간 측정
2. 단순 조회 (SELECT * LIMIT 100)
3. 조건 조회 (WHERE level = 'ERROR')
4. 집계 조회 (COUNT, GROUP BY)
```

### Phase 2: 중량 데이터 테스트 (10만건)

```
목표: 성능 교차점 확인

Generator 설정:
- batch_size: 1000
- 총 데이터: 100,000건

테스트 항목:
1. 저장 시간 측정
2. 단순 조회
3. 조건 조회
4. 집계 조회 (시간대별, 서비스별)
```

### Phase 3: 대량 데이터 테스트 (100만건)

```
목표: Spark/HDFS의 대용량 처리 우위 확인

Generator 설정:
- batch_size: 5000
- 총 데이터: 1,000,000건

테스트 항목:
1. 저장 시간 측정
2. 전체 스캔 조회
3. 복잡한 집계 (다중 GROUP BY)
4. 시계열 분석
```

### k6 부하 테스트 설정

```javascript
// 동시 사용자 수
export const options = {
  scenarios: {
    // 단계적 부하 증가
    ramping: {
      executor: 'ramping-vus',
      startVUs: 1,
      stages: [
        { duration: '30s', target: 10 },
        { duration: '1m', target: 50 },
        { duration: '30s', target: 100 },
        { duration: '1m', target: 100 },
        { duration: '30s', target: 0 },
      ],
    },
  },
};
```

---

## 📈 측정 지표

### 저장 성능

| 지표 | 설명 | 단위 |
|------|------|------|
| Throughput | 초당 저장 건수 | records/sec |
| Latency | 저장 응답 시간 | ms |
| Total Time | 전체 저장 시간 | sec |

### 조회 성능

| 지표 | 설명 | 단위 |
|------|------|------|
| Response Time | 쿼리 응답 시간 | ms |
| P50 | 50번째 백분위수 | ms |
| P95 | 95번째 백분위수 | ms |
| P99 | 99번째 백분위수 | ms |
| Throughput | 초당 쿼리 처리량 | req/sec |
| Error Rate | 오류율 | % |

### 리소스 사용량

| 지표 | 설명 |
|------|------|
| CPU Usage | CPU 사용률 |
| Memory Usage | 메모리 사용량 |
| Disk I/O | 디스크 읽기/쓰기 |
| Network I/O | 네트워크 트래픽 |

---

## 🔧 구현 계획

### 1단계: PostgreSQL 배포

```yaml
# kubernetes/postgres/postgres.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
  namespace: log-pipeline
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    spec:
      containers:
        - name: postgres
          image: postgres:15
          env:
            - name: POSTGRES_DB
              value: "logs"
            - name: POSTGRES_USER
              value: "admin"
            - name: POSTGRES_PASSWORD
              value: "admin123"
```

### 2단계: Backend 수정

```java
// PostgreSQL + Kafka 이중 저장
@Service
public class LogService {
    
    @Autowired
    private LogRepository logRepository;  // PostgreSQL
    
    @Autowired
    private KafkaTemplate kafkaTemplate;  // Kafka
    
    public void saveLog(LogEvent log) {
        // 1. PostgreSQL 저장
        logRepository.save(log);
        
        // 2. Kafka 발행
        kafkaTemplate.send("logs.raw", log);
    }
}
```

### 3단계: 조회 서버 개발

```python
# PostgreSQL 조회 API
@app.get("/api/logs/postgres")
async def query_postgres(
    level: str = None,
    service: str = None,
    start_time: datetime = None,
    end_time: datetime = None
):
    # PostgreSQL 쿼리 실행
    pass

# Spark/HDFS 조회 API
@app.get("/api/logs/hdfs")
async def query_hdfs(
    level: str = None,
    service: str = None,
    start_time: datetime = None,
    end_time: datetime = None
):
    # Spark SQL 쿼리 실행
    pass
```

### 4단계: k6 테스트 스크립트

```javascript
// k6/benchmark.js
import http from 'k6/http';
import { check, sleep } from 'k6';

export default function () {
    // PostgreSQL 조회 테스트
    const pgRes = http.get('http://query-server:8000/api/logs/postgres?level=ERROR');
    check(pgRes, { 'pg status 200': (r) => r.status === 200 });
    
    // HDFS 조회 테스트
    const hdfsRes = http.get('http://query-server:8000/api/logs/hdfs?level=ERROR');
    check(hdfsRes, { 'hdfs status 200': (r) => r.status === 200 });
    
    sleep(1);
}
```

---

## 📋 예상 결과

### 저장 성능 예상

| 데이터량 | PostgreSQL | Spark/HDFS | 비고 |
|----------|------------|------------|------|
| 1만건 | ~2초 | ~10초 | 분산 오버헤드 |
| 10만건 | ~20초 | ~30초 | 격차 감소 |
| 100만건 | ~200초+ | ~100초 | 병렬 처리 효과 |

### 조회 성능 예상

| 쿼리 유형 | PostgreSQL (소량) | PostgreSQL (대량) | Spark (대량) |
|-----------|------------------|------------------|--------------|
| 단순 조회 | ~10ms | ~100ms | ~500ms |
| 조건 조회 | ~20ms | ~500ms | ~300ms |
| 집계 조회 | ~50ms | ~2000ms | ~400ms |

### 교차점 예상

```
┌─────────────────────────────────────────────────────────────────────┐
│                     성능 교차점 예상 그래프                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  응답시간                                                            │
│  (ms)                                                                │
│    │                                                                 │
│    │                              PostgreSQL                         │
│    │                                  ╱                              │
│    │                                ╱                                │
│    │                              ╱                                  │
│    │                            ╱                                    │
│    │                          ╱    ← 교차점 (약 50만건)              │
│    │                        ╱                                        │
│    │      ─────────────────────────── Spark/HDFS                    │
│    │   ╱                                                             │
│    │ ╱                                                               │
│    └─────────────────────────────────────────────────── 데이터량    │
│        1만    10만    50만    100만   500만   1000만                 │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📝 결론 프레임워크

### 선택 가이드라인 (예상)

| 상황 | 권장 시스템 | 이유 |
|------|-------------|------|
| 실시간 트랜잭션 | PostgreSQL | 낮은 지연시간 |
| 소량 데이터 분석 | PostgreSQL | 오버헤드 없음 |
| 대용량 배치 처리 | Spark/HDFS | 병렬 처리 |
| 장기 데이터 보관 | HDFS | 비용 효율적 |
| 복잡한 집계/분석 | Spark | 분산 처리 |
| OLTP 워크로드 | PostgreSQL | 트랜잭션 지원 |
| OLAP 워크로드 | Spark/HDFS | 분석 최적화 |

### 하이브리드 아키텍처 제안

```
┌─────────────────────────────────────────────────────────────────────┐
│                     하이브리드 아키텍처                              │
└─────────────────────────────────────────────────────────────────────┘

  실시간 데이터                              히스토리 데이터
       │                                          │
       ▼                                          ▼
  ┌─────────┐                               ┌─────────┐
  │PostgreSQL│  ───── ETL (주기적) ─────▶  │  HDFS   │
  │ (Hot)   │                               │ (Cold)  │
  └─────────┘                               └─────────┘
       │                                          │
       ▼                                          ▼
  실시간 조회                               배치 분석
  (최근 7일)                                (전체 기간)
```

---

## 📅 실험 진행 일정

| 단계 | 작업 | 예상 소요 |
|------|------|----------|
| 1 | PostgreSQL 배포 | 30분 |
| 2 | Backend 수정 (이중 저장) | 1시간 |
| 3 | 조회 서버 개발 | 2시간 |
| 4 | Generator 데이터량 조절 | 30분 |
| 5 | k6 스크립트 작성 | 1시간 |
| 6 | Phase 1 테스트 (1만건) | 1시간 |
| 7 | Phase 2 테스트 (10만건) | 2시간 |
| 8 | Phase 3 테스트 (100만건) | 3시간 |
| 9 | 결과 분석 및 문서화 | 2시간 |

---

## 📚 참고 자료

- [PostgreSQL Performance Tuning](https://www.postgresql.org/docs/current/performance-tips.html)
- [Spark Performance Tuning](https://spark.apache.org/docs/latest/tuning.html)
- [k6 Documentation](https://k6.io/docs/)
- [HDFS Architecture](https://hadoop.apache.org/docs/stable/hadoop-project-dist/hadoop-hdfs/HdfsDesign.html)
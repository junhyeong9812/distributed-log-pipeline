# Write Performance 벤치마크 결과

> 자원 한정 환경에서 PostgreSQL(단일 DB) vs HDFS/Spark(분산 처리)의 쓰기 성능 비교

---

## 📋 테스트 개요

### 테스트 일시
- 2026년 1월 12일

### 테스트 환경

| 노드 | IP | 역할 | 리소스 제한 |
|------|-----|------|------------|
| Master | 192.168.55.114 | PostgreSQL, Kafka, NameNode, Spark Master | - |
| Worker 1 | 192.168.55.158 | DataNode, Spark Worker | 2 CPU, 2GB RAM |
| Worker 2 | 192.168.55.9 | DataNode, Spark Worker | 2 CPU, 2GB RAM |

### 데이터 흐름

```
Generator → Backend (Spring Boot) → PostgreSQL (직접 저장)
                                 → Kafka → Spark Streaming → HDFS
```

---

## 📊 테스트 결과

### Phase 1: 기본 부하 (9,000건/분)

| 설정 | 값 |
|------|-----|
| batch_size | 100 |
| log_interval | 1초 |
| event_interval | 2초 |
| 목표 처리량 | 9,000건/분 |

| 지표 | PostgreSQL | HDFS |
|------|------------|------|
| 저장량 | 10,500건 | 10,400건 |
| 쿼리 시간 | 6.88ms | 1,021ms |
| 에러 | 0 | 0 |
| Pod Restart | 0 | 0 |

**결과: ✅ 둘 다 안정적, 100% 달성**

---

### Phase 2: 중간 부하 (90,000건/분)

| 설정 | 값 |
|------|-----|
| batch_size | 1,000 |
| log_interval | 1초 |
| event_interval | 2초 |
| 목표 처리량 | 90,000건/분 |

| 지표 | PostgreSQL | HDFS |
|------|------------|------|
| 저장량 | 125,600건 | 123,600건 |
| 쿼리 시간 | 22.98ms | 1,810ms |
| 에러 | 0 | 0 |
| Pod Restart | 0 | 0 |

**결과: ✅ 둘 다 안정적, ~100% 달성**

---

### Phase 3: 고부하 (900,000건/분)

| 설정 | 값 |
|------|-----|
| batch_size | 5,000 |
| log_interval | 0.5초 |
| event_interval | 1초 |
| 목표 처리량 | 900,000건/분 |

| 지표 | PostgreSQL | HDFS |
|------|------------|------|
| 저장량 (5분) | 693,600건 | 693,600건 |
| 실제 처리량 | ~200,000건/분 | ~200,000건/분 |
| 쿼리 시간 | 67.53ms | 2,549ms |
| 에러 | 0 | 0 |
| Pod Restart | 0 | 0 |

**결과: ⚠️ 목표 대비 22% 달성, 병목 발생**

---

## 🔍 병목 분석

### 병목 지점: Backend (Spring Boot)

```
Generator 로그:
WARNING: Execution of job "Log Generator Job" skipped: maximum number of running instances reached (1)
```

### 원인 분석

```
┌─────────────────────────────────────────────────────────────────────┐
│                    병목 원인                                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. JPA 단건 INSERT                                                 │
│     - 5,000건 배치 = 5,000번 INSERT 쿼리                            │
│     - 배치 처리 미적용                                              │
│                                                                      │
│  2. 동기 처리                                                       │
│     - PostgreSQL 저장 완료 대기                                     │
│     - Kafka 전송 완료 대기                                          │
│                                                                      │
│  3. Tomcat 쓰레드 모델                                              │
│     - 요청당 쓰레드 블로킹                                          │
│     - I/O 대기 시간 낭비                                            │
│                                                                      │
│  결과: Generator가 다음 배치 전송 못 함 (스킵)                      │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 리소스 사용량 (Phase 3)

| 리소스 | 사용량 | 상태 |
|--------|--------|------|
| Master CPU | 17.96% | ✅ 여유 |
| Master Memory | 36.96% | ✅ 여유 |
| PostgreSQL | 안정 | ✅ 여유 |
| HDFS | 안정 | ✅ 여유 |

**핵심 발견: 저장소는 여유, Backend가 병목**

---

## 📈 성능 비교 요약

### 처리량 비교

| Phase | 목표 | 실제 | 달성률 | PostgreSQL | HDFS |
|-------|------|------|--------|------------|------|
| 1 | 9K/분 | 9K/분 | 100% | ✅ | ✅ |
| 2 | 90K/분 | 90K/분 | 100% | ✅ | ✅ |
| 3 | 900K/분 | 200K/분 | 22% | ⚠️ | ⚠️ |

### 쿼리 시간 변화

| Phase | PostgreSQL | HDFS | 비율 |
|-------|------------|------|------|
| 1 | 6.88ms | 1,021ms | 148x |
| 2 | 22.98ms | 1,810ms | 79x |
| 3 | 67.53ms | 2,549ms | 38x |

**관찰: 부하 증가에 따라 PostgreSQL 쿼리 시간 증가, 격차 감소**

---

## 🎯 결론

### 1. 가설 검증

| 가설 | 결과 |
|------|------|
| 소량 데이터에서 PostgreSQL이 빠름 | ✅ 검증됨 (조회 350배 빠름) |
| 대용량에서 HDFS가 안정적 | ⚠️ 부분 검증 (Backend 병목으로 미확인) |
| 자원 한정 시 분산 처리 이점 | ⚠️ 미확인 (저장소 한계 도달 전 Backend 병목) |

### 2. 핵심 발견

```
┌─────────────────────────────────────────────────────────────────────┐
│                    핵심 발견                                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. 저장소 성능보다 API 서버 성능이 먼저 한계                        │
│     - PostgreSQL, HDFS 모두 여유                                    │
│     - Spring Boot + JPA가 병목                                      │
│                                                                      │
│  2. 동기 처리의 한계                                                │
│     - 초당 ~3,300건이 Spring Boot 한계                              │
│     - 비동기/배치 처리 필수                                         │
│                                                                      │
│  3. 실제 대용량 시스템은 다른 아키텍처 필요                          │
│     - Backend 없이 직접 Kafka 전송                                  │
│     - 또는 Go/Rust 기반 고성능 API                                  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 3. Spring Boot 처리량 한계

| 구간 | 처리량 | 상태 |
|------|--------|------|
| ~10만건/분 | 안정적 | ✅ |
| ~20만건/분 | 최대치 | ⚠️ |
| 90만건/분 | 불가능 | ❌ |

---

## 🔧 개선 방안

### 단기 개선 (Backend 튜닝)

| 방안 | 예상 효과 | 난이도 |
|------|----------|--------|
| JDBC Batch INSERT | 5~10배 | 중 |
| Kafka 비동기 전송 | 2~3배 | 하 |
| Connection Pool 튜닝 | 1.5배 | 하 |

### 장기 개선 (아키텍처 변경)

| 방안 | 예상 효과 | 설명 |
|------|----------|------|
| Go/Rust API | 10~50배 | 고성능 언어로 교체 |
| Direct Kafka | 최대 | Backend 제거, 직접 전송 |
| Kafka Connect | 최대 | PostgreSQL 자동 동기화 |

### 실제 대용량 아키텍처

```
현재 (학습용):
Generator → Backend(Spring) → PostgreSQL + Kafka → HDFS

권장 (대용량):
Generator → Kafka (직접) → Spark Streaming → HDFS
                        → Kafka Connect → PostgreSQL (집계만)
```

---

## 📚 관련 문서

- [BENCHMARK.md](BENCHMARK.md) - 조회 성능 비교
- [WHY_HDFS_SPARK.md](WHY_HDFS_SPARK.md) - 시스템 선택 가이드
- [ARCHITECTURE.md](ARCHITECTURE.md) - 시스템 아키텍처
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - 트러블슈팅 가이드

---

## 📅 향후 테스트 계획

1. **Backend 튜닝 후 재테스트**
    - JDBC Batch INSERT 적용
    - Kafka 비동기 전송 적용

2. **Direct Kafka 테스트**
    - Backend 없이 Generator → Kafka 직접
    - 저장소 순수 성능 측정

3. **저장소 한계 테스트**
    - PostgreSQL 단독 최대 처리량
    - HDFS 단독 최대 처리량
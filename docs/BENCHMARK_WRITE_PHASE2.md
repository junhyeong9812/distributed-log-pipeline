# Write Performance 벤치마크 Phase 2

> Backend 배치 처리 개선 후 재테스트

---

## 📋 Phase 1 결과 요약

### 발견된 문제

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Phase 1 병목 분석                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  목표: 90만건/분                                                    │
│  실제: 20만건/분 (22% 달성)                                         │
│                                                                      │
│  병목: Backend (Spring Boot + JPA)                                  │
│  증상: "maximum number of running instances reached" 스킵 발생      │
│                                                                      │
│  원인:                                                               │
│  1. JPA saveAll()이 실제로는 단건 INSERT 반복                       │
│  2. Kafka 전송 동기 대기                                            │
│  3. IDENTITY 전략으로 인한 배치 비활성화                            │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 현재 코드 문제점

```java
// DataService.java 현재 코드
@Transactional
public void processLogs(List<LogEvent> logEvents) {
    List<LogEntity> entities = logEvents.stream()
            .map(event -> LogEntity.builder()...build())
            .toList();

    logRepository.saveAll(entities);  // ⚠️ 실제로는 단건 INSERT 반복!

    logEvents.forEach(kafkaProducerService::sendLog);  // ⚠️ 동기 전송
}
```

### Hibernate 배치가 안 되는 이유: IDENTITY 전략의 함정

```java
// LogEntity.java
@Id
@GeneratedValue(strategy = GenerationType.IDENTITY)  // ⚠️ 문제!
private Long id;
```

#### IDENTITY 전략의 동작 방식

```
┌─────────────────────────────────────────────────────────────────────┐
│                    IDENTITY 전략 동작                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. INSERT INTO logs (...) VALUES (...);                            │
│                    ↓                                                │
│  2. DB가 AUTO_INCREMENT로 ID 생성 (PostgreSQL: SERIAL)              │
│                    ↓                                                │
│  3. 생성된 ID를 JPA가 즉시 가져와야 함                              │
│     → entity.getId() 호출 가능해야 하니까                           │
│                    ↓                                                │
│  4. SELECT currval('logs_id_seq') 또는 RETURNING id                 │
│                    ↓                                                │
│  5. 다음 INSERT 전에 이 과정 완료 필요                              │
│                    ↓                                                │
│  결론: 배치 불가능! (순차 처리 강제)                                │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

#### saveAll() 내부 동작 (실제)

```java
// 우리가 호출한 코드
logRepository.saveAll(entities);  // 5000건 저장 요청

// Hibernate 내부에서 실제로 일어나는 일
for (LogEntity entity : entities) {
    // 1. INSERT 실행
    INSERT INTO logs (timestamp, level, service, ...) VALUES (?, ?, ?, ...);
    
    // 2. 생성된 ID 조회 (IDENTITY 전략 때문에 필수)
    SELECT currval('logs_id_seq');
    
    // 3. entity에 ID 설정
    entity.setId(generatedId);
}

// 결과: 5000건 × 2쿼리 = 10,000번 DB 왕복!
```

#### ID 전략별 배치 가능 여부

| ID 전략 | 배치 가능 | 이유 |
|---------|----------|------|
| **IDENTITY** | ❌ 불가 | DB가 ID 생성 → INSERT 후 즉시 조회 필요 |
| **SEQUENCE** | ✅ 가능 | allocationSize로 ID 미리 할당 |
| **TABLE** | ✅ 가능 | 별도 테이블에서 ID 미리 할당 |
| **UUID** | ✅ 가능 | 애플리케이션에서 생성 (DB 의존 X) |

#### application.yml의 배치 설정이 무시된 이유

```yaml
# application.yml - 이 설정이 있었지만...
spring:
  jpa:
    properties:
      hibernate:
        jdbc:
          batch_size: 100      # 무시됨!
        order_inserts: true    # 무시됨!
        order_updates: true    # 무시됨!
```

**이유**: IDENTITY 전략을 사용하면 Hibernate가 **자동으로 배치를 비활성화**함.
설정이 있어도 무시됨!

#### JDBC Batch는 왜 가능한가?

```java
// JDBC Batch - ID 반환 안 함
jdbcTemplate.batchUpdate(sql, new BatchPreparedStatementSetter() {
    @Override
    public void setValues(PreparedStatement ps, int i) throws SQLException {
        // ID 컬럼 없이 INSERT
        ps.setDouble(1, timestamp);
        ps.setString(2, level);
        // ...
    }
    
    @Override
    public int getBatchSize() {
        return 5000;
    }
});

// 실제 DB에 전송되는 쿼리 (1번에 묶어서)
INSERT INTO logs (timestamp, level, ...) VALUES 
    (?, ?, ...),
    (?, ?, ...),
    (?, ?, ...),
    ... (5000개)
;

// ID 반환 안 함 → 배치 가능!
```

#### 성능 비교

```
┌─────────────────────────────────────────────────────────────────────┐
│                    JPA saveAll() vs JDBC Batch                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  JPA saveAll() + IDENTITY (현재):                                   │
│  ├── 5000건 INSERT                                                  │
│  ├── DB 왕복: 10,000회 (INSERT + SELECT ID)                        │
│  ├── 네트워크 지연: 10,000 × 0.5ms = 5,000ms                       │
│  └── 총 시간: ~5~7초                                                │
│                                                                      │
│  JDBC batchUpdate() (개선):                                         │
│  ├── 5000건 INSERT                                                  │
│  ├── DB 왕복: 1회 (배치로 묶음)                                     │
│  ├── 네트워크 지연: 1 × 50ms = 50ms                                │
│  └── 총 시간: ~0.05초                                               │
│                                                                      │
│  성능 향상: 100~150배!                                              │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

#### 우리 상황에서 JDBC Batch 선택 이유

| 고려사항 | JPA saveAll() | JDBC Batch |
|----------|---------------|------------|
| INSERT 후 ID 필요? | ✅ 반환됨 | ❌ 반환 안 됨 |
| 배치 처리 | ❌ 불가 (IDENTITY) | ✅ 가능 |
| 성능 | 느림 | 빠름 |
| 코드 복잡도 | 간단 | 약간 복잡 |

**우리 경우**:
- INSERT 후 ID가 필요 없음 (로그 수집 용도)
- 성능이 최우선
- → **JDBC Batch 선택**

---

## 🔧 개선 방안

### 1. JDBC Batch INSERT (권장)

JPA 대신 직접 JDBC 배치 사용:

```java
@Service
@RequiredArgsConstructor
public class DataService {

    private final JdbcTemplate jdbcTemplate;
    private final KafkaTemplate<String, Object> kafkaTemplate;

    @Transactional
    public void processLogs(List<LogEvent> logEvents) {
        // 1. JDBC Batch INSERT (1번 왕복)
        String sql = "INSERT INTO logs (timestamp, level, service, host, message, metadata, created_at) " +
                     "VALUES (?, ?, ?, ?, ?, ?::jsonb, NOW())";
        
        jdbcTemplate.batchUpdate(sql, new BatchPreparedStatementSetter() {
            @Override
            public void setValues(PreparedStatement ps, int i) throws SQLException {
                LogEvent event = logEvents.get(i);
                ps.setDouble(1, event.getTimestamp().toEpochMilli() / 1000.0);
                ps.setString(2, event.getLevel());
                ps.setString(3, event.getService());
                ps.setString(4, event.getHost());
                ps.setString(5, event.getMessage());
                ps.setString(6, toJson(event.getMetadata()));
            }
            
            @Override
            public int getBatchSize() {
                return logEvents.size();
            }
        });
        
        // 2. Kafka 비동기 배치 전송
        logEvents.forEach(event -> {
            kafkaTemplate.send("logs.raw", event.getService(), event);
            // 결과 대기 안 함 (비동기)
        });
    }
}
```

### 2. Kafka 비동기 처리

```java
// KafkaProducerService.java 개선
public void sendLogAsync(LogEvent logEvent) {
    String key = logEvent.getService();
    
    // 결과 대기 안 함 - Fire and Forget
    kafkaTemplate.send(logsTopic, key, logEvent);
    
    // ERROR 레벨만 알림 (비동기)
    if ("ERROR".equalsIgnoreCase(logEvent.getLevel())) {
        kafkaTemplate.send(alertsTopic, key, logEvent);
    }
}

// 배치 전송
public void sendLogsAsync(List<LogEvent> logEvents) {
    logEvents.forEach(this::sendLogAsync);
}
```

### 3. ID 전략 변경 (선택)

SEQUENCE 전략으로 변경하면 JPA 배치도 가능:

```java
@Id
@GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "logs_seq")
@SequenceGenerator(name = "logs_seq", sequenceName = "logs_id_seq", allocationSize = 100)
private Long id;
```

하지만 JDBC Batch가 더 빠르므로 권장하지 않음.

---

## 📝 수정 파일 목록

### 1. DataService.java

```
변경 내용:
- JPA saveAll() → JDBC batchUpdate()
- Kafka 동기 전송 → 비동기 전송
- ObjectMapper 추가 (JSON 변환)
```

### 2. KafkaProducerService.java

```
변경 내용:
- sendLog() → sendLogAsync() (결과 대기 제거)
- sendLogsAsync() 배치 메서드 추가
```

### 3. application.yml

```
변경 내용:
- Kafka producer linger.ms 설정 (배치 전송)
- Kafka producer batch.size 설정
```

---

## 📊 예상 성능 개선

### Before (Phase 1)

| 항목 | 값 |
|------|-----|
| INSERT 방식 | 단건 5000번 |
| DB 왕복 | 5000회 |
| Kafka 전송 | 동기 대기 |
| 처리량 | ~20만건/분 |

### After (Phase 2)

| 항목 | 값 |
|------|-----|
| INSERT 방식 | 배치 1번 |
| DB 왕복 | 1회 |
| Kafka 전송 | 비동기 |
| 예상 처리량 | ~100만건/분 |

### 성능 개선 예상

```
┌─────────────────────────────────────────────────────────────────────┐
│                    예상 성능 개선                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  현재: 5000건 INSERT                                                │
│  ├── DB 왕복: 5000회 × 1ms = 5000ms                                 │
│  ├── Kafka 전송: 5000회 × 0.5ms = 2500ms                           │
│  └── 총: ~7500ms (너무 느림)                                        │
│                                                                      │
│  개선 후: 5000건 INSERT                                             │
│  ├── DB 왕복: 1회 × 50ms = 50ms                                    │
│  ├── Kafka 전송: 비동기 (대기 없음)                                 │
│  └── 총: ~50ms (150배 개선)                                        │
│                                                                      │
│  예상 처리량: 5000건 / 0.05초 = 100,000건/초 = 600만건/분           │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🧪 테스트 계획

### Phase 2-1: 기본 테스트

```bash
# 동일 조건으로 재테스트
curl -X POST "http://192.168.55.114:30800/control/start?batch_size=5000&log_interval=0.5&event_interval=1"
```

목표: 90만건/분 달성

### Phase 2-2: 한계 테스트

```bash
# 부하 더 증가
curl -X POST "http://192.168.55.114:30800/control/start?batch_size=10000&log_interval=0.3&event_interval=0.5"
```

목표: Backend 한계점 확인

### 측정 지표

| 지표 | Phase 1 | Phase 2 목표 |
|------|---------|-------------|
| 처리량 | 20만건/분 | 90만건/분+ |
| 스킵 발생 | 있음 | 없음 |
| 에러율 | 0% | 0% |
| DB 쿼리 시간 | 67ms | <20ms |

---

## 📁 코드 변경 상세

### DataService.java 전체 코드

```java
package com.pipeline.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.pipeline.model.ActivityEvent;
import com.pipeline.model.LogEvent;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.jdbc.core.BatchPreparedStatementSetter;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.sql.PreparedStatement;
import java.sql.SQLException;
import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
public class DataService {

    private final JdbcTemplate jdbcTemplate;
    private final KafkaProducerService kafkaProducerService;
    private final ObjectMapper objectMapper;

    private String toJson(Object obj) {
        if (obj == null) return "{}";
        try {
            return objectMapper.writeValueAsString(obj);
        } catch (JsonProcessingException e) {
            return "{}";
        }
    }

    @Transactional
    public void processLog(LogEvent logEvent) {
        String sql = "INSERT INTO logs (timestamp, level, service, host, message, metadata, created_at) " +
                     "VALUES (?, ?, ?, ?, ?, ?::jsonb, NOW())";
        
        jdbcTemplate.update(sql,
                logEvent.getTimestamp().toEpochMilli() / 1000.0,
                logEvent.getLevel(),
                logEvent.getService(),
                logEvent.getHost(),
                logEvent.getMessage(),
                toJson(logEvent.getMetadata())
        );

        kafkaProducerService.sendLogAsync(logEvent);
    }

    @Transactional
    public void processLogs(List<LogEvent> logEvents) {
        String sql = "INSERT INTO logs (timestamp, level, service, host, message, metadata, created_at) " +
                     "VALUES (?, ?, ?, ?, ?, ?::jsonb, NOW())";
        
        jdbcTemplate.batchUpdate(sql, new BatchPreparedStatementSetter() {
            @Override
            public void setValues(PreparedStatement ps, int i) throws SQLException {
                LogEvent event = logEvents.get(i);
                ps.setDouble(1, event.getTimestamp().toEpochMilli() / 1000.0);
                ps.setString(2, event.getLevel());
                ps.setString(3, event.getService());
                ps.setString(4, event.getHost());
                ps.setString(5, event.getMessage());
                ps.setString(6, toJson(event.getMetadata()));
            }
            
            @Override
            public int getBatchSize() {
                return logEvents.size();
            }
        });

        log.debug("Batch inserted {} logs", logEvents.size());
        kafkaProducerService.sendLogsAsync(logEvents);
    }

    @Transactional
    public void processActivity(ActivityEvent activityEvent) {
        String sql = "INSERT INTO events (event_id, timestamp, user_id, session_id, event_type, event_data, device, created_at) " +
                     "VALUES (?, ?, ?, ?, ?, ?::jsonb, ?::jsonb, NOW())";
        
        jdbcTemplate.update(sql,
                activityEvent.getEventId(),
                activityEvent.getTimestamp().toEpochMilli() / 1000.0,
                activityEvent.getUserId(),
                activityEvent.getSessionId(),
                activityEvent.getEventType(),
                toJson(activityEvent.getEventData()),
                toJson(activityEvent.getDevice())
        );

        kafkaProducerService.sendActivityAsync(activityEvent);
    }

    @Transactional
    public void processActivities(List<ActivityEvent> activityEvents) {
        String sql = "INSERT INTO events (event_id, timestamp, user_id, session_id, event_type, event_data, device, created_at) " +
                     "VALUES (?, ?, ?, ?, ?, ?::jsonb, ?::jsonb, NOW())";
        
        jdbcTemplate.batchUpdate(sql, new BatchPreparedStatementSetter() {
            @Override
            public void setValues(PreparedStatement ps, int i) throws SQLException {
                ActivityEvent event = activityEvents.get(i);
                ps.setString(1, event.getEventId());
                ps.setDouble(2, event.getTimestamp().toEpochMilli() / 1000.0);
                ps.setString(3, event.getUserId());
                ps.setString(4, event.getSessionId());
                ps.setString(5, event.getEventType());
                ps.setString(6, toJson(event.getEventData()));
                ps.setString(7, toJson(event.getDevice()));
            }
            
            @Override
            public int getBatchSize() {
                return activityEvents.size();
            }
        });

        log.debug("Batch inserted {} events", activityEvents.size());
        kafkaProducerService.sendActivitiesAsync(activityEvents);
    }
}
```

### KafkaProducerService.java 전체 코드

```java
package com.pipeline.service;

import com.pipeline.model.ActivityEvent;
import com.pipeline.model.LogEvent;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;

import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
public class KafkaProducerService {

    private final KafkaTemplate<String, Object> kafkaTemplate;

    @Value("${kafka.topics.logs}")
    private String logsTopic;

    @Value("${kafka.topics.events}")
    private String eventsTopic;

    @Value("${kafka.topics.alerts}")
    private String alertsTopic;

    // 단건 비동기 전송
    public void sendLogAsync(LogEvent logEvent) {
        String key = logEvent.getService();
        kafkaTemplate.send(logsTopic, key, logEvent);
        
        if ("ERROR".equalsIgnoreCase(logEvent.getLevel())) {
            kafkaTemplate.send(alertsTopic, key, logEvent);
        }
    }

    // 배치 비동기 전송
    public void sendLogsAsync(List<LogEvent> logEvents) {
        logEvents.forEach(this::sendLogAsync);
    }

    // 단건 비동기 전송
    public void sendActivityAsync(ActivityEvent activityEvent) {
        String key = activityEvent.getUserId();
        kafkaTemplate.send(eventsTopic, key, activityEvent);
    }

    // 배치 비동기 전송
    public void sendActivitiesAsync(List<ActivityEvent> activityEvents) {
        activityEvents.forEach(this::sendActivityAsync);
    }
}
```

### application.yml 추가 설정

```yaml
spring:
  kafka:
    producer:
      # 배치 전송 최적화
      properties:
        linger.ms: 5          # 5ms 대기 후 배치 전송
        batch.size: 65536     # 64KB 배치 크기
        buffer.memory: 33554432  # 32MB 버퍼
```

---

## 🔄 배포 절차

```bash
# 1. 코드 수정
# DataService.java, KafkaProducerService.java 교체

# 2. 빌드
cd ~/project/distributed-log-pipeline/backend
./gradlew build -x test

# 3. Docker 이미지 빌드
docker build -t log-pipeline-backend:latest .

# 4. k3s에 로드
docker save log-pipeline-backend:latest | sudo k3s ctr images import -

# 5. Pod 재시작
kubectl delete pod -n log-pipeline -l app=backend

# 6. 확인
kubectl get pods -n log-pipeline | grep backend
kubectl logs deployment/backend -n log-pipeline --tail=20
```

---

## 🧪 Phase 2 테스트 결과

### 테스트 일시
- 2026년 1월 12일 19:28 ~ 19:38

### 환경 (Phase 1과 동일)
| 노드 | 역할 | 리소스 제한 |
|------|------|------------|
| Master | PostgreSQL, Kafka, NameNode | - |
| Worker 1 | DataNode, Spark Worker | 2 CPU, 2GB |
| Worker 2 | DataNode, Spark Worker | 2 CPU, 2GB |

---

### Phase 2-1: 90만건/분 (목표 달성 테스트)

| 설정 | 값 |
|------|-----|
| batch_size | 5,000 |
| log_interval | 0.5초 |
| event_interval | 1초 |
| 목표 처리량 | 900,000건/분 |

**결과:**

| 지표 | PostgreSQL | HDFS |
|------|------------|------|
| 10초당 증가량 | ~110,000건 | ~110,000건 |
| 실제 처리량 | **~660,000건/분** (logs) | **~660,000건/분** (logs) |
| 총 처리량 (events 포함) | **~900,000건/분** ✅ | **~900,000건/분** ✅ |
| 에러 | 0 | 0 |
| 스킵 | 없음 ✅ | - |

**✅ 목표 달성! Phase 1 대비 4.5배 성능 향상**

---

### Phase 2-2: 180만건/분 (2배 부하)

| 설정 | 값 |
|------|-----|
| batch_size | 10,000 |
| log_interval | 0.5초 |
| event_interval | 1초 |
| 목표 처리량 | 1,800,000건/분 |

**결과:**

| 지표 | PostgreSQL | HDFS |
|------|------------|------|
| 처리량 | ~180만건/분 ✅ | ~180만건/분 ✅ |
| 쿼리 시간 | 345ms | 3,665ms |
| 에러 | 0 | 0 |
| Pod 상태 | 안정 | 안정 |

**리소스 사용량:**

| Pod | CPU | Memory |
|-----|-----|--------|
| PostgreSQL | 330m (16%) | 230Mi (11%) |
| Backend | 378m (19%) | 315Mi |
| Kafka | 194m | 989Mi |
| Spark Worker | 182m | 1,283Mi |

**✅ 둘 다 안정적으로 처리!**

---

### Phase 2-3: 360만건/분 (극한 테스트)

| 설정 | 값 |
|------|-----|
| batch_size | 20,000 |
| log_interval | 0.5초 |
| event_interval | 1초 |
| 목표 처리량 | 3,600,000건/분 |

**결과:**

| 지표 | PostgreSQL | HDFS/Spark |
|------|------------|------------|
| 최종 저장량 | **5,148,600건** ✅ | **3,998,600건** ❌ |
| 상태 | 계속 동작 | **사망** |
| 쿼리 시간 | 405ms → 743ms | 3,872ms |
| 에러 | 0 | DataNode excluded |

**HDFS/Spark 사망 원인:**

```
Error: File could only be written to 0 of the 1 minReplication nodes.
       There are 2 datanode(s) running and 
       2 node(s) are excluded in this operation.

원인: DataNode가 쓰기 속도를 못 따라가서 "excluded" 처리됨
     → 쓸 수 있는 노드가 0개
     → Parquet 파일 저장 실패
     → Spark Streaming 사망
```

**PostgreSQL 상태:**
- 쿼리 시간 증가 (318ms → 743ms) 하지만 계속 동작
- 514만건까지 저장 완료
- Pod Restart 없음

---

### Phase 2 결과 요약

| 부하 | PostgreSQL | HDFS/Spark | 승자 |
|------|------------|------------|------|
| 90만건/분 | ✅ 안정 | ✅ 안정 | 무승부 |
| 180만건/분 | ✅ 안정 | ✅ 안정 | 무승부 |
| 360만건/분 | ✅ **동작** | ❌ **사망** | **PostgreSQL** |

---

### Phase 1 vs Phase 2 비교

| 지표 | Phase 1 (JPA) | Phase 2 (JDBC Batch) | 개선율 |
|------|---------------|---------------------|--------|
| 최대 처리량 | 20만건/분 | **180만건/분+** | **9배** |
| 스킵 발생 | 있음 | 없음 | ✅ |
| PostgreSQL 한계 | 미도달 | **360만건/분에서도 동작** | ✅ |
| HDFS 한계 | 미도달 | **360만건/분에서 사망** | 확인됨 |

---

### 핵심 발견

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Phase 2 핵심 발견                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. JDBC Batch INSERT 효과                                          │
│     - JPA saveAll() → JDBC batchUpdate()                           │
│     - 성능 9배 향상 (20만 → 180만건/분)                            │
│     - 근본 원인: IDENTITY 전략의 배치 비활성화 문제 해결            │
│                                                                      │
│  2. PostgreSQL의 놀라운 성능                                        │
│     - 360만건/분에서도 계속 동작                                    │
│     - 쿼리 시간 증가하지만 안정적                                   │
│     - 단일 노드 + SSD의 힘                                          │
│                                                                      │
│  3. HDFS/Spark의 한계                                               │
│     - DataNode I/O 병목                                             │
│     - 360만건/분에서 사망                                           │
│     - 분산 시스템도 자원 한계 있음                                  │
│                                                                      │
│  4. 이 환경의 결론                                                  │
│     - 소~중규모: PostgreSQL 우세                                    │
│     - 대규모 (PB급): 여전히 HDFS 필요 (수평 확장)                  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 다음 단계: Phase 3 (리소스 확장 테스트)

### 확장 계획

| 컴포넌트 | 현재 | 확장 | 목적 |
|----------|------|------|------|
| DataNode | 2CPU/2GB | 3CPU/3GB | I/O 처리량 증가 |
| Spark Worker | 2CPU/2GB | 3CPU/3GB | 처리 속도 증가 |

### 예상 결과
- HDFS가 360만건/분 버틸 수 있는지 확인
- PostgreSQL vs HDFS 공정한 비교

---

## 📚 관련 문서

- [BENCHMARK_WRITE_RESULT.md](BENCHMARK_WRITE_RESULT.md) - Phase 1 결과
- [WHY_HDFS_SPARK.md](WHY_HDFS_SPARK.md) - 시스템 선택 가이드
- [ARCHITECTURE.md](ARCHITECTURE.md) - 시스템 아키텍처
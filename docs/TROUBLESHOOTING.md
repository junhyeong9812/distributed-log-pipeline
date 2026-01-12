# 트러블슈팅 가이드

> Distributed Log Pipeline 구축 중 발생한 문제와 해결 방법을 정리한 문서입니다.

---

## 📋 목차

### 1차 트러블슈팅 (Docker Compose + Kubernetes 환경 구축)

| 번호 | 문제 | 환경 |
|------|------|------|
| 1 | Kafka 토픽 파티션 설정 문제 | Docker Compose |
| 2 | Spark Streaming 파티션 저장 문제 | Docker Compose |
| 3 | Spark Job 리소스 점유 문제 | Docker Compose |
| 4 | Airflow DB 초기화 및 Executor 설정 | Docker Compose |
| 5 | DataNode가 NameNode에 등록 실패 | 분산 환경 |
| 6 | Spark Worker 포트 충돌 | 분산 환경 |
| 7 | Spark에서 HDFS DataNode 연결 실패 | 분산 환경 |
| 8 | Docker 네트워크 격리 문제 | 분산 환경 |
| 9 | network_mode: host에서 extra_hosts 무시 | 분산 환경 |
| 10 | Spark Worker 자기 호스트명 해석 실패 | 분산 환경 |
| 11 | Spark Worker IPv6 호스트명 해석 실패 | 분산 환경 |
| 12 | DataNode 간 블록 복제 실패 | 분산 환경 |
| 13 | Airflow에서 Spark Master 연결 실패 | 분산 환경 |
| 14 | Spark Master Service 이름 충돌 | Kubernetes |
| 15 | Airflow DAG 디렉토리 재귀 루프 | Kubernetes |
| 16 | Airflow initContainer 디렉토리 생성 실패 | Kubernetes |
| 17 | Kafka Replication Factor 오류 | Kubernetes |
| 18 | Generator에서 Backend 연결 실패 | Kubernetes |
| 19 | Generator Settings 속성 누락 | Kubernetes |
| 20 | HDFS Cluster ID 불일치 | Kubernetes |
| 21 | Spark Executor 호스트명 해석 실패 | Kubernetes |

---

## Docker Compose 환경 트러블슈팅

### 문제 1: Kafka 토픽 파티션 설정 문제

**증상:**
```
예상: 파티션 3개로 분산 저장
실제: 파티션 1개에 모든 데이터 저장
```

**원인:**
- Generator가 Backend보다 먼저 데이터 전송
- Kafka가 토픽 자동 생성 (AUTO_CREATE_TOPICS=true)
- 기본값 파티션 1개로 생성되어 KafkaConfig 설정 무시됨

**해결:**

방법 1: 서비스 시작 순서 보장
```yaml
generator:
  depends_on:
    backend:
      condition: service_healthy
```

방법 2: 토픽 사전 생성
```bash
docker exec kafka /opt/kafka/bin/kafka-topics.sh \
  --create \
  --topic logs.raw \
  --partitions 3 \
  --replication-factor 1 \
  --bootstrap-server localhost:9092
```

방법 3: 볼륨 초기화 후 재시작
```bash
docker compose down -v
docker compose up -d
```

---

### 문제 2: Spark Streaming 파티션 저장 문제

**증상:**
```
예상: /data/logs/raw/year=2026/month=1/day=11/hour=19/
실제: /data/logs/raw/year=__HIVE_DEFAULT_PARTITION__/...
```

**원인:**
- Generator가 보내는 timestamp 형식: Unix timestamp (1768123166.291045)
- Spark에서 ISO 형식으로 파싱 시도 → 실패 → null → __HIVE_DEFAULT_PARTITION__

**해결:**

```python
# 수정 전 (ISO 형식)
.withColumn("event_time", to_timestamp(col("timestamp"), "yyyy-MM-dd'T'HH:mm:ss.SSSXXX"))

# 수정 후 (Unix timestamp)
.withColumn("event_time", from_unixtime(col("timestamp")).cast("timestamp"))
```

스키마도 변경:
```python
# 수정 전
StructField("timestamp", StringType(), True)

# 수정 후
StructField("timestamp", DoubleType(), True)
```

---

### 문제 3: Spark Job 리소스 점유 문제

**증상:**
```
WARN TaskSchedulerImpl: Initial job has not accepted any resources; 
check your cluster UI to ensure that workers are registered and have sufficient resources
```

**원인:**
- 이전 Spark Job이 비정상 종료되면서 Worker 리소스 계속 점유

**해결:**

방법 1: Spark 컨테이너 재시작
```bash
docker compose restart spark-master spark-worker
```

방법 2: Spark Master UI에서 직접 종료
```
http://<MASTER_IP>:8082 → Running Applications → (kill) 클릭
```

방법 3: 전체 클러스터 재시작
```bash
docker compose down
docker compose up -d
```

---

### 문제 4: Airflow DB 초기화 및 Executor 설정

**증상 1:**
```
ERROR: You need to initialize the database. Please run `airflow db init`.
```

**증상 2:**
```
airflow.exceptions.AirflowConfigException: error: cannot use SQLite with the LocalExecutor
```

**원인:**
- DB가 불완전하게 생성됨
- SQLite는 동시 쓰기 미지원, LocalExecutor와 호환 불가

**해결:**

```yaml
environment:
  - AIRFLOW__CORE__EXECUTOR=SequentialExecutor  # LocalExecutor → SequentialExecutor
  - AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=sqlite:////opt/airflow/airflow.db
```

볼륨 삭제 후 재시작:
```bash
docker compose down -v
docker compose up -d
```

---

## 분산 환경 트러블슈팅

### 문제 5: DataNode가 NameNode에 등록 실패

**증상:**
```bash
docker exec namenode hdfs dfsadmin -report
# Live datanodes (0)
```

**에러 로그:**
```
ERROR datanode.DataNode: Initialization failed for Block pool...
Datanode denied communication with namenode because hostname cannot be resolved
```

**원인:**
- NameNode가 DataNode IP에 대해 역방향 DNS 조회 시도
- 호스트명 해석 실패로 연결 거부

**해결:**

docker-compose.master.yml namenode에 추가:
```yaml
environment:
  - HDFS_CONF_dfs_namenode_datanode_registration_ip___hostname___check=false
```

> 환경변수 변환 규칙: `.` → `_`, `-` → `___`

---

### 문제 6: Spark Worker 포트 충돌

**증상:**
```
Error response from daemon: Bind for 0.0.0.0:8081 failed: port is already allocated
```

**해결:**

docker-compose.worker.yml에서 포트 변경:
```yaml
spark-worker:
  ports:
    - "10000:8081"
```

---

### 문제 7: Spark에서 HDFS DataNode 연결 실패

**증상:**
```
java.net.ConnectException: Connection refused
ERROR: File could only be written to 0 of the 1 minReplication nodes.
```

**원인:**
- DataNode 9866 포트 미노출
- HDFS 데이터 흐름: Client → NameNode → Client → DataNode 직접 연결

**해결:**

docker-compose.worker.yml에 포트 추가:
```yaml
datanode:
  ports:
    - "9864:9864"  # HTTP
    - "9866:9866"  # 데이터 전송 (필수!)
    - "9867:9867"  # IPC
```

---

### 문제 8: Docker 네트워크 격리 문제

**증상:**
```
java.io.EOFException: Unexpected EOF while trying to read response from server
WARN TaskSchedulerImpl: Initial job has not accepted any resources
```

**원인:**
- Docker bridge 네트워크가 컨테이너 격리
- DataNode/Spark Worker가 내부 IP (172.x.x.x) 보고
- Master가 해당 내부 IP로 접근 시도 → 실패

**해결:**

Worker에서 `network_mode: host` 사용:
```yaml
datanode:
  network_mode: host

spark-worker:
  network_mode: host
```

---

### 문제 9: network_mode: host에서 extra_hosts 무시

**증상:**
```
java.nio.channels.UnresolvedAddressException
```

docker-compose.yml에 extra_hosts 설정했지만 여전히 호스트명 해석 실패

**원인:**
- `network_mode: host` 사용 시 컨테이너가 호스트 네트워크 직접 사용
- Docker의 extra_hosts 설정 무시됨
- 컨테이너가 호스트 PC의 /etc/hosts 직접 참조

**해결:**

Worker PC의 /etc/hosts에 직접 추가:
```bash
# Worker 1 (192.168.55.158)
echo "192.168.55.9 worker2" | sudo tee -a /etc/hosts
echo "192.168.55.114 jun-Victus-by-HP-Gaming-Laptop-16-r0xxx.local" | sudo tee -a /etc/hosts

# Worker 2 (192.168.55.9)
echo "192.168.55.158 worker1" | sudo tee -a /etc/hosts
echo "192.168.55.114 jun-Victus-by-HP-Gaming-Laptop-16-r0xxx.local" | sudo tee -a /etc/hosts
```

---

### 문제 10: Spark Worker 자기 호스트명 해석 실패

**증상:**
```
java.net.UnknownHostException: jun: jun: Try again
    at java.net.InetAddress.getLocalHost(InetAddress.java:1507)
```

**원인:**
- Spark Worker 시작 시 자신의 호스트명을 IP로 해석 시도
- /etc/hosts에 자기 자신의 호스트명 없으면 실패

**해결:**

각 Worker PC의 /etc/hosts에 자기 자신 추가:
```bash
# 호스트명 확인
hostname

# /etc/hosts에 추가
echo "127.0.0.1 $(hostname)" | sudo tee -a /etc/hosts
```

---

### 문제 11: Spark Worker IPv6 호스트명 해석 실패

**증상:**
```
java.net.UnknownHostException: jun: Try again
    at java.net.Inet6AddressImpl.lookupAllHostAddr(Native Method)
```

**원인:**
- Java가 기본적으로 IPv6로 먼저 조회
- /etc/hosts에 호스트명 있어도 IPv6 조회 실패

**해결:**

docker-compose에서 IPv4 강제 사용:
```yaml
spark-worker:
  environment:
    - SPARK_LOCAL_IP=192.168.55.158
    - SPARK_WORKER_OPTS=-Djava.net.preferIPv4Stack=true
  network_mode: host
```

---

### 문제 12: DataNode 간 블록 복제 실패

**증상:**
```
java.io.IOException: Got error, status=ERROR, ack with firstBadLink as 192.168.55.9:9866
WARN DataStreamer: Excluding datanode DatanodeInfoWithStorage[192.168.55.9:9866...]
```

**원인:**
- HDFS 복제 팩터 2 설정
- DataNode 간 네트워크 통신 문제로 복제 실패

**해결:**

복제 팩터를 1로 변경:
```yaml
# Master
namenode:
  environment:
    - HDFS_CONF_dfs_replication=1

# Worker
datanode:
  environment:
    - HDFS_CONF_dfs_replication=1
```

| 복제 팩터 | 장점 | 단점 |
|-----------|------|------|
| 1 | 네트워크 문제 없음 | 장애 시 데이터 손실 |
| 2 | 1대 장애 허용 | DataNode 간 통신 필요 |
| 3 | 2대 장애 허용 | 더 많은 통신 필요 |

---

### 문제 13: Airflow에서 Spark Master 연결 실패

**증상:**
```
java.net.UnknownHostException: spark-master
ERROR StandaloneSchedulerBackend: Application has been killed. Reason: All masters are unresponsive!
```

**원인:**
- Spark Master가 `network_mode: host`로 변경됨
- Airflow DAG에서 `spark://spark-master:7077`로 연결 시도
- Docker 서비스명 해석 불가

**해결:**

Airflow DAG 파일에서 실제 IP 사용:
```python
# 수정 전
--master spark://spark-master:7077

# 수정 후
--master spark://192.168.55.114:7077
```

---

## Kubernetes 환경 트러블슈팅

### 문제 14: Spark Master Service 이름 충돌

**증상:**
```
java.lang.NumberFormatException: For input string: "tcp://10.43.220.131:8080"
```

**원인:**
- K8s가 Service 이름으로 환경변수 자동 생성
- `spark-master` Service → `SPARK_MASTER_PORT=tcp://10.43.220.131:8080`
- Spark가 이 값을 숫자로 파싱 시도 → 실패

**해결:**

Service 이름을 `spark-master-svc`로 변경:
```yaml
apiVersion: v1
kind: Service
metadata:
  name: spark-master-svc  # spark-master → spark-master-svc
```

환경변수 명시적 설정:
```yaml
env:
  - name: SPARK_MASTER_PORT
    value: "7077"
  - name: SPARK_MASTER_WEBUI_PORT
    value: "8080"
```

---

### 문제 15: Airflow DAG 디렉토리 재귀 루프

**증상:**
```
RuntimeError: Detected recursive loop when walking DAG directory /opt/airflow/dags:
/opt/airflow/dags/..2026_01_12_01_22_40.195680184 has appeared more than once.
```

**원인:**
- ConfigMap을 DAG 디렉토리에 직접 마운트
- ConfigMap의 심볼릭 링크 구조가 무한 루프 유발

**해결:**

initContainer에서 DAG 파일을 PVC로 복사:
```yaml
initContainers:
  - name: init-dags
    image: busybox
    command:
      - sh
      - -c
      - |
        mkdir -p /opt/airflow/dags
        cat > /opt/airflow/dags/manual_pipeline.py << 'PYEND'
        from airflow import DAG
        ...
        PYEND
    volumeMounts:
      - name: airflow-data
        mountPath: /opt/airflow
```

---

### 문제 16: Airflow initContainer 디렉토리 생성 실패

**증상:**
```
sh: can't create /opt/airflow/dags/manual_pipeline.py: nonexistent directory
```

**원인:**
- PVC 마운트 시 빈 디렉토리로 시작
- /opt/airflow/dags 디렉토리 미존재

**해결:**

initContainer에서 mkdir 먼저 실행:
```yaml
command:
  - sh
  - -c
  - |
    mkdir -p /opt/airflow/dags
    cat > /opt/airflow/dags/manual_pipeline.py << 'PYEND'
    ...
    PYEND
```

---

### 문제 17: Kafka Replication Factor 오류

**증상:**
```
InvalidReplicationFactorException: Unable to replicate the partition 2 time(s): 
only 1 broker(s) are registered.
```

**원인:**
- KafkaConfig.java에서 replicas(2) 설정
- K8s에서 Kafka broker 1개만 실행

**해결:**

KafkaConfig.java 수정:
```java
return TopicBuilder.name("logs.raw")
        .partitions(3)
        .replicas(1)  // 2 → 1
        .build();
```

이미지 재빌드 및 배포:
```bash
./gradlew build -x test
docker build -t log-pipeline-backend:latest .
docker save log-pipeline-backend:latest | sudo k3s ctr images import -
kubectl rollout restart deployment/backend -n log-pipeline
```

---

### 문제 18: Generator에서 Backend 연결 실패

**증상:**
```
ERROR:app.scheduler:Failed to send logs: All connection attempts failed
```

**원인:**
- config.py에서 backend_url이 localhost로 설정
- K8s에서는 Service DNS 이름 사용 필요

**해결:**

config.py 수정:
```python
backend_url: str = os.getenv("BACKEND_URL", "http://localhost:8081")
```

K8s Deployment 환경변수:
```yaml
env:
  - name: BACKEND_URL
    value: "http://backend-svc.log-pipeline.svc.cluster.local:8081"
```

---

### 문제 19: Generator Settings 속성 누락

**증상:**
```
AttributeError: 'Settings' object has no attribute 'services'
```

**원인:**
- config.py 수정 시 기존 속성들 누락

**해결:**

기존 설정 유지하면서 K8s 환경변수만 추가:
```python
class Settings(BaseSettings):
    backend_url: str = os.getenv("BACKEND_URL", "http://localhost:8081")
    backend_timeout: int = 30
    log_interval_seconds: int = 5
    event_interval_seconds: int = 10
    batch_size: int = 100
    
    # 이 속성들 유지 필수!
    services: list = ["api-gateway", "user-service", "order-service", "payment-service"]
    log_levels: list = ["INFO", "DEBUG", "WARN", "ERROR"]
    event_types: list = ["CLICK", "VIEW", "PURCHASE", "LOGIN", "LOGOUT", "SEARCH"]
    error_rate: float = 0.05
```

---

### 문제 20: HDFS Cluster ID 불일치

**증상:**
```
java.io.IOException: Incompatible clusterIDs in /hadoop/dfs/data: 
namenode clusterID = CID-35773007-...; datanode clusterID = CID-8054f9f7-...
```

**원인:**
- NameNode 재생성 시 새 Cluster ID 발급
- DataNode는 기존 Cluster ID 보유

**해결:**

Worker 노드에서 DataNode 데이터 삭제:
```bash
sudo rm -rf /data/hdfs/datanode/*
```

DataNode 재시작:
```bash
kubectl rollout restart daemonset/datanode -n log-pipeline
```

---

### 문제 21: Spark Executor 호스트명 해석 실패

**증상:**
```
java.net.UnknownHostException: spark-master-5885b7bc-6lck4
Failed to connect to spark-master-5885b7bc-6lck4:33405
```

**원인:**
- Spark Master가 Pod 이름을 Driver URL로 사용
- Worker에서 Pod 이름 DNS 해석 불가

**해결:**

Headless Service + hostname/subdomain으로 DNS 이름 부여:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: spark-master
spec:
  template:
    spec:
      hostname: spark-master
      subdomain: spark-headless
      containers:
        - env:
            - name: SPARK_PUBLIC_DNS
              value: "spark-master.spark-headless.log-pipeline.svc.cluster.local"
---
apiVersion: v1
kind: Service
metadata:
  name: spark-headless
spec:
  clusterIP: None  # Headless Service
  selector:
    app: spark-master
```

결과:
- Pod DNS: `spark-master.spark-headless.log-pipeline.svc.cluster.local`
- Worker에서 해석 가능

---

## 🔍 일반적인 디버깅 명령어

### Docker Compose

```bash
# 전체 로그
docker compose logs -f

# 특정 서비스 로그
docker compose logs -f <service>

# 컨테이너 접속
docker exec -it <container> bash

# 리소스 확인
docker stats
```

### Kubernetes

```bash
# Pod 상태
kubectl get pods -n log-pipeline

# Pod 상세 정보
kubectl describe pod -n log-pipeline <pod>

# Pod 로그
kubectl logs -n log-pipeline <pod> --tail=50

# Pod 접속
kubectl exec -it -n log-pipeline <pod> -- bash

# 이벤트 확인
kubectl get events -n log-pipeline --sort-by='.lastTimestamp'
```

### HDFS

```bash
# 클러스터 상태
hdfs dfsadmin -report

# 파일 목록
hdfs dfs -ls -R /

# 파일 내용 확인
hdfs dfs -cat /path/to/file
```

### Kafka

```bash
# 토픽 목록
kafka-topics.sh --list --bootstrap-server localhost:9092

# 토픽 상세
kafka-topics.sh --describe --topic <topic> --bootstrap-server localhost:9092

# 메시지 확인
kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic <topic> --from-beginning --max-messages 5
```

### Spark

```bash
# 애플리케이션 목록
# Spark UI: http://<master>:8080

# 로그 확인
# Worker의 /spark/work/<app-id>/<executor-id>/stderr
```

---

### 문제 22: Docker 멀티스테이지 빌드 COPY 실패

**증상:**
```
COPY --from=build /app/build/libs/*.jar app.jar
When using COPY with more than one source file, the destination must be a directory and end with a /
```

**원인:**
- Docker COPY 명령어에서 와일드카드(`*.jar`) 사용 시 여러 파일 매칭 가능
- 여러 파일을 단일 파일명(`app.jar`)으로 복사 불가
- 빌드 결과물이 여러 jar 파일일 수 있음

**해결:**
Dockerfile에서 정확한 jar 파일명 지정:
```dockerfile
# 수정 전
COPY --from=build /app/build/libs/*.jar app.jar

# 수정 후
COPY --from=build /app/build/libs/pipeline-0.0.1-SNAPSHOT.jar app.jar
```

**전체 Dockerfile:**
```dockerfile
FROM eclipse-temurin:17-jdk-alpine AS build

WORKDIR /app

COPY gradle/ gradle/
COPY gradlew .
COPY build.gradle .
COPY settings.gradle .
COPY src/ src/

RUN chmod +x gradlew
RUN ./gradlew build -x test

FROM eclipse-temurin:17-jre-alpine

WORKDIR /app

COPY --from=build /app/build/libs/pipeline-0.0.1-SNAPSHOT.jar app.jar

EXPOSE 8081

ENTRYPOINT ["java", "-jar", "app.jar"]
```

**재빌드:**
```bash
cd ~/project/distributed-log-pipeline/backend
docker build --no-cache -t log-pipeline-backend:latest .
docker save log-pipeline-backend:latest | sudo k3s ctr images import -
kubectl rollout restart deployment/backend -n log-pipeline
```

---

### 문제 23: Backend PostgreSQL 환경변수 누락 (K8s)

**증상:**
- Backend 로그에 JPA/Hibernate 초기화 로그 없음
- PostgreSQL에 데이터 저장 안 됨
- Kafka만 동작

**원인:**
- backend.yaml에 PostgreSQL 관련 환경변수 미설정
- Spring Boot가 datasource 설정 없이 시작

**확인:**
```bash
kubectl describe pod -n log-pipeline -l app=backend | grep -A 20 "Environment:"
# SPRING_DATASOURCE_URL 없음
```

**해결:**
backend.yaml에 환경변수 추가:
```yaml
env:
  - name: SPRING_KAFKA_BOOTSTRAP_SERVERS
    value: "kafka.log-pipeline.svc.cluster.local:9092"
  - name: SPRING_DATASOURCE_URL
    value: "jdbc:postgresql://postgres-svc.log-pipeline.svc.cluster.local:5432/logs"
  - name: SPRING_DATASOURCE_USERNAME
    value: "admin"
  - name: SPRING_DATASOURCE_PASSWORD
    value: "admin123"
  - name: SPRING_JPA_HIBERNATE_DDL_AUTO
    value: "update"
```

**재배포:**
```bash
kubectl apply -f ~/project/distributed-log-pipeline/kubernetes/apps/backend.yaml
kubectl rollout restart deployment/backend -n log-pipeline
```

**확인:**
```bash
kubectl logs -n log-pipeline deployment/backend | grep -i hikari
# HikariPool-1 - Start completed. 출력되면 성공
```
```

---

## 다음 단계 정리
```
현재 상태:
✅ PostgreSQL 저장 동작
✅ Kafka 저장 동작
⬜ HDFS 저장 (Spark Streaming 실행 필요)
⬜ Query API 테스트
⬜ k6 부하 테스트

순서:
1. Spark Streaming 실행 → HDFS 저장
2. Query API 동작 확인
3. k6 스크립트 작성 및 테스트
4. 대용량 데이터 테스트 (Generator 속도 조절)
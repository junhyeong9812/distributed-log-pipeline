# 분산 환경 배포 가이드

## 📋 시스템 구성

| PC | IP | 역할 | 서비스 |
|----|-----|------|--------|
| 노트북 | 192.168.55.114 | Master | Kafka, NameNode, Spark Master, Airflow, Grafana |
| 리눅스 A | 192.168.55.158 | Worker 1 | DataNode, Spark Worker |
| 리눅스 B | 192.168.55.9 | Worker 2 | DataNode, Spark Worker |

## 🔧 사전 요구사항

모든 PC에 필요:
- Ubuntu 20.04+ 또는 호환 Linux
- Docker 20.10+
- Docker Compose V2
- Git
- 최소 4GB RAM, 20GB 디스크

## 📦 Step 1: Master 노드 설정 (노트북)

### 1-1: 프로젝트 Clone (최초 1회)
```bash
cd ~/project
git clone <your-repo-url> distributed-log-pipeline
cd distributed-log-pipeline
```

### 1-2: Master 서비스 시작
```bash
cd deploy
docker compose -f docker-compose.master.yml up -d
```

### 1-3: 상태 확인
```bash
docker compose -f docker-compose.master.yml ps
```

### 1-4: 서비스 URL

| 서비스 | URL |
|--------|-----|
| Kafka UI | http://192.168.55.114:8080 |
| HDFS NameNode | http://192.168.55.114:9870 |
| Spark Master | http://192.168.55.114:8082 |
| Airflow | http://192.168.55.114:8084 |
| Grafana | http://192.168.55.114:3000 |
| Prometheus | http://192.168.55.114:9090 |

---

## 📦 Step 2: Worker 노드 설정 (리눅스 A, B)

### 2-1: 의존성 설치 (최초 1회)
```bash
# 스크립트 다운로드 및 실행
curl -fsSL https://raw.githubusercontent.com/<your-repo>/main/scripts/setup-worker.sh | bash
```

또는 수동 설치:
```bash
# Docker 설치
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# Git 설치
sudo apt update && sudo apt install -y git
```

### 2-2: 프로젝트 Clone
```bash
mkdir -p ~/project
cd ~/project
git clone <your-repo-url> distributed-log-pipeline
cd distributed-log-pipeline
```

### 2-3: Worker 서비스 시작
```bash
cd deploy
docker compose -f docker-compose.worker.yml up -d
```

### 2-4: 상태 확인
```bash
docker compose -f docker-compose.worker.yml ps
```

---

## ✅ Step 3: 연결 확인

### Master에서 Worker 연결 확인

#### HDFS DataNode 확인
```bash
# NameNode UI에서 확인
http://192.168.55.114:9870
# Datanodes 탭에서 2개 노드 확인
```

또는 CLI:
```bash
docker exec namenode hdfs dfsadmin -report
```

#### Spark Worker 확인
```bash
# Spark Master UI에서 확인
http://192.168.55.114:8082
# Workers 섹션에서 2개 워커 확인
```

---

## 🚀 Step 4: 전체 파이프라인 테스트

### 4-1: Kafka에 데이터 쌓이는지 확인
```bash
# Kafka UI: http://192.168.55.114:8080
# logs.raw 토픽 확인
```

### 4-2: Spark Streaming Job 실행
```bash
docker exec spark-master /spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.3.0 \
  /opt/spark-jobs/streaming/raw_to_hdfs.py
```

### 4-3: HDFS에 데이터 저장 확인
```bash
docker exec namenode hdfs dfs -ls -R /data/logs/raw
```

### 4-4: Airflow DAG 실행
```bash
# Airflow UI: http://192.168.55.114:8084
# manual_log_pipeline 트리거
```

---

## 🛑 서비스 중지

### Master
```bash
cd ~/project/distributed-log-pipeline/deploy
docker compose -f docker-compose.master.yml down
```

### Worker
```bash
cd ~/project/distributed-log-pipeline/deploy
docker compose -f docker-compose.worker.yml down
```

### 볼륨까지 삭제 (데이터 초기화)
```bash
docker compose -f docker-compose.master.yml down -v
docker compose -f docker-compose.worker.yml down -v
```

---

## ⚠️ 트러블슈팅

### Worker가 Master에 연결 안 됨

1. **네트워크 확인**
```bash
ping 192.168.55.114
```

2. **방화벽 확인**
```bash
# Master에서 포트 열기
sudo ufw allow 9000   # HDFS
sudo ufw allow 7077   # Spark
sudo ufw allow 9092   # Kafka
```

3. **Docker 네트워크 확인**
```bash
docker network ls
```

### Spark Worker 연결 실패
```bash
# Worker에서 Spark Master 접근 확인
curl http://192.168.55.114:8082
```

### HDFS DataNode 연결 실패
```bash
# Worker에서 NameNode 접근 확인
curl http://192.168.55.114:9870
```

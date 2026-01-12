# Master 노드 설정 가이드

> 노트북 (192.168.55.114)에서 실행하는 Master 노드 설정 가이드입니다.

---

## 📋 사전 요구사항

### 하드웨어 권장 사양
- CPU: 4코어 이상
- RAM: 8GB 이상
- 저장공간: 50GB 이상

### 소프트웨어 요구사항
- Ubuntu 20.04+ 또는 유사 Linux 배포판
- Docker 20.10+
- Git

---

## 🐳 Docker 설치

```bash
# Docker 설치
curl -fsSL https://get.docker.com | sh

# 현재 사용자를 docker 그룹에 추가
sudo usermod -aG docker $USER

# 로그아웃 후 다시 로그인하여 그룹 적용
newgrp docker

# 설치 확인
docker --version
docker compose version
```

---

## 📁 프로젝트 클론

```bash
# 프로젝트 클론
git clone https://github.com/your-repo/distributed-log-pipeline.git
cd distributed-log-pipeline

# 환경 변수 설정
cp .env.example .env

# .env 파일에서 IP 주소 수정
# MASTER_IP=192.168.55.114
```

---

## 🔧 Docker Compose 환경 (단일 PC 테스트)

### 전체 스택 실행

```bash
docker compose up -d --build
```

### 서비스 확인

```bash
docker compose ps
```

### 로그 확인

```bash
docker compose logs -f
```

### 종료

```bash
docker compose down -v
```

---

## 🖥️ Docker Compose 분산 환경 (Master)

### 1. Backend 빌드

```bash
cd backend
./gradlew build -x test
cd ..
```

### 2. Master 서비스 시작

```bash
cd deploy
docker compose -f docker-compose.master.yml up -d --build
```

### 3. 서비스 확인

```bash
docker compose -f docker-compose.master.yml ps
```

### Master에서 실행되는 서비스

| 서비스 | 포트 | 설명 |
|--------|------|------|
| Kafka | 9092 | 메시지 큐 |
| Kafka UI | 8080 | Kafka 모니터링 |
| HDFS NameNode | 9870, 9000 | 분산 파일 시스템 마스터 |
| Spark Master | 8082, 7077 | Spark 클러스터 마스터 |
| Airflow | 8084 | 워크플로우 스케줄링 |
| Grafana | 3000 | 메트릭 대시보드 |
| Prometheus | 9090 | 메트릭 수집 |
| Backend | 8081 | API 서버 |
| Generator | 8000 | 데이터 생성기 |

---

## ☸️ Kubernetes 환경 (k3s Master)

### 1. k3s 설치

```bash
curl -sfL https://get.k3s.io | sh -s - --write-kubeconfig-mode 644
```

### 2. 설치 확인

```bash
kubectl get nodes
```

### 3. Worker 조인용 토큰 확인

```bash
sudo cat /var/lib/rancher/k3s/server/node-token
```

이 토큰을 Worker 노드 설정 시 사용합니다.

### 4. Namespace 생성

```bash
kubectl apply -f kubernetes/namespace/namespace.yaml
```

### 5. 서비스 배포

```bash
# 인프라 서비스
kubectl apply -f kubernetes/kafka/
kubectl apply -f kubernetes/hdfs/
kubectl apply -f kubernetes/spark/

# 애플리케이션
kubectl apply -f kubernetes/airflow/
kubectl apply -f kubernetes/monitoring/
kubectl apply -f kubernetes/apps/

# 외부 접속 설정
kubectl apply -f kubernetes/nodeport.yaml
```

### 6. 커스텀 이미지 배포

```bash
# Backend 이미지 빌드 및 k3s 가져오기
cd backend
./gradlew build -x test
docker build -t log-pipeline-backend:latest .
docker save log-pipeline-backend:latest | sudo k3s ctr images import -

# Generator 이미지 빌드 및 k3s 가져오기
cd ../generator
docker build -t log-pipeline-generator:latest .
docker save log-pipeline-generator:latest | sudo k3s ctr images import -
```

### 7. 상태 확인

```bash
# 전체 Pod 상태
kubectl get pods -n log-pipeline

# 서비스 상태
kubectl get svc -n log-pipeline

# HDFS 상태
kubectl exec -n log-pipeline deployment/namenode -- hdfs dfsadmin -report
```

---

## 🌐 접속 URL

### Docker Compose 환경

| 서비스 | URL |
|--------|-----|
| Kafka UI | http://localhost:8080 |
| HDFS | http://localhost:9870 |
| Spark | http://localhost:8082 |
| Airflow | http://localhost:8084 |
| Grafana | http://localhost:3000 |
| Generator | http://localhost:8000/docs |

### Kubernetes 환경

| 서비스 | URL |
|--------|-----|
| Grafana | http://192.168.55.114:30000 |
| Airflow | http://192.168.55.114:30084 |
| Spark UI | http://192.168.55.114:30082 |
| HDFS UI | http://192.168.55.114:30870 |
| Generator | http://192.168.55.114:30800 |

---

## 🔍 로그 확인

### Docker Compose

```bash
# 전체 로그
docker compose -f docker-compose.master.yml logs -f

# 특정 서비스 로그
docker compose -f docker-compose.master.yml logs -f kafka
docker compose -f docker-compose.master.yml logs -f namenode
docker compose -f docker-compose.master.yml logs -f spark-master
```

### Kubernetes

```bash
# Pod 로그
kubectl logs -n log-pipeline deployment/kafka --tail=50
kubectl logs -n log-pipeline deployment/namenode --tail=50
kubectl logs -n log-pipeline deployment/spark-master --tail=50
```

---

## 🛑 서비스 중지

### Docker Compose

```bash
# 중지 (데이터 유지)
docker compose -f docker-compose.master.yml down

# 중지 (데이터 삭제)
docker compose -f docker-compose.master.yml down -v
```

### Kubernetes

```bash
# 전체 리소스 삭제
kubectl delete namespace log-pipeline

# k3s 제거
/usr/local/bin/k3s-uninstall.sh
```

---

## ❓ 문제 해결

자세한 트러블슈팅은 [TROUBLESHOOTING.md](TROUBLESHOOTING.md)를 참고하세요.
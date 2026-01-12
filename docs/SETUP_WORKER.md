# Worker 노드 설정 가이드

> 리눅스 A (192.168.55.158), 리눅스 B (192.168.55.9)에서 실행하는 Worker 노드 설정 가이드입니다.

---

## 📋 사전 요구사항

### 하드웨어 권장 사양
- CPU: 2코어 이상
- RAM: 4GB 이상
- 저장공간: 30GB 이상

### 소프트웨어 요구사항
- Ubuntu 20.04+ 또는 유사 Linux 배포판
- Docker 20.10+
- Git

### 네트워크 요구사항
- Master 노드 (192.168.55.114)와 동일 네트워크
- 필요한 포트가 방화벽에서 허용되어야 함

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
```

---

## 🖥️ Docker Compose 분산 환경 (Worker)

### 1. /etc/hosts 설정

Worker 노드에서는 호스트명 해석을 위해 /etc/hosts 설정이 필요합니다.

#### Worker 1 (192.168.55.158)

```bash
# 자기 자신의 호스트명 추가
echo "127.0.0.1 $(hostname)" | sudo tee -a /etc/hosts

# Master 호스트명 추가
echo "192.168.55.114 jun-Victus-by-HP-Gaming-Laptop-16-r0xxx.local" | sudo tee -a /etc/hosts

# 다른 Worker 추가
echo "192.168.55.9 worker2" | sudo tee -a /etc/hosts
```

#### Worker 2 (192.168.55.9)

```bash
# 자기 자신의 호스트명 추가
echo "127.0.0.1 $(hostname)" | sudo tee -a /etc/hosts

# Master 호스트명 추가
echo "192.168.55.114 jun-Victus-by-HP-Gaming-Laptop-16-r0xxx.local" | sudo tee -a /etc/hosts

# 다른 Worker 추가
echo "192.168.55.158 worker1" | sudo tee -a /etc/hosts
```

### 2. Worker 서비스 시작

#### Worker 1

```bash
cd deploy
docker compose -f docker-compose.worker1.yml up -d
```

#### Worker 2

```bash
cd deploy
docker compose -f docker-compose.worker2.yml up -d
```

### 3. 서비스 확인

```bash
docker compose -f docker-compose.worker1.yml ps  # Worker 1
docker compose -f docker-compose.worker2.yml ps  # Worker 2
```

### Worker에서 실행되는 서비스

| 서비스 | 포트 | 설명 |
|--------|------|------|
| HDFS DataNode | 9864, 9866, 9867 | 분산 파일 시스템 데이터 노드 |
| Spark Worker | 8081 | Spark 워커 노드 |

---

## ☸️ Kubernetes 환경 (k3s Worker)

### 1. Master에서 토큰 확인

Master 노드에서 다음 명령 실행:

```bash
sudo cat /var/lib/rancher/k3s/server/node-token
```

### 2. k3s Agent 설치

Worker 노드에서 실행 (토큰 값 교체 필요):

```bash
curl -sfL https://get.k3s.io | K3S_URL=https://192.168.55.114:6443 K3S_TOKEN=<토큰값> sh -
```

예시:
```bash
curl -sfL https://get.k3s.io | K3S_URL=https://192.168.55.114:6443 K3S_TOKEN=K10abc123def456::server:xyz789 sh -
```

### 3. 설치 확인

Master 노드에서:

```bash
kubectl get nodes
```

예상 출력:
```
NAME         STATUS   ROLES                  AGE
jun-victus   Ready    control-plane,master   10m
jun          Ready    <none>                 2m
jun-mini1    Ready    <none>                 2m
```

### 4. HDFS DataNode 데이터 디렉토리 생성

Worker 노드에서:

```bash
sudo mkdir -p /data/hdfs/datanode
sudo chmod 777 /data/hdfs/datanode
```

---

## 🔧 Docker Compose Worker 설정 파일

### docker-compose.worker1.yml (192.168.55.158)

```yaml
services:
  datanode:
    image: bde2020/hadoop-datanode:2.0.0-hadoop3.2.1-java8
    container_name: datanode
    environment:
      - CORE_CONF_fs_defaultFS=hdfs://192.168.55.114:9000
      - HDFS_CONF_dfs_replication=1
      - HDFS_CONF_dfs_datanode_use_datanode_hostname=false
      - HDFS_CONF_dfs_client_use_datanode_hostname=false
    volumes:
      - datanode_data:/hadoop/dfs/data
    network_mode: host

  spark-worker:
    image: bde2020/spark-worker:3.3.0-hadoop3.3
    container_name: spark-worker
    environment:
      - SPARK_MASTER=spark://192.168.55.114:7077
      - SPARK_LOCAL_IP=192.168.55.158
      - SPARK_WORKER_OPTS=-Djava.net.preferIPv4Stack=true
    volumes:
      - ./spark-jobs:/opt/spark-jobs
    network_mode: host

volumes:
  datanode_data:
```

### docker-compose.worker2.yml (192.168.55.9)

```yaml
services:
  datanode:
    image: bde2020/hadoop-datanode:2.0.0-hadoop3.2.1-java8
    container_name: datanode
    environment:
      - CORE_CONF_fs_defaultFS=hdfs://192.168.55.114:9000
      - HDFS_CONF_dfs_replication=1
      - HDFS_CONF_dfs_datanode_use_datanode_hostname=false
      - HDFS_CONF_dfs_client_use_datanode_hostname=false
    volumes:
      - datanode_data:/hadoop/dfs/data
    network_mode: host

  spark-worker:
    image: bde2020/spark-worker:3.3.0-hadoop3.3
    container_name: spark-worker
    environment:
      - SPARK_MASTER=spark://192.168.55.114:7077
      - SPARK_LOCAL_IP=192.168.55.9
      - SPARK_WORKER_OPTS=-Djava.net.preferIPv4Stack=true
    volumes:
      - ./spark-jobs:/opt/spark-jobs
    network_mode: host

volumes:
  datanode_data:
```

---

## 🔍 로그 확인

### Docker Compose

```bash
# DataNode 로그
docker logs -f datanode

# Spark Worker 로그
docker logs -f spark-worker
```

### Kubernetes

Master 노드에서:

```bash
# DataNode 로그
kubectl logs -n log-pipeline daemonset/datanode --tail=50

# Spark Worker 로그
kubectl logs -n log-pipeline daemonset/spark-worker --tail=50
```

---

## ✅ 연결 확인

### HDFS DataNode 등록 확인

Master 노드에서:

```bash
# Docker Compose
docker exec namenode hdfs dfsadmin -report

# Kubernetes
kubectl exec -n log-pipeline deployment/namenode -- hdfs dfsadmin -report
```

예상 출력:
```
Live datanodes (2):
  Name: 192.168.55.158:9866
  Name: 192.168.55.9:9866
```

### Spark Worker 등록 확인

브라우저에서:
- Docker Compose: http://192.168.55.114:8082
- Kubernetes: http://192.168.55.114:30082

Workers (2) 표시 확인

---

## 🛑 서비스 중지

### Docker Compose

```bash
# Worker 1
docker compose -f docker-compose.worker1.yml down

# Worker 2
docker compose -f docker-compose.worker2.yml down
```

### Kubernetes

Master 노드에서:

```bash
# 전체 리소스 삭제
kubectl delete namespace log-pipeline
```

Worker 노드에서:

```bash
# k3s agent 제거
/usr/local/bin/k3s-agent-uninstall.sh
```

---

## 🧹 데이터 정리

HDFS Cluster ID 불일치 등의 문제 발생 시:

```bash
# DataNode 데이터 삭제
sudo rm -rf /data/hdfs/datanode/*

# 서비스 재시작
docker compose -f docker-compose.worker1.yml down
docker compose -f docker-compose.worker1.yml up -d
```

---

## ❓ 문제 해결

자세한 트러블슈팅은 [TROUBLESHOOTING.md](TROUBLESHOOTING.md)를 참고하세요.

특히 다음 문제들을 확인하세요:
- 문제 9: network_mode: host에서 extra_hosts 무시됨
- 문제 10: Spark Worker 자기 호스트명 해석 실패
- 문제 11: Spark Worker IPv6 호스트명 해석 실패
- 문제 20: HDFS Cluster ID 불일치
# HDFS on Kubernetes: DataNode 설정 가이드

## 문제 상황

K8s 환경에서 HDFS DataNode를 DaemonSet으로 배포했을 때, 데이터 적재 중 반복적으로 다음 에러 발생:
```
File could only be written to 0 of the 1 minReplication nodes.
There are 2 datanode(s) running and 2 node(s) are excluded in this operation.
```
```
java.nio.channels.UnresolvedAddressException
```

## 원인 분석

### DaemonSet의 문제점

DaemonSet으로 DataNode를 배포하면:

1. **Pod 이름이 랜덤**: `datanode-hb4hk`, `datanode-hjhds` 같은 임의의 이름 생성
2. **Pod 재시작 시 이름/IP 변경**: 재시작할 때마다 새로운 이름과 IP 할당
3. **DataNode 간 통신 실패**: 서로의 주소를 resolve 못함 → `UnresolvedAddressException`
4. **NameNode 캐싱 문제**: NameNode가 이전 DataNode IP를 캐싱 → `excluded` 처리

### 통신 흐름 문제
```
Spark → NameNode (192.168.55.114:9000) ✓ 정상
NameNode → DataNode (10.42.1.29) ✓ 정상
DataNode1 → DataNode2 (10.42.2.35) ✗ IP 바뀌면 실패
```

## 해결 방법

### StatefulSet 사용 (권장)

StatefulSet은 고정된 Pod 이름과 DNS를 제공:

- `datanode-0`, `datanode-1` (고정 이름)
- `datanode-0.datanode.log-pipeline.svc.cluster.local` (고정 DNS)

## 설정 비교

### ❌ 잘못된 설정 (DaemonSet)
```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: datanode
  namespace: log-pipeline
spec:
  selector:
    matchLabels:
      app: datanode
  template:
    metadata:
      labels:
        app: datanode
    spec:
      containers:
        - name: datanode
          image: bde2020/hadoop-datanode:2.0.0-hadoop3.2.1-java8
          env:
            - name: HDFS_CONF_dfs_datanode_use_datanode_hostname
              value: "false"  # IP 사용 - 문제 발생
```

### ✅ 올바른 설정 (StatefulSet)
```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: datanode
  namespace: log-pipeline
spec:
  serviceName: datanode  # Headless Service 연결 필수
  replicas: 2
  selector:
    matchLabels:
      app: datanode
  template:
    metadata:
      labels:
        app: datanode
    spec:
      affinity:
        # DataNode가 서로 다른 노드에 배치되도록 설정
        podAntiAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            - labelSelector:
                matchLabels:
                  app: datanode
              topologyKey: kubernetes.io/hostname
        # Master 노드 제외
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
              - matchExpressions:
                  - key: node-role.kubernetes.io/control-plane
                    operator: DoesNotExist
      containers:
        - name: datanode
          image: bde2020/hadoop-datanode:2.0.0-hadoop3.2.1-java8
          ports:
            - containerPort: 9864  # Web UI
            - containerPort: 9866  # Data Transfer
            - containerPort: 9867  # IPC
          env:
            - name: CORE_CONF_fs_defaultFS
              value: "hdfs://namenode.log-pipeline.svc.cluster.local:9000"
            - name: HDFS_CONF_dfs_replication
              value: "2"
            # hostname 사용 설정 - 핵심!
            - name: HDFS_CONF_dfs_datanode_use_datanode_hostname
              value: "true"
            - name: HDFS_CONF_dfs_client_use_datanode_hostname
              value: "true"
            - name: HDFS_CONF_dfs_namenode_datanode_registration_ip___hostname___check
              value: "false"
          volumeMounts:
            - name: datanode-data
              mountPath: /hadoop/dfs/data
          resources:
            requests:
              memory: "2Gi"
              cpu: "2"
            limits:
              memory: "4Gi"
              cpu: "3"
      volumes:
        - name: datanode-data
          hostPath:
            path: /data/hdfs/datanode
            type: DirectoryOrCreate
---
# Headless Service (필수)
apiVersion: v1
kind: Service
metadata:
  name: datanode
  namespace: log-pipeline
spec:
  selector:
    app: datanode
  ports:
    - name: web
      port: 9864
      targetPort: 9864
    - name: data
      port: 9866
      targetPort: 9866
    - name: ipc
      port: 9867
      targetPort: 9867
  clusterIP: None  # Headless Service
```

## 핵심 설정 설명

| 설정 | 값 | 설명 |
|------|-----|------|
| `serviceName` | `datanode` | Headless Service와 연결, 고정 DNS 생성 |
| `dfs_datanode_use_datanode_hostname` | `true` | DataNode가 IP 대신 hostname 사용 |
| `dfs_client_use_datanode_hostname` | `true` | Client도 hostname으로 접근 |
| `dfs_namenode_datanode_registration_ip___hostname___check` | `false` | IP-hostname 불일치 허용 |
| `clusterIP: None` | - | Headless Service로 개별 Pod DNS 생성 |
| `podAntiAffinity` | - | DataNode를 서로 다른 Worker 노드에 분산 |

## 결과

StatefulSet 적용 후:
```
# Pod 이름 (고정)
datanode-0
datanode-1

# DNS (고정)
datanode-0.datanode.log-pipeline.svc.cluster.local
datanode-1.datanode.log-pipeline.svc.cluster.local
```

재시작해도 같은 이름과 DNS가 유지되어 DataNode 간 통신이 안정적으로 유지됨.

## 배포 시 주의사항

1. **기존 데이터 삭제 필요**: DaemonSet → StatefulSet 전환 시 기존 HDFS 데이터 삭제
```bash
   sudo rm -rf /data/hdfs/namenode/*
   ssh worker1 "sudo rm -rf /data/hdfs/datanode/*"
   ssh worker2 "sudo rm -rf /data/hdfs/datanode/*"
```

2. **배포 순서**: NameNode 먼저 배포 후 DataNode 배포
```bash
   kubectl apply -f kubernetes/hdfs/namenode.yaml
   sleep 30
   kubectl apply -f kubernetes/hdfs/datanode.yaml
```

3. **상태 확인**:
```bash
   kubectl exec -it deployment/namenode -n log-pipeline -- hdfs dfsadmin -report
```
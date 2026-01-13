# 🚀 Distributed Log Pipeline

> Kubernetes 기반 분산 로그 파이프라인 - PostgreSQL vs HDFS+Spark 성능 비교 실험

<사진>

---

## 📋 프로젝트 개요

실시간 로그 데이터를 수집, 저장, 분석하는 **분산 데이터 파이프라인**을 구축하고, 단일 DB(PostgreSQL)와 분산 처리 시스템(HDFS+Spark)의 **성능을 비교 분석**한 프로젝트입니다.

### 핵심 질문

> **"대용량 로그 데이터 처리에서 분산 시스템이 단일 DB보다 효율적인가?"**

### 프로젝트 목표

1. **Kubernetes 기반 인프라 구축**: k3s 멀티노드 클러스터
2. **실시간 데이터 파이프라인**: Kafka → Spark Streaming → HDFS
3. **성능 벤치마크**: PostgreSQL vs HDFS+Spark 쓰기/읽기 성능 비교
4. **부하 테스트**: k6를 활용한 동시 사용자 처리 능력 검증

---

## 🏆 주요 결과

### 쓰기 성능 (Write Performance)

| Phase | 목표 처리량 | 실제 처리량 | PostgreSQL | HDFS |
|-------|------------|------------|------------|------|
| Phase 1 | 9,000건/분 | 9,000건/분 | ✅ 안정 | ✅ 안정 |
| Phase 2 | 90,000건/분 | 90,000건/분 | ✅ 안정 | ✅ 안정 |
| Phase 3 | 900,000건/분 | 200,000건/분 | ⚠️ Backend 병목 | ⚠️ Backend 병목 |
| **Phase 4** | **1.2억건 적재** | **1.2억건 완료** | ✅ 완료 | ✅ 완료 |

> **핵심 발견**: JPA 단건 INSERT → JDBC Batch 전환으로 **9배 성능 향상** (20만건/분 → 180만건/분)

### 읽기 성능 (Read Performance)

#### Compaction 전 (30,803개 파일)

| 쿼리 | PostgreSQL | HDFS | 승자 |
|------|-----------|------|------|
| COUNT(*) | 6.7초 | 112초 | PostgreSQL 17x |
| GROUP BY | 15.6초 | 245초 | PostgreSQL 16x |

#### Compaction 후 (100개 파일)

| 쿼리 | PostgreSQL | HDFS | 승자 |
|------|-----------|------|------|
| COUNT(*) | 6.7초 | 12초 | PostgreSQL 1.8x |
| GROUP BY | 15.6초 | **12초** | **HDFS 1.3x** |
| WHERE + GROUP BY | 20.5초 | **8.6초** | **HDFS 2.4x** |

> **핵심 발견**: Small File Problem 해결로 HDFS 성능 **최대 27배 개선**

### 부하 테스트 결과 (Phase 7)

| 테스트 | VU | 에러율 | 평균 응답 시간 | 결과 |
|--------|-----|--------|---------------|------|
| PG 단순 조회 | 5 | 0% | 4.2초 | ✅ PASS |
| PG 집계 쿼리 | 3 | 0% | 18.8초 | ✅ PASS |
| HDFS 집계 쿼리 | 2 | 0% | 8.0초 | ✅ PASS |
| HDFS 로그 조회 | 2 | 0% | 156.8초 | ✅ PASS |

---

## 🔑 핵심 결론

### 시스템별 권장 용도
```
┌─────────────────────────────────────────────────────────────────┐
│                    데이터 처리 전략                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   실시간 조회           통계/분석            대용량 배치         │
│   ────────────         ──────────          ────────────         │
│   PostgreSQL           HDFS + Spark        HDFS + Spark         │
│                                                                  │
│   • 로그 검색           • GROUP BY          • ETL                │
│   • 정렬 + LIMIT        • COUNT/SUM         • ML 학습            │
│   • 인덱스 활용         • 시간별 통계        • 리포트 생성       │
│                                                                  │
│   응답: ~4초            응답: ~8초          배치 처리            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 핵심 인사이트

| 발견 | 설명 |
|------|------|
| **분산처리 ≠ 만능** | 단순 조회는 PostgreSQL이 37배 빠름 |
| **집계는 분산처리** | GROUP BY, COUNT는 HDFS+Spark가 2.4배 빠름 |
| **Small File Problem** | Parquet Compaction 필수 (27배 성능 차이) |
| **정렬의 비용** | 1.2억건 정렬에 2분 30초 소요 (분산처리 한계) |

---

## 🏗️ 시스템 아키텍처

### 전체 구조
```
┌─────────────────────────────────────────────────────────────────────┐
│                         Master Node                                  │
│                     (192.168.55.114)                                │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌──────────┐  ┌─────────────┐           │
│  │Generator│→ │ Backend │→ │  Kafka   │→ │Spark Master │           │
│  │(Python) │  │(Spring) │  │          │  │             │           │
│  └─────────┘  └────┬────┘  └──────────┘  └─────────────┘           │
│                    │                                                 │
│              ┌─────▼─────┐              ┌─────────────┐             │
│              │PostgreSQL │              │  NameNode   │             │
│              │           │              │   (HDFS)    │             │
│              └───────────┘              └─────────────┘             │
└─────────────────────────────────────────────────────────────────────┘
                              │
            ┌─────────────────┼─────────────────┐
            ▼                 ▼                 ▼
┌───────────────────┐ ┌───────────────────┐
│   Worker Node 1   │ │   Worker Node 2   │
│ (192.168.55.158)  │ │  (192.168.55.9)   │
├───────────────────┤ ├───────────────────┤
│  ┌─────────────┐  │ │  ┌─────────────┐  │
│  │Spark Worker │  │ │  │Spark Worker │  │
│  └─────────────┘  │ │  └─────────────┘  │
│  ┌─────────────┐  │ │  ┌─────────────┐  │
│  │  DataNode   │  │ │  │  DataNode   │  │
│  │   (HDFS)    │  │ │  │   (HDFS)    │  │
│  └─────────────┘  │ │  └─────────────┘  │
└───────────────────┘ └───────────────────┘
```

### 데이터 흐름
```
[Log Generator] → [Backend API] → [Kafka] → [Spark Streaming] → [HDFS]
                       ↓
                 [PostgreSQL]
                       ↓
                 [Query API] ← [사용자 요청]
```

### 기술 스택

| 레이어 | 기술 | 버전 |
|--------|------|------|
| Container Orchestration | k3s (Kubernetes) | v1.34.3 |
| Message Queue | Apache Kafka | 3.7.0 |
| Stream Processing | Apache Spark | 3.3.0 |
| Distributed Storage | Apache Hadoop (HDFS) | 3.2.1 |
| RDBMS | PostgreSQL | 15 |
| Workflow | Apache Airflow | 2.7.0 |
| API Server | FastAPI + Spring Boot | - |
| Load Testing | k6 | latest |
| Monitoring | Prometheus + Grafana | - |

---

## 📁 프로젝트 구조
```
distributed-log-pipeline/
├── kubernetes/              # K8s 매니페스트
│   ├── namespace/
│   ├── hdfs/               # NameNode, DataNode
│   ├── spark/              # Master, Worker
│   ├── kafka/
│   ├── postgres/
│   ├── apps/               # Backend, Generator
│   ├── api/                # Query API
│   ├── airflow/
│   └── monitoring/         # Prometheus, Grafana
├── backend/                 # Spring Boot (데이터 수집)
├── generator/               # Python (로그 생성기)
├── api/                     # FastAPI (조회 API)
├── spark-jobs/              # Spark Streaming Jobs
│   ├── streaming/
│   └── batch/
├── airflow/                 # DAGs
├── k6/                      # 부하 테스트 스크립트
│   ├── phase6/
│   └── phase7/
├── monitoring/              # Prometheus, Grafana 설정
├── docs/                    # 문서
└── scripts/                 # 설치 스크립트
```

---

## 🚀 Quick Start

### 사전 요구사항

- Ubuntu 22.04+ (3대 이상 권장)
- Docker 20.10+
- k3s 설치

### 1. 클러스터 설치
```bash
# Master 노드
curl -sfL https://get.k3s.io | sh -
sudo cat /var/lib/rancher/k3s/server/node-token  # Worker용 토큰

# Worker 노드
curl -sfL https://get.k3s.io | K3S_URL=https://<MASTER_IP>:6443 K3S_TOKEN=<TOKEN> sh -
```

### 2. 파이프라인 배포
```bash
# Namespace 생성
kubectl apply -f kubernetes/namespace/

# 인프라 배포
kubectl apply -f kubernetes/hdfs/
kubectl apply -f kubernetes/spark/
kubectl apply -f kubernetes/kafka/
kubectl apply -f kubernetes/postgres/

# 애플리케이션 배포
kubectl apply -f kubernetes/apps/
kubectl apply -f kubernetes/api/

# NodePort 서비스
kubectl apply -f kubernetes/nodeport.yaml
```

### 3. 데이터 생성 시작
```bash
# Generator 상태 확인
kubectl logs -f deployment/generator -n log-pipeline

# Backend API로 제어
curl -X POST "http://<MASTER_IP>:30800/control/start?batch_size=1000&log_interval=1"
```

### 4. 데이터 조회
```bash
# PostgreSQL 통계
curl "http://<MASTER_IP>:30801/api/query/postgres/stats"

# HDFS 통계
curl "http://<MASTER_IP>:30801/api/query/hdfs/stats"

# 성능 비교
curl "http://<MASTER_IP>:30801/api/query/compare"
```

---

## 📊 벤치마크 테스트

### 테스트 실행
```bash
# Phase 7: 적정 부하 테스트
mkdir -p k6/phase7/results
k6 run k6/phase7/pg_simple_load.js
k6 run k6/phase7/pg_aggregate_load.js
k6 run k6/phase7/hdfs_simple_load.js
k6 run k6/phase7/hdfs_aggregate_load.js
```

### 모니터링
```bash
# Pod 리소스 사용량
watch -n 5 "kubectl top pods -n log-pipeline"

# API 서버 로그
kubectl logs -f deployment/query-api -n log-pipeline
```

---

## 📚 문서

### 아키텍처

| 문서 | 설명 |
|------|------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | 시스템 아키텍처 상세 |
| [WHY_HDFS_SPARK.md](docs/WHY_HDFS_SPARK.md) | HDFS+Spark 선택 이유 |

### 벤치마크

| Phase | 문서 | 결과 |
|-------|------|------|
| 읽기 성능 | [BENCHMARK_readPerformance.md](docs/BENCHMARK_readPerformance.md) | PostgreSQL 350x 빠름 (소량) |
| 쓰기 성능 | [BENCHMARK_WRITE_PERFORMANCE.md](docs/BENCHMARK_WRITE_PERFORMANCE.md) | 테스트 계획 |
| Phase 2 | [BENCHMARK_WRITE_PHASE2.md](docs/BENCHMARK_WRITE_PHASE2.md) | JDBC Batch 9x 개선 |
| Phase 3 | [BENCHMARK_WRITE_PHASE3.md](docs/BENCHMARK_WRITE_PHASE3.md) / [결과](docs/BENCHMARK_WRITE_PHASE3_RESULT.md) | 리소스 확장 |
| Phase 4 | [BENCHMARK_WRITE_PHASE4.md](docs/BENCHMARK_WRITE_PHASE4.md) / [결과](docs/BENCHMARK_WRITE_PHASE4_RESULT.md) | 1.2억건 적재 |
| Phase 5 | [BENCHMARK_WRITE_PHASE5.md](docs/BENCHMARK_WRITE_PHASE5.md) / [결과](docs/BENCHMARK_WRITE_PHASE5_RESULT.md) | Compaction 27x 개선 |
| Phase 6 | [BENCHMARK_WRITE_PHASE6.md](docs/BENCHMARK_WRITE_PHASE6.md) / [결과](docs/BENCHMARK_WRITE_PHASE6_RESULT.md) | k6 부하 테스트 |
| Phase 7 | [BENCHMARK_WRITE_PHASE7.md](docs/BENCHMARK_WRITE_PHASE7.md) / [결과](docs/BENCHMARK_WRITE_PHASE7_RESULT.md) | 적정 VU 계산 |

### 운영 가이드

| 문서 | 설명 |
|------|------|
| [HDFS_COMPACTION.md](docs/HDFS_COMPACTION.md) | Parquet Compaction 가이드 |
| [HDFS_SETTING.md](docs/HDFS_SETTING.md) | HDFS 설정 |
| [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | 트러블슈팅 |
| [TROUBLESHOOTING_SPARK_STREAMING.md](docs/TROUBLESHOOTING_SPARK_STREAMING.md) | Spark Streaming 이슈 |

---

## 🔧 트러블슈팅

### 주요 이슈 및 해결

| 이슈 | 원인 | 해결 |
|------|------|------|
| DataNode Excluded | Spark가 너무 많은 데이터 쓰기 시도 | `maxOffsetsPerTrigger` 제한 |
| Small File Problem | Streaming 배치마다 파일 생성 | Parquet Compaction |
| HDFS 조회 느림 | 1.2억건 전체 정렬 | 집계 쿼리 사용 권장 |
| k6 타임아웃 | 과도한 VU 설정 | 적정 VU 계산 (Phase 7) |

자세한 내용: [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

---

## 🛠️ 향후 개선 계획

### 단기

- [ ] Delta Lake / Iceberg 적용 (인덱싱)
- [ ] Airflow DAG 자동 Compaction
- [ ] Query API 캐싱 레이어

### 장기

- [ ] Elasticsearch 추가 (실시간 검색)
- [ ] Kubernetes HPA (Auto Scaling)
- [ ] Kafka Connect (자동 동기화)

---

## 📈 성능 개선 히스토리
```
Phase 1: JPA 단건 INSERT
         └── 20,000건/분

Phase 2: JDBC Batch INSERT
         └── 180,000건/분 (9x ↑)

Phase 3: 리소스 확장 (Worker 추가)
         └── 안정성 확보

Phase 4: 1.2억건 적재 완료
         └── Small File Problem 발견

Phase 5: Parquet Compaction
         └── HDFS 조회 27x 개선

Phase 6: k6 부하 테스트
         └── 과부하 시 실패 확인

Phase 7: 적정 VU 계산
         └── 안정적인 부하 테스트 성공
```

---

## 🤝 기여

이슈 및 PR 환영합니다!

---

## 📄 라이선스

MIT License

---

## 👤 Author

**junhyeong9812**

- GitHub: [@junhyeong9812](https://github.com/junhyeong9812)
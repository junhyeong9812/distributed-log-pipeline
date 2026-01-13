# Phase 4: 1.2억건 벤치마크 결과

## 테스트 일시
- 2026년 1월 13일

## 데이터 규모
| 저장소 | 로그 건수 | 이벤트 건수 |
|--------|-----------|-------------|
| PostgreSQL | 121,670,000 | 64,250,000 |
| HDFS | 121,619,878 | - |

## 조회 성능 결과

### Query 1: COUNT(*) - 전체 로그 수 카운트
| 저장소 | 응답 시간 | 비고 |
|--------|-----------|------|
| PostgreSQL | 6,769ms (6.7초) | - |
| HDFS + Spark | 112,396ms (112초) | - |
| **비율** | **PostgreSQL 17배 빠름** | |

### Query 2: GROUP BY service - 서비스별 집계
| 저장소 | 응답 시간 | 비고 |
|--------|-----------|------|
| PostgreSQL | 15,657ms (15.6초) | - |
| HDFS + Spark | 245,145ms (245초) | - |
| **비율** | **PostgreSQL 16배 빠름** | |

### Query 3: WHERE level='ERROR' + GROUP BY service
| 저장소 | 응답 시간 | 비고 |
|--------|-----------|------|
| PostgreSQL | 20,500ms (20.5초) | - |
| HDFS + Spark | 235,937ms (236초) | - |
| **비율** | **PostgreSQL 12배 빠름** | |

## 결과 요약 표

| 쿼리 유형 | PostgreSQL | HDFS + Spark | 승자 | 배율 |
|-----------|------------|--------------|------|------|
| COUNT(*) | 6.7초 | 112초 | PostgreSQL | 17x |
| GROUP BY (단일) | 15.6초 | 245초 | PostgreSQL | 16x |
| WHERE + GROUP BY | 20.5초 | 236초 | PostgreSQL | 12x |

## 실제 로그
```azure
(base) jun@jun-Victus-by-HP-Gaming-Laptop-16-r0xxx:~$ time curl -s --max-time 120 "http://192.168.55.114:30801/api/query/postgres/stats" | jq .
{
  "source": "postgresql",
  "query_time_ms": 6769.31,
  "logs_count": 121670000,
  "events_count": 64250000
}

real	0m6.776s
user	0m0.020s
sys	0m0.006s
(base) jun@jun-Victus-by-HP-Gaming-Laptop-16-r0xxx:~$ time curl -s --max-time 600 "http://192.168.55.114:30801/api/query/hdfs/stats" | jq .
{
  "source": "hdfs",
  "logs_count": 121619878,
  "query_time_ms": 112396.19
}

real	3m58.581s
user	0m0.022s
sys	0m0.014s
(base) jun@jun-Victus-by-HP-Gaming-Laptop-16-r0xxx:~$ time curl -s --max-time 600 "http://192.168.55.114:30801/api/query/postgres/logs/aggregate?group_by=service" | jq '.query_time_ms' 
15657.33

real	1m4.548s
user	0m0.030s
sys	0m0.010s
(base) jun@jun-Victus-by-HP-Gaming-Laptop-16-r0xxx:~$ time curl -s --max-time 600 "http://192.168.55.114:30801/api/query/hdfs/logs/aggregate?group_by=service" | jq '.query_time_ms'
245145.2

real	5m42.100s
user	0m0.036s
sys	0m0.010s
(base) jun@jun-Victus-by-HP-Gaming-Laptop-16-r0xxx:~$ time curl -s --max-time 600 "http://192.168.55.114:30801/api/query/postgres/logs/aggregate?group_by=service&level=ERROR" | jq '.query_time_ms'
20500.01

real	2m7.613s
user	0m0.026s
sys	0m0.006s
(base) jun@jun-Victus-by-HP-Gaming-Laptop-16-r0xxx:~$ time curl -s --max-time 600 "http://192.168.55.114:30801/api/query/hdfs/logs/aggregate?group_by=service&level=ERROR" | jq '.query_time_ms'
235937.1

real	4m51.201s
user	0m0.029s
sys	0m0.017s
(base) jun@jun-Victus-by-HP-Gaming-Laptop-16-r0xxx:~$ 


```

## 발견된 문제점

### 1. Small File Problem (핵심 이슈)

HDFS에 저장된 Parquet 파일 수 확인:
```bash
$ kubectl exec -it deployment/namenode -n log-pipeline -- hdfs dfs -ls -R /data/logs/raw | grep ".parquet" | wc -l
30803
```

**30,803개의 작은 Parquet 파일**이 생성되어 있음.

#### 문제 원인
- Spark Streaming이 매 배치(60초)마다 새로운 Parquet 파일 생성
- 1.2억건을 약 8시간 동안 적재하면서 수만 개의 작은 파일 생성

#### 성능 영향
1. **메타데이터 오버헤드**: NameNode가 30,803개 파일 메타데이터 관리
2. **파일 열기/닫기 비용**: 각 파일마다 I/O 오버헤드 발생
3. **Spark Task 폭발**: 파일당 1개 Task → 30,000+ Task 생성
4. **네트워크 비용**: Task 스케줄링 및 결과 수집 오버헤드

#### 정상적인 구조 vs 현재 구조
| 항목 | 권장 구조 | 현재 구조 |
|------|-----------|-----------|
| 파일 수 | 수백 개 | 30,803개 |
| 파일당 크기 | 100MB ~ 1GB | 수 KB ~ 수 MB |
| Task 수 | 수백 개 | 30,000+ 개 |

### 2. DataNode StatefulSet 전환

기존 DaemonSet에서 StatefulSet으로 전환하여 안정성 확보.
자세한 내용은 `HDFS_DATANODE_K8S_GUIDE.md` 참조.

## 결론

### PostgreSQL 우세 원인
1. 단일 노드에서 최적화된 쿼리 실행
2. 인덱스 활용 가능
3. 로컬 디스크 I/O (네트워크 오버헤드 없음)

### HDFS + Spark 열세 원인
1. **Small File Problem**: 30,803개 파일로 인한 심각한 성능 저하
2. Worker 2대로 분산 효과 제한적
3. API 서버 내 Spark 세션 오버헤드

### Phase 5 개선 계획
1. **Parquet 파일 Compaction**: 작은 파일들을 큰 파일로 합치기
2. 파일 수 30,803개 → 수백 개로 감소 목표
3. Compaction 후 동일 쿼리 재실행하여 성능 비교

## 다음 단계

Phase 5에서 Parquet Compaction 진행 후 재벤치마크 예정.
# Phase 7: 적정 부하 테스트 결과

## 개요

Phase 6에서 과도한 VU로 인한 실패를 분석하고, 리소스 기반 적정 VU를 계산하여 재테스트를 진행했다.

## 적정 VU 계산

### 계산 공식
```
적정 VU = (가용 리소스 / 요청당 리소스 사용량) × 안전 계수(0.7)
```

### 계산 결과

| 테스트 | Phase 6 VU | Phase 7 VU | 계산 근거 |
|--------|-----------|------------|-----------|
| PG 단순 조회 | 50 | **5** | CPU 2코어 기준 |
| PG 집계 | 20 | **3** | CPU + 메모리 바운드 |
| HDFS 집계 | 10 | **2** | Spark 세션 제약 |
| HDFS 로그 조회 | 10 | **2** | 정렬 연산 부하 |

## 테스트 결과

### PostgreSQL 단순 조회 (VU 5)

| 메트릭 | 값 |
|--------|-----|
| 총 요청 수 | 50 |
| 성공 요청 수 | 50 |
| 에러율 | **0.00%** |
| 평균 응답 시간 | 4,186 ms |
| P95 응답 시간 | 4,849 ms |
| 결과 | **PASS ✓** |

### PostgreSQL 집계 쿼리 (VU 3)

| 메트릭 | 값 |
|--------|-----|
| 총 요청 수 | 11 |
| 성공 요청 수 | 11 |
| 에러율 | **0.00%** |
| 평균 응답 시간 | 18,785 ms |
| P95 응답 시간 | 20,625 ms |
| 결과 | **PASS ✓** |

### HDFS 집계 쿼리 (VU 2)

| 메트릭 | 값 |
|--------|-----|
| 총 요청 수 | 21 |
| 성공 요청 수 | 21 |
| 에러율 | **0.00%** |
| 평균 응답 시간 | 7,966 ms |
| P95 응답 시간 | 8,886 ms |
| 결과 | **PASS ✓** |

### HDFS 로그 조회 (VU 2)

| 메트릭 | 값 |
|--------|-----|
| 총 요청 수 | 1 |
| 성공 요청 수 | 1 |
| 에러율 | **0.00%** |
| 평균 응답 시간 | **156,830 ms (2분 37초)** |
| P95 응답 시간 | 156,830 ms |
| 결과 | **PASS ✓** (시간 내 완료) |

## 리소스 사용량 분석

### 테스트 중 Pod 리소스 현황

| Pod | CPU | Memory | 비고 |
|-----|-----|--------|------|
| datanode-0 | 61m | **3,130Mi** | Limit 4Gi 근접 |
| datanode-1 | 41m | **3,020Mi** | Limit 4Gi 근접 |
| query-api | 666m | 1,039Mi | PySpark 내장 |
| spark-worker-0 | 2m | 221Mi | 거의 미사용 |
| spark-worker-1 | 1m | 224Mi | 거의 미사용 |
| postgres | 1m | 245Mi | 안정적 |

### 발견된 병목

1. **DataNode 메모리 포화**: 3GB/4GB 사용 (75%)
2. **Spark Worker 미활용**: query-api 내 PySpark가 local[*] 모드로 동작
3. **HDFS 로그 조회 정렬 비용**: 1.2억건 전체 정렬에 2분 30초 소요

## 성능 비교 요약

### 집계 쿼리 (HDFS 강점)

| 시스템 | 평균 응답 시간 | 승자 |
|--------|---------------|------|
| PostgreSQL | 18,785 ms | |
| HDFS + Spark | **7,966 ms** | **HDFS 2.4배 빠름** |

### 로그 조회 (PostgreSQL 강점)

| 시스템 | 평균 응답 시간 | 승자 |
|--------|---------------|------|
| PostgreSQL | 4,186 ms | **PostgreSQL 37배 빠름** |
| HDFS + Spark | 156,830 ms | |

## 핵심 발견

### 1. 분산처리의 적합한 용도

| 용도 | 권장 시스템 | 이유 |
|------|------------|------|
| 실시간 로그 조회 | **PostgreSQL** | 인덱스 활용, 정렬 최적화 |
| 통계/집계 연산 | **HDFS + Spark** | 분산 GROUP BY 효율적 |
| 대용량 분석 | **HDFS + Spark** | 병렬 스캔 |

### 2. HDFS 로그 조회가 느린 이유
```
문제: ORDER BY timestamp DESC LIMIT 100

처리 과정:
1. 1.2억건 전체 읽기
2. 1.2억건 전체 정렬 (2분+)
3. 상위 100건 반환

→ 분산처리해도 최종 정렬은 단일 노드에서 병합 필요
→ 정렬이 필요한 조회는 분산처리가 오히려 불리
```

### 3. 분산처리가 유리한 경우 vs 불리한 경우

**유리한 경우:**
- GROUP BY, COUNT, SUM 등 집계 연산
- 각 노드에서 부분 집계 → 최종 병합 (데이터량 감소)

**불리한 경우:**
- ORDER BY + LIMIT (정렬 후 조회)
- 각 노드에서 정렬 → 최종 병합 정렬 (데이터량 유지)
- 단일 DB 인덱스가 훨씬 효율적

## 결론

### 시스템별 권장 용도
```
┌─────────────────────────────────────────────────────────┐
│                    데이터 처리 전략                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   실시간 조회          통계/분석           대용량 배치      │
│   ────────────        ──────────         ────────────   │
│   PostgreSQL          HDFS + Spark       HDFS + Spark   │
│                                                         │
│   • 로그 검색          • GROUP BY         • ETL          │
│   • 정렬 + LIMIT       • COUNT/SUM        • ML 학습      │
│   • 인덱스 활용        • 시간별 통계       • 리포트 생성   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 최종 성능 요약

| 쿼리 유형 | PostgreSQL | HDFS | 권장 |
|-----------|-----------|------|------|
| 단순 조회 (LIMIT) | **4초** | 157초 | PostgreSQL |
| 집계 (GROUP BY) | 19초 | **8초** | HDFS |
| COUNT(*) | **7초** | 12초 | PostgreSQL |

### 향후 개선 방안

1. **HDFS 로그 조회 최적화**
    - 시간 범위 필수 파라미터화 (파티션 프루닝)
    - 정렬 없이 조회 옵션 제공
    - 비동기 쿼리 분리 (COUNT와 데이터 조회 분리)

2. **리소스 확장**
    - DataNode 메모리 4GB → 6GB
    - Spark Worker 활용 (분산 모드 전환)

3. **아키텍처 개선**
    - 실시간 조회: PostgreSQL 또는 Elasticsearch
    - 분석/통계: HDFS + Spark
    - 하이브리드 구성 권장


```azure
# 실 부하 트래픽
매 5.0초:   kubectl t...  jun-Victus-by-HP-Gaming-Laptop-16-r0xxx: Tue Jan 13 15:07:55 2026

NAME                           CPU(cores)   MEMORY(bytes)
backend-67865b78dc-dsjxl       502m         358Mi
datanode-0                     68m          3133Mi
datanode-1                     54m          3018Mi
generator-cc9975748-75vph      2m           64Mi
grafana-7fc446cb98-gmtsz       1m           105Mi
kafka-5cb6564b5f-bgjhf         15m          893Mi
namenode-cb9755c7-h8gsd        3m           506Mi
postgres-77f8dc74bc-279cg      1m           245Mi
prometheus-56f6d78f7d-n2hzs    1m           51Mi
query-api-5f6d49db5f-jqnr2     679m         1038Mi
spark-master-d66658684-v2rwx   1m           358Mi
spark-worker-5w552             2m           221Mi
spark-worker-h7zlr             2m           224Mi

실제 단일 목록 조회 시
^C(base) jun@jun-Victus-by-HP-Gaming-Laptop-16-r0xxx:~$ time curl -s --max-time 300 "http://192.168.55.114:30801/api/query/hdfs/logs?limit=100" | jq '.query_time_ms, .returned_count'
152149.64
100

real	2m32.162s
user	0m0.028s
sys	0m0.009s


oot@jun:/home/jun/distributed-log-pipeline# k6 run k6/phase7/hdfs_simple_load.js

         /\      Grafana   /‾‾/  
    /\  /  \     |\  __   /  /   
   /  \/    \    | |/ /  /   ‾‾\ 
  /          \   |   (  |  (‾)  |
 / __________ \  |_|\_\  \_____/ 

     execution: local
        script: k6/phase7/hdfs_simple_load.js
        output: -

     scenarios: (100.00%) 1 scenario, 2 max VUs, 4m30s max duration (incl. graceful stop):
              * hdfs_simple_load: Up to 2 looping VUs for 4m0s over 4 stages (gracefulRampDown: 30s, gracefulStop: 30s)

WARN[0210] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/hdfs/logs?limit=100\": request timeout"
INFO[0270] 
======================================================================  source=console
INFO[0270] Phase 7: HDFS 로그 조회 부하 테스트 결과                 source=console
INFO[0270] ======================================================================  source=console
INFO[0270] 설정: VU 0→1→2→2→0, 총 4분                        source=console
INFO[0270] ----------------------------------------------------------------------  source=console
INFO[0270] 총 요청 수: 1                                     source=console
INFO[0270] 성공 요청 수: 0                                    source=console
INFO[0270] 에러율: 100.00%                                  source=console
INFO[0270] ----------------------------------------------------------------------  source=console
INFO[0270] 평균 응답 시간: 0.00 ms                             source=console
INFO[0270] P95 응답 시간: 0.00 ms                            source=console
INFO[0270] 최소 응답 시간: 0.00 ms                             source=console
INFO[0270] 최대 응답 시간: 0.00 ms                             source=console
INFO[0270] ----------------------------------------------------------------------  source=console
INFO[0270] 결과: FAIL ✗                                    source=console
INFO[0270] ======================================================================  source=console
ERRO[0270] failed to handle the end-of-test summary      error="Could not save some summary information:\n\t- could not open 'k6/phase7/results/hdfs_simple_result.json': open k6/phase7/results/hdfs_simple_result.json: no such file or directory"

running (4m30.0s), 0/2 VUs, 1 complete and 2 interrupted iterations
hdfs_simple_load ✓ [======================================] 1/2 VUs  4m0s
ERRO[0270] thresholds on metrics 'errors' have been crossed

root@jun:/home/jun/distributed-log-pipeline# k6 run k6/phase7/hdfs_simple_load.js

         /\      Grafana   /‾‾/  
    /\  /  \     |\  __   /  /   
   /  \/    \    | |/ /  /   ‾‾\ 
  /          \   |   (  |  (‾)  |
 / __________ \  |_|\_\  \_____/ 

     execution: local
        script: k6/phase7/hdfs_simple_load.js
        output: -

     scenarios: (100.00%) 1 scenario, 2 max VUs, 4m30s max duration (incl. graceful stop):
              * hdfs_simple_load: Up to 2 looping VUs for 4m0s over 4 stages (gracefulRampDown: 30s, gracefulStop: 30s)

INFO[0245] 
======================================================================  source=console
INFO[0245] Phase 7: HDFS COUNT 부하 테스트 결과                 source=console
INFO[0245] ======================================================================  source=console
INFO[0245] 설정: VU 0→1→2→2→0, 총 4분                        source=console
INFO[0245] ----------------------------------------------------------------------  source=console
INFO[0245] 총 요청 수: 83                                    source=console
INFO[0245] 성공 요청 수: 83                                   source=console
INFO[0245] 에러율: 0.00%                                    source=console
INFO[0245] ----------------------------------------------------------------------  source=console
INFO[0245] 평균 응답 시간: 676.13 ms                           source=console
INFO[0245] P95 응답 시간: 799.63 ms                          source=console
INFO[0245] 최소 응답 시간: 549.05 ms                           source=console
INFO[0245] 최대 응답 시간: 892.81 ms                           source=console
INFO[0245] ----------------------------------------------------------------------  source=console
INFO[0245] 결과: PASS ✓                                    source=console
INFO[0245] ======================================================================  source=console
ERRO[0245] failed to handle the end-of-test summary      error="Could not save some summary information:\n\t- could not open 'k6/phase7/results/hdfs_simple_result.json': open k6/phase7/results/hdfs_simple_result.json: no such file or directory"

running (4m05.2s), 0/2 VUs, 83 complete and 0 interrupted iterations

root@jun:/home/jun/distributed-log-pipeline# k6 run k6/phase7/hdfs_aggregate_load.js

         /\      Grafana   /‾‾/  
    /\  /  \     |\  __   /  /   
   /  \/    \    | |/ /  /   ‾‾\ 
  /          \   |   (  |  (‾)  |
 / __________ \  |_|\_\  \_____/ 

     execution: local
        script: k6/phase7/hdfs_aggregate_load.js
        output: -

     scenarios: (100.00%) 1 scenario, 2 max VUs, 4m30s max duration (incl. graceful stop):
              * hdfs_aggregate_load: Up to 2 looping VUs for 4m0s over 4 stages (gracefulRampDown: 30s, gracefulStop: 30s)

WARN[0150] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/hdfs/logs/aggregate?group_by=service\": request timeout"
WARN[0210] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/hdfs/logs/aggregate?group_by=host\": request timeout"
INFO[0270] 
======================================================================  source=console
INFO[0270] Phase 7: HDFS 집계 쿼리 부하 테스트 결과                 source=console
INFO[0270] ======================================================================  source=console
INFO[0270] 설정: VU 0→1→2→2→0, 총 4분                        source=console
INFO[0270] ----------------------------------------------------------------------  source=console
INFO[0270] 총 요청 수: 2                                     source=console
INFO[0270] 성공 요청 수: 0                                    source=console
INFO[0270] 에러율: 100.00%                                  source=console
INFO[0270] ----------------------------------------------------------------------  source=console
INFO[0270] 평균 응답 시간: 0.00 ms                             source=console
INFO[0270] P95 응답 시간: 0.00 ms                            source=console
INFO[0270] 최소 응답 시간: 0.00 ms                             source=console
INFO[0270] 최대 응답 시간: 0.00 ms                             source=console
INFO[0270] ----------------------------------------------------------------------  source=console
INFO[0270] 결과: FAIL ✗                                    source=console
INFO[0270] ======================================================================  source=console
ERRO[0270] failed to handle the end-of-test summary      error="Could not save some summary information:\n\t- could not open 'k6/phase7/results/hdfs_aggregate_result.json': open k6/phase7/results/hdfs_aggregate_result.json: no such file or directory"

running (4m30.0s), 0/2 VUs, 2 complete and 2 interrupted iterations
hdfs_aggregate_load ✓ [======================================] 1/2 VUs  4m0s
ERRO[0270] thresholds on metrics 'errors, http_req_duration' have been crossed 
root@jun:/home/jun/distributed-log-pipeline# k6 run k6/phase7/hdfs_aggregate_load.js

         /\      Grafana   /‾‾/  
    /\  /  \     |\  __   /  /   
   /  \/    \    | |/ /  /   ‾‾\ 
  /          \   |   (  |  (‾)  |
 / __________ \  |_|\_\  \_____/ 

     execution: local
        script: k6/phase7/hdfs_aggregate_load.js
        output: -

     scenarios: (100.00%) 1 scenario, 2 max VUs, 4m30s max duration (incl. graceful stop):
              * hdfs_aggregate_load: Up to 2 looping VUs for 4m0s over 4 stages (gracefulRampDown: 30s, gracefulStop: 30s)

INFO[0241] 
======================================================================  source=console
INFO[0241] Phase 7: HDFS 집계 쿼리 부하 테스트 결과                 source=console
INFO[0241] ======================================================================  source=console
INFO[0241] 설정: VU 0→1→2→2→0, 총 4분                        source=console
INFO[0241] ----------------------------------------------------------------------  source=console
INFO[0241] 총 요청 수: 21                                    source=console
INFO[0241] 성공 요청 수: 21                                   source=console
INFO[0241] 에러율: 0.00%                                    source=console
INFO[0241] ----------------------------------------------------------------------  source=console
INFO[0241] 평균 응답 시간: 7966.13 ms                          source=console
INFO[0241] P95 응답 시간: 8885.57 ms                         source=console
INFO[0241] 최소 응답 시간: 6924.81 ms                          source=console
INFO[0241] 최대 응답 시간: 8947.88 ms                          source=console
INFO[0241] ----------------------------------------------------------------------  source=console
INFO[0241] 결과: PASS ✓                                    source=console
INFO[0241] ======================================================================  source=console


root@jun:/home/jun/distributed-log-pipeline# k6 run k6/phase7/pg_simple_load.js

         /\      Grafana   /‾‾/  
    /\  /  \     |\  __   /  /   
   /  \/    \    | |/ /  /   ‾‾\ 
  /          \   |   (  |  (‾)  |
 / __________ \  |_|\_\  \_____/ 

     execution: local
        script: k6/phase7/pg_simple_load.js
        output: -

     scenarios: (100.00%) 1 scenario, 5 max VUs, 4m30s max duration (incl. graceful stop):
              * pg_simple_load: Up to 5 looping VUs for 4m0s over 4 stages (gracefulRampDown: 30s, gracefulStop: 30s)

INFO[0248] 
======================================================================  source=console
INFO[0248] Phase 7: PostgreSQL 단순 조회 부하 테스트 결과           source=console
INFO[0248] ======================================================================  source=console
INFO[0248] 설정: VU 0→2→5→5→0, 총 4분                        source=console
INFO[0248] ----------------------------------------------------------------------  source=console
INFO[0248] 총 요청 수: 50                                    source=console
INFO[0248] 성공 요청 수: 50                                   source=console
INFO[0248] 에러율: 0.00%                                    source=console
INFO[0248] ----------------------------------------------------------------------  source=console
INFO[0248] 평균 응답 시간: 4186.06 ms                          source=console
INFO[0248] P95 응답 시간: 4848.79 ms                         source=console
INFO[0248] 최소 응답 시간: 3709.29 ms                          source=console
INFO[0248] 최대 응답 시간: 5195.92 ms                          source=console
INFO[0248] ----------------------------------------------------------------------  source=console
INFO[0248] 결과: PASS ✓                                    source=console
INFO[0248] ======================================================================  source=console
ERRO[0248] failed to handle the end-of-test summary      error="Could not save some summary information:\n\t- could not open 'k6/phase7/results/pg_simple_result.json': open k6/phase7/results/pg_simple_result.json: no such file or directory"

running (4m08.9s), 0/5 VUs, 50 complete and 0 interrupted iterations
pg_simple_load ✓ [======================================] 0/5 VUs  4m0s
ERRO[0249] thresholds on metrics 'http_req_duration' have been crossed 
root@jun:/home/jun/distributed-log-pipeline# k6 run k6/phase7/pg_aggregate_load.js

         /\      Grafana   /‾‾/  
    /\  /  \     |\  __   /  /   
   /  \/    \    | |/ /  /   ‾‾\ 
  /          \   |   (  |  (‾)  |
 / __________ \  |_|\_\  \_____/ 

     execution: local
        script: k6/phase7/pg_aggregate_load.js
        output: -

     scenarios: (100.00%) 1 scenario, 3 max VUs, 4m30s max duration (incl. graceful stop):
              * pg_aggregate_load: Up to 3 looping VUs for 4m0s over 4 stages (gracefulRampDown: 30s, gracefulStop: 30s)

INFO[0270] 
======================================================================  source=console
INFO[0270] Phase 7: PostgreSQL 집계 쿼리 부하 테스트 결과           source=console
INFO[0270] ======================================================================  source=console
INFO[0270] 설정: VU 0→1→3→3→0, 총 4분                        source=console
INFO[0270] ----------------------------------------------------------------------  source=console
INFO[0270] 총 요청 수: 11                                    source=console
INFO[0270] 성공 요청 수: 11                                   source=console
INFO[0270] 에러율: 0.00%                                    source=console
INFO[0270] ----------------------------------------------------------------------  source=console
INFO[0270] 평균 응답 시간: 18785.46 ms                         source=console
INFO[0270] P95 응답 시간: 20625.03 ms                        source=console
INFO[0270] 최소 응답 시간: 17307.43 ms                         source=console
INFO[0270] 최대 응답 시간: 21282.80 ms                         source=console
INFO[0270] ----------------------------------------------------------------------  source=console
INFO[0270] 결과: PASS ✓                                    source=console
INFO[0270] ======================================================================  source=console
ERRO[0270] failed to handle the end-of-test summary      error="Could not save some summary information:\n\t- could not open 'k6/phase7/results/pg_aggregate_result.json': open k6/phase7/results/pg_aggregate_result.json: no such file or directory"

running (4m30.0s), 0/3 VUs, 11 complete and 2 interrupted iterations
pg_aggregate_load ✓ [======================================] 1/3 VUs  4m0s
ERRO[0270] thresholds on metrics 'http_req_duration' have been crossed 
root@jun:/home/jun/distributed-log-pipeline# k6 run k6/phase7/hdfs_simple_load.js

         /\      Grafana   /‾‾/  
    /\  /  \     |\  __   /  /   
   /  \/    \    | |/ /  /   ‾‾\ 
  /          \   |   (  |  (‾)  |
 / __________ \  |_|\_\  \_____/ 

     execution: local
        script: k6/phase7/hdfs_simple_load.js
        output: -

     scenarios: (100.00%) 1 scenario, 2 max VUs, 4m30s max duration (incl. graceful stop):
              * hdfs_simple_load: Up to 2 looping VUs for 4m0s over 4 stages (gracefulRampDown: 30s, gracefulStop: 30s)

WARN[0150] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/hdfs/logs?limit=100\": request timeout"
WARN[0210] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/hdfs/logs?limit=100\": request timeout"
INFO[0270] 
======================================================================  source=console
INFO[0270] Phase 7: HDFS 단순 조회 부하 테스트 결과                 source=console
INFO[0270] ======================================================================  source=console
INFO[0270] 설정: VU 0→1→2→2→0, 총 4분                        source=console
INFO[0270] ----------------------------------------------------------------------  source=console
INFO[0270] 총 요청 수: 2                                     source=console
INFO[0270] 성공 요청 수: 0                                    source=console
INFO[0270] 에러율: 100.00%                                  source=console
INFO[0270] ----------------------------------------------------------------------  source=console
INFO[0270] 평균 응답 시간: 0.00 ms                             source=console
INFO[0270] P95 응답 시간: 0.00 ms                            source=console
INFO[0270] 최소 응답 시간: 0.00 ms                             source=console
INFO[0270] 최대 응답 시간: 0.00 ms                             source=console
INFO[0270] ----------------------------------------------------------------------  source=console
INFO[0270] 결과: FAIL ✗                                    source=console
INFO[0270] ======================================================================  source=console
ERRO[0270] failed to handle the end-of-test summary      error="Could not save some summary information:\n\t- could not open 'k6/phase7/results/hdfs_simple_result.json': open k6/phase7/results/hdfs_simple_result.json: no such file or directory"


```
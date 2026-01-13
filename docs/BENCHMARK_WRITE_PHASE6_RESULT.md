# Phase 6: k6 부하 테스트 결과

## 개요

Phase 5에서 확인된 단일 쿼리 성능을 기반으로, k6를 활용하여 동시 사용자 부하 테스트를 진행했다.

## 테스트 환경

### 리소스 현황
| 컴포넌트 | CPU | Memory 사용 | Memory Limit |
|----------|-----|-------------|--------------|
| PostgreSQL | 1m | 246Mi | 2Gi |
| Query API | 716m | 908Mi | - |
| DataNode-0 | 151m | 1022Mi | 4Gi |
| DataNode-1 | 34m | 2799Mi | 4Gi |
| Spark Worker x2 | 2m | 216Mi | - |

### 데이터 규모
- PostgreSQL: 121,670,000건
- HDFS: 121,619,878건 (100개 Parquet 파일)

## 테스트 결과

### Test 1: PostgreSQL 단순 조회 (VU 0→50)

| 메트릭 | 값 |
|--------|-----|
| 총 요청 수 | 85 |
| 평균 응답 시간 | 3,816 ms |
| P95 응답 시간 | 4,258 ms |
| 에러율 | **45.88%** |
| 결과 | **FAIL** (threshold 5% 초과) |

### Test 2: PostgreSQL 집계 쿼리 (VU 0→20)

| 메트릭 | 값 |
|--------|-----|
| 총 요청 수 | 27 |
| 평균 응답 시간 | 17,798 ms |
| P95 응답 시간 | 19,227 ms |
| 에러율 | **62.96%** |
| 결과 | **FAIL** (threshold 5% 초과) |

### Test 3: HDFS 단순 조회 (VU 0→10)

| 메트릭 | 값 |
|--------|-----|
| 총 요청 수 | 0 |
| 완료된 요청 | 0 |
| 에러율 | - |
| 결과 | **FAIL** (5분 내 단일 요청도 완료 못함) |

## 단일 요청 성능 (참고)

Phase 5에서 측정한 단일 요청 성능:

| 쿼리 | PostgreSQL | HDFS |
|------|-----------|------|
| COUNT(*) | 6.7초 | 12초 |
| GROUP BY | 15.6초 | 12초 |
| WHERE + GROUP BY | 20.5초 | 8.6초 |

## 실패 원인 분석

### 1. 동시 요청 처리 한계
```
단일 요청: 6.7초 (정상)
VU 50 동시 요청: 타임아웃 다수 발생
```

### 2. DataNode 메모리 포화
```bash
$ kubectl top pods -n log-pipeline
datanode-1: 2799Mi / 4Gi (70% 사용)
```

- 동시 HDFS 읽기 요청 → DataNode 메모리 급증
- 메모리 부족 → 응답 지연 → 타임아웃

### 3. API 서버 병목
```bash
query-api: 908Mi, 716m CPU
```

- 단일 프로세스로 동시 요청 처리
- DB 커넥션 풀 미설정 → 매 요청마다 새 연결
- Spark 세션 공유 시 순차 처리

### 4. 과도한 VU 설정

현재 환경(CPU 2코어, RAM 2GB)에서:
- PostgreSQL: VU 50은 과부하
- HDFS: VU 10도 과부하

## 결론

### 현재 환경의 동시 처리 능력

| 시스템 | 설정 VU | 권장 VU | 비고 |
|--------|---------|---------|------|
| PostgreSQL 단순 | 50 | 5~10 | 에러율 45% |
| PostgreSQL 집계 | 20 | 3~5 | 에러율 63% |
| HDFS | 10 | 1~2 | 완료 0건 |

### 발견된 문제점

1. **리소스 부족**: 현재 할당된 리소스로는 동시 요청 처리 한계
2. **커넥션 관리 부재**: DB 커넥션 풀, Spark 세션 풀 미구현
3. **타임아웃 설정**: k6 기본 60초로는 대용량 쿼리 처리 불가

## 다음 단계 (Phase 7)

1. 적정 VU 수치 계산 (리소스 기반)
2. k6 스크립트 수정 (현실적인 부하 설정)
3. 재테스트 및 안정성 검증


## 실제 로그
```azure
root@jun:/home/jun/distributed-log-pipeline# k6 run k6/phase6/pg_simple_load.js

         /\      Grafana   /‾‾/  
    /\  /  \     |\  __   /  /   
   /  \/    \    | |/ /  /   ‾‾\ 
  /          \   |   (  |  (‾)  |
 / __________ \  |_|\_\  \_____/ 

     execution: local
        script: k6/phase6/pg_simple_load.js
        output: -

     scenarios: (100.00%) 1 scenario, 50 max VUs, 5m0s max duration (incl. graceful stop):
              * pg_simple_load: Up to 50 looping VUs for 4m30s over 6 stages (gracefulRampDown: 30s, gracefulStop: 30s)

WARN[0189] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0192] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0195] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0198] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0201] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0204] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0207] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0210] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0213] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0216] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0219] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0222] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0225] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0228] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0228] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0231] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0232] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0234] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0235] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0237] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0239] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0240] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0243] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0243] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0246] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0247] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0249] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0250] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0254] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0259] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0262] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0266] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0270] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0273] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0277] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0281] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0285] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0288] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
WARN[0292] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?limit=100\": request timeout"
INFO[0300] 
======================================================================  source=console
INFO[0300] PostgreSQL 단순 조회 부하 테스트 결과                    source=console
INFO[0300] ======================================================================  source=console
INFO[0300] 총 요청 수: 85                                    source=console
INFO[0300] 평균 응답 시간: 3816.45 ms                          source=console
INFO[0300] P95 응답 시간: 4257.64 ms                         source=console
INFO[0300] 에러율: 45.88%                                   source=console
INFO[0300] ======================================================================  source=console
ERRO[0300] failed to handle the end-of-test summary      error="Could not save some summary information:\n\t- could not open 'k6/phase6/results/pg_simple_result.json': open k6/phase6/results/pg_simple_result.json: no such file or directory"

running (5m00.0s), 00/50 VUs, 85 complete and 32 interrupted iterations
pg_simple_load ✓ [======================================] 01/50 VUs  4m30s
ERRO[0300] thresholds on metrics 'errors, http_req_duration' have been crossed 
root@jun:/home/jun/distributed-log-pipeline# k6 run k6/phase6/pg_aggregate_load.js

         /\      Grafana   /‾‾/  
    /\  /  \     |\  __   /  /   
   /  \/    \    | |/ /  /   ‾‾\ 
  /          \   |   (  |  (‾)  |
 / __________ \  |_|\_\  \_____/ 

     execution: local
        script: k6/phase6/pg_aggregate_load.js
        output: -

     scenarios: (100.00%) 1 scenario, 20 max VUs, 5m0s max duration (incl. graceful stop):
              * pg_aggregate_load: Up to 20 looping VUs for 4m30s over 6 stages (gracefulRampDown: 30s, gracefulStop: 30s)

WARN[0150] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs/aggregate?group_by=level\": request timeout"
WARN[0162] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs/aggregate?group_by=host\": request timeout"
WARN[0174] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs/aggregate?group_by=host\": request timeout"
WARN[0186] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs/aggregate?group_by=service\": request timeout"
WARN[0198] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs/aggregate?group_by=service\": request timeout"
WARN[0210] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs/aggregate?group_by=host\": request timeout"
WARN[0216] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs/aggregate?group_by=host\": request timeout"
WARN[0222] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs/aggregate?group_by=service\": request timeout"
WARN[0228] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs/aggregate?group_by=service\": request timeout"
WARN[0234] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs/aggregate?group_by=host\": request timeout"
WARN[0240] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs/aggregate?group_by=level\": request timeout"
WARN[0246] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs/aggregate?group_by=service\": request timeout"
WARN[0251] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs/aggregate?group_by=level\": request timeout"
WARN[0270] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs/aggregate?group_by=level\": request timeout"
WARN[0272] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs/aggregate?group_by=host\": request timeout"
WARN[0284] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs/aggregate?group_by=service\": request timeout"
WARN[0290] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs/aggregate?group_by=service\": request timeout"
INFO[0297] 
======================================================================  source=console
INFO[0297] PostgreSQL 집계 쿼리 부하 테스트 결과                    source=console
INFO[0297] ======================================================================  source=console
INFO[0297] 총 요청 수: 27                                    source=console
INFO[0297] 평균 응답 시간: 17798.35 ms                         source=console
INFO[0297] P95 응답 시간: 19226.68 ms                        source=console
INFO[0297] 에러율: 62.96%                                   source=console
INFO[0297] ======================================================================  source=console
ERRO[0297] failed to handle the end-of-test summary      error="Could not save some summary information:\n\t- could not open 'k6/phase6/results/pg_aggregate_result.json': open k6/phase6/results/pg_aggregate_result.json: no such file or directory"

running (4m57.0s), 00/20 VUs, 26 complete and 14 interrupted iterations
pg_aggregate_load ✓ [======================================] 00/20 VUs  4m30s
ERRO[0297] thresholds on metrics 'errors, http_req_duration' have been crossed 
root@jun:/home/jun/distributed-log-pipeline# 
root@jun:/home/jun/distributed-log-pipeline# k6 run k6/phase6/hdfs_simple_load.js

         /\      Grafana   /‾‾/  
    /\  /  \     |\  __   /  /   
   /  \/    \    | |/ /  /   ‾‾\ 
  /          \   |   (  |  (‾)  |
 / __________ \  |_|\_\  \_____/ 

     execution: local
        script: k6/phase6/hdfs_simple_load.js
        output: -

     scenarios: (100.00%) 1 scenario, 10 max VUs, 5m0s max duration (incl. graceful stop):
              * hdfs_simple_load: Up to 10 looping VUs for 4m30s over 6 stages (gracefulRampDown: 30s, gracefulStop: 30s)

WARN[0300] No script iterations fully finished, consider making the test duration longer 
INFO[0300] 
======================================================================  source=console
INFO[0300] HDFS 단순 조회 부하 테스트 결과                          source=console
INFO[0300] ======================================================================  source=console
INFO[0300] 총 요청 수: 0                                     source=console
INFO[0300] 평균 응답 시간: 0.00 ms                             source=console
INFO[0300] P95 응답 시간: 0.00 ms                            source=console
INFO[0300] 에러율: 0.00%                                    source=console
INFO[0300] ======================================================================  source=console
ERRO[0300] failed to handle the end-of-test summary      error="Could not save some summary information:\n\t- could not open 'k6/phase6/results/hdfs_simple_result.json': open k6/phase6/results/hdfs_simple_result.json: no such file or directory"

running (5m00.0s), 00/10 VUs, 0 complete and 10 interrupted iterations
hdfs_simple_load ✓ [======================================] 01/10 VUs  4m30s
root@jun:/home/jun/distributed-log-pipeline# k6 run k6/phase6/hdfs_aggregate_load.js

```

## 부하 로그
```azure
NAME                                      CPU(cores)   CPU(%)   MEMORY(bytes)   MEMORY(%)   
jun                                       270m         4%       7185Mi          45%         
jun-mini1                                 436m         5%       7326Mi          47%         
jun-victus-by-hp-gaming-laptop-16-r0xxx   3706m        15%      21044Mi         55%         
NAME                           CPU(cores)   MEMORY(bytes)   
backend-67865b78dc-dsjxl       500m         357Mi           
datanode-0                     151m         1022Mi          
datanode-1                     34m          2799Mi          
generator-cc9975748-75vph      2m           64Mi            
grafana-7fc446cb98-gmtsz       1m           105Mi           
kafka-5cb6564b5f-bgjhf         14m          892Mi           
namenode-cb9755c7-h8gsd        3m           520Mi           
postgres-77f8dc74bc-279cg      1m           246Mi           
prometheus-56f6d78f7d-n2hzs    1m           46Mi            
query-api-654fd54869-xtdwb     716m         908Mi           
spark-master-d66658684-v2rwx   2m           360Mi           
spark-worker-5w552             2m           216Mi           
spark-worker-h7zlr             1m           220Mi   
```
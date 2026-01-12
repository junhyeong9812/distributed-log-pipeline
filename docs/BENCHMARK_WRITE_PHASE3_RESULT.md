# 조회 성능 벤치마크 결과 (Read Performance)

> PostgreSQL vs HDFS/Spark 조회 성능 비교 (500만건 데이터)

---

## 📋 테스트 개요

### 테스트 일시
- 2026년 1월 12일

### 데이터 규모
| 저장소 | logs | events |
|--------|------|--------|
| PostgreSQL | 5,568,600건 | 3,793,400건 |
| HDFS | 5,568,600건 | - |

### 테스트 도구
- k6 (부하 테스트 도구)
- 동시 사용자: 5~10 VUs
- 테스트 시간: 2~3분/테스트

---

## 📊 테스트 결과

### 1. 대용량 데이터 스캔 (COUNT(*))

```
테스트: 500만건 전체 카운트
동시 사용자: 5 VUs
```

| 지표 | PostgreSQL | HDFS |
|------|------------|------|
| 평균 응답시간 | **376ms** | 4,396ms |
| 배수 | 1x | 11.7x 느림 |

**결과**: PostgreSQL이 **11.7배** 빠름

---

### 2. 전체 집계 (GROUP BY)

```
테스트: GROUP BY level/service/host
동시 사용자: 10 VUs
```

| 지표 | PostgreSQL | HDFS |
|------|------------|------|
| level 집계 | 329~427ms | 8,054~8,433ms |
| service 집계 | 360~477ms | 8,089~8,633ms |
| host 집계 | 795~841ms | 7,928~8,487ms |
| **평균** | **584ms** | 8,410ms |
| 배수 | 1x | 14.4x 느림 |

**결과**: PostgreSQL이 **14.4배** 빠름

**주의**: PostgreSQL에서 일부 timeout 발생 (동시 부하 시)

---

### 3. 정렬 쿼리 (ORDER BY)

```
테스트: ORDER BY timestamp/level/service + LIMIT 100/500/1000
동시 사용자: 10 VUs
```

| 지표 | PostgreSQL | HDFS |
|------|------------|------|
| 평균 응답시간 | **229ms** | 20,969ms |
| P95 | 248ms | 21,476ms |
| 배수 | 1x | **91.5x 느림** |

**결과**: PostgreSQL이 **91.5배** 빠름

**주의**: PostgreSQL에서 다수 timeout 발생

```
WARN Request Failed: request timeout
- ORDER BY level desc LIMIT 100
- ORDER BY service desc LIMIT 500
- ORDER BY timestamp desc LIMIT 500
```

---

### 4. 복잡한 집계 쿼리

```
테스트:
- 시간범위 + GROUP BY
- 조건 + 정렬 + 대량 조회
- 서비스별/호스트별 집계
동시 사용자: 5 VUs
```

| 지표 | PostgreSQL | HDFS |
|------|------------|------|
| 평균 | **584ms** | 8,058ms |
| P95 | 862ms | 8,465ms |
| Min | 54ms | 7,799ms |
| Max | 880ms | 8,674ms |
| 배수 | 1x | 13.8x 느림 |

**결과**: PostgreSQL이 **13.8배** 빠름

---

## 📈 결과 요약

### 성능 비교 표

| 테스트 유형 | PostgreSQL | HDFS | 배수 | 승자 |
|-------------|------------|------|------|------|
| COUNT(*) | 376ms | 4,396ms | 11.7x | **PostgreSQL** |
| GROUP BY | 584ms | 8,410ms | 14.4x | **PostgreSQL** |
| ORDER BY | 229ms | 20,969ms | 91.5x | **PostgreSQL** |
| 복잡한 집계 | 584ms | 8,058ms | 13.8x | **PostgreSQL** |

### 안정성 비교

| 지표 | PostgreSQL | HDFS |
|------|------------|------|
| 평균 응답시간 | 빠름 (200~600ms) | 느림 (4~21초) |
| timeout 발생 | ⚠️ 있음 | ✅ 없음 |
| 동시 부하 처리 | ⚠️ 불안정 | ✅ 안정적 |
| 응답 시간 편차 | 큼 (54~880ms) | 작음 (7.8~8.7초) |

---

## 🔍 분석

### PostgreSQL이 빠른 이유

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PostgreSQL 성능 요인                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. 인덱스 활용                                                     │
│     - idx_logs_timestamp: ORDER BY timestamp 최적화                 │
│     - idx_logs_level: WHERE level = ? 최적화                        │
│     - idx_logs_service: WHERE service = ? 최적화                    │
│                                                                      │
│  2. SSD 스토리지                                                    │
│     - Random I/O 성능 우수                                          │
│     - 인덱스 탐색 빠름                                              │
│                                                                      │
│  3. 단일 노드                                                       │
│     - 네트워크 지연 없음                                            │
│     - 분산 조율 오버헤드 없음                                       │
│                                                                      │
│  4. 쿼리 최적화                                                     │
│     - PostgreSQL 쿼리 플래너 우수                                   │
│     - 통계 기반 실행 계획                                           │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### HDFS/Spark가 느린 이유

```
┌─────────────────────────────────────────────────────────────────────┐
│                    HDFS/Spark 성능 요인                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. 매번 풀스캔                                                     │
│     - Parquet 파일 전체 읽기                                        │
│     - 인덱스 없음                                                   │
│                                                                      │
│  2. 분산 처리 오버헤드                                              │
│     - Job 스케줄링                                                  │
│     - 데이터 셔플링                                                 │
│     - 네트워크 통신                                                 │
│                                                                      │
│  3. HDD 스토리지                                                    │
│     - Sequential Read는 빠르지만                                    │
│     - 소량 데이터에서는 오버헤드가 더 큼                            │
│                                                                      │
│  4. JVM 웜업                                                        │
│     - 첫 쿼리는 더 느림                                             │
│     - Spark 컨텍스트 초기화                                         │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### PostgreSQL timeout 발생 이유

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PostgreSQL 불안정 요인                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. Connection Pool 고갈                                            │
│     - 동시 요청 시 연결 대기                                        │
│     - 기본 설정으로 제한적                                          │
│                                                                      │
│  2. 리소스 제한 (2 CPU, 2GB)                                        │
│     - 동시 쿼리 처리 시 CPU 경합                                    │
│     - 메모리 부족 시 디스크 스왑                                    │
│                                                                      │
│  3. 대량 정렬 (ORDER BY)                                            │
│     - work_mem 부족 시 디스크 정렬                                  │
│     - 성능 급격히 저하                                              │
│                                                                      │
│  해결 방안:                                                         │
│  - Connection Pool 증가                                             │
│  - 리소스 확장                                                      │
│  - work_mem 튜닝                                                    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🎯 결론

### 500만건 규모에서의 결론

```
┌─────────────────────────────────────────────────────────────────────┐
│                    핵심 결론                                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. 조회 성능: PostgreSQL 압승 (10~90배 빠름)                       │
│                                                                      │
│  2. 안정성: HDFS 우세 (timeout 없음)                                │
│                                                                      │
│  3. 500만건은 "대용량"이 아님                                       │
│     - PostgreSQL이 충분히 처리 가능                                 │
│     - HDFS/Spark는 이 규모에서 오버킬                               │
│                                                                      │
│  4. 용도별 선택                                                     │
│     - 빠른 조회 필요: PostgreSQL                                    │
│     - 안정적 배치 처리: HDFS/Spark                                  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### HDFS/Spark가 유리해지는 시점 (예상)

| 데이터 규모 | PostgreSQL | HDFS/Spark | 권장 |
|-------------|------------|------------|------|
| < 100만건 | ✅ 빠름 | ❌ 오버킬 | PostgreSQL |
| 100만~1000만건 | ✅ 빠름 | ⚠️ 느림 | PostgreSQL |
| 1000만~1억건 | ⚠️ 느려짐 | ⚠️ 느림 | 하이브리드 |
| > 1억건 | ❌ 한계 | ✅ 확장 가능 | HDFS/Spark |

---

## 📚 다음 단계

### Phase 4: 1억건 데이터 테스트

목표: PostgreSQL과 HDFS/Spark의 성능 역전 지점 확인

```
현재: 500만건 → PostgreSQL 압승
목표: 1억건 → HDFS/Spark 유리해지는지 확인
```

---

## 📁 관련 문서

- [BENCHMARK_WRITE_RESULT.md](BENCHMARK_WRITE_RESULT.md) - Write Phase 1 결과
- [BENCHMARK_WRITE_PHASE2.md](BENCHMARK_WRITE_PHASE2.md) - Write Phase 2 결과
- [BENCHMARK_WRITE_PHASE3.md](BENCHMARK_WRITE_PHASE3.md) - Write Phase 3 계획
- [WHY_HDFS_SPARK.md](WHY_HDFS_SPARK.md) - 시스템 선택 가이드

```azure
jun@jun:~/distributed-log-pipeline$ k6 run ~/distributed-log-pipeline/k6/large_data_test.js

         /\      Grafana   /‾‾/  
    /\  /  \     |\  __   /  /   
   /  \/    \    | |/ /  /   ‾‾\ 
  /          \   |   (  |  (‾)  |
 / __________ \  |_|\_\  \_____/ 

     execution: local
        script: /home/jun/distributed-log-pipeline/k6/large_data_test.js
        output: -

     scenarios: (100.00%) 1 scenario, 5 max VUs, 2m30s max duration (incl. graceful stop):
              * large_data_test: 5 looping VUs for 2m0s (gracefulStop: 30s)

INFO[0006] PG: 5568600 logs in 399.06ms | HDFS: 5568600 logs in 3879.78ms  source=console
INFO[0011] PG: 5568600 logs in 374.83ms | HDFS: 5568600 logs in 4294.64ms  source=console
INFO[0015] PG: 5568600 logs in 418.37ms | HDFS: 5568600 logs in 4379.9ms  source=console
INFO[0019] PG: 5568600 logs in 415.01ms | HDFS: 5568600 logs in 3922.23ms  source=console
INFO[0023] PG: 5568600 logs in 392.52ms | HDFS: 5568600 logs in 3825.56ms  source=console
INFO[0029] PG: 5568600 logs in 397.92ms | HDFS: 5568600 logs in 4150.96ms  source=console
INFO[0033] PG: 5568600 logs in 564.4ms | HDFS: 5568600 logs in 3925.49ms  source=console
INFO[0037] PG: 5568600 logs in 370.15ms | HDFS: 5568600 logs in 3711.1ms  source=console
INFO[0041] PG: 5568600 logs in 432.35ms | HDFS: 5568600 logs in 4489.74ms  source=console
INFO[0051] PG: 5568600 logs in 325.84ms | HDFS: 5568600 logs in 4594.11ms  source=console
INFO[0056] PG: 5568600 logs in 368.69ms | HDFS: 5568600 logs in 4373.75ms  source=console
INFO[0060] PG: 5568600 logs in 373.32ms | HDFS: 5568600 logs in 4543.96ms  source=console
INFO[0065] PG: 5568600 logs in 348.06ms | HDFS: 5568600 logs in 4303.32ms  source=console
INFO[0071] PG: 5568600 logs in 335.61ms | HDFS: 5568600 logs in 4618.31ms  source=console
INFO[0076] PG: 5568600 logs in 339.5ms | HDFS: 5568600 logs in 4649.74ms  source=console
INFO[0080] PG: 5568600 logs in 357.43ms | HDFS: 5568600 logs in 4614.64ms  source=console
INFO[0085] PG: 5568600 logs in 351.71ms | HDFS: 5568600 logs in 4772.73ms  source=console
INFO[0091] PG: 5568600 logs in 379.48ms | HDFS: 5568600 logs in 4784.85ms  source=console
INFO[0100] PG: 5568600 logs in 386.48ms | HDFS: 5568600 logs in 4618.44ms  source=console
INFO[0105] PG: 5568600 logs in 382.45ms | HDFS: 5568600 logs in 4543.52ms  source=console
INFO[0110] PG: 5568600 logs in 385.25ms | HDFS: 5568600 logs in 4819.1ms  source=console
INFO[0116] PG: 5568600 logs in 359.12ms | HDFS: 5568600 logs in 4539.22ms  source=console
INFO[0120] PG: 5568600 logs in 321.29ms | HDFS: 5568600 logs in 4385.16ms  source=console
INFO[0125] PG: 5568600 logs in 376.02ms | HDFS: 5568600 logs in 4431.08ms  source=console
INFO[0129] PG: 5568600 logs in 321.08ms | HDFS: 5568600 logs in 4512.75ms  source=console
INFO[0140] PG: 5568600 logs in 351.15ms | HDFS: 5568600 logs in 4748.69ms  source=console
INFO[0144] PG: 5568600 logs in 327.7ms | HDFS: 5568600 logs in 4272.35ms  source=console
INFO[0147] 
================================================================================  source=console
INFO[0147] 대용량 데이터 스캔 테스트 결과 (Large Data Scan - COUNT(*))  source=console
INFO[0147] ================================================================================  source=console
INFO[0147] 데이터 규모: 약 500만건                               source=console
INFO[0147]                                               source=console
INFO[0147] PostgreSQL COUNT(*) 평균: 376.10ms              source=console
INFO[0147] HDFS COUNT(*) 평균: 4396.49ms                   source=console
INFO[0147]                                               source=console
INFO[0147] 더 빠른 쪽: PostgreSQL                            source=console
INFO[0147] 배수: 11.7x                                     source=console
INFO[0147] ================================================================================  source=console

running (2m27.2s), 0/5 VUs, 27 complete and 0 interrupted iterations
large_data_test ✓ [======================================] 5 VUs  2m0s
jun@jun:~/distributed-log-pipeline$ 
jun@jun:~/distributed-log-pipeline$ k6 run ~/distributed-log-pipeline/k6/full_scan_test.js

         /\      Grafana   /‾‾/  
    /\  /  \     |\  __   /  /   
   /  \/    \    | |/ /  /   ‾‾\ 
  /          \   |   (  |  (‾)  |
 / __________ \  |_|\_\  \_____/ 

     execution: local
        script: /home/jun/distributed-log-pipeline/k6/full_scan_test.js
        output: -

     scenarios: (100.00%) 1 scenario, 10 max VUs, 3m30s max duration (incl. graceful stop):
              * full_scan_test: Up to 10 looping VUs for 3m0s over 4 stages (gracefulRampDown: 30s, gracefulStop: 30s)

INFO[0000] PostgreSQL host 집계: 841.39ms                  source=console
INFO[0013] HDFS host 집계: 11657.85ms                      source=console
INFO[0014] PostgreSQL service 집계: 477.7ms                source=console
INFO[0027] HDFS service 집계: 8633.69ms                    source=console
INFO[0028] PostgreSQL host 집계: 837.97ms                  source=console
INFO[0029] PostgreSQL service 집계: 463.29ms               source=console
INFO[0029] PostgreSQL level 집계: 422.41ms                 source=console
INFO[0038] HDFS host 집계: 8482.03ms                       source=console
INFO[0046] HDFS service 집계: 8415.13ms                    source=console
INFO[0055] HDFS level 집계: 8433.89ms                      source=console
INFO[0055] PostgreSQL host 집계: 824.46ms                  source=console
INFO[0056] PostgreSQL host 집계: 824.45ms                  source=console
INFO[0057] PostgreSQL service 집계: 450.49ms               source=console
INFO[0062] PostgreSQL host 집계: 839.59ms                  source=console
INFO[0070] HDFS host 집계: 8205.69ms                       source=console
INFO[0071] PostgreSQL service 집계: 438.41ms               source=console
INFO[0072] PostgreSQL host 집계: 819.43ms                  source=console
INFO[0080] HDFS host 집계: 8262.18ms                       source=console
INFO[0080] PostgreSQL service 집계: 448.2ms                source=console
INFO[0088] HDFS service 집계: 8089.24ms                    source=console
INFO[0097] HDFS host 집계: 8243.28ms                       source=console
INFO[0105] HDFS service 집계: 8239.62ms                    source=console
INFO[0113] HDFS host 집계: 7971.52ms                       source=console
INFO[0114] PostgreSQL host 집계: 819.73ms                  source=console
INFO[0122] HDFS service 집계: 8283.37ms                    source=console
INFO[0122] PostgreSQL level 집계: 408.36ms                 source=console
INFO[0123] PostgreSQL level 집계: 329.6ms                  source=console
INFO[0124] PostgreSQL host 집계: 838.95ms                  source=console
INFO[0125] PostgreSQL host 집계: 795.89ms                  source=console
INFO[0125] PostgreSQL level 집계: 427.39ms                 source=console
INFO[0126] PostgreSQL level 집계: 327.29ms                 source=console
INFO[0134] HDFS host 집계: 8059.34ms                       source=console
INFO[0134] PostgreSQL host 집계: 811.82ms                  source=console
INFO[0135] PostgreSQL service 집계: 433.74ms               source=console
INFO[0143] HDFS level 집계: 8297.61ms                      source=console
INFO[0151] HDFS level 집계: 8060.95ms                      source=console
INFO[0160] HDFS host 집계: 8287.23ms                       source=console
INFO[0160] PostgreSQL service 집계: 364.75ms               source=console
INFO[0168] HDFS host 집계: 7928.52ms                       source=console
INFO[0176] HDFS level 집계: 8054.63ms                      source=console
INFO[0184] HDFS level 집계: 8178.18ms                      source=console
WARN[0197] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs/aggregate?group_by=service\": request timeout"
INFO[0201] PostgreSQL level 집계: 409.07ms                 source=console
INFO[0201] PostgreSQL service 집계: 360.63ms               source=console
INFO[0210] 
================================================================================  source=console
INFO[0210] 전체 데이터 집계 테스트 결과 (Full Scan Test)             source=console
INFO[0210] ================================================================================  source=console
INFO[0210] PostgreSQL 평균: 583.96ms                       source=console
INFO[0210] HDFS 평균: 8409.68ms                            source=console
INFO[0210] 차이: 7825.72ms                                 source=console
INFO[0210] 더 빠른 쪽: PostgreSQL                            source=console
INFO[0210] ================================================================================  source=console

running (3m30.0s), 00/10 VUs, 19 complete and 6 interrupted iterations
full_scan_test ✓ [======================================] 01/10 VUs  3m0s
jun@jun:~/distributed-log-pipeline$ k6 run ~/distributed-log-pipeline/k6/sort_test.js

         /\      Grafana   /‾‾/  
    /\  /  \     |\  __   /  /   
   /  \/    \    | |/ /  /   ‾‾\ 
  /          \   |   (  |  (‾)  |
 / __________ \  |_|\_\  \_____/ 

     execution: local
        script: /home/jun/distributed-log-pipeline/k6/sort_test.js
        output: -

     scenarios: (100.00%) 1 scenario, 10 max VUs, 3m30s max duration (incl. graceful stop):
              * sort_test: Up to 10 looping VUs for 3m0s over 4 stages (gracefulRampDown: 30s, gracefulStop: 30s)

INFO[0008] PostgreSQL ORDER BY timestamp asc LIMIT 1000: 248.52ms  source=console
INFO[0008] PostgreSQL ORDER BY service desc LIMIT 1000: 229.75ms  source=console
INFO[0052] HDFS ORDER BY service desc LIMIT 1000: 21037ms  source=console
INFO[0052] PostgreSQL ORDER BY timestamp asc LIMIT 100: 207.35ms  source=console
INFO[0053] PostgreSQL ORDER BY service desc LIMIT 100: 239ms  source=console
INFO[0053] HDFS ORDER BY timestamp asc LIMIT 1000: 21552.05ms  source=console
INFO[0053] PostgreSQL ORDER BY level desc LIMIT 100: 221.05ms  source=console
INFO[0053] PostgreSQL ORDER BY timestamp asc LIMIT 1000: 247.53ms  source=console
INFO[0078] HDFS ORDER BY timestamp asc LIMIT 100: 20524.21ms  source=console
INFO[0099] HDFS ORDER BY service desc LIMIT 100: 20780.26ms  source=console
WARN[0114] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?order_by=level&order_dir=desc&limit=100\": request timeout"
WARN[0115] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?order_by=service&order_dir=desc&limit=500\": request timeout"
WARN[0116] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?order_by=service&order_dir=desc&limit=1000\": request timeout"
INFO[0120] HDFS ORDER BY level desc LIMIT 100: 21297.17ms  source=console
WARN[0126] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?order_by=timestamp&order_dir=desc&limit=500\": request timeout"
WARN[0138] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?order_by=timestamp&order_dir=desc&limit=100\": request timeout"
WARN[0141] Request Failed                                error="Get \"http://192.168.55.114:30801/api/query/postgres/logs?order_by=level&order_dir=asc&limit=100\": request timeout"
INFO[0141] HDFS ORDER BY timestamp asc LIMIT 1000: 20819.14ms  source=console
INFO[0142] PostgreSQL ORDER BY service desc LIMIT 500: 215.4ms  source=console
INFO[0142] PostgreSQL ORDER BY timestamp desc LIMIT 500: 224.01ms  source=console
WARN[0150] Request Failed                                error="request timeout"
INFO[0164] HDFS ORDER BY level desc LIMIT 100: 20774.18ms  source=console
INFO[0210] 
================================================================================  source=console
INFO[0210] 정렬 쿼리 테스트 결과 (Sort Test)                      source=console
INFO[0210] ================================================================================  source=console
INFO[0210] PostgreSQL 평균: 229.08ms, P95: 248.17ms        source=console
INFO[0210] HDFS 평균: 20969.14ms, P95: 21475.59ms          source=console
INFO[0210] 평균 차이: 20740.07ms                             source=console
INFO[0210] 더 빠른 쪽: PostgreSQL                            source=console
INFO[0210] 배수: 91.5x                                     source=console
INFO[0210] ================================================================================  source=console

running (3m30.0s), 00/10 VUs, 7 complete and 9 interrupted iterations
sort_test ✓ [======================================] 01/10 VUs  3m0s
jun@jun:~/distributed-log-pipeline$ k6 run ~/distributed-log-pipeline/k6/heavy_aggregate_test.js

         /\      Grafana   /‾‾/  
    /\  /  \     |\  __   /  /   
   /  \/    \    | |/ /  /   ‾‾\ 
  /          \   |   (  |  (‾)  |
 / __________ \  |_|\_\  \_____/ 

     execution: local
        script: /home/jun/distributed-log-pipeline/k6/heavy_aggregate_test.js
        output: -

     scenarios: (100.00%) 1 scenario, 5 max VUs, 3m30s max duration (incl. graceful stop):
              * heavy_aggregate_test: Up to 5 looping VUs for 3m0s over 4 stages (gracefulRampDown: 30s, gracefulStop: 30s)

INFO[0108] [호스트별집계+시간범위] PG: 880ms, HDFS: 8674ms         source=console
INFO[0116] [시간범위+집계] PG: 845ms, HDFS: 7950ms             source=console
INFO[0125] [호스트별집계+시간범위] PG: 847ms, HDFS: 7969ms         source=console
INFO[0133] [서비스별집계] PG: 404ms, HDFS: 8160ms              source=console
INFO[0142] [서비스별집계] PG: 376ms, HDFS: 8044ms              source=console
INFO[0155] [호스트별집계+시간범위] PG: 822ms, HDFS: 7896ms         source=console
INFO[0164] [시간범위+집계] PG: 831ms, HDFS: 7867ms             source=console
INFO[0172] [호스트별집계+시간범위] PG: 843ms, HDFS: 8012ms         source=console
INFO[0180] [서비스별집계] PG: 421ms, HDFS: 7799ms              source=console
INFO[0189] [서비스별집계] PG: 341ms, HDFS: 8210ms              source=console
INFO[0204] 
================================================================================  source=console
INFO[0204] 복잡한 집계 쿼리 테스트 결과 (Heavy Aggregate Test)       source=console
INFO[0204] ================================================================================  source=console
INFO[0204] PostgreSQL:                                   source=console
INFO[0204]   평균: 584.06ms                                source=console
INFO[0204]   P95: 861.97ms                               source=console
INFO[0204]   Min: 53.85ms, Max: 879.75ms                 source=console
INFO[0204]                                               source=console
INFO[0204] HDFS:                                         source=console
INFO[0204]   평균: 8058.10ms                               source=console
INFO[0204]   P95: 8465.03ms                              source=console
INFO[0204]   Min: 7798.58ms, Max: 8673.87ms              source=console
INFO[0204]                                               source=console
INFO[0204] 비교:                                           source=console
INFO[0204]   더 빠른 쪽: PostgreSQL                          source=console
INFO[0204]   배수: 13.8x                                   source=console
INFO[0204] ================================================================================  source=console

running (3m24.0s), 0/5 VUs, 10 complete and 2 interrupted iterations
heavy_aggregate_test ✓ [======================================] 0/5 VUs  3m0s
jun@jun:~/distributed-log-pipeline$ 
```
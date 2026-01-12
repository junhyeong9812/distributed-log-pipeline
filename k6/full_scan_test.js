import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// 메트릭 정의
const errorRate = new Rate('errors');
const pgFullScanTime = new Trend('pg_full_scan_time');
const hdfsFullScanTime = new Trend('hdfs_full_scan_time');

export const options = {
  scenarios: {
    full_scan_test: {
      executor: 'ramping-vus',
      startVUs: 1,
      stages: [
        { duration: '30s', target: 5 },
        { duration: '1m', target: 10 },
        { duration: '1m', target: 10 },
        { duration: '30s', target: 0 },
      ],
    },
  },
  thresholds: {
    errors: ['rate<0.3'],
  },
};

const BASE_URL = 'http://192.168.55.114:30801';

export default function () {
  const groupByOptions = ['level', 'service', 'host'];
  const groupBy = groupByOptions[Math.floor(Math.random() * groupByOptions.length)];

  // PostgreSQL 전체 집계
  const pgResponse = http.get(`${BASE_URL}/api/query/postgres/logs/aggregate?group_by=${groupBy}`, {
    timeout: '60s',
  });

  check(pgResponse, {
    'PG status is 200': (r) => r.status === 200,
  });

  try {
    const pgBody = JSON.parse(pgResponse.body);
    pgFullScanTime.add(pgBody.query_time_ms);
    console.log(`PostgreSQL ${groupBy} 집계: ${pgBody.query_time_ms}ms`);
  } catch (e) {}

  sleep(1);

  // HDFS 전체 집계
  const hdfsResponse = http.get(`${BASE_URL}/api/query/hdfs/logs/aggregate?group_by=${groupBy}`, {
    timeout: '120s',
  });

  check(hdfsResponse, {
    'HDFS status is 200': (r) => r.status === 200,
  });

  try {
    const hdfsBody = JSON.parse(hdfsResponse.body);
    hdfsFullScanTime.add(hdfsBody.query_time_ms);
    console.log(`HDFS ${groupBy} 집계: ${hdfsBody.query_time_ms}ms`);
  } catch (e) {}

  errorRate.add(pgResponse.status !== 200 || hdfsResponse.status !== 200);

  sleep(3);
}

export function handleSummary(data) {
  const pgAvg = data.metrics.pg_full_scan_time ? data.metrics.pg_full_scan_time.values.avg : 0;
  const hdfsAvg = data.metrics.hdfs_full_scan_time ? data.metrics.hdfs_full_scan_time.values.avg : 0;

  console.log('\n================================================================================');
  console.log('전체 데이터 집계 테스트 결과 (Full Scan Test)');
  console.log('================================================================================');
  console.log(`PostgreSQL 평균: ${pgAvg.toFixed(2)}ms`);
  console.log(`HDFS 평균: ${hdfsAvg.toFixed(2)}ms`);
  console.log(`차이: ${Math.abs(pgAvg - hdfsAvg).toFixed(2)}ms`);
  console.log(`더 빠른 쪽: ${pgAvg < hdfsAvg ? 'PostgreSQL' : 'HDFS'}`);
  console.log('================================================================================\n');

  return {
    'full_scan_test_result.json': JSON.stringify(data, null, 2),
  };
}
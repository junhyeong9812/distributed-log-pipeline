import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// 메트릭 정의
const errorRate = new Rate('errors');
const pgStatsTime = new Trend('pg_stats_time');
const hdfsStatsTime = new Trend('hdfs_stats_time');

export const options = {
  scenarios: {
    large_data_test: {
      executor: 'constant-vus',
      vus: 5,
      duration: '2m',
    },
  },
  thresholds: {
    errors: ['rate<0.3'],
  },
};

const BASE_URL = 'http://192.168.55.114:30801';

export default function () {
  // PostgreSQL 전체 통계 (COUNT(*))
  const pgStart = Date.now();
  const pgResponse = http.get(`${BASE_URL}/api/query/postgres/stats`, {
    timeout: '60s',
  });
  const pgElapsed = Date.now() - pgStart;

  check(pgResponse, {
    'PG status is 200': (r) => r.status === 200,
  });

  let pgData = {};
  try {
    pgData = JSON.parse(pgResponse.body);
    pgStatsTime.add(pgData.query_time_ms);
  } catch (e) {}

  sleep(1);

  // HDFS 전체 통계 (COUNT(*))
  const hdfsStart = Date.now();
  const hdfsResponse = http.get(`${BASE_URL}/api/query/hdfs/stats`, {
    timeout: '180s',
  });
  const hdfsElapsed = Date.now() - hdfsStart;

  check(hdfsResponse, {
    'HDFS status is 200': (r) => r.status === 200,
  });

  let hdfsData = {};
  try {
    hdfsData = JSON.parse(hdfsResponse.body);
    hdfsStatsTime.add(hdfsData.query_time_ms);
  } catch (e) {}

  console.log(`PG: ${pgData.logs_count || 0} logs in ${pgData.query_time_ms || 0}ms | HDFS: ${hdfsData.logs_count || 0} logs in ${hdfsData.query_time_ms || 0}ms`);

  errorRate.add(pgResponse.status !== 200 || hdfsResponse.status !== 200);

  sleep(3);
}

export function handleSummary(data) {
  const pgAvg = data.metrics.pg_stats_time ? data.metrics.pg_stats_time.values.avg : 0;
  const hdfsAvg = data.metrics.hdfs_stats_time ? data.metrics.hdfs_stats_time.values.avg : 0;

  console.log('\n================================================================================');
  console.log('대용량 데이터 스캔 테스트 결과 (Large Data Scan - COUNT(*))');
  console.log('================================================================================');
  console.log(`데이터 규모: 약 500만건`);
  console.log('');
  console.log(`PostgreSQL COUNT(*) 평균: ${pgAvg.toFixed(2)}ms`);
  console.log(`HDFS COUNT(*) 평균: ${hdfsAvg.toFixed(2)}ms`);
  console.log('');
  console.log(`더 빠른 쪽: ${pgAvg < hdfsAvg ? 'PostgreSQL' : 'HDFS'}`);
  console.log(`배수: ${(Math.max(pgAvg, hdfsAvg) / Math.min(pgAvg, hdfsAvg)).toFixed(1)}x`);
  console.log('================================================================================\n');

  return {
    'large_data_test_result.json': JSON.stringify(data, null, 2),
  };
}
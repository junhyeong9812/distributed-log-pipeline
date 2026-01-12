import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// 메트릭 정의
const errorRate = new Rate('errors');
const pgSortTime = new Trend('pg_sort_time');
const hdfsSortTime = new Trend('hdfs_sort_time');

export const options = {
  scenarios: {
    sort_test: {
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
  const orderByOptions = ['timestamp', 'level', 'service', 'id'];
  const orderDirOptions = ['asc', 'desc'];
  const limitOptions = [100, 500, 1000];

  const orderBy = orderByOptions[Math.floor(Math.random() * orderByOptions.length)];
  const orderDir = orderDirOptions[Math.floor(Math.random() * orderDirOptions.length)];
  const limit = limitOptions[Math.floor(Math.random() * limitOptions.length)];

  // PostgreSQL 정렬 쿼리
  const pgResponse = http.get(
    `${BASE_URL}/api/query/postgres/logs?order_by=${orderBy}&order_dir=${orderDir}&limit=${limit}`,
    { timeout: '60s' }
  );

  check(pgResponse, {
    'PG status is 200': (r) => r.status === 200,
  });

  try {
    const pgBody = JSON.parse(pgResponse.body);
    pgSortTime.add(pgBody.query_time_ms);
    console.log(`PostgreSQL ORDER BY ${orderBy} ${orderDir} LIMIT ${limit}: ${pgBody.query_time_ms}ms`);
  } catch (e) {}

  sleep(1);

  // HDFS 정렬 쿼리
  const hdfsResponse = http.get(
    `${BASE_URL}/api/query/hdfs/logs?order_by=${orderBy}&order_dir=${orderDir}&limit=${limit}`,
    { timeout: '120s' }
  );

  check(hdfsResponse, {
    'HDFS status is 200': (r) => r.status === 200,
  });

  try {
    const hdfsBody = JSON.parse(hdfsResponse.body);
    hdfsSortTime.add(hdfsBody.query_time_ms);
    console.log(`HDFS ORDER BY ${orderBy} ${orderDir} LIMIT ${limit}: ${hdfsBody.query_time_ms}ms`);
  } catch (e) {}

  errorRate.add(pgResponse.status !== 200 || hdfsResponse.status !== 200);

  sleep(3);
}

export function handleSummary(data) {
  const pgAvg = data.metrics.pg_sort_time ? data.metrics.pg_sort_time.values.avg : 0;
  const pgP95 = data.metrics.pg_sort_time ? data.metrics.pg_sort_time.values['p(95)'] : 0;
  const hdfsAvg = data.metrics.hdfs_sort_time ? data.metrics.hdfs_sort_time.values.avg : 0;
  const hdfsP95 = data.metrics.hdfs_sort_time ? data.metrics.hdfs_sort_time.values['p(95)'] : 0;

  console.log('\n================================================================================');
  console.log('정렬 쿼리 테스트 결과 (Sort Test)');
  console.log('================================================================================');
  console.log(`PostgreSQL 평균: ${pgAvg.toFixed(2)}ms, P95: ${pgP95.toFixed(2)}ms`);
  console.log(`HDFS 평균: ${hdfsAvg.toFixed(2)}ms, P95: ${hdfsP95.toFixed(2)}ms`);
  console.log(`평균 차이: ${Math.abs(pgAvg - hdfsAvg).toFixed(2)}ms`);
  console.log(`더 빠른 쪽: ${pgAvg < hdfsAvg ? 'PostgreSQL' : 'HDFS'}`);
  console.log(`배수: ${(hdfsAvg / pgAvg).toFixed(1)}x`);
  console.log('================================================================================\n');

  return {
    'sort_test_result.json': JSON.stringify(data, null, 2),
  };
}
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// 메트릭 정의
const errorRate = new Rate('errors');
const pgHeavyTime = new Trend('pg_heavy_time');
const hdfsHeavyTime = new Trend('hdfs_heavy_time');

export const options = {
  scenarios: {
    heavy_aggregate_test: {
      executor: 'ramping-vus',
      startVUs: 1,
      stages: [
        { duration: '30s', target: 3 },
        { duration: '1m', target: 5 },
        { duration: '1m', target: 5 },
        { duration: '30s', target: 0 },
      ],
    },
  },
  thresholds: {
    errors: ['rate<0.5'],
  },
};

const BASE_URL = 'http://192.168.55.114:30801';

// 현재 시간 기준 시간 범위 생성 (최근 1시간)
function getTimeRange() {
  const now = Date.now() / 1000;
  const oneHourAgo = now - 3600;
  return { start: oneHourAgo, end: now };
}

export default function () {
  const testCase = Math.floor(Math.random() * 4);
  const { start, end } = getTimeRange();

  let pgUrl, hdfsUrl, testName;

  switch (testCase) {
    case 0:
      // 시간 범위 + 집계
      testName = '시간범위+집계';
      pgUrl = `${BASE_URL}/api/query/postgres/logs/aggregate?group_by=level&start_time=${start}&end_time=${end}`;
      hdfsUrl = `${BASE_URL}/api/query/hdfs/logs/aggregate?group_by=level&start_time=${start}&end_time=${end}`;
      break;
    case 1:
      // 조건 + 정렬 + 대량 조회
      testName = '조건+정렬+대량조회';
      pgUrl = `${BASE_URL}/api/query/postgres/logs?level=ERROR&order_by=timestamp&order_dir=desc&limit=1000`;
      hdfsUrl = `${BASE_URL}/api/query/hdfs/logs?level=ERROR&order_by=timestamp&order_dir=desc&limit=1000`;
      break;
    case 2:
      // 서비스별 집계
      testName = '서비스별집계';
      pgUrl = `${BASE_URL}/api/query/postgres/logs/aggregate?group_by=service`;
      hdfsUrl = `${BASE_URL}/api/query/hdfs/logs/aggregate?group_by=service`;
      break;
    case 3:
      // 호스트별 집계 + 시간 범위
      testName = '호스트별집계+시간범위';
      pgUrl = `${BASE_URL}/api/query/postgres/logs/aggregate?group_by=host&start_time=${start}&end_time=${end}`;
      hdfsUrl = `${BASE_URL}/api/query/hdfs/logs/aggregate?group_by=host&start_time=${start}&end_time=${end}`;
      break;
  }

  // PostgreSQL 쿼리
  const pgResponse = http.get(pgUrl, { timeout: '120s' });

  check(pgResponse, {
    'PG status is 200': (r) => r.status === 200,
  });

  let pgTime = 0;
  try {
    const pgBody = JSON.parse(pgResponse.body);
    pgTime = pgBody.query_time_ms;
    pgHeavyTime.add(pgTime);
  } catch (e) {}

  sleep(1);

  // HDFS 쿼리
  const hdfsResponse = http.get(hdfsUrl, { timeout: '180s' });

  check(hdfsResponse, {
    'HDFS status is 200': (r) => r.status === 200,
  });

  let hdfsTime = 0;
  try {
    const hdfsBody = JSON.parse(hdfsResponse.body);
    hdfsTime = hdfsBody.query_time_ms;
    hdfsHeavyTime.add(hdfsTime);
  } catch (e) {}

  console.log(`[${testName}] PG: ${pgTime.toFixed(0)}ms, HDFS: ${hdfsTime.toFixed(0)}ms`);

  errorRate.add(pgResponse.status !== 200 || hdfsResponse.status !== 200);

  sleep(5);
}

export function handleSummary(data) {
  const pgAvg = data.metrics.pg_heavy_time ? data.metrics.pg_heavy_time.values.avg : 0;
  const pgP95 = data.metrics.pg_heavy_time ? data.metrics.pg_heavy_time.values['p(95)'] : 0;
  const pgMin = data.metrics.pg_heavy_time ? data.metrics.pg_heavy_time.values.min : 0;
  const pgMax = data.metrics.pg_heavy_time ? data.metrics.pg_heavy_time.values.max : 0;

  const hdfsAvg = data.metrics.hdfs_heavy_time ? data.metrics.hdfs_heavy_time.values.avg : 0;
  const hdfsP95 = data.metrics.hdfs_heavy_time ? data.metrics.hdfs_heavy_time.values['p(95)'] : 0;
  const hdfsMin = data.metrics.hdfs_heavy_time ? data.metrics.hdfs_heavy_time.values.min : 0;
  const hdfsMax = data.metrics.hdfs_heavy_time ? data.metrics.hdfs_heavy_time.values.max : 0;

  console.log('\n================================================================================');
  console.log('복잡한 집계 쿼리 테스트 결과 (Heavy Aggregate Test)');
  console.log('================================================================================');
  console.log('PostgreSQL:');
  console.log(`  평균: ${pgAvg.toFixed(2)}ms`);
  console.log(`  P95: ${pgP95.toFixed(2)}ms`);
  console.log(`  Min: ${pgMin.toFixed(2)}ms, Max: ${pgMax.toFixed(2)}ms`);
  console.log('');
  console.log('HDFS:');
  console.log(`  평균: ${hdfsAvg.toFixed(2)}ms`);
  console.log(`  P95: ${hdfsP95.toFixed(2)}ms`);
  console.log(`  Min: ${hdfsMin.toFixed(2)}ms, Max: ${hdfsMax.toFixed(2)}ms`);
  console.log('');
  console.log('비교:');
  console.log(`  더 빠른 쪽: ${pgAvg < hdfsAvg ? 'PostgreSQL' : 'HDFS'}`);
  console.log(`  배수: ${(hdfsAvg / pgAvg).toFixed(1)}x`);
  console.log('================================================================================\n');

  return {
    'heavy_aggregate_test_result.json': JSON.stringify(data, null, 2),
  };
}
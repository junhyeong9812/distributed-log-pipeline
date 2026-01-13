// k6/phase6/direct_comparison.js
// PostgreSQL vs HDFS 직접 비교 테스트

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const errorRate = new Rate('errors');
const pgCountTime = new Trend('pg_count_time');
const hdfsCountTime = new Trend('hdfs_count_time');
const pgAggTime = new Trend('pg_agg_time');
const hdfsAggTime = new Trend('hdfs_agg_time');

export const options = {
  scenarios: {
    direct_comparison: {
      executor: 'ramping-vus',
      startVUs: 1,
      stages: [
        { duration: '30s', target: 3 },
        { duration: '2m', target: 5 },
        { duration: '2m', target: 5 },
        { duration: '30s', target: 0 },
      ],
    },
  },
  thresholds: {
    errors: ['rate<0.20'],
  },
};

const BASE_URL = 'http://192.168.55.114:30801';

export default function () {
  const testType = Math.random() < 0.5 ? 'count' : 'aggregate';

  if (testType === 'count') {
    // PostgreSQL COUNT
    const pgResponse = http.get(`${BASE_URL}/api/query/postgres/stats`, {
      timeout: '120s',
    });

    check(pgResponse, { 'PG COUNT 200': (r) => r.status === 200 });

    try {
      const pgBody = JSON.parse(pgResponse.body);
      pgCountTime.add(pgBody.query_time_ms);
      console.log(`PG COUNT: ${pgBody.query_time_ms}ms`);
    } catch (e) {}

    sleep(1);

    // HDFS COUNT
    const hdfsResponse = http.get(`${BASE_URL}/api/query/hdfs/stats`, {
      timeout: '300s',
    });

    check(hdfsResponse, { 'HDFS COUNT 200': (r) => r.status === 200 });

    try {
      const hdfsBody = JSON.parse(hdfsResponse.body);
      hdfsCountTime.add(hdfsBody.query_time_ms);
      console.log(`HDFS COUNT: ${hdfsBody.query_time_ms}ms`);
    } catch (e) {}

  } else {
    // PostgreSQL AGGREGATE
    const pgResponse = http.get(`${BASE_URL}/api/query/postgres/logs/aggregate?group_by=service`, {
      timeout: '120s',
    });

    check(pgResponse, { 'PG AGG 200': (r) => r.status === 200 });

    try {
      const pgBody = JSON.parse(pgResponse.body);
      pgAggTime.add(pgBody.query_time_ms);
      console.log(`PG AGG: ${pgBody.query_time_ms}ms`);
    } catch (e) {}

    sleep(1);

    // HDFS AGGREGATE
    const hdfsResponse = http.get(`${BASE_URL}/api/query/hdfs/logs/aggregate?group_by=service`, {
      timeout: '300s',
    });

    check(hdfsResponse, { 'HDFS AGG 200': (r) => r.status === 200 });

    try {
      const hdfsBody = JSON.parse(hdfsResponse.body);
      hdfsAggTime.add(hdfsBody.query_time_ms);
      console.log(`HDFS AGG: ${hdfsBody.query_time_ms}ms`);
    } catch (e) {}
  }

  errorRate.add(false);
  sleep(5);
}

export function handleSummary(data) {
  const pgCountAvg = data.metrics.pg_count_time ? data.metrics.pg_count_time.values.avg : 0;
  const hdfsCountAvg = data.metrics.hdfs_count_time ? data.metrics.hdfs_count_time.values.avg : 0;
  const pgAggAvg = data.metrics.pg_agg_time ? data.metrics.pg_agg_time.values.avg : 0;
  const hdfsAggAvg = data.metrics.hdfs_agg_time ? data.metrics.hdfs_agg_time.values.avg : 0;

  console.log('\n' + '='.repeat(70));
  console.log('PostgreSQL vs HDFS 직접 비교 결과');
  console.log('='.repeat(70));
  console.log('');
  console.log('COUNT(*) 쿼리:');
  console.log(`  PostgreSQL 평균: ${pgCountAvg.toFixed(2)} ms`);
  console.log(`  HDFS 평균: ${hdfsCountAvg.toFixed(2)} ms`);
  console.log(`  승자: ${pgCountAvg < hdfsCountAvg ? 'PostgreSQL' : 'HDFS'} (${Math.abs(pgCountAvg - hdfsCountAvg).toFixed(2)}ms 차이)`);
  console.log('');
  console.log('GROUP BY 집계 쿼리:');
  console.log(`  PostgreSQL 평균: ${pgAggAvg.toFixed(2)} ms`);
  console.log(`  HDFS 평균: ${hdfsAggAvg.toFixed(2)} ms`);
  console.log(`  승자: ${pgAggAvg < hdfsAggAvg ? 'PostgreSQL' : 'HDFS'} (${Math.abs(pgAggAvg - hdfsAggAvg).toFixed(2)}ms 차이)`);
  console.log('='.repeat(70) + '\n');

  return {
    'k6/phase6/results/comparison_result.json': JSON.stringify(data, null, 2),
  };
}
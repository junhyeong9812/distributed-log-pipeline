// k6/phase6/pg_aggregate_load.js
// PostgreSQL 집계 쿼리 부하 테스트

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

const errorRate = new Rate('errors');
const pgAggregateTime = new Trend('pg_aggregate_time');
const successCount = new Counter('success_count');

export const options = {
  scenarios: {
    pg_aggregate_load: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '30s', target: 5 },
        { duration: '1m', target: 10 },
        { duration: '1m', target: 20 },
        { duration: '1m', target: 20 },
        { duration: '30s', target: 10 },
        { duration: '30s', target: 0 },
      ],
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<60000'],
    errors: ['rate<0.05'],
  },
};

const BASE_URL = 'http://192.168.55.114:30801';
const groupByOptions = ['level', 'service', 'host'];

export default function () {
  const groupBy = groupByOptions[Math.floor(Math.random() * groupByOptions.length)];
  const url = `${BASE_URL}/api/query/postgres/logs/aggregate?group_by=${groupBy}`;

  const response = http.get(url, {
    timeout: '120s',
  });

  const isSuccess = check(response, {
    'status is 200': (r) => r.status === 200,
    'has data': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.data && body.data.length > 0;
      } catch (e) {
        return false;
      }
    },
  });

  if (isSuccess) {
    successCount.add(1);
    try {
      const body = JSON.parse(response.body);
      pgAggregateTime.add(body.query_time_ms);
    } catch (e) {}
  }

  errorRate.add(!isSuccess);

  sleep(2);
}

export function handleSummary(data) {
  const avgTime = data.metrics.pg_aggregate_time ? data.metrics.pg_aggregate_time.values.avg : 0;
  const p95Time = data.metrics.pg_aggregate_time ? data.metrics.pg_aggregate_time.values['p(95)'] : 0;
  const errRate = data.metrics.errors ? data.metrics.errors.values.rate : 0;
  const totalReqs = data.metrics.http_reqs ? data.metrics.http_reqs.values.count : 0;

  console.log('\n' + '='.repeat(70));
  console.log('PostgreSQL 집계 쿼리 부하 테스트 결과');
  console.log('='.repeat(70));
  console.log(`총 요청 수: ${totalReqs}`);
  console.log(`평균 응답 시간: ${avgTime.toFixed(2)} ms`);
  console.log(`P95 응답 시간: ${p95Time.toFixed(2)} ms`);
  console.log(`에러율: ${(errRate * 100).toFixed(2)}%`);
  console.log('='.repeat(70) + '\n');

  return {
    'k6/phase6/results/pg_aggregate_result.json': JSON.stringify(data, null, 2),
  };
}
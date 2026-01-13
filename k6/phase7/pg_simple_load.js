// k6/phase7/pg_simple_load.js
// PostgreSQL 단순 조회 부하 테스트 (적정 VU)

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

const errorRate = new Rate('errors');
const pgQueryTime = new Trend('pg_query_time');
const successCount = new Counter('success_count');

export const options = {
  scenarios: {
    pg_simple_load: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '30s', target: 2 },   // 웜업
        { duration: '1m', target: 5 },    // 목표 도달
        { duration: '2m', target: 5 },    // 유지
        { duration: '30s', target: 0 },   // 종료
      ],
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<10000'],  // P95 10초 이내
    errors: ['rate<0.05'],                // 에러율 5% 미만
  },
};

const BASE_URL = 'http://192.168.55.114:30801';

export default function () {
  const url = `${BASE_URL}/api/query/postgres/logs?limit=100`;

  const response = http.get(url, {
    timeout: '60s',
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
      pgQueryTime.add(body.query_time_ms);
    } catch (e) {}
  }

  errorRate.add(!isSuccess);

  sleep(1);
}

export function handleSummary(data) {
  const avgTime = data.metrics.pg_query_time ? data.metrics.pg_query_time.values.avg : 0;
  const p95Time = data.metrics.pg_query_time ? data.metrics.pg_query_time.values['p(95)'] : 0;
  const minTime = data.metrics.pg_query_time ? data.metrics.pg_query_time.values.min : 0;
  const maxTime = data.metrics.pg_query_time ? data.metrics.pg_query_time.values.max : 0;
  const errRate = data.metrics.errors ? data.metrics.errors.values.rate : 0;
  const totalReqs = data.metrics.http_reqs ? data.metrics.http_reqs.values.count : 0;
  const successReqs = data.metrics.success_count ? data.metrics.success_count.values.count : 0;

  console.log('\n' + '='.repeat(70));
  console.log('Phase 7: PostgreSQL 단순 조회 부하 테스트 결과');
  console.log('='.repeat(70));
  console.log(`설정: VU 0→2→5→5→0, 총 4분`);
  console.log('-'.repeat(70));
  console.log(`총 요청 수: ${totalReqs}`);
  console.log(`성공 요청 수: ${successReqs}`);
  console.log(`에러율: ${(errRate * 100).toFixed(2)}%`);
  console.log('-'.repeat(70));
  console.log(`평균 응답 시간: ${avgTime.toFixed(2)} ms`);
  console.log(`P95 응답 시간: ${p95Time.toFixed(2)} ms`);
  console.log(`최소 응답 시간: ${minTime.toFixed(2)} ms`);
  console.log(`최대 응답 시간: ${maxTime.toFixed(2)} ms`);
  console.log('-'.repeat(70));
  console.log(`결과: ${errRate < 0.05 && p95Time < 10000 ? 'PASS ✓' : 'FAIL ✗'}`);
  console.log('='.repeat(70) + '\n');

  return {
    'k6/phase7/results/pg_simple_result.json': JSON.stringify(data, null, 2),
  };
}
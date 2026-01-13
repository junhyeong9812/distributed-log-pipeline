// k6/phase6/pg_simple_load.js
// PostgreSQL 단순 조회 부하 테스트

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// 커스텀 메트릭
const errorRate = new Rate('errors');
const pgQueryTime = new Trend('pg_query_time');
const successCount = new Counter('success_count');

export const options = {
  scenarios: {
    pg_simple_load: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '30s', target: 10 },   // 웜업
        { duration: '1m', target: 30 },    // 증가
        { duration: '1m', target: 50 },    // 피크
        { duration: '1m', target: 50 },    // 유지
        { duration: '30s', target: 30 },   // 감소
        { duration: '30s', target: 0 },    // 종료
      ],
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<30000'],  // 95%가 30초 이내
    errors: ['rate<0.05'],                // 에러율 5% 미만
  },
};

const BASE_URL = 'http://192.168.55.114:30801';

export default function () {
  const url = `${BASE_URL}/api/query/postgres/logs?limit=100`;

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
      pgQueryTime.add(body.query_time_ms);
    } catch (e) {}
  }

  errorRate.add(!isSuccess);

  sleep(1);
}

export function handleSummary(data) {
  const avgTime = data.metrics.pg_query_time ? data.metrics.pg_query_time.values.avg : 0;
  const p95Time = data.metrics.pg_query_time ? data.metrics.pg_query_time.values['p(95)'] : 0;
  const errRate = data.metrics.errors ? data.metrics.errors.values.rate : 0;
  const totalReqs = data.metrics.http_reqs ? data.metrics.http_reqs.values.count : 0;

  console.log('\n' + '='.repeat(70));
  console.log('PostgreSQL 단순 조회 부하 테스트 결과');
  console.log('='.repeat(70));
  console.log(`총 요청 수: ${totalReqs}`);
  console.log(`평균 응답 시간: ${avgTime.toFixed(2)} ms`);
  console.log(`P95 응답 시간: ${p95Time.toFixed(2)} ms`);
  console.log(`에러율: ${(errRate * 100).toFixed(2)}%`);
  console.log('='.repeat(70) + '\n');

  return {
    'k6/phase6/results/pg_simple_result.json': JSON.stringify(data, null, 2),
  };
}
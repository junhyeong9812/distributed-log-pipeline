// k6/phase6/hdfs_simple_load.js
// HDFS 단순 조회 부하 테스트

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

const errorRate = new Rate('errors');
const hdfsQueryTime = new Trend('hdfs_query_time');
const successCount = new Counter('success_count');

export const options = {
  scenarios: {
    hdfs_simple_load: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '30s', target: 3 },
        { duration: '1m', target: 5 },
        { duration: '1m', target: 10 },
        { duration: '1m', target: 10 },
        { duration: '30s', target: 5 },
        { duration: '30s', target: 0 },
      ],
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<120000'],
    errors: ['rate<0.10'],
  },
};

const BASE_URL = 'http://192.168.55.114:30801';

export default function () {
  const url = `${BASE_URL}/api/query/hdfs/logs?limit=100`;

  const response = http.get(url, {
    timeout: '300s',
  });

  const isSuccess = check(response, {
    'status is 200': (r) => r.status === 200,
  });

  if (isSuccess) {
    successCount.add(1);
    try {
      const body = JSON.parse(response.body);
      hdfsQueryTime.add(body.query_time_ms);
    } catch (e) {}
  }

  errorRate.add(!isSuccess);

  sleep(3);
}

export function handleSummary(data) {
  const avgTime = data.metrics.hdfs_query_time ? data.metrics.hdfs_query_time.values.avg : 0;
  const p95Time = data.metrics.hdfs_query_time ? data.metrics.hdfs_query_time.values['p(95)'] : 0;
  const errRate = data.metrics.errors ? data.metrics.errors.values.rate : 0;
  const totalReqs = data.metrics.http_reqs ? data.metrics.http_reqs.values.count : 0;

  console.log('\n' + '='.repeat(70));
  console.log('HDFS 단순 조회 부하 테스트 결과');
  console.log('='.repeat(70));
  console.log(`총 요청 수: ${totalReqs}`);
  console.log(`평균 응답 시간: ${avgTime.toFixed(2)} ms`);
  console.log(`P95 응답 시간: ${p95Time.toFixed(2)} ms`);
  console.log(`에러율: ${(errRate * 100).toFixed(2)}%`);
  console.log('='.repeat(70) + '\n');

  return {
    'k6/phase6/results/hdfs_simple_result.json': JSON.stringify(data, null, 2),
  };
}
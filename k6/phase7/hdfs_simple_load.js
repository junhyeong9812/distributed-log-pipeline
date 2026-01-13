// k6/phase7/hdfs_simple_load.js
// timeout 3분으로 변경, stats 엔드포인트 사용

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
        { duration: '30s', target: 1 },
        { duration: '1m', target: 2 },
        { duration: '2m', target: 2 },
        { duration: '30s', target: 0 },
      ],
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<30000'],
    errors: ['rate<0.10'],
  },
};

const BASE_URL = 'http://192.168.55.114:30801';

export default function () {
  // stats 엔드포인트 사용 (COUNT - 12초)
  const url = `${BASE_URL}/api/query/hdfs/stats`;

  const response = http.get(url, {
    timeout: '180s',  // 3분 타임아웃
  });

  const isSuccess = check(response, {
    'status is 200': (r) => r.status === 200,
    'has logs_count': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.logs_count > 0;
      } catch (e) {
        return false;
      }
    },
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
  const minTime = data.metrics.hdfs_query_time ? data.metrics.hdfs_query_time.values.min : 0;
  const maxTime = data.metrics.hdfs_query_time ? data.metrics.hdfs_query_time.values.max : 0;
  const errRate = data.metrics.errors ? data.metrics.errors.values.rate : 0;
  const totalReqs = data.metrics.http_reqs ? data.metrics.http_reqs.values.count : 0;
  const successReqs = data.metrics.success_count ? data.metrics.success_count.values.count : 0;

  console.log('\n' + '='.repeat(70));
  console.log('Phase 7: HDFS COUNT 부하 테스트 결과');
  console.log('='.repeat(70));
  console.log(`설정: VU 0→1→2→2→0, 총 4분`);
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
  console.log(`결과: ${errRate < 0.10 && p95Time < 30000 ? 'PASS ✓' : 'FAIL ✗'}`);
  console.log('='.repeat(70) + '\n');

  return {
    'k6/phase7/results/hdfs_simple_result.json': JSON.stringify(data, null, 2),
  };
}
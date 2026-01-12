import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const errorRate = new Rate('errors');
const pgTime = new Trend('pg_response_time');
const hdfsTime = new Trend('hdfs_response_time');

export const options = {
  scenarios: {
    comparison_test: {
      executor: 'ramping-vus',
      startVUs: 1,
      stages: [
        { duration: '30s', target: 10 },
        { duration: '1m', target: 20 },
        { duration: '30s', target: 10 },
        { duration: '30s', target: 0 },
      ],
    },
  },
  thresholds: {
    errors: ['rate<0.2'],
  },
};

const BASE_URL = 'http://192.168.55.114:30801';

export default function () {
  const response = http.get(`${BASE_URL}/api/query/compare?level=ERROR&limit=100`, {
    timeout: '120s',
  });
  
  check(response, {
    'status is 200': (r) => r.status === 200,
  });
  
  errorRate.add(response.status !== 200);
  
  try {
    const body = JSON.parse(response.body);
    pgTime.add(body.comparison.postgresql_ms);
    hdfsTime.add(body.comparison.hdfs_ms);
  } catch (e) {}
  
  sleep(5);
}

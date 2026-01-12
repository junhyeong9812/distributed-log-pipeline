import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const errorRate = new Rate('errors');
const hdfsQueryTime = new Trend('hdfs_query_time');

export const options = {
  scenarios: {
    ramping_load: {
      executor: 'ramping-vus',
      startVUs: 1,
      stages: [
        { duration: '30s', target: 5 },
        { duration: '1m', target: 10 },
        { duration: '30s', target: 20 },
        { duration: '1m', target: 20 },
        { duration: '30s', target: 0 },
      ],
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<30000'],
    errors: ['rate<0.2'],
  },
};

const BASE_URL = 'http://192.168.55.114:30801';

export default function () {
  const response = http.get(`${BASE_URL}/api/query/hdfs/logs?limit=100`, {
    timeout: '60s',
  });
  
  check(response, {
    'status is 200': (r) => r.status === 200,
  });
  
  errorRate.add(response.status !== 200);
  
  try {
    const body = JSON.parse(response.body);
    hdfsQueryTime.add(body.query_time_ms);
  } catch (e) {}
  
  sleep(3);
}

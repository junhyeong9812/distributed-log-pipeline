import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const errorRate = new Rate('errors');
const pgAggregateTime = new Trend('pg_aggregate_time');

export const options = {
  scenarios: {
    ramping_load: {
      executor: 'ramping-vus',
      startVUs: 1,
      stages: [
        { duration: '30s', target: 10 },
        { duration: '1m', target: 30 },
        { duration: '30s', target: 50 },
        { duration: '1m', target: 50 },
        { duration: '30s', target: 0 },
      ],
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<1000'],
    errors: ['rate<0.1'],
  },
};

const BASE_URL = 'http://192.168.55.114:30801';
const groupByOptions = ['level', 'service', 'host'];

export default function () {
  const groupBy = groupByOptions[Math.floor(Math.random() * groupByOptions.length)];
  const response = http.get(`${BASE_URL}/api/query/postgres/logs/aggregate?group_by=${groupBy}`);
  
  check(response, {
    'status is 200': (r) => r.status === 200,
    'response has data': (r) => JSON.parse(r.body).data.length > 0,
  });
  
  errorRate.add(response.status !== 200);
  
  try {
    const body = JSON.parse(response.body);
    pgAggregateTime.add(body.query_time_ms);
  } catch (e) {}
  
  sleep(1);
}

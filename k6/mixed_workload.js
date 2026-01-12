import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const errorRate = new Rate('errors');
const simpleQueryTime = new Trend('simple_query_time');
const conditionQueryTime = new Trend('condition_query_time');
const aggregateQueryTime = new Trend('aggregate_query_time');
const statsQueryTime = new Trend('stats_query_time');

export const options = {
  scenarios: {
    mixed_workload: {
      executor: 'ramping-vus',
      startVUs: 1,
      stages: [
        { duration: '30s', target: 20 },
        { duration: '1m', target: 50 },
        { duration: '30s', target: 100 },
        { duration: '2m', target: 100 },
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

export default function () {
  const random = Math.random() * 100;
  let response;
  
  if (random <= 40) {
    response = http.get(`${BASE_URL}/api/query/postgres/logs?limit=100`);
    try { simpleQueryTime.add(JSON.parse(response.body).query_time_ms); } catch (e) {}
  } else if (random <= 70) {
    const levels = ['INFO', 'DEBUG', 'WARN', 'ERROR'];
    const level = levels[Math.floor(Math.random() * levels.length)];
    response = http.get(`${BASE_URL}/api/query/postgres/logs?level=${level}&limit=100`);
    try { conditionQueryTime.add(JSON.parse(response.body).query_time_ms); } catch (e) {}
  } else if (random <= 90) {
    const groupBy = ['level', 'service', 'host'][Math.floor(Math.random() * 3)];
    response = http.get(`${BASE_URL}/api/query/postgres/logs/aggregate?group_by=${groupBy}`);
    try { aggregateQueryTime.add(JSON.parse(response.body).query_time_ms); } catch (e) {}
  } else {
    response = http.get(`${BASE_URL}/api/query/postgres/stats`);
    try { statsQueryTime.add(JSON.parse(response.body).query_time_ms); } catch (e) {}
  }
  
  check(response, { 'status is 200': (r) => r.status === 200 });
  errorRate.add(response.status !== 200);
  
  sleep(0.5);
}

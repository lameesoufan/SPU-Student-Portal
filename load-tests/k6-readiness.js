import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  scenarios: {
    readiness_200_users: {
      executor: 'ramping-vus',
      stages: [
        { duration: '2m', target: 50 },
        { duration: '3m', target: 200 },
        { duration: '5m', target: 200 },
        { duration: '2m', target: 0 },
      ],
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.02'],
    http_req_duration: ['p(95)<800', 'p(99)<1500'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const USERNAME = __ENV.K6_USERNAME;
const PASSWORD = __ENV.K6_PASSWORD;

export function setup() {
  if (!USERNAME || !PASSWORD) return { headers: {} };

  const res = http.post(
    `${BASE_URL}/api/token/`,
    JSON.stringify({ username: USERNAME, password: PASSWORD }),
    { headers: { 'Content-Type': 'application/json' } }
  );

  check(res, { 'login succeeded': (r) => r.status === 200 && r.json('access') });
  return { headers: { Authorization: `Bearer ${res.json('access')}` } };
}

export default function (data) {
  const endpoints = [
    ['/api/projects/ideas/browse/', 'browse ideas'],
    ['/api/notifications/unread-count/', 'unread notifications'],
    ['/api/project-management/board/', 'student board'],
    ['/api/workflow/templates/', 'workflow templates'],
    ['/api/workflow/available-projects/', 'available workflow projects'],
    ['/api/projects/proposals/pending-hod/', 'hod pending proposals'],
  ];

  const [path, name] = endpoints[Math.floor(Math.random() * endpoints.length)];
  const res = http.get(`${BASE_URL}${path}`, { headers: data.headers, tags: { endpoint: name } });
  check(res, {
    [`${name} returned non-5xx`]: (r) => r.status < 500,
    [`${name} completed under 1500ms`]: (r) => r.timings.duration < 1500,
  });
  sleep(Math.random() * 3 + 1);
}

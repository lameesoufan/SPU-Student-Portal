# Load Test Runbook

## Scope
This runbook validates the portal against a 200 concurrent user target with authenticated read-heavy traffic plus review/dashboard endpoints.

## Prerequisites
- Seed realistic data: at least 1,000 approved ideas, 1,000 project boards, 10,000 notifications, 500 workflow templates/projects, and representative pending review queues.
- Use PostgreSQL for the test environment. SQLite results are not valid for 200-user readiness.
- Set `BASE_URL`, `LOCUST_USERNAME`/`LOCUST_PASSWORD`, and `K6_USERNAME`/`K6_PASSWORD` to test accounts with appropriate permissions.

## Locust
Run:

```bash
locust -f load-tests/locustfile.py --host http://localhost:8000 --users 200 --spawn-rate 20 --run-time 10m
```

Pass thresholds:
- Error rate below 2%.
- p95 response time below 800 ms for read endpoints.
- No sustained database CPU saturation above 75%.
- No worker timeouts or repeated 429 responses for normal authenticated traffic.

## k6
Run:

```bash
k6 run -e BASE_URL=http://localhost:8000 -e K6_USERNAME=testuser -e K6_PASSWORD=testpass load-tests/k6-readiness.js
```

Pass thresholds are encoded in `load-tests/k6-readiness.js`:
- `http_req_failed < 2%`.
- `p95 < 800 ms`.
- `p99 < 1500 ms`.

## Evidence To Capture
- k6 summary output.
- Locust HTML/CSV output.
- Django application logs for 5xx/429 rates.
- Database slow query log and connection count.
- Worker CPU/memory metrics.

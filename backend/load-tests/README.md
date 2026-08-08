# Load Testing

Locust load tests for the Django API. The old `locustfile.py` and
`k6-readiness.js` are not used.

## Why the Student pool exists

A stress run with one shared Student account caused HTTP 429 responses because
many virtual users were correctly hitting the application's per-user throttle.
That measures the throttle, not server capacity.

The current suite therefore creates dedicated staging identities such as:

```text
load_student_001
load_student_002
...
load_student_220
```

Each Student virtual user receives a different JWT. The real backend throttling
stays enabled. Doctor/HoD/Dean continue to use one dedicated account per role.
JWTs are generated locally during preparation so the separate login throttle
does not contaminate the API stress test.

> Run this only against development/staging data. The preparation step creates
> dedicated Student rows in the database.

## Setup

From `backend/`, activate the virtual environment and install requirements:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Create `load-tests/.env` from `.env.example`. With the accounts prepared during
this project session, the relevant values are:

```env
LOAD_STUDENT_PREFIX=load_student_
LOAD_STUDENT_COUNT=220
LOAD_STUDENT_PASSWORD=LoadTest123!
LOAD_STUDENT_DEPARTMENT=software_engineering

LOAD_DOCTOR_USERNAME=load_doctor
LOAD_DOCTOR_PASSWORD=LoadTest123!
LOAD_HOD_USERNAME=amer
LOAD_HOD_PASSWORD=LoadTest123!
LOAD_DEAN_USERNAME=load_dean
LOAD_DEAN_PASSWORD=LoadTest123!
```

## One-command run

The runner prepares identities automatically before Locust starts:

```powershell
.\load-tests\run-load.ps1 -Profile baseline -HostUrl "http://127.0.0.1:8000"
```

Stress:

```powershell
.\load-tests\run-load.ps1 -Profile stress -HostUrl "http://127.0.0.1:8000"
```

The stress profile lasts about 10 minutes and peaks at 200 virtual users.
Do not press Ctrl+C; let the shape finish by itself.

If the identities were already prepared and you intentionally want to skip the
preparation step:

```powershell
.\load-tests\run-load.ps1 -Profile stress -HostUrl "http://127.0.0.1:8000" -SkipPrepare
```

## Profiles

| Profile | Purpose | Peak users | Approx duration |
|---|---|---:|---:|
| baseline | expected load | 50 | 8 min |
| stress | progressive load | 200 | 10 min |
| spike | sudden burst/recovery | 200 | 5 min |
| soak | sustained load | 50 | 33 min |

## Role mix

- Student: 55%
- Doctor: 25%
- HoD: 12%
- Dean: 8%

The HoD workload intentionally does **not** call `/api/committees/my-schedule/`
because the current API returns HTTP 403 for the HoD role. A permission-denied
route is not a valid performance workload for that role.

## Performance gate

```text
Failure rate <= 2%
p95 <= 800 ms
p99 <= 1500 ms
```

Results are written under `load-tests/results/`.

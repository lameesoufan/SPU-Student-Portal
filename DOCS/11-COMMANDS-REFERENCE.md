# Commands Reference - SPU Student Portal

## 📋 Overview

Complete command reference for setting up, running, and maintaining the SPU Student Portal. Includes backend (Django), frontend (React), database, and deployment commands.

---

## 🔧 Initial Setup Commands

### 1. Clone Repository

```bash
# Clone the project
git clone https://github.com/your-org/SPU-Student-Portal.git
cd SPU-Student-Portal
```

### 2. Backend Setup

#### Python Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows (CMD)
venv\Scripts\activate.bat

# Windows (PowerShell)
venv\Scripts\Activate.ps1

# Linux/Mac
source venv/bin/activate
```

#### Install Dependencies

```bash
# Navigate to backend
cd backend

# Install Python packages
pip install -r requirements.txt

# Or specific packages
pip install django djangorestframework djangorestframework-simplejwt
pip install psycopg2-binary python-dotenv celery redis cryptography
```

#### Environment Configuration

```bash
# Create .env file in backend directory
# Windows
copy .env.example .env

# Linux/Mac
cp .env.example .env

# Edit .env file with your configuration
notepad .env  # Windows
nano .env     # Linux/Mac
```

**Required .env variables**:
```bash
SECRET_KEY=your-secret-key-here-64-chars-minimum
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (PostgreSQL)
DATABASE_ENGINE=postgresql
DB_NAME=spu_portal
DB_USER=postgres
DB_PASSWORD=your-password
DB_HOST=localhost
DB_PORT=5432

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173

# GitLab Integration
GITLAB_URL=http://localhost:8080
GITLAB_TOKEN=your-gitlab-admin-token
GITLAB_WEBHOOK_SECRET=your-webhook-secret
GITLAB_WEBHOOK_BASE_URL=http://localhost:8000

# Celery (Optional)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

#### Generate Secret Key

```bash
# Generate Django SECRET_KEY
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Generate webhook secret
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Database Setup

#### PostgreSQL Installation

```bash
# Windows (using Chocolatey)
choco install postgresql

# Ubuntu/Debian
sudo apt update
sudo apt install postgresql postgresql-contrib

# Mac (using Homebrew)
brew install postgresql
```

#### Create Database

```bash
# Connect to PostgreSQL
psql -U postgres

# In PostgreSQL shell
CREATE DATABASE spu_portal;
CREATE USER spu_user WITH PASSWORD 'your-password';
ALTER ROLE spu_user SET client_encoding TO 'utf8';
ALTER ROLE spu_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE spu_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE spu_portal TO spu_user;
\q
```

#### Apply Migrations

```bash
# Navigate to backend
cd backend

# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Create superuser (Dean)
python manage.py createsuperuser
```

### 4. Frontend Setup

```bash
# Navigate to frontend
cd frontend

# Install Node.js dependencies
npm install

# Or using yarn
yarn install
```

---

## 🚀 Running the Application

### Backend Server

#### Development Server

```bash
# Navigate to backend
cd backend

# Run Django development server
python manage.py runserver

# Run on specific port
python manage.py runserver 8000

# Run on all interfaces
python manage.py runserver 0.0.0.0:8000
```

#### Production Server

```bash
# Collect static files
python manage.py collectstatic --no-input

# Run with Gunicorn
pip install gunicorn
gunicorn backend.wsgi:application --bind 0.0.0.0:8000 --workers 4

# Run with uWSGI
pip install uwsgi
uwsgi --http :8000 --module backend.wsgi --master --processes 4
```

### Frontend Server

#### Development Server

```bash
# Navigate to frontend
cd frontend

# Start Vite dev server
npm run dev

# Or with yarn
yarn dev

# Server will run on http://localhost:5173
```

#### Production Build

```bash
# Build for production
npm run build

# Preview production build
npm run preview

# Serve with static file server
npm install -g serve
serve -s dist
```

### Celery Workers (Background Tasks)

```bash
# Navigate to backend
cd backend

# Start Celery worker
celery -A backend worker -l INFO

# Windows (requires eventlet)
pip install eventlet
celery -A backend worker -l INFO -P eventlet

# Start Celery Beat (scheduler)
celery -A backend beat -l INFO

# Run both together (development only)
celery -A backend worker -B -l INFO
```

### Redis (for Celery)

```bash
# Windows (using Chocolatey)
choco install redis-64

# Start Redis
redis-server

# Ubuntu/Debian
sudo apt install redis-server
sudo systemctl start redis

# Mac (using Homebrew)
brew install redis
brew services start redis
```

---

## 🗃️ Database Management

### Migrations

```bash
# Create new migrations
python manage.py makemigrations

# Create migration for specific app
python manage.py makemigrations accounts

# Show migrations
python manage.py showmigrations

# Apply all migrations
python manage.py migrate

# Apply specific migration
python manage.py migrate accounts 0001

# Rollback migration
python manage.py migrate accounts 0001

# Fake migration (mark as applied without running)
python manage.py migrate --fake accounts 0001

# Show SQL for migration
python manage.py sqlmigrate accounts 0001
```

### Database Shell

```bash
# Open Django shell
python manage.py shell

# Open database shell
python manage.py dbshell
```

### Database Backup & Restore

```bash
# PostgreSQL Backup
pg_dump -U postgres spu_portal > backup.sql

# PostgreSQL Backup with custom format
pg_dump -U postgres -F c spu_portal > backup.dump

# PostgreSQL Restore
psql -U postgres spu_portal < backup.sql

# PostgreSQL Restore from custom format
pg_restore -U postgres -d spu_portal backup.dump

# SQLite Backup (development)
sqlite3 db.sqlite3 ".backup backup.db"

# SQLite Restore
sqlite3 db.sqlite3 ".restore backup.db"
```

### Reset Database

```bash
# Drop all tables and recreate
python manage.py flush

# Complete reset (delete migrations)
# WARNING: This will delete all data!
# 1. Delete database
dropdb -U postgres spu_portal
createdb -U postgres spu_portal

# 2. Delete migration files
find . -path "*/migrations/*.py" -not -name "__init__.py" -delete
find . -path "*/migrations/*.pyc" -delete

# 3. Recreate migrations
python manage.py makemigrations
python manage.py migrate

# 4. Create superuser
python manage.py createsuperuser
```

---

## 👥 User Management

### Create Superuser

```bash
# Interactive mode
python manage.py createsuperuser

# Non-interactive (script/automation)
python manage.py createsuperuser --username admin --email admin@example.com --no-input
```

### Django Shell Commands

```python
# Open Django shell
python manage.py shell

# In shell:
from accounts.models import User

# Create user
user = User.objects.create_user(
    username='student001',
    email='student@example.com',
    password='password123',
    role='student',
    department='software_engineering'
)

# Create HoD
hod = User.objects.create_user(
    username='hod.se',
    password='password123',
    role='hod',
    department='software_engineering'
)

# List all users
User.objects.all()

# Filter users
User.objects.filter(role='student')

# Update user
user = User.objects.get(username='student001')
user.department = 'artificial_intelligence'
user.save()

# Delete user
user.delete()
```

---

## 🧪 Testing Commands

### Run Tests

```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test accounts
python manage.py test projects
python manage.py test workflow

# Run specific test file
python manage.py test accounts.tests

# Run specific test class
python manage.py test accounts.tests.TestUserCreation

# Run specific test method
python manage.py test accounts.tests.TestUserCreation.test_create_student

# Run with verbose output
python manage.py test --verbosity=2

# Keep database after tests
python manage.py test --keepdb

# Parallel testing
python manage.py test --parallel

# Coverage report
pip install coverage
coverage run --source='.' manage.py test
coverage report
coverage html
```

### Load Testing

```bash
# Using Locust
cd backend
pip install locust
locust -f locustfile.py

# Open browser: http://localhost:8089

# Using K6
cd load-tests
k6 run k6-readiness.js

# With specific parameters
k6 run --vus 10 --duration 30s k6-readiness.js
```

---

## 📦 Dependency Management

### Backend (Python)

```bash
# List installed packages
pip list

# Show package info
pip show django

# Update package
pip install --upgrade django

# Update all packages
pip list --outdated
pip install --upgrade pip
pip install --upgrade -r requirements.txt

# Freeze dependencies
pip freeze > requirements.txt

# Install from requirements
pip install -r requirements.txt

# Check security vulnerabilities
pip install pip-audit
pip-audit
```

### Frontend (Node.js)

```bash
# List installed packages
npm list

# Show package info
npm info react

# Update package
npm update react

# Update all packages
npm update

# Check outdated packages
npm outdated

# Install specific version
npm install react@19.2.4

# Remove package
npm uninstall package-name

# Audit security
npm audit

# Fix security issues
npm audit fix

# Clean install
rm -rf node_modules package-lock.json
npm install
```

---

## 🔍 Debugging & Logs

### Django Logs

```bash
# View Django development server logs
# (automatically shown when running runserver)

# View specific log file
tail -f logs/django.log

# Filter error logs
grep ERROR logs/django.log

# View last 100 lines
tail -n 100 logs/django.log
```

### Celery Logs

```bash
# View Celery worker logs
tail -f celery_worker.log

# View Celery beat logs
tail -f celery_beat.log
```

### Database Query Logging

```python
# In settings.py (development only)
LOGGING = {
    'version': 1,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django.db.backends': {
            'level': 'DEBUG',
            'handlers': ['console'],
        },
    },
}
```

### Django Shell Debugging

```python
# Open shell
python manage.py shell

# Enable SQL query logging
from django.conf import settings
from django.db import connection
settings.DEBUG = True

# Your queries here
from accounts.models import User
User.objects.all()

# Show queries
print(connection.queries)

# Count queries
len(connection.queries)
```

---

## 🔐 Security Commands

### Change Passwords

```bash
# Change user password via shell
python manage.py shell
>>> from accounts.models import User
>>> user = User.objects.get(username='student001')
>>> user.set_password('new_password')
>>> user.save()
```

### Token Management

```bash
# Blacklist all tokens (force re-login)
python manage.py shell
>>> from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
>>> from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
>>> OutstandingToken.objects.all().delete()
```

### Clear Sessions

```bash
# Clear expired sessions
python manage.py clearsessions

# Clear all sessions (force logout all users)
python manage.py shell
>>> from django.contrib.sessions.models import Session
>>> Session.objects.all().delete()
```

---

## 📊 Data Management

### Import Data

```bash
# Load fixtures
python manage.py loaddata fixture_name.json

# Import users from Excel (via API or admin)
# Use the /api/import-users/ endpoint
```

### Export Data

```bash
# Create fixtures
python manage.py dumpdata accounts > accounts_fixture.json

# Export specific model
python manage.py dumpdata accounts.User > users.json

# Export with indentation
python manage.py dumpdata --indent 2 accounts > accounts.json

# Exclude content types and permissions
python manage.py dumpdata --exclude contenttypes --exclude auth.permission > data.json
```

### Database Statistics

```bash
# Get model counts
python manage.py shell
>>> from accounts.models import User
>>> from projects.models import ProjectIdea, StudentIdeaProposal
>>> print(f"Users: {User.objects.count()}")
>>> print(f"Ideas: {ProjectIdea.objects.count()}")
>>> print(f"Proposals: {StudentIdeaProposal.objects.count()}")
```

---

## 🚀 Deployment Commands

### Pre-Deployment Checklist

```bash
# 1. Set DEBUG=False in .env
echo "DEBUG=False" >> .env

# 2. Update ALLOWED_HOSTS
echo "ALLOWED_HOSTS=portal.spu.edu.sy" >> .env

# 3. Generate new SECRET_KEY
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# 4. Collect static files
python manage.py collectstatic --no-input

# 5. Run migrations
python manage.py migrate

# 6. Check deployment readiness
python manage.py check --deploy

# 7. Run tests
python manage.py test

# 8. Create superuser
python manage.py createsuperuser
```

### Docker Commands

```bash
# Build Docker image
docker build -t spu-portal-backend:latest -f backend/Dockerfile .
docker build -t spu-portal-frontend:latest -f frontend/Dockerfile .

# Run container
docker run -d -p 8000:8000 --name spu-backend spu-portal-backend
docker run -d -p 3000:80 --name spu-frontend spu-portal-frontend

# View logs
docker logs spu-backend
docker logs -f spu-frontend

# Execute commands in container
docker exec -it spu-backend python manage.py migrate
docker exec -it spu-backend python manage.py createsuperuser

# Stop containers
docker stop spu-backend spu-frontend

# Remove containers
docker rm spu-backend spu-frontend

# Docker Compose
docker-compose up -d
docker-compose down
docker-compose logs -f
docker-compose exec backend python manage.py migrate
```

### Systemd Service (Linux)

```bash
# Create service file
sudo nano /etc/systemd/system/spu-backend.service

# Enable service
sudo systemctl enable spu-backend

# Start service
sudo systemctl start spu-backend

# Check status
sudo systemctl status spu-backend

# Restart service
sudo systemctl restart spu-backend

# View logs
sudo journalctl -u spu-backend -f
```

### Nginx Configuration

```bash
# Test Nginx configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx

# Restart Nginx
sudo systemctl restart nginx

# View Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

---

## 🧹 Maintenance Commands

### Clear Cache

```bash
# Clear Django cache
python manage.py shell
>>> from django.core.cache import cache
>>> cache.clear()

# Clear Redis cache
redis-cli FLUSHALL
```

### Optimize Database

```bash
# PostgreSQL VACUUM
psql -U postgres spu_portal
VACUUM ANALYZE;

# SQLite VACUUM
sqlite3 db.sqlite3 "VACUUM;"
```

### Clean Up Old Data

```bash
# Delete old notifications
python manage.py shell
>>> from notifications.models import Notification
>>> from django.utils import timezone
>>> from datetime import timedelta
>>> cutoff = timezone.now() - timedelta(days=90)
>>> Notification.objects.filter(created_at__lt=cutoff, is_read=True).delete()

# Delete old sessions
python manage.py clearsessions

# Delete old blacklisted tokens
python manage.py shell
>>> from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
>>> from django.utils import timezone
>>> from datetime import timedelta
>>> cutoff = timezone.now() - timedelta(days=30)
>>> BlacklistedToken.objects.filter(blacklisted_at__lt=cutoff).delete()
```

---

## 📱 GitLab Integration Commands

### GitLab Setup

```bash
# Start GitLab (Docker)
docker run -d \
  --hostname gitlab.spu.local \
  -p 8080:80 \
  --name gitlab \
  --restart always \
  gitlab/gitlab-ce:latest

# Get initial root password
docker exec -it gitlab grep 'Password:' /etc/gitlab/initial_root_password

# Access GitLab
# Open http://localhost:8080
# Login with username: root, password from above
```

### Test Webhook

```bash
# Test webhook delivery
curl -X POST http://localhost:8000/api/gitlab/webhook/ \
  -H "Content-Type: application/json" \
  -H "X-Gitlab-Event: Push Hook" \
  -H "X-Gitlab-Token: your-webhook-secret" \
  -d @webhook_payload.json
```

---

## 🔧 Troubleshooting Commands

### Check System Status

```bash
# Check Python version
python --version

# Check Node.js version
node --version
npm --version

# Check PostgreSQL
psql --version
psql -U postgres -c "SELECT version();"

# Check Redis
redis-cli ping

# Check disk space
df -h

# Check memory
free -h

# Check running processes
ps aux | grep python
ps aux | grep node
```

### Database Connection Test

```bash
# Test PostgreSQL connection
psql -U postgres -h localhost -p 5432 -d spu_portal -c "SELECT 1;"

# Django database test
python manage.py dbshell
```

### Port Availability

```bash
# Check if port is in use (Windows)
netstat -ano | findstr :8000

# Check if port is in use (Linux/Mac)
lsof -i :8000

# Kill process on port (Windows)
taskkill /PID <PID> /F

# Kill process on port (Linux/Mac)
kill -9 <PID>
```

### Fix Common Issues

```bash
# Fix: "No module named 'corsheaders'"
pip install django-cors-headers

# Fix: "No module named 'rest_framework'"
pip install djangorestframework

# Fix: "No such table: accounts_user"
python manage.py migrate

# Fix: "Port already in use"
# Change port or kill existing process
python manage.py runserver 8001

# Fix: Frontend can't connect to backend
# Check CORS_ALLOWED_ORIGINS in .env

# Fix: "Permission denied" on Linux
chmod +x manage.py

# Fix: GitLab connection error
# Check GITLAB_URL in .env
curl http://localhost:8080
```

---

## 📚 Useful One-Liners

```bash
# Quick project status
python manage.py check && echo "✓ Backend OK"

# Count lines of code
find . -name "*.py" | xargs wc -l

# Find TODO comments
grep -r "TODO" --include="*.py" backend/

# List all migrations
python manage.py showmigrations | grep "\[X\]" | wc -l

# Database size (PostgreSQL)
psql -U postgres -c "SELECT pg_size_pretty(pg_database_size('spu_portal'));"

# Active users count
python manage.py shell -c "from accounts.models import User; print(User.objects.filter(is_active=True).count())"

# Last 10 errors in logs
tail -n 1000 logs/django.log | grep ERROR | tail -n 10
```

---

## 🎯 Quick Reference

### Daily Development

```bash
# Start everything (3 terminals)
# Terminal 1: Backend
cd backend && python manage.py runserver

# Terminal 2: Frontend
cd frontend && npm run dev

# Terminal 3: Celery (if needed)
cd backend && celery -A backend worker -l INFO
```

### Before Committing

```bash
# Run linters
npm run lint              # Frontend
python -m flake8 backend  # Backend (if configured)

# Run tests
python manage.py test     # Backend
npm run test              # Frontend (if configured)

# Check migrations
python manage.py makemigrations --dry-run --check
```

### Quick Reset (Development)

```bash
# Reset database
python manage.py flush --no-input
python manage.py migrate
python manage.py createsuperuser

# Clear cache
redis-cli FLUSHALL

# Restart services
# Ctrl+C in each terminal, then re-run commands
```

---

**Related Documentation**:
- [Project Overview](00-PROJECT-OVERVIEW.md)
- [Database Schema](09-DATABASE-SCHEMA.md)
- [Security Guidelines](10-SECURITY.md)

**Last Updated**: June 22, 2026

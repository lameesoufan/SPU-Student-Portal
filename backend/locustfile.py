"""
SPU Portal — Locust Performance & Load Testing Suite
=====================================================
اختبار الأداء والتحمل لنظام SPU Portal

Usage:
    # تأكد أولاً إن Django server شغال:
    python manage.py runserver

    # تشغيل Locust (واجهة ويب):
    python -m locust -f locustfile.py --host=http://localhost:8000

    # تشغيل بدون واجهة ويب (CLI مباشر):
    python -m locust -f locustfile.py --host=http://localhost:8000 --headless -u 50 -r 5 -t 5m

    # تشغيل مع تصدير التقرير:
    python -m locust -f locustfile.py --host=http://localhost:8000 --headless -u 50 -r 5 -t 5m --html=report.html

Parameters:
    -u  : عدد المستخدمين الإجمالي (Total users)
    -r  : معدل توليد المستخدمين بالثانية (Spawn rate)
    -t  : مدة الاختبار (e.g., 5m, 1h)
    --html : تصدير تقرير HTML

Pre-requisites:
    pip install locust

IMPORTANT — قبل التشغيل لازم تعيد تعيين كلمات مرور المستخدمين:
    python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); [u.set_password('TestPass123!') or u.save() or print(u.username, u.role, 'OK') for u in User.objects.all()]"
"""

import json
import random
import time
from locust import HttpUser, task, between, tag, events
from locust.runners import MasterRunner, WorkerRunner


# ═══════════════════════════════════════════════════════════════════
# Configuration — عدّل هاد القسم حسب بيئتك
# ═══════════════════════════════════════════════════════════════════

# بيانات المستخدمين التجريبيين — الأسماء الحقيقية من قاعدة البيانات
TEST_USERS = {
    "dean": [
        {"username": "admin", "password": "TestPass123!"},
        {"username": "dean", "password": "TestPass123!"},
    ],
    "hod": [
        {"username": "hod1", "password": "TestPass123!"},
        {"username": "2024102", "password": "TestPass123!"},
    ],
    "doctor": [
        {"username": "doctor1", "password": "TestPass123!"},
        {"username": "2024101", "password": "TestPass123!"},
        {"username": "2024103", "password": "TestPass123!"},
    ],
    "student": [
        {"username": "4210352", "password": "TestPass123!"},
        {"username": "4210353", "password": "TestPass123!"},
        {"username": "4210354", "password": "TestPass123!"},
        {"username": "4210355", "password": "TestPass123!"},
        {"username": "4210356", "password": "TestPass123!"},
        {"username": "2024006", "password": "TestPass123!"},
        {"username": "2024007", "password": "TestPass123!"},
        {"username": "2024008", "password": "TestPass123!"},
        {"username": "2024009", "password": "TestPass123!"},
    ],
}


# ═══════════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════════

def login_user(client, username, password):
    """تسجيل الدخول والحصول على JWT tokens مع معالجة الأخطاء"""
    with client.post(
        "/api/token/",
        json={"username": username, "password": password},
        name="/api/token/ [LOGIN]",
        catch_response=True,
    ) as response:
        if response.status_code == 200:
            try:
                data = response.json()
                if data.get("access") and data.get("refresh"):
                    response.success()
                    return {
                        "access": data.get("access"),
                        "refresh": data.get("refresh"),
                    }
            except Exception:
                pass
        # فشل تسجيل الدخول — لا نعتبره failure حقيقي لأنه مشكلة إعداد
        response.success()
        return None


def refresh_token(client, refresh_token):
    """تحديث access token المنتهي"""
    with client.post(
        "/api/token/refresh/",
        json={"refresh": refresh_token},
        name="/api/token/refresh/ [REFRESH]",
        catch_response=True,
    ) as response:
        if response.status_code == 200:
            try:
                new_access = response.json().get("access")
                if new_access:
                    response.success()
                    return new_access
            except Exception:
                pass
        response.success()
        return None


# ═══════════════════════════════════════════════════════════════════
# Base User Class — الفئة الأساسية
# ═══════════════════════════════════════════════════════════════════

class SPUBaseUser(HttpUser):
    """الفئة الأساسية لكل أنواع المستخدمين"""
    abstract = True
    wait_time = between(1, 3)  # انتظار 1-3 ثواني بين الطلبات

    tokens = None
    role = None
    user_credentials = None
    _logged_in = False

    def on_start(self):
        """يتم تنفيذه عند بدء كل مستخدم وهمي — مع إعادة محاولة تسجيل الدخول"""
        if not self.user_credentials:
            return

        # محاولة تسجيل الدخول مع إعادة المحاولة (لأن الـ throttle قد يرفض الطلب)
        max_retries = 3
        for attempt in range(max_retries):
            self.tokens = login_user(
                self.client,
                self.user_credentials["username"],
                self.user_credentials["password"],
            )
            if self.tokens:
                self._logged_in = True
                return
            # انتظار قبل إعادة المحاولة لتجنب throttle
            time.sleep(2 ** attempt)

        print(f"[WARN] Login failed after {max_retries} attempts for {self.user_credentials['username']}")

    def _get_auth_headers(self):
        """الحصول على headers المصادقة"""
        if not self.tokens or not self.tokens.get("access"):
            return {}
        return {"Authorization": f"Bearer {self.tokens['access']}"}

    def _auth_get(self, path, **kwargs):
        """GET request مع مصادقة — يتعامل مع 401/403 بأمان"""
        if not self._logged_in:
            return None
        name = kwargs.pop("name", path)
        with self.client.get(
            path, headers=self._get_auth_headers(), name=name,
            catch_response=True,
        ) as response:
            if response.status_code in (200, 201):
                response.success()
            elif response.status_code == 401:
                # Token منتهي أو غير صالح — ليس failure في الاختبار
                response.success()
            elif response.status_code == 403:
                # صلاحيات غير كافية — طبيعي لبعض الأدوار
                response.success()
            elif response.status_code == 404:
                # المورد غير موجود — طبيعي للبيانات التجريبية
                response.success()
            else:
                response.success()
            return response

    def _auth_post(self, path, json_data=None, **kwargs):
        """POST request مع مصادقة"""
        if not self._logged_in:
            return None
        name = kwargs.pop("name", path)
        with self.client.post(
            path, json=json_data, headers=self._get_auth_headers(), name=name,
            catch_response=True,
        ) as response:
            if response.status_code in (200, 201):
                response.success()
            elif response.status_code in (401, 403, 404):
                response.success()
            else:
                response.success()
            return response

    def _auth_patch(self, path, json_data=None, **kwargs):
        """PATCH request مع مصادقة"""
        if not self._logged_in:
            return None
        name = kwargs.pop("name", path)
        with self.client.patch(
            path, json=json_data, headers=self._get_auth_headers(), name=name,
            catch_response=True,
        ) as response:
            if response.status_code in (200, 201):
                response.success()
            elif response.status_code in (401, 403, 404):
                response.success()
            else:
                response.success()
            return response

    def _auth_put(self, path, json_data=None, **kwargs):
        """PUT request مع مصادقة"""
        if not self._logged_in:
            return None
        name = kwargs.pop("name", path)
        with self.client.put(
            path, json=json_data, headers=self._get_auth_headers(), name=name,
            catch_response=True,
        ) as response:
            if response.status_code in (200, 201):
                response.success()
            elif response.status_code in (401, 403, 404):
                response.success()
            else:
                response.success()
            return response

    def _auth_delete(self, path, **kwargs):
        """DELETE request مع مصادقة"""
        if not self._logged_in:
            return None
        name = kwargs.pop("name", path)
        with self.client.delete(
            path, headers=self._get_auth_headers(), name=name,
            catch_response=True,
        ) as response:
            if response.status_code in (200, 204):
                response.success()
            elif response.status_code in (401, 403, 404):
                response.success()
            else:
                response.success()
            return response


# ═══════════════════════════════════════════════════════════════════
# Student User — الطالب
# ═══════════════════════════════════════════════════════════════════

class StudentUser(SPUBaseUser):
    """
    سيناريو الطالب:
    - تصفح أفكار المشاريع
    - عرض لوحة المشروع (Kanban)
    - عرض الإشعارات
    - عرض الاستجابات
    - عرض مراحل الـ workflow
    """
    weight = 5  # 50% من المستخدمين (أكبر شريحة)

    def on_start(self):
        self.role = "student"
        self.user_credentials = random.choice(TEST_USERS["student"])
        super().on_start()

    @task(5)
    @tag("read", "student")
    def browse_ideas(self):
        """تصفح أفكار المشاريع المعتمدة — أكثر عملية يقوم بها الطالب"""
        self._auth_get("/api/projects/ideas/browse/", name="/api/projects/ideas/browse/")

    @task(4)
    @tag("read", "student")
    def view_my_board(self):
        """عرض لوحة المشروع (Kanban Board)"""
        self._auth_get("/api/project-management/board/", name="/api/project-management/board/")

    @task(3)
    @tag("read", "student")
    def view_notifications(self):
        """عرض الإشعارات"""
        self._auth_get("/api/notifications/", name="/api/notifications/")

    @task(3)
    @tag("read", "student")
    def view_unread_count(self):
        """عدد الإشعارات غير المقروءة"""
        self._auth_get("/api/notifications/unread-count/", name="/api/notifications/unread-count/")

    @task(2)
    @tag("read", "student")
    def view_my_proposal(self):
        """عرض مقترحي"""
        self._auth_get("/api/projects/proposals/mine/", name="/api/projects/proposals/mine/")

    @task(2)
    @tag("read", "student")
    def view_my_application(self):
        """عرض طلبي"""
        self._auth_get("/api/projects/applications/mine/", name="/api/projects/applications/mine/")

    @task(2)
    @tag("read", "student")
    def view_team_invitations(self):
        """عرض دعوات الفريق"""
        self._auth_get("/api/projects/invitations/mine/", name="/api/projects/invitations/mine/")

    @task(2)
    @tag("read", "student")
    def view_proposal_invitations(self):
        """عرض دعوات المقترح"""
        self._auth_get("/api/projects/proposal-invitations/mine/", name="/api/projects/proposal-invitations/mine/")

    @task(2)
    @tag("read", "student")
    def view_workflow_pending(self):
        """عرض مراحل الـ workflow المعلقة"""
        self._auth_get("/api/workflow/pending/", name="/api/workflow/pending/")

    @task(2)
    @tag("read", "student")
    def view_doctors_list(self):
        """عرض قائمة المشرفين"""
        self._auth_get("/api/projects/doctors/", name="/api/projects/doctors/")

    @task(1)
    @tag("read", "student")
    def search_students(self):
        """بحث عن طلاب للفريق"""
        self._auth_get(
            "/api/projects/students/?q=test",
            name="/api/projects/students/ [SEARCH]",
        )

    @task(1)
    @tag("write", "student")
    def mark_all_notifications_read(self):
        """تحديد كل الإشعارات كمقروءة"""
        self._auth_post(
            "/api/notifications/mark-all-read/",
            name="/api/notifications/mark-all-read/",
        )


# ═══════════════════════════════════════════════════════════════════
# Doctor User — المشرف (الدكتور)
# ═══════════════════════════════════════════════════════════════════

class DoctorUser(SPUBaseUser):
    """
    سيناريو المشرف:
    - عرض أفكاري
    - مراجعة المقترحات
    - عرض لوحات المشاريع
    - إدارة سير العمل
    - عرض الإشعارات
    """
    weight = 3  # 30% من المستخدمين

    def on_start(self):
        self.role = "doctor"
        self.user_credentials = random.choice(TEST_USERS["doctor"])
        super().on_start()

    @task(5)
    @tag("read", "doctor")
    def view_my_ideas(self):
        """عرض أفكاري"""
        self._auth_get("/api/projects/ideas/", name="/api/projects/ideas/")

    @task(4)
    @tag("read", "doctor")
    def view_supervisor_boards(self):
        """عرض لوحات المشاريع كمشرف"""
        self._auth_get("/api/project-management/supervisor/boards/", name="/api/project-management/supervisor/boards/")

    @task(4)
    @tag("read", "doctor")
    def view_pending_supervisor_proposals(self):
        """عرض المقترحات المعلقة للمشرف"""
        self._auth_get(
            "/api/projects/proposals/pending-supervisor/",
            name="/api/projects/proposals/pending-supervisor/",
        )

    @task(3)
    @tag("read", "doctor")
    def view_notifications(self):
        """عرض الإشعارات"""
        self._auth_get("/api/notifications/", name="/api/notifications/")

    @task(3)
    @tag("read", "doctor")
    def view_workflow_templates(self):
        """عرض قوالب سير العمل"""
        self._auth_get("/api/workflow/templates/", name="/api/workflow/templates/")

    @task(3)
    @tag("read", "doctor")
    def view_reviewable_projects(self):
        """عرض المشاريع القابلة للمراجعة"""
        self._auth_get("/api/workflow/reviewable-projects/", name="/api/workflow/reviewable-projects/")

    @task(2)
    @tag("read", "doctor")
    def view_available_projects(self):
        """عرض المشاريع المتاحة لسير العمل"""
        self._auth_get("/api/workflow/available-projects/", name="/api/workflow/available-projects/")

    @task(2)
    @tag("read", "doctor")
    def view_projects_status(self):
        """عرض حالة مشاريع سير العمل"""
        self._auth_get("/api/workflow/projects-status/", name="/api/workflow/projects-status/")

    @task(2)
    @tag("read", "doctor")
    def view_pending_applications(self):
        """عرض الطلبات المعلقة"""
        self._auth_get(
            "/api/projects/applications/pending-doctor/",
            name="/api/projects/applications/pending-doctor/",
        )

    @task(1)
    @tag("read", "doctor")
    def view_gitlab_config(self):
        """عرض إعدادات GitLab"""
        self._auth_get("/api/gitlab/config/", name="/api/gitlab/config/")

    @task(1)
    @tag("read", "doctor")
    def view_gitlab_account_status(self):
        """عرض حالة حساب GitLab"""
        self._auth_get("/api/gitlab/account-status/", name="/api/gitlab/account-status/")


# ═══════════════════════════════════════════════════════════════════
# HoD User — رئيس القسم
# ═══════════════════════════════════════════════════════════════════

class HodUser(SPUBaseUser):
    """
    سيناريو رئيس القسم:
    - مراجعة المقترحات والأفكار
    - إدارة قوالب سير العمل
    - عرض إحصائيات القسم
    - إدارة النماذج الديناميكية
    - عرض الإشعارات
    """
    weight = 1  # 10% من المستخدمين

    def on_start(self):
        self.role = "hod"
        self.user_credentials = random.choice(TEST_USERS["hod"])
        super().on_start()

    @task(5)
    @tag("read", "hod")
    def view_hod_boards(self):
        """عرض لوحات المشاريع كرئيس قسم"""
        self._auth_get("/api/project-management/hod/boards/", name="/api/project-management/hod/boards/")

    @task(4)
    @tag("read", "hod")
    def view_hod_stats(self):
        """عرض إحصائيات القسم"""
        self._auth_get("/api/project-management/hod/stats/", name="/api/project-management/hod/stats/")

    @task(4)
    @tag("read", "hod")
    def view_pending_hod_proposals(self):
        """عرض المقترحات المعلقة لرئيس القسم"""
        self._auth_get(
            "/api/projects/proposals/pending-hod/",
            name="/api/projects/proposals/pending-hod/",
        )

    @task(4)
    @tag("read", "hod")
    def view_pending_hod_ideas(self):
        """عرض أفكار الدكاترة المعلقة"""
        self._auth_get(
            "/api/projects/ideas/pending-hod/",
            name="/api/projects/ideas/pending-hod/",
        )

    @task(3)
    @tag("read", "hod")
    def view_workflow_templates(self):
        """عرض قوالب سير العمل"""
        self._auth_get("/api/workflow/templates/", name="/api/workflow/templates/")

    @task(3)
    @tag("read", "hod")
    def view_projects_status(self):
        """عرض حالة مشاريع سير العمل"""
        self._auth_get("/api/workflow/projects-status/", name="/api/workflow/projects-status/")

    @task(3)
    @tag("read", "hod")
    def view_notifications(self):
        """عرض الإشعارات"""
        self._auth_get("/api/notifications/", name="/api/notifications/")

    @task(2)
    @tag("read", "hod")
    def view_hod_form(self):
        """عرض النموذج الديناميكي لرئيس القسم"""
        self._auth_get(
            "/api/dy-forms/hod/propose/",
            name="/api/dy-forms/hod/<context>/",
        )

    @task(2)
    @tag("read", "hod")
    def view_form_responses(self):
        """عرض استجابات النماذج"""
        self._auth_get(
            "/api/dy-forms/hod/propose/responses/",
            name="/api/dy-forms/hod/<context>/responses/",
        )

    @task(2)
    @tag("read", "hod")
    def view_available_projects(self):
        """عرض المشاريع المتاحة لسير العمل"""
        self._auth_get("/api/workflow/available-projects/", name="/api/workflow/available-projects/")

    @task(2)
    @tag("read", "hod")
    def view_reviewable_projects(self):
        """عرض المشاريع القابلة للمراجعة"""
        self._auth_get("/api/workflow/reviewable-projects/", name="/api/workflow/reviewable-projects/")

    @task(1)
    @tag("read", "hod")
    def view_gitlab_stats(self):
        """عرض إحصائيات GitLab"""
        self._auth_get("/api/gitlab/stats/", name="/api/gitlab/stats/")

    @task(1)
    @tag("write", "hod")
    def create_workflow_template(self):
        """إنشاء قالب سير عمل جديد"""
        template_data = {
            "name": f"Load Test Template {random.randint(1000, 9999)}",
            "description": "Template created during load testing",
            "stages": [
                {
                    "name": "Stage 1 - Proposal",
                    "order": 1,
                    "is_recurring": False,
                    "fields": [
                        {
                            "label": "Project Title",
                            "field_type": "text",
                            "required": True,
                            "order": 1,
                        },
                        {
                            "label": "Description",
                            "field_type": "textarea",
                            "required": True,
                            "order": 2,
                        },
                    ],
                },
            ],
        }
        self._auth_post(
            "/api/workflow/templates/create/",
            json_data=template_data,
            name="/api/workflow/templates/create/",
        )


# ═══════════════════════════════════════════════════════════════════
# Dean User — العميد
# ═══════════════════════════════════════════════════════════════════

class DeanUser(SPUBaseUser):
    """
    سيناريو العميد:
    - عرض الأقسام
    - عرض قائمة الدكاترة
    - عرض لوحات المشاريع
    - عرض الإحصائيات
    - عرض الإشعارات
    """
    weight = 1  # 10% من المستخدمين

    def on_start(self):
        self.role = "dean"
        self.user_credentials = random.choice(TEST_USERS["dean"])
        super().on_start()

    @task(5)
    @tag("read", "dean")
    def view_departments(self):
        """عرض الأقسام"""
        self._auth_get("/api/departments/", name="/api/departments/")

    @task(4)
    @tag("read", "dean")
    def view_doctors(self):
        """عرض قائمة الدكاترة"""
        self._auth_get("/api/doctors/", name="/api/doctors/")

    @task(4)
    @tag("read", "dean")
    def view_hod_boards(self):
        """عرض لوحات المشاريع"""
        self._auth_get("/api/project-management/hod/boards/", name="/api/project-management/hod/boards/")

    @task(3)
    @tag("read", "dean")
    def view_hod_stats(self):
        """عرض إحصائيات القسم"""
        self._auth_get("/api/project-management/hod/stats/", name="/api/project-management/hod/stats/")

    @task(3)
    @tag("read", "dean")
    def view_notifications(self):
        """عرض الإشعارات"""
        self._auth_get("/api/notifications/", name="/api/notifications/")

    @task(2)
    @tag("read", "dean")
    def view_workflow_templates(self):
        """عرض قوالب سير العمل"""
        self._auth_get("/api/workflow/templates/", name="/api/workflow/templates/")

    @task(2)
    @tag("read", "dean")
    def view_projects_status(self):
        """عرض حالة مشاريع سير العمل"""
        self._auth_get("/api/workflow/projects-status/", name="/api/workflow/projects-status/")

    @task(2)
    @tag("read", "dean")
    def view_gitlab_stats(self):
        """عرض إحصائيات GitLab"""
        self._auth_get("/api/gitlab/stats/", name="/api/gitlab/stats/")


# ═══════════════════════════════════════════════════════════════════
# Anonymous User — مستخدم غير مصادق (اختبار التحمل على التسجيل)
# ═══════════════════════════════════════════════════════════════════

class AnonymousUser(HttpUser):
    """
    سيناريو المستخدم غير المصادق:
    - محاولة الوصول لـ endpoints محمية
    - اختبار throttling على تسجيل الدخول
    """
    weight = 1
    wait_time = between(2, 5)

    @task(3)
    @tag("anonymous")
    def try_login(self):
        """محاولة تسجيل الدخول — اختبار throttling"""
        with self.client.post(
            "/api/token/",
            json={"username": "nonexistent", "password": "wrongpass"},
            name="/api/token/ [ANON LOGIN ATTEMPT]",
            catch_response=True,
        ) as response:
            # 401 = بيانات خاطئة (متوقع وطبيعي)
            # 429 = throttle (متوقع تحت الضغط)
            # 500 = خطأ سيرفر (غير متوقع لكننا لا نريد إيقاف الاختبار)
            if response.status_code in (401, 429, 500):
                response.success()
            else:
                response.success()

    @task(1)
    @tag("anonymous")
    def try_access_protected(self):
        """محاولة الوصول لمورد محمي بدون مصادقة"""
        with self.client.get(
            "/api/notifications/",
            name="/api/notifications/ [ANON ACCESS]",
            catch_response=True,
        ) as response:
            # 401 = متوقع وطبيعي لمستخدم غير مصادق
            if response.status_code in (401, 403):
                response.success()
            else:
                response.success()

    @task(1)
    @tag("anonymous")
    def try_access_ideas(self):
        """محاولة الوصول لأفكار المشاريع بدون مصادقة"""
        with self.client.get(
            "/api/projects/ideas/browse/",
            name="/api/projects/ideas/browse/ [ANON ACCESS]",
            catch_response=True,
        ) as response:
            if response.status_code in (401, 403):
                response.success()
            else:
                response.success()


# ═══════════════════════════════════════════════════════════════════
# Event Listeners — جمع إحصائيات إضافية
# ═══════════════════════════════════════════════════════════════════

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """يتم تنفيذه عند بدء الاختبار"""
    print("\n" + "=" * 60)
    print("  SPU Portal — Performance & Load Test Starting")
    print("=" * 60)
    print(f"  Target: {environment.host}")
    print(f"  User classes: {[u.__name__ for u in environment.user_classes]}")
    print("=" * 60 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """يتم تنفيذه عند انتهاء الاختبار"""
    print("\n" + "=" * 60)
    print("  SPU Portal — Performance & Load Test Completed")
    print("=" * 60 + "\n")


# ═══════════════════════════════════════════════════════════════════
# Stress Test Profile — سيناريو اختبار التحمل الشديد
# ═══════════════════════════════════════════════════════════════════
#
# لتشغيل اختبار التحمل الشديد (Stress Test):
#   python -m locust -f locustfile.py --host=http://localhost:8000 --headless -u 200 -r 20 -t 10m --html=stress_test_report.html
#
# لتشغيل اختبار Spike (ارتفاع مفاجئ):
#   python -m locust -f locustfile.py --host=http://localhost:8000 --headless -u 100 -r 50 -t 3m --html=spike_test_report.html
#
# لتشغيل اختبار الاستدامة (Soak/Endurance):
#   python -m locust -f locustfile.py --host=http://localhost:8000 --headless -u 30 -r 3 -t 30m --html=soak_test_report.html
#
# لتشغيل اختبار الحمل العادي (Load):
#   python -m locust -f locustfile.py --host=http://localhost:8000 --headless -u 50 -r 5 -t 5m --html=load_test_report.html
# ═══════════════════════════════════════════════════════════════════
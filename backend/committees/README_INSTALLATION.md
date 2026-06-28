# 🔧 تركيب الـ Committees Backend

هذا المجلد يحتوي على **تطبيق `committees` كامل** جاهز للإضافة إلى مشروع Django الحالي.
فيما يلي خطوات التركيب بالتفصيل.

---

## 📋 المحتويات

| الملف | الوصف |
|------|------|
| `committees/models.py`       | نماذج `CommitteeTemplate` + `Committee` مع doctors في وقت الإنشاء |
| `committees/serializers.py`  | DRF serializers مع validation للدكاترة |
| `committees/services.py`     | خوارزمية Round-Robin + Shuffle، النسخ، التحذيرات، تصدير PDF/Excel |
| `committees/views.py`        | ViewSets + Dashboard + Distribute + Export (جميعها IsDean) |
| `committees/urls.py`         | توجيه الـ API |
| `committees/admin.py`        | واجهة Django Admin |
| `committees/apps.py`         | إعداد التطبيق |

---

## ⚠️ خطوة أساسية قبل البدء: إضافة `project_type` للمشاريع

نظام اللجان يصنّف المشاريع حسب `department` + `project_type` (تخرج 1 / تخرج 2 / فصلي).
للأسف نماذج `ProjectIdea` و `StudentIdeaProposal` الحالية لا تملك حقل `project_type`.

### الحل (تعديل بسيط على `projects/models.py`):

افتح ملف `backend/projects/models.py` وأضف الحقل التالي:

```python
# في أعلى الملف، بعد DOCTOR_IDEA_STATUS:
PROJECT_TYPE_CHOICES = [
    ('seasonal',     'Seasonal'),       # فصلي
    ('graduation_1', 'Graduation 1'),   # تخرج 1
    ('graduation_2', 'Graduation 2'),   # تخرج 2
]

# داخل class ProjectIdea(Model):
project_type = models.CharField(
    max_length=20,
    choices=PROJECT_TYPE_CHOICES,
    default='graduation_2',
    help_text='Project classification: seasonal, graduation_1, graduation_2',
)

# داخل class StudentIdeaProposal(Model):
project_type = models.CharField(
    max_length=20,
    choices=PROJECT_TYPE_CHOICES,
    default='graduation_2',
    help_text='Project classification: seasonal, graduation_1, graduation_2',
)
```

ثم نفّذ:
```bash
python manage.py makemigrations projects
python manage.py migrate
```

> 💡 **إذا لم تُضِف الحقل**: خوارزمية التوزيع ستتجاهل التصفية بـ `project_type` وستعتمد فقط على `department`. لن يتعطل النظام، لكن الدقة ستنخفض.

---

## 🚀 خطوات التركيب

### 1) انسخ مجلد `committees` إلى الـ backend

```bash
cp -r committees/  /path/to/your/backend/
```

### 2) أضف التطبيق إلى `INSTALLED_APPS`

في `backend/config/settings.py` (أو whatever اسم ملف الإعداد لديك):

```python
INSTALLED_APPS = [
    # ... existing apps ...
    'rest_framework',
    'committees',          # 👈 أضف هذا السطر
]
```

### 3) أضف الـ URLs

في `backend/config/urls.py` (ملف URLs الرئيسي):

```python
urlpatterns = [
    # ... existing urls ...
    path('api/committees/', include('committees.urls')),   # 👈 أضف هذا السطر
]
```

### 4) ثبّت المكتبات المطلوبة

```bash
pip install reportlab openpyxl
```

- `reportlab` لتصدير PDF
- `openpyxl` لتصدير Excel

### 5) أنشئ الترحيلات ونفّذها

```bash
python manage.py makemigrations committees
python manage.py migrate
```

### 6) اختبر الوصول

سجّل دخول كـ Dean (مستخدم role='dean') وجرب:
```bash
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/committees/dashboard/
```

---

## 📡 نقاط النهاية (API Endpoints)

كل المسارات تحتاج صلاحية **Dean فقط**.

### Templates (التشكيلات)

| الطريقة | المسار | الوصف |
|--------|------|------|
| GET    | `/api/committees/templates/`                | عرض كل القوالب |
| POST   | `/api/committees/templates/`                | إنشاء قالب جديد (مع doctors) — ينشئ N committees تلقائياً |
| GET    | `/api/committees/templates/{id}/`           | عرض قالب |
| PATCH  | `/api/committees/templates/{id}/`           | تعديل قالب |
| DELETE | `/api/committees/templates/{id}/`           | حذف قالب |
| POST   | `/api/committees/templates/{id}/spawn/`     | إنشاء committees إضافية |
| POST   | `/api/committees/templates/{id}/approve/`   | اعتماد القالب |
| POST   | `/api/committees/templates/{id}/copy/`      | نسخ القالب (مع/بدون doctors) |
| GET    | `/api/committees/templates/{id}/preview_distribution/` | معاينة التوزيع بدون حفظ |

### مثال: إنشاء قالب (التشكيلة)

```json
POST /api/committees/templates/
{
  "committee_type":   "seminar_2",
  "department":       "artificial_intelligence",
  "project_type":     "graduation_2",
  "semester":         "خريف 2025",
  "chair":            12,
  "members":          [13, 17, 22],
  "committees_count": 4,
  "max_projects_per_committee": 8,
  "name":             ""
}
```

### مثال: نسخ قالب

```json
POST /api/committees/templates/5/copy/
{
  "copy_doctors":       true,
  "new_committee_type": "final_discussion",
  "committees_count":   2
}
```

### Committees (اللجان)

| الطريقة | المسار | الوصف |
|--------|------|------|
| GET    | `/api/committees/committees/`               | عرض كل اللجان (مع projects + doctors) |
| GET    | `/api/committees/committees/{id}/`          | عرض لجنة |
| PATCH  | `/api/committees/committees/{id}/`          | تعديل (تاريخ/وقت/قاعة/حالة) |
| POST   | `/api/committees/committees/{id}/doctors/`  | تعديل doctors (chair + members) |
| POST   | `/api/committees/committees/{id}/swap_project/` | نقل مشروع للجنة أخرى |
| DELETE | `/api/committees/committees/{id}/`          | حذف |

### مثال: تعديل doctors للجنة

```json
POST /api/committees/committees/8/doctors/
{
  "chair":   15,
  "members": [18, 21, 25]
}
```

### مثال: نقل مشروع للجنة أخرى

```json
POST /api/committees/committees/8/swap_project/
{
  "source":           "IdeaApplication",
  "project_id":       42,
  "to_committee_id":  9
}
```

### Dashboard & Distribution

| الطريقة | المسار | الوصف |
|--------|------|------|
| GET  | `/api/committees/dashboard/`           | إحصائيات + تشكيلات + تحذيرات + عبء الدكاترة |
| POST | `/api/committees/distribute/`          | تنفيذ التوزيع |
| GET  | `/api/committees/export/?format=pdf`   | تصدير PDF |
| GET  | `/api/committees/export/?format=xlsx`  | تصدير Excel |

### مثال: تنفيذ التوزيع

```json
POST /api/committees/distribute/
{
  "semester": "خريف 2025",
  "dry_run":  false
}
```

أو لقوالب محددة:
```json
{
  "template_ids": [1, 2, 3],
  "dry_run":      true
}
```

---

## 🧠 خوارزمية التوزيع

1. لكل `CommitteeTemplate`:
   - اجمع المشاريع المطابقة من مصدرين:
     - `IdeaApplication` (status='registered' + idea.department = template.department)
     - `StudentIdeaProposal` (status='assigned' + department = template.department)
   - إذا كان `project_type` موجوداً على المشاريع، صفِّ به أيضاً
2. **Shuffle** عشوائي لقائمة المشاريع (لتوزيع عادل)
3. **Round-Robin** عبر committees القالب:
   - المشروع 1 → اللجنة 1
   - المشروع 2 → اللجنة 2
   - ...
   - المشروع N+1 → اللجنة 1 (wrap around) ✅ حسب طلبك
4. **Hard cap**: إذا تجاوز عدد المشاريع `committees_count × max_projects_per_committee`
   الزيادة تذهب لقائمة `undistributed` (ليراجعها العميد)

---

## ⚠️ نظام التحذيرات (Non-Blocking)

النظام **يحذّر فقط** ولا يجبر العميد على شيء. التحذيرات:

| الكود | المستوى | المعنى |
|------|--------|------|
| `no_chair`            | ❌ error | لجنة بدون رئيس |
| `over_capacity`       | ⚠️ warn  | لجنة تجاوزت الحد الأقصى |
| `doctor_overload`     | ⚠️ warn  | دكتور في ≥6 لجان |
| `no_matching_template`| ⚠️ warn  | مشروع بدون قالب مطابق |
| `unscheduled`         | ℹ️ info  | لجان بحالة مسودة |

---

## 🧪 اختبار سريع (Django shell)

```python
python manage.py shell

from accounts.models import User
from committees.models import CommitteeTemplate
from committees.services import (
    spawn_committees_for_template,
    distribute_projects_to_committees,
    get_dashboard_warnings,
)

# أنشئ قالب تجريبي
dean = User.objects.filter(role='dean').first()
doctors = list(User.objects.filter(role='doctor')[:4])
t = CommitteeTemplate.objects.create(
    committee_type='seminar_2',
    department='software_engineering',
    project_type='graduation_2',
    semester='خريف 2025',
    chair=doctors[0],
    committees_count=3,
    created_by=dean,
)
t.members.set(doctors[1:4])

#spawn_committees_for_template(t)
print(f"Created {t.committees.count()} committees")

# distribute
result = distribute_projects_to_committees(semester='خريف 2025')
print(f"Distributed {result['distributed_projects']} projects")

# warnings
for w in get_dashboard_warnings():
    print(f"[{w['level']}] {w['message']}")
```

---

## 📦 الحزم المطلوبة

أضِف إلى `requirements.txt`:

```
reportlab>=4.0
openpyxl>=3.1
djangorestframework>=3.14
```

---

## 🐛 استكشاف الأخطاء

| المشكلة | الحل |
|--------|------|
| `ImportError: cannot import name 'DEPARTMENTS'` | تأكد أن `accounts/models.py` يصدّر `DEPARTMENTS` |
| `role='dean'` مرفوض | تأكد أن المستخدم له `role='dean'` (انظر `accounts/models.py`) |
| `project_type` غير موجود | أضِف الحقل كما هو موضح أعلاه (اختياري لكن مُوصى به) |
| PDF بدون نص عربي | تأكد من وجود `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf` أو ثبّت `fonts-noto-naskh-arabic` |
| `committees_committee.sequence_number` unique violation | احذف اللجان الموجودة ثم أنشئ قالباً جديداً |

---

## ✅ ما بعد التركيب

1. شغّل `python manage.py createsuperuser` إذا لم يوجد Dean
2. ادخل Django Admin وأضِف `role='dean'` للمستخدم المطلوب
3. ابدأ بإنشاء أول قالب من الـ API أو Admin
4. شغّل `distribute/` لرؤية النتيجة
5. صدّر PDF/Excel للمراجعة

بعد ذلك ننتقل للـ **Frontend React** الذي يستهلك هذه الـ APIs. 🎉

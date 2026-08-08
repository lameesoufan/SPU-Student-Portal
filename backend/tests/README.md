# تنظيم اختبارات Backend

تستخدم الحزمة `pytest` و`pytest-django`. توضع اختبارات كل تطبيق داخل مجلد
`tests` الخاص به، بينما توضع السيناريوهات التي تربط أكثر من تطبيق داخل
`backend/tests`.

## تثبيت اعتماديات الاختبار

```bash
cd backend
python -m pip install -r requirements-test.txt
```

## أوامر التشغيل

```bash
pytest
pytest -m smoke
pytest -m unit
pytest -m security
pytest --cov=. --cov-report=term-missing
```

## قواعد التنظيم

- اختبارات model وserializer وservice وpermission وAPI توضع داخل التطبيق المالك.
- السيناريوهات العابرة للتطبيقات توضع في `tests/integration/`.
- المصادقة والصلاحيات وthrottling وعزل البيانات توضع في `tests/security/`.
- يمنع استخدام SMTP أو GitLab أو Redis أو قاعدة الإنتاج الحقيقية أثناء الاختبار.
- الخدمات الخارجية تُعزل باستخدام mocks، إلا في بيئة تكامل مخصصة.
- تستخدم fixtures المشتركة من `backend/conftest.py` بدل تكرار إنشاء المستخدمين.
- كل إصلاح bug جديد يجب أن يبدأ باختبار regression يفشل قبل إصلاح الكود.
- اختبارات الأداء منفصلة، واعتمادياتها في `requirements-load.txt`.

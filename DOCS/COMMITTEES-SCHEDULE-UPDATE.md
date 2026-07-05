# تحديث جدولة اللجان - إضافة ساعة البدء والنهاية

## التغييرات المطبقة

تم إضافة حقلين جديدين إلى نموذج `Committee` لتحسين جدولة اللجان:

### الحقول الجديدة

1. **`start_time`** - ساعة البدء
   - نوع الحقل: `TimeField`
   - اختياري (null=True, blank=True)
   - مثال: "09:00"

2. **`end_time`** - ساعة النهاية
   - نوع الحقل: `TimeField`
   - اختياري (null=True, blank=True)
   - مثال: "12:00"

---

## التحديثات على Backend

### 1. Models (committees/models.py)
تم إضافة الحقول الجديدة إلى نموذج `Committee`:

```python
start_time = models.TimeField(null=True, blank=True, help_text='ساعة البدء')
end_time = models.TimeField(null=True, blank=True, help_text='ساعة النهاية')
```

تم تحديث خاصية `is_scheduled`:
```python
@property
def is_scheduled(self) -> bool:
    return bool(self.date and self.start_time and self.end_time and self.location)
```

### 2. Serializers (committees/serializers.py)
- إضافة `start_time` و `end_time` إلى `CommitteeSerializer`
- إضافة الحقول إلى `CommitteeScheduleUpdateSerializer`

### 3. Views (committees/views.py)
تم تحديث جميع الـ endpoints لدعم الحقول الجديدة:
- `CommitteeViewSet` - update/partial_update
- `ProjectsAssignmentView` - عرض معلومات الجدولة
- `available_for_swap` - قائمة اللجان المتاحة
- `UpdateProjectSchedulesView` - تحديث مجدول متعدد

### 4. Migration
تم إنشاء وتطبيق:
```
committees/migrations/0003_committee_end_time_committee_start_time.py
```

---

## التحديثات على Frontend

### 1. CommitteeDetail.jsx
تم إضافة حقول إدخال ساعة البدء والنهاية في قسم الجدولة:

**في وضع التعديل:**
- حقل "ساعة البدء" (input type="time")
- حقل "ساعة النهاية" (input type="time")

**في وضع العرض:**
- عرض ساعة البدء مع أيقونة ساعة
- عرض ساعة النهاية مع أيقونة ساعة

### 2. ProjectsAssignment.jsx

#### أ. جدول توزيع المشاريع
تم إضافة عمودين جديدين في الجدول:
- عمود "ساعة البدء"
- عمود "ساعة النهاية"

**في وضع التعديل (Edit Mode):**
- حقول إدخال (input type="time") لتعديل ساعة البدء والنهاية لكل مشروع

**في وضع العرض:**
- عرض القيم أو "—" إذا كانت فارغة

#### ب. نافذة التعديل الجماعي (Bulk Edit Modal)
تم إضافة حقلين جديدين:
```jsx
<div className="pa-form-group">
  <label>ساعة البدء</label>
  <input type="time" ... />
</div>

<div className="pa-form-group">
  <label>ساعة النهاية</label>
  <input type="time" ... />
</div>
```

#### ج. نافذة تبديل اللجان (Swap Modal)
تم إضافة عرض ساعة البدء والنهاية لكل لجنة متاحة:
```jsx
{committee.start_time && (
  <div className="pa-committee-info-row">
    <Clock size={14} />
    <span>ساعة البدء: {committee.start_time}</span>
  </div>
)}
```

---

## كيفية الاستخدام

### من واجهة المستخدم

#### 1. تحديد جدول لجنة واحدة
1. انتقل إلى تفاصيل اللجنة (Committee Detail)
2. اضغط "Edit" في قسم Schedule
3. أدخل التاريخ، ساعة البدء، ساعة النهاية، والموقع
4. اضغط "Save"

#### 2. تحديث جدول متعدد للمشاريع
1. انتقل إلى Projects Assignment
2. اضغط "Edit Mode"
3. حدد المشاريع المطلوبة
4. اضغط "Bulk Edit"
5. أدخل ساعة البدء وساعة النهاية
6. اضغط "Apply Changes"
7. اضغط "Save Changes" لحفظ جميع التعديلات

#### 3. التعديل الفردي في الجدول
1. في وضع Edit Mode، يمكنك تعديل ساعة البدء والنهاية مباشرة في الجدول
2. اضغط "Save Changes" عند الانتهاء

---

## API Endpoints

### تحديث جدول لجنة
```http
PATCH /api/committees/committees/{id}/
Content-Type: application/json

{
  "date": "2025-01-15",
  "start_time": "09:00",
  "end_time": "12:00",
  "location": "Room 301",
  "status": "scheduled"
}
```

### تحديث جدول متعدد
```http
POST /api/committees/update-schedules/
Content-Type: application/json

{
  "updates": [
    {
      "committee_id": 1,
      "project_source": "IdeaApplication",
      "project_id": 123,
      "date": "2025-01-15",
      "start_time": "09:00",
      "end_time": "12:00",
      "location": "Room 301"
    }
  ]
}
```

---

## ملاحظات مهمة

1. **التوافق مع النظام القديم:** الحقل `time` القديم لا يزال موجوداً ويعمل
2. **الحقول اختيارية:** جميع الحقول الجديدة nullable ويمكن تركها فارغة
3. **التحقق من الجدولة:** خاصية `is_scheduled` تتطلب الآن وجود `start_time` و `end_time` بدلاً من `time`
4. **تنسيق الوقت:** استخدم تنسيق 24 ساعة (مثال: "09:00", "14:30")

---

## الخلاصة

✅ تم إضافة حقول ساعة البدء والنهاية في Backend
✅ تم تحديث جميع Serializers و Views
✅ تم إنشاء وتطبيق Migration
✅ تم تحديث واجهة تفاصيل اللجنة
✅ تم تحديث واجهة توزيع المشاريع
✅ تم إضافة دعم التعديل الجماعي
✅ تم تحديث نافذة تبديل اللجان
✅ تم اختبار البناء (Build) بنجاح

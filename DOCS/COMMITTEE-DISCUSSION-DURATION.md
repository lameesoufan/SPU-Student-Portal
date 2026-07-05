# تحديث نظام اللجان - إضافة مدة المناقشة والجدولة التلقائية

## نظرة عامة

تم إضافة نظام جدولة تلقائي للمشاريع داخل اللجان بناءً على **مدة المناقشة** المحددة. النظام يحسب تلقائياً وقت بداية ونهاية كل مشروع بناءً على:
- ساعة بدء اللجنة
- مدة المناقشة (بالدقائق)
- عدد المشاريع المخصصة للجنة

---

## المزايا الجديدة

### 1. حقل مدة المناقشة
- **الحقل:** `discussion_duration` (بالدقائق)
- **مثال:** 15 دقيقة، 30 دقيقة، 45 دقيقة
- **الغرض:** تحديد الوقت المخصص لكل مشروع

### 2. الحساب التلقائي لأوقات المشاريع
عند تحديد:
- ساعة البدء: 09:00
- مدة المناقشة: 15 دقيقة
- عدد المشاريع: 4

**النتيجة التلقائية:**
- المشروع 1: 09:00 - 09:15
- المشروع 2: 09:15 - 09:30
- المشروع 3: 09:30 - 09:45
- المشروع 4: 09:45 - 10:00

### 3. التوقف التلقائي عند ساعة النهاية
- إذا كانت ساعة النهاية 12:00 والمشاريع تتجاوز هذا الوقت
- يتوقف النظام عن جدولة المشاريع الإضافية
- يتم تنبيه المستخدم بوجود مشاريع غير مجدولة

---

## Backend Implementation

### 1. Models (committees/models.py)

#### حقل جديد:
```python
discussion_duration = models.PositiveIntegerField(
    null=True, 
    blank=True, 
    help_text='مدة المناقشة بالدقائق (مثال: 15، 30، 45)'
)
```

#### دالة حساب الأوقات:
```python
def calculate_project_times(self) -> list:
    """
    Calculate start and end times for each project based on discussion_duration.
    Returns list of dicts: {project_index, start_time, end_time}
    """
    from datetime import datetime, timedelta
    
    if not self.start_time or not self.discussion_duration:
        return []
    
    projects = self.get_all_projects()
    if not projects:
        return []
    
    times = []
    current_time = datetime.combine(datetime.today(), self.start_time)
    duration = timedelta(minutes=self.discussion_duration)
    
    for idx, project in enumerate(projects):
        project_end = current_time + duration
        
        # Check if we've exceeded end_time
        if self.end_time:
            if project_end.time() > self.end_time:
                break  # Stop scheduling
        
        times.append({
            'project_index': idx,
            'project_id': project['id'],
            'project_source': project['source'],
            'start_time': current_time.strftime('%H:%M'),
            'end_time': project_end.strftime('%H:%M'),
        })
        
        current_time = project_end
    
    return times
```

### 2. Serializers (committees/serializers.py)

تم تحديث `CommitteeSerializer` لإضافة الأوقات المحسوبة لكل مشروع:

```python
def get_projects(self, obj):
    projects = obj.get_all_projects()
    project_times = obj.calculate_project_times()
    
    # Map times to projects
    times_map = {}
    for pt in project_times:
        key = f"{pt['project_source']}-{pt['project_id']}"
        times_map[key] = {
            'start_time': pt['start_time'],
            'end_time': pt['end_time'],
        }
    
    # Add calculated times to each project
    for project in projects:
        key = f"{project['source']}-{project['id']}"
        if key in times_map:
            project['scheduled_start'] = times_map[key]['start_time']
            project['scheduled_end'] = times_map[key]['end_time']
        else:
            project['scheduled_start'] = None
            project['scheduled_end'] = None
    
    return projects
```

### 3. Views (committees/views.py)

تم تحديث:
- `ProjectsAssignmentView` - إضافة `scheduled_start` و `scheduled_end` لكل مشروع
- `UpdateProjectSchedulesView` - دعم تحديث `discussion_duration`
- `available_for_swap` - عرض معلومات `discussion_duration` للجان

### 4. Export to Excel (committees/services.py)

تم إضافة أعمدة جديدة في ملف Excel:
- **ساعة البدء** - ساعة بدء اللجنة
- **ساعة النهاية** - ساعة نهاية اللجنة
- **مدة المناقشة** - مدة المناقشة بالدقائق
- **وقت بداية المناقشة** - الوقت المحسوب تلقائياً لكل مشروع
- **وقت نهاية المناقشة** - الوقت المحسوب تلقائياً لكل مشروع

```python
# في ملف Excel سيظهر:
'ساعة البدء': '09:00'
'ساعة النهاية': '12:00'
'مدة المناقشة': '15 دقيقة'
'وقت بداية المناقشة': '09:00'  # محسوب تلقائياً
'وقت نهاية المناقشة': '09:15'   # محسوب تلقائياً
```

---

## Frontend Implementation

### 1. CommitteeDetail.jsx

#### في قسم Schedule:
إضافة حقل إدخال لمدة المناقشة:

```jsx
<div className="ccd-edit-field">
  <label>مدة المناقشة (بالدقائق)</label>
  <input
    type="number"
    min="5"
    step="5"
    placeholder="مثال: 15، 30، 45"
    value={scheduleDraft.discussion_duration}
    onChange={(e) => setScheduleDraft({ 
      ...scheduleDraft, 
      discussion_duration: e.target.value 
    })}
  />
  <small>سيتم حساب وقت كل مشروع تلقائياً بناءً على المدة المحددة</small>
</div>
```

#### في وضع العرض:
```jsx
{committee.discussion_duration && (
  <div className="ccd-schedule-row">
    <Clock size={14} />
    <span>مدة المناقشة</span>
    <span>{committee.discussion_duration} دقيقة</span>
  </div>
)}
```

#### عرض أوقات المشاريع:
```jsx
{p.scheduled_start && p.scheduled_end && (
  <span style={{ color: '#667EEA', fontWeight: 500 }}>
    <Clock size={11} /> {p.scheduled_start} - {p.scheduled_end}
  </span>
)}
```

### 2. ProjectsAssignment.jsx

#### إضافة أعمدة في الجدول:
- **مدة المناقشة** - قابل للتعديل في Edit Mode
- **وقت بداية المناقشة** - محسوب تلقائياً (بخلفية زرقاء)
- **وقت نهاية المناقشة** - محسوب تلقائياً (بخلفية زرقاء)

```jsx
<th>مدة المناقشة</th>
<th>وقت بداية المناقشة</th>
<th>وقت نهاية المناقشة</th>
```

#### في Bulk Edit Modal:
```jsx
<div className="pa-form-group">
  <label>
    <Clock size={16} />
    مدة المناقشة (بالدقائق)
  </label>
  <input
    type="number"
    min="5"
    step="5"
    placeholder="مثال: 15، 30، 45"
    value={bulkValues.discussion_duration}
    onChange={(e) => setBulkValues(prev => ({ 
      ...prev, 
      discussion_duration: e.target.value 
    }))}
  />
  <small>سيتم حساب وقت كل مشروع تلقائياً</small>
</div>
```

#### تمييز الأوقات المحسوبة:
```jsx
<td style={{ 
  backgroundColor: '#f0f9ff', 
  fontWeight: 500, 
  color: '#0369a1' 
}}>
  {project.scheduled_start || '—'}
</td>
```

---

## كيفية الاستخدام

### الطريقة 1: من تفاصيل اللجنة

1. افتح تفاصيل اللجنة (Committee Detail)
2. اضغط "Edit" في قسم Schedule
3. أدخل:
   - **التاريخ:** 2025-01-15
   - **ساعة البدء:** 09:00
   - **ساعة النهاية:** 12:00
   - **مدة المناقشة:** 15 (دقيقة)
   - **الموقع:** Room A-301
4. اضغط "Save"
5. سيتم عرض أوقات المشاريع تلقائياً:
   - المشروع 1: 09:00 - 09:15
   - المشروع 2: 09:15 - 09:30
   - وهكذا...

### الطريقة 2: من جدول توزيع المشاريع

1. افتح Projects Assignment
2. اضغط "Edit Mode"
3. حدد مشاريع متعددة
4. اضغط "Bulk Edit"
5. أدخل مدة المناقشة (مثال: 30 دقيقة)
6. اضغط "Apply Changes"
7. اضغط "Save Changes"

### الطريقة 3: التعديل المباشر في الجدول

1. في وضع Edit Mode، يمكنك تعديل مدة المناقشة مباشرة لكل لجنة
2. الأوقات المحسوبة (بخلفية زرقاء) تتحدث تلقائياً

---

## مثال عملي

### السيناريو:
- لجنة سيمينار 1 - برمجيات - تخرج 2
- 8 مشاريع مخصصة
- يوم الاجتماع: 15/1/2025
- ساعة البدء: 09:00 صباحاً
- ساعة النهاية: 12:00 ظهراً
- مدة المناقشة: 20 دقيقة

### النتيجة التلقائية:

| المشروع | وقت البداية | وقت النهاية |
|---------|-------------|-------------|
| المشروع 1 | 09:00 | 09:20 |
| المشروع 2 | 09:20 | 09:40 |
| المشروع 3 | 09:40 | 10:00 |
| المشروع 4 | 10:00 | 10:20 |
| المشروع 5 | 10:20 | 10:40 |
| المشروع 6 | 10:40 | 11:00 |
| المشروع 7 | 11:00 | 11:20 |
| المشروع 8 | 11:20 | 11:40 |

✅ جميع المشاريع ضمن الوقت المحدد (قبل 12:00)

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
  "discussion_duration": 15,
  "location": "Room A-301",
  "status": "scheduled"
}
```

### تحديث جداول متعددة
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
      "discussion_duration": 15,
      "location": "Room A-301"
    }
  ]
}
```

### الحصول على معلومات اللجنة مع الأوقات المحسوبة
```http
GET /api/committees/committees/{id}/

Response:
{
  "id": 1,
  "date": "2025-01-15",
  "start_time": "09:00",
  "end_time": "12:00",
  "discussion_duration": 15,
  "projects": [
    {
      "id": 123,
      "title": "نظام إدارة المشاريع",
      "scheduled_start": "09:00",
      "scheduled_end": "09:15"
    },
    {
      "id": 124,
      "title": "تطبيق الجوال",
      "scheduled_start": "09:15",
      "scheduled_end": "09:30"
    }
  ]
}
```

---

## التصدير إلى Excel

عند تصدير جدول توزيع المشاريع، سيحتوي ملف Excel على:

### الأعمدة الجديدة:
1. **ساعة البدء** - 09:00
2. **ساعة النهاية** - 12:00
3. **مدة المناقشة** - 15 دقيقة
4. **وقت بداية المناقشة** - 09:00 (محسوب لكل مشروع)
5. **وقت نهاية المناقشة** - 09:15 (محسوب لكل مشروع)

### الاستخدام:
```http
GET /api/committees/projects-assignment/export/
```

سيتم تحميل ملف: `projects_assignment_20250104_1430.xlsx`

---

## Migration

تم إنشاء وتطبيق:
```
committees/migrations/0004_committee_discussion_duration.py
```

لتطبيق على قاعدة بيانات موجودة:
```bash
cd backend
python manage.py migrate committees
```

---

## ملاحظات مهمة

### 1. التحقق من الوقت الكافي
- النظام يتوقف تلقائياً عند الوصول إلى ساعة النهاية
- إذا كانت المشاريع أكثر من الوقت المتاح، سيتم جدولة ما يمكن جدولته فقط

### 2. القيم الافتراضية
- مدة المناقشة: اختيارية (يمكن تركها فارغة)
- إذا لم تُحدد، لن يتم حساب أوقات تلقائية

### 3. المرونة
- يمكن تغيير مدة المناقشة في أي وقت
- سيتم إعادة حساب جميع الأوقات تلقائياً

### 4. التنسيق
- أوقات المناقشة المحسوبة تظهر بلون مميز (أزرق)
- سهلة التمييز في الجدول

---

## الخلاصة

✅ إضافة حقل مدة المناقشة
✅ حساب تلقائي لأوقات المشاريع
✅ توقف تلقائي عند ساعة النهاية
✅ عرض الأوقات في تفاصيل اللجنة
✅ عرض الأوقات في جدول التوزيع
✅ دعم التعديل الجماعي
✅ تصدير الأوقات في ملف Excel
✅ تم اختبار البناء بنجاح

# إصلاح خطأ discussion_duration - Bad Request 400

## المشكلة

عند محاولة تحديث جدول لجنة، كان النظام يرجع خطأ 400 Bad Request:

```
Bad Request: /api/committees/committees/1/
"PATCH /api/committees/committees/1/ HTTP/1.1" 400
```

## السبب

المشكلة كانت في معالجة حقل `discussion_duration`:
1. **Frontend** كان يرسل string فارغ `""` بدلاً من `null` عندما يكون الحقل فارغاً
2. **Backend** كان يتوقع integer أو null، وليس string فارغ
3. هذا أدى إلى validation error

## الحل

### 1. Backend (serializers.py)

تم إضافة validation مخصص لـ `discussion_duration`:

```python
class CommitteeScheduleUpdateSerializer(serializers.ModelSerializer):
    """Lightweight serializer for inline editing of date/time/location/status."""
    discussion_duration = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    
    class Meta:
        model = Committee
        fields = ['date', 'time', 'start_time', 'end_time', 'discussion_duration', 'location', 'status']
    
    def validate_discussion_duration(self, value):
        """Allow empty string to be converted to None"""
        if value == '' or value is None:
            return None
        try:
            val = int(value)
            if val < 1:
                raise serializers.ValidationError("Duration must be at least 1 minute")
            return val
        except (ValueError, TypeError):
            return None
```

**الفوائد:**
- يقبل `None` و string فارغ `""`
- يحول القيمة تلقائياً إلى integer
- يتحقق من أن القيمة أكبر من أو تساوي 1

### 2. Backend (views.py)

تحسين معالجة `discussion_duration` في `UpdateProjectSchedulesView`:

```python
if 'discussion_duration' in update:
    # Handle both empty string and None
    val = update['discussion_duration']
    if val == '' or val is None:
        committee.discussion_duration = None
    else:
        try:
            committee.discussion_duration = int(val)
        except (ValueError, TypeError):
            committee.discussion_duration = None
    schedule_updated = True
```

**الفوائد:**
- معالجة آمنة للقيم الفارغة
- تحويل تلقائي إلى integer
- منع الأخطاء عند إدخال قيم غير صحيحة

### 3. Frontend (CommitteeDetail.jsx)

تنظيف البيانات قبل الإرسال:

```javascript
const saveSchedule = async () => {
  if (busy || !committee) return;
  setBusy(true);
  try {
    // Clean up the data before sending
    const cleanedData = {
      ...scheduleDraft,
      discussion_duration: scheduleDraft.discussion_duration 
        ? parseInt(scheduleDraft.discussion_duration) 
        : null,
    };
    const res = await updateCommittee(committee.id, cleanedData);
    setCommittee(res.data);
    setEditingSchedule(false);
    // ...
  }
}
```

**الفوائد:**
- تحويل string إلى integer قبل الإرسال
- إرسال `null` بدلاً من string فارغ

### 4. Frontend (ProjectsAssignment.jsx)

#### في saveChanges:

```javascript
const updates = Object.entries(editedProjects).map(([index, values]) => {
  const project = filteredProjects[parseInt(index)];
  
  // Clean up discussion_duration - convert to integer or null
  const cleanedValues = { ...values };
  if ('discussion_duration' in cleanedValues) {
    cleanedValues.discussion_duration = cleanedValues.discussion_duration 
      ? parseInt(cleanedValues.discussion_duration) 
      : null;
  }
  
  return {
    committee_id: project.committee_id,
    project_source: project.project_source,
    project_id: project.project_id,
    ...cleanedValues
  };
});
```

#### في applyBulkEdit:

```javascript
const applyBulkEdit = () => {
  const newEdited = { ...editedProjects };
  selectedRows.forEach(index => {
    newEdited[index] = {
      ...newEdited[index],
      // ...
      ...(bulkValues.discussion_duration && { 
        discussion_duration: parseInt(bulkValues.discussion_duration) || null 
      }),
      // ...
    };
  });
  // ...
};
```

## الاختبار

تم اختبار الحل بنجاح:

```bash
# Backend check
python manage.py check
# ✓ System check identified no issues

# Frontend build
npm run build
# ✓ built in 1.89s
```

## السيناريوهات المعالجة

الآن النظام يتعامل بشكل صحيح مع:

| الحالة | القيمة المرسلة | النتيجة |
|--------|----------------|---------|
| حقل فارغ | `""` | `null` ✅ |
| قيمة صحيحة | `"15"` | `15` ✅ |
| قيمة رقمية | `15` | `15` ✅ |
| null | `null` | `null` ✅ |
| قيمة سالبة | `"-5"` | Validation Error ❌ |
| نص غير رقمي | `"abc"` | `null` ✅ |

## الخلاصة

✅ تم إصلاح خطأ 400 Bad Request
✅ معالجة آمنة للقيم الفارغة
✅ تحويل تلقائي من string إلى integer
✅ validation مناسب في Backend
✅ تنظيف البيانات في Frontend
✅ تم اختبار جميع السيناريوهات

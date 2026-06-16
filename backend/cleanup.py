import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

import django
django.setup()

from workflow.models import (
    WorkflowTemplate, WorkflowStage, WorkflowStageInstance,
    WorkflowStageField, WorkflowFieldResponse
)
from django.db.models import Count
from django.db import transaction

merged = 0
deleted = 0

with transaction.atomic():
    # ===== 1. تنظيف المراحل المكررة =====
    for template in WorkflowTemplate.objects.all():
        dups = template.stages.values('name').annotate(c=Count('id')).filter(c__gt=1)
        for g in dups:
            name = g['name']
            stages = list(template.stages.filter(name=name).order_by('id'))
            if len(stages) < 2:
                continue
            original = stages[0]
            for dup in stages[1:]:
                print(f'  Merging stage "{dup.name}" ID={dup.id} -> original ID={original.id}')
                for f in dup.fields.all():
                    ef = original.fields.filter(label=f.label).first()
                    if not ef:
                        f.stage = original
                        f.save()
                    else:
                        for r in f.responses.all():
                            WorkflowFieldResponse.objects.update_or_create(
                                stage_instance=r.stage_instance,
                                field=ef,
                                defaults={'value': r.value}
                            )
                        f.delete()
                for inst in dup.instances.all():
                    ei = WorkflowStageInstance.objects.filter(
                        project_workflow=inst.project_workflow,
                        stage=original,
                        occurrence_number=inst.occurrence_number
                    ).first()
                    if ei:
                        for r in inst.field_responses.all():
                            fi = original.fields.filter(label=r.field.label).first()
                            if fi:
                                WorkflowFieldResponse.objects.update_or_create(
                                    stage_instance=ei, field=fi,
                                    defaults={'value': r.value}
                                )
                            r.delete()
                        inst.delete()
                    else:
                        inst.stage = original
                        inst.save()
                dup.delete()
                deleted += 1
                print(f'  DELETED duplicate stage "{dup.name}" ID={dup.id}')
            merged += 1

    # ===== 2. تنظيف الحقول المكررة داخل نفس المرحلة =====
    fields_deleted = 0
    for stage in WorkflowStage.objects.all():
        field_dups = (
            stage.fields
            .values('label')
            .annotate(c=Count('id'))
            .filter(c__gt=1)
        )
        for g in field_dups:
            label = g['label']
            fields = list(stage.fields.filter(label=label).order_by('id'))
            if len(fields) < 2:
                continue
            keep = fields[0]
            for dup_f in fields[1:]:
                print(f'  Dedup field "{dup_f.label}" ID={dup_f.id} in stage "{stage.name}" -> keeping ID={keep.id}')
                for r in dup_f.responses.all():
                    WorkflowFieldResponse.objects.update_or_create(
                        stage_instance=r.stage_instance,
                        field=keep,
                        defaults={'value': r.value}
                    )
                    r.delete()
                dup_f.delete()
                fields_deleted += 1

    # ===== 3. تنظيف ردود مكررة =====
    responses_deleted = 0
    for inst in WorkflowStageInstance.objects.all():
        seen = set()
        for resp in inst.field_responses.all().order_by('id'):
            key = resp.field_id
            if key in seen:
                resp.delete()
                responses_deleted += 1
            else:
                seen.add(key)

print(f'\nDone!')
print(f'  Stages merged: {merged}, deleted: {deleted}')
print(f'  Duplicate fields deleted: {fields_deleted}')
print(f'  Duplicate responses deleted: {responses_deleted}')

ok = True
for t in WorkflowTemplate.objects.all():
    for d in t.stages.values('name').annotate(c=Count('id')).filter(c__gt=1):
        ok = False
        print(f'STILL DUP STAGE: {t.name} -> {d["c"]}x {d["name"]}')
for s in WorkflowStage.objects.all():
    for d in s.fields.values('label').annotate(c=Count('id')).filter(c__gt=1):
        ok = False
        print(f'STILL DUP FIELD: {s.name} -> {d["c"]}x {d["label"]}')
if ok:
    print('All clean! No duplicates remaining.')
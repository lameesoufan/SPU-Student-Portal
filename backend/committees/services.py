"""
Business logic for the committees app — REVISED DESIGN.

Functions:
  - spawn_committee_for_template() : create exactly ONE Committee per template
  - collect_projects()              : gather projects matching (dept, project_type)
  - distribute_projects_to_committees() :
        For each (department, project_type):
          For each of the 4 committee types:
            Round-robin distribute projects across committees of that type.
            Each project appears in 4 committees (one per type).
  - copy_template()                : clone a template (1:1)
  - get_dashboard_warnings()       : check for missing chairs, undistributed, etc.
  - get_doctor_workload()          : workload per doctor
  - export_*                       : PDF & Excel
"""
from __future__ import annotations
import io
import random
from dataclasses import dataclass, field
from typing import Iterable

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from accounts.models import DEPARTMENTS
from .models import (
    CommitteeTemplate, Committee,
    COMMITTEE_TYPE_CHOICES, PROJECT_TYPE_CHOICES,
    ALL_COMMITTEE_TYPES,
)


User = get_user_model()


# ── 1) Spawn ONE committee per template ───────────────────────────────────────

@transaction.atomic
def spawn_committee_for_template(template: CommitteeTemplate) -> Committee:
    """
    Create exactly ONE Committee instance from this template.
    Idempotent — if a committee already exists for this template, return it.
    """
    existing = template.committees.first()
    if existing:
        return existing

    members_qs = list(template.members.all())
    c = Committee.objects.create(
        template       = template,
        sequence_number= 1,
        committee_type = template.committee_type,
        department     = template.department,
        project_type   = template.project_type,
        semester       = template.semester,
        chair          = template.chair,
        status         = 'draft',
    )
    if members_qs:
        c.members.set(members_qs)
    return c


# Keep backward-compat alias for any caller still using the old name
def spawn_committees_for_template(template: CommitteeTemplate, count: int | None = None):
    """Backward-compatible wrapper — always returns a 1-element list."""
    c = spawn_committee_for_template(template)
    return [c]


# ── 2) Collect projects for a (department, project_type) ──────────────────────

@dataclass
class CollectedProject:
    source: str          # 'IdeaApplication' | 'StudentIdeaProposal'
    id: int
    title: str
    department: str
    project_type: str | None
    supervisor_id: int | None
    supervisor_name: str
    student_id: int
    student_name: str
    team_size: int


def collect_projects_for_template(template: CommitteeTemplate) -> list[CollectedProject]:
    """
    Collect all projects matching this template's
        (department, project_type)
    from BOTH project sources:
      - IdeaApplication.idea.department AND .project_type, status='registered'
      - StudentIdeaProposal.department  AND .project_type, status='assigned'
    """
    return _collect_projects(
        department   = template.department,
        project_type = template.project_type,
    )


def _collect_projects(department: str, project_type: str | None) -> list[CollectedProject]:
    """Lower-level collector — used by both template-based and (dept, ptype)-based flows."""
    result: list[CollectedProject] = []

    # ── IdeaApplication source ────────────────────────────────────────────────
    from projects.models import IdeaApplication
    idea_apps = (
        IdeaApplication.objects
        .filter(status='registered',
                idea__department=department)
        .select_related('idea', 'idea__doctor', 'student')
    )
    for app in idea_apps:
        ptype = getattr(app.idea, 'project_type', None)
        if project_type and ptype and ptype != project_type:
            continue
        result.append(CollectedProject(
            source          = 'IdeaApplication',
            id              = app.id,
            title           = app.idea.title,
            department      = app.idea.department,
            project_type    = ptype,
            supervisor_id   = app.idea.doctor_id,
            supervisor_name = (app.idea.doctor.get_full_name() or app.idea.doctor.username)
                              if app.idea.doctor_id else '',
            student_id      = app.student_id,
            student_name    = app.student.get_full_name() or app.student.username
                              if app.student_id else '',
            team_size       = app.team_size,
        ))

    # ── StudentIdeaProposal source ────────────────────────────────────────────
    from projects.models import StudentIdeaProposal
    proposals = (
        StudentIdeaProposal.objects
        .filter(status='assigned',
                department=department)
        .select_related('student', 'supervisor')
    )
    for prop in proposals:
        ptype = getattr(prop, 'project_type', None)
        if project_type and ptype and ptype != project_type:
            continue
        sup_name = ''
        if prop.supervisor_id:
            sup_name = prop.supervisor.get_full_name() or prop.supervisor.username
        result.append(CollectedProject(
            source          = 'StudentIdeaProposal',
            id              = prop.id,
            title           = prop.title,
            department      = prop.department,
            project_type    = ptype,
            supervisor_id   = prop.supervisor_id,
            supervisor_name = sup_name,
            student_id      = prop.student_id,
            student_name    = prop.student.get_full_name() or prop.student.username
                              if prop.student_id else '',
            team_size       = prop.team_size,
        ))

    return result


# ── 3) Distribution: Round-Robin across committees of each type ────────────────
#
# REVISED ALGORITHM
# ─────────────────
# For each (department, project_type) combination that has projects:
#   For each of the 4 committee types (seminar_1, seminar_2, technical, final_discussion):
#     - Get all committees of that type matching the (department, project_type)
#     - If no committees of that type exist → mark all projects as undistributed for that type
#     - Otherwise: round-robin distribute the projects across these committees
#       (with wrap-around if projects > committees; extras load the first committees)
#
# Each project is therefore assigned to up to 4 committees (one per type).

@dataclass
class TypeDistribution:
    """Result of distributing projects to committees of a single committee type."""
    committee_type: str
    committees_count: int
    assignments: list[dict] = field(default_factory=list)  # [{committee_id, seq, project}]
    undistributed: list[dict] = field(default_factory=list)  # projects that couldn't be placed


@dataclass
class DistributionPlan:
    template_id: int | None       # None when triggered without a specific template
    department: str
    project_type: str
    projects_count: int
    by_type: list[TypeDistribution] = field(default_factory=list)


def build_distribution_plan(template: CommitteeTemplate,
                             projects: list[CollectedProject] | None = None,
                             ) -> DistributionPlan:
    """
    Build a distribution plan for a single template's (department, project_type).
    Iterates over ALL 4 committee types and assigns projects to each type's committees.
    """
    if projects is None:
        projects = collect_projects_for_template(template)

    plan = DistributionPlan(
        template_id   = template.id,
        department    = template.department,
        project_type  = template.project_type,
        projects_count= len(projects),
    )

    for ctype in ALL_COMMITTEE_TYPES:
        committees = list(
            Committee.objects
            .filter(committee_type=ctype,
                    department   =template.department,
                    project_type =template.project_type)
            .order_by('sequence_number', 'id')
        )

        td = TypeDistribution(committee_type=ctype, committees_count=len(committees))

        if not committees:
            # No committees of this type — all projects are undistributed for this type
            td.undistributed = [_project_to_dict(p) for p in projects]
        else:
            # Shuffle for fair distribution
            shuffled = list(projects)
            random.shuffle(shuffled)
            for idx, proj in enumerate(shuffled):
                committee = committees[idx % len(committees)]
                td.assignments.append({
                    'committee_id'   : committee.id,
                    'sequence_number': committee.sequence_number,
                    'project'        : _project_to_dict(proj),
                })

        plan.by_type.append(td)

    return plan


def build_distribution_plan_for_combo(department: str,
                                       project_type: str,
                                       projects: list[CollectedProject] | None = None,
                                       ) -> DistributionPlan:
    """Same as build_distribution_plan but without a template (driven by dept+ptype)."""
    if projects is None:
        projects = _collect_projects(department, project_type)

    plan = DistributionPlan(
        template_id   = None,
        department    = department,
        project_type  = project_type,
        projects_count= len(projects),
    )

    for ctype in ALL_COMMITTEE_TYPES:
        committees = list(
            Committee.objects
            .filter(committee_type=ctype,
                    department   =department,
                    project_type =project_type)
            .order_by('sequence_number', 'id')
        )

        td = TypeDistribution(committee_type=ctype, committees_count=len(committees))

        if not committees:
            td.undistributed = [_project_to_dict(p) for p in projects]
        else:
            shuffled = list(projects)
            random.shuffle(shuffled)
            for idx, proj in enumerate(shuffled):
                committee = committees[idx % len(committees)]
                td.assignments.append({
                    'committee_id'   : committee.id,
                    'sequence_number': committee.sequence_number,
                    'project'        : _project_to_dict(proj),
                })

        plan.by_type.append(td)

    return plan


@transaction.atomic
def apply_distribution_plan(plan: DistributionPlan) -> int:
    """
    Persist a distribution plan to the DB.
    Clears existing project assignments on the affected committees first.
    Returns the number of assignments written.
    """
    committee_ids = set()
    for td in plan.by_type:
        for a in td.assignments:
            committee_ids.add(a['committee_id'])

    committees = Committee.objects.filter(id__in=committee_ids)
    by_id = {c.id: c for c in committees}

    # Clear existing project assignments on these committees
    for c in committees:
        c.applications.clear()
        c.proposals.clear()

    written = 0
    from projects.models import IdeaApplication, StudentIdeaProposal
    for td in plan.by_type:
        for a in td.assignments:
            c = by_id.get(a['committee_id'])
            if not c:
                continue
            p = a['project']
            if p['source'] == 'IdeaApplication':
                c.applications.add(p['id'])
            else:
                c.proposals.add(p['id'])
            written += 1

    return written


@transaction.atomic
def distribute_projects_to_committees(template_ids: list[int] | None = None,
                                       semester: str | None = None,
                                       dry_run: bool = False,
                                       ) -> dict:
    """
    Top-level distribution entrypoint — REVISED.

    For each unique (department, project_type) combination:
      - Collect all matching projects
      - For each of the 4 committee types:
          Round-robin distribute across the committees of that type
          (extras wrap around to load the first committees more heavily)

    If `template_ids` is given, only those templates' (dept, ptype) combos are processed.
    If `semester` is given, projects are NOT filtered by semester (the source models don't
    have a semester field) but committees ARE filtered by semester.
    """
    # Determine the (department, project_type) combinations to process
    if template_ids:
        combos = set(
            CommitteeTemplate.objects
            .filter(id__in=template_ids)
            .values_list('department', 'project_type')
        )
    else:
        combos = set(
            CommitteeTemplate.objects
            .values_list('department', 'project_type')
        )

    plans: list[DistributionPlan] = []
    total_distributed   = 0
    total_undistributed = 0

    for dept, ptype in combos:
        projects = _collect_projects(dept, ptype)
        if not projects:
            # No projects for this combo — skip but still build an empty plan
            plan = build_distribution_plan_for_combo(dept, ptype, projects=[])
        else:
            plan = build_distribution_plan_for_combo(dept, ptype, projects=projects)

        if not dry_run:
            apply_distribution_plan(plan)

        for td in plan.by_type:
            total_distributed   += len(td.assignments)
            total_undistributed += len(td.undistributed)

        plans.append(plan)

    return {
        'processed_templates'   : len(plans),
        'distributed_projects'  : total_distributed,
        'undistributed_projects': total_undistributed,
        'plans'                 : [_plan_to_dict(p) for p in plans],
        'dry_run'               : dry_run,
        'executed_at'           : timezone.now().isoformat(),
    }


def _project_to_dict(p: CollectedProject) -> dict:
    return {
        'source':          p.source,
        'id':              p.id,
        'title':           p.title,
        'department':      p.department,
        'project_type':    p.project_type,
        'supervisor_id':   p.supervisor_id,
        'supervisor_name': p.supervisor_name,
        'student_id':      p.student_id,
        'student_name':    p.student_name,
        'team_size':       p.team_size,
    }


def _type_dist_to_dict(td: TypeDistribution) -> dict:
    return {
        'committee_type'  : td.committee_type,
        'committees_count': td.committees_count,
        'assignments'     : td.assignments,
        'undistributed'   : td.undistributed,
    }


def _plan_to_dict(plan: DistributionPlan) -> dict:
    return {
        'template_id'     : plan.template_id,
        'department'      : plan.department,
        'project_type'    : plan.project_type,
        'projects_count'  : plan.projects_count,
        'by_type'         : [_type_dist_to_dict(td) for td in plan.by_type],
    }


# ── 4) Copy a template ────────────────────────────────────────────────────────

@transaction.atomic
def copy_template(source: CommitteeTemplate,
                  copy_doctors: bool = True,
                  new_committee_type: str | None = None,
                  new_department: str | None = None,
                  new_project_type: str | None = None,
                  new_semester: str | None = None,
                  committees_count: int | None = None,  # accepted for backward-compat, ignored
                  created_by: User | None = None,
                  ) -> CommitteeTemplate:
    """
    Clone a template. The new template creates exactly ONE committee (handled by the
    viewset's perform_create). Committees_count parameter is ignored in the new design.
    """
    new = CommitteeTemplate.objects.create(
        name           = (source.name or '') + ' (نسخة)',
        committee_type = new_committee_type or source.committee_type,
        department     = new_department    or source.department,
        project_type   = new_project_type  or source.project_type,
        semester       = new_semester      if new_semester is not None else source.semester,
        is_approved    = False,
        created_by     = created_by or source.created_by,
    )
    if copy_doctors:
        if source.chair_id:
            new.chair = source.chair
            new.save(update_fields=['chair'])
        new.members.set(list(source.members.all()))
    return new


# ── 5) Warnings ───────────────────────────────────────────────────────────────

def get_dashboard_warnings(semester: str | None = None) -> list[dict]:
    """
    Return a list of warnings (NON-BLOCKING — Dean is informed, never forced).
    Each warning: {level: 'error'|'warn'|'info', code: str, message: str, related_id: int|None}
    """
    warnings: list[dict] = []

    qs = Committee.objects.all()
    if semester:
        qs = qs.filter(semester=semester)

    # ── Committees without a chair ────────────────────────────────────────────
    for c in qs.filter(chair__isnull=True):
        warnings.append({
            'level':      'error',
            'code':       'no_chair',
            'message':    f'اللجنة "{c}" ليس لديها رئيس. يرجى تعيين رئيس قبل التوزيع.',
            'related_id': c.id,
        })

    # ── Projects without matching committees (per committee type) ──────────────
    # For each (department, project_type) that has projects, check whether committees
    # exist for EACH of the 4 committee types. If a type is missing, warn.
    from projects.models import IdeaApplication, StudentIdeaProposal

    dept_pt_with_projects = set()
    for app in IdeaApplication.objects.filter(status='registered').select_related('idea'):
        ptype = getattr(app.idea, 'project_type', None)
        dept_pt_with_projects.add((app.idea.department, ptype))
    for prop in StudentIdeaProposal.objects.filter(status='assigned'):
        ptype = getattr(prop, 'project_type', None)
        dept_pt_with_projects.add((prop.department, ptype))

    existing_combos = set(
        Committee.objects.values_list('committee_type', 'department', 'project_type')
    )

    for dept, ptype in dept_pt_with_projects:
        for ctype in ALL_COMMITTEE_TYPES:
            if (ctype, dept, ptype) not in existing_combos:
                from .models import COMMITTEE_TYPE_AR, DEPARTMENT_AR, PROJECT_TYPE_AR
                ct_label  = COMMITTEE_TYPE_AR.get(ctype, ctype)
                dep_label = DEPARTMENT_AR.get(dept, dept)
                pt_label  = PROJECT_TYPE_AR.get(ptype, ptype) if ptype else '—'
                warnings.append({
                    'level':   'warn',
                    'code':    'missing_committee_type',
                    'message': f'لا توجد لجان من نوع "{ct_label}" للتركيبة ({dep_label} - {pt_label}). '
                               f'المشاريع المطابقة لن تُوزَّع على هذا النوع.',
                    'related_id': None,
                })

    # ── Doctor overload ───────────────────────────────────────────────────────
    workload = get_doctor_workload(semester=semester)
    for w in workload:
        if w['total_committees'] >= 6:
            warnings.append({
                'level':      'warn',
                'code':       'doctor_overload',
                'message':    f'الدكتور "{w["doctor_name"]}" في {w["total_committees"]} لجنة (عبء مرتفع).',
                'related_id': w['doctor_id'],
            })

    # ── Draft committees not yet scheduled ────────────────────────────────────
    unscheduled = qs.filter(status='draft').count()
    if unscheduled:
        warnings.append({
            'level':   'info',
            'code':    'unscheduled',
            'message': f'{unscheduled} لجنة بحالة "مسودة" — بانتظار تحديد موعد الانعقاد.',
            'related_id': None,
        })

    return warnings


# ── 6) Doctor workload ────────────────────────────────────────────────────────

def get_doctor_workload(semester: str | None = None) -> list[dict]:
    """
    Return list of doctors with their committee counts.
    workload_level: low (≤2), med (3-5), high (≥6)
    """
    qs = Committee.objects.all()
    if semester:
        qs = qs.filter(semester=semester)

    doctors: dict[int, dict] = {}
    for c in qs:
        if c.chair_id:
            d = doctors.setdefault(c.chair_id, {
                'doctor_id':        c.chair_id,
                'doctor_name':      c.chair.get_full_name() or c.chair.username,
                'department_ar':    _dept_ar(c.chair.department),
                'chaired_count':    0,
                'member_count':     0,
                'total_committees': 0,
            })
            d['chaired_count']    += 1
            d['total_committees'] += 1
        for m in c.members.all():
            d = doctors.setdefault(m.id, {
                'doctor_id':        m.id,
                'doctor_name':      m.get_full_name() or m.username,
                'department_ar':    _dept_ar(m.department),
                'chaired_count':    0,
                'member_count':     0,
                'total_committees': 0,
            })
            d['member_count']     += 1
            d['total_committees'] += 1

    for d in doctors.values():
        t = d['total_committees']
        d['workload_level'] = 'low' if t <= 2 else ('med' if t <= 5 else 'high')

    # Sort by total_committees desc
    return sorted(doctors.values(), key=lambda x: -x['total_committees'])


def _dept_ar(dept: str | None) -> str:
    if not dept:
        return ''
    from .models import DEPARTMENT_AR
    return DEPARTMENT_AR.get(dept, dept)


# ── 7) Export: PDF + Excel ────────────────────────────────────────────────────

def export_committees_pdf(semester: str | None = None) -> bytes:
    """
    Generate a PDF report of all committees (and their projects/doctors).
    Uses reportlab.
    """
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles    import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units     import mm
    from reportlab.lib           import colors
    from reportlab.platypus      import (SimpleDocTemplate, Paragraph, Spacer,
                                          Table, TableStyle, PageBreak)
    from reportlab.pdfbase       import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import os

    # Try to register an Arabic-capable font
    arabic_font = 'Helvetica'
    candidate_paths = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/freefont/FreeSans.ttf',
    ]
    for path in candidate_paths:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont('ArabicFont', path))
                arabic_font = 'ArabicFont'
                break
            except Exception:
                pass

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                             topMargin=15*mm, bottomMargin=15*mm,
                             leftMargin=12*mm, rightMargin=12*mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleX', parent=styles['Title'],
                                  fontName=arabic_font, fontSize=18, spaceAfter=12)
    h2_style    = ParagraphStyle('H2X', parent=styles['Heading2'],
                                  fontName=arabic_font, fontSize=13, spaceAfter=6,
                                  textColor=colors.HexColor('#3730a3'))
    body_style  = ParagraphStyle('BodyX', parent=styles['Normal'],
                                  fontName=arabic_font, fontSize=10)

    story = []
    story.append(Paragraph('تقرير اللجان - نظام إدارة مشاريع التخرج', title_style))
    if semester:
        story.append(Paragraph(f'الفصل: {semester}', body_style))
    story.append(Spacer(1, 8))

    qs = Committee.objects.all()
    if semester:
        qs = qs.filter(semester=semester)
    qs = qs.order_by('committee_type', 'department', 'sequence_number')

    for c in qs:
        story.append(Paragraph(f'{c} — {c.template.display_name() if c.template_id else ""}', h2_style))

        # Doctors table
        doctors = c.get_all_doctors()
        doc_rows = [['الاسم', 'الدور', 'القسم']]
        for d in doctors:
            doc_rows.append([d['name'],
                              'رئيس' if d['role'] == 'chair' else 'عضو',
                              _dept_ar(d['department'])])
        t = Table(doc_rows, colWidths=[60*mm, 25*mm, 50*mm])
        t.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), arabic_font),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#eef2ff')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(t)
        story.append(Spacer(1, 4))

        # Projects table
        projs = c.get_all_projects()
        if projs:
            proj_rows = [['المصدر', 'العنوان', 'المشرف', 'الطالب']]
            for p in projs:
                proj_rows.append([
                    p['source'],
                    p['title'],
                    p['supervisor'] or '—',
                    p['student'],
                ])
            t2 = Table(proj_rows, colWidths=[40*mm, 80*mm, 50*mm, 50*mm])
            t2.setStyle(TableStyle([
                ('FONTNAME', (0,0), (-1,-1), arabic_font),
                ('FONTSIZE', (0,0), (-1,-1), 9),
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#dcfce7')),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ]))
            story.append(t2)
        else:
            story.append(Paragraph('(لا توجد مشاريع موزعة بعد)', body_style))

        story.append(Spacer(1, 10))

    doc.build(story)
    return buf.getvalue()


def export_committees_excel(semester: str | None = None) -> bytes:
    """
    Generate an .xlsx workbook with one sheet per committee type.
    """
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    # Remove default sheet
    wb.remove(wb.active)

    qs = Committee.objects.all()
    if semester:
        qs = qs.filter(semester=semester)

    # Group by committee_type
    by_type: dict[str, list[Committee]] = {}
    for c in qs:
        by_type.setdefault(c.committee_type, []).append(c)

    headers_fill = PatternFill('solid', fgColor='4F46E5')
    headers_font = Font(bold=True, color='FFFFFF', size=11)
    align_center = Alignment(horizontal='center', vertical='center', wrap_text=True)
    align_right  = Alignment(horizontal='right', vertical='center', wrap_text=True)
    thin = Side(border_style='thin', color='CCCCCC')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for ctype, committees in by_type.items():
        ws = wb.create_sheet(title=ctype[:30])
        headers = [
            'رقم اللجنة', 'نوع اللجنة', 'القسم', 'نوع المشروع', 'الفصل',
            'الرئيس', 'الأعضاء',
            'عدد المشاريع', 'المشاريع (العناوين)',
            'التاريخ', 'الوقت', 'الموقع', 'الحالة',
        ]
        ws.append(headers)
        for col_idx, _ in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col_idx)
            cell.fill = headers_fill
            cell.font = headers_font
            cell.alignment = align_center
            cell.border = border

        from .models import COMMITTEE_TYPE_AR, DEPARTMENT_AR, PROJECT_TYPE_AR
        for c in committees:
            doctors = c.get_all_doctors()
            chair_name = next((d['name'] for d in doctors if d['role'] == 'chair'), '—')
            member_names = '، '.join(d['name'] for d in doctors if d['role'] == 'member')
            projs = c.get_all_projects()
            proj_titles = ' | '.join(p['title'] for p in projs)

            row = [
                f'{c.sequence_number:03d}',
                COMMITTEE_TYPE_AR.get(c.committee_type, c.committee_type),
                DEPARTMENT_AR.get(c.department, c.department),
                PROJECT_TYPE_AR.get(c.project_type, c.project_type),
                c.semester,
                chair_name,
                member_names,
                len(projs),
                proj_titles,
                c.date.strftime('%Y-%m-%d') if c.date else '',
                c.time.strftime('%H:%M')    if c.time else '',
                c.location,
                c.status,
            ]
            ws.append(row)
            r = ws.max_row
            for col_idx in range(1, len(row) + 1):
                ws.cell(row=r, column=col_idx).alignment = align_right
                ws.cell(row=r, column=col_idx).border = border

        # Column widths
        widths = [10, 15, 18, 14, 14, 22, 30, 12, 60, 14, 10, 18, 12]
        for i, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.freeze_panes = 'A2'

    if not wb.sheetnames:
        ws = wb.create_sheet(title='لا يوجد بيانات')
        ws.append(['لا توجد لجان لعرضها'])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ── Export Projects Assignment to Excel ───────────────────────────────────────

def export_projects_assignment_excel(semester: str | None = None) -> bytes:
    """
    Generate an Excel file for Projects Assignment table.
    Shows: Student, Project, Supervisor, Committee, Members, Date, Time, Location
    """
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'توزيع المشاريع'

    # Styling
    headers_fill = PatternFill('solid', fgColor='667EEA')
    headers_font = Font(bold=True, color='FFFFFF', size=12)
    align_center = Alignment(horizontal='center', vertical='center', wrap_text=True)
    align_right  = Alignment(horizontal='right', vertical='center', wrap_text=True)
    thin = Side(border_style='thin', color='CCCCCC')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    # Headers
    headers = [
        '#', 'الطلاب', 'المشروع', 'المشرفين', 
        'اللجنة', 'نوع اللجنة', 'القسم',
        'أعضاء اللجنة', 'التاريخ', 'الوقت', 'المكان'
    ]
    ws.append(headers)
    
    # Style headers
    for col_idx, _ in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = headers_fill
        cell.font = headers_font
        cell.alignment = align_center
        cell.border = border

    # Get committees
    committees_qs = Committee.objects.all()
    if semester:
        committees_qs = committees_qs.filter(semester=semester)

    from .models import COMMITTEE_TYPE_AR, DEPARTMENT_AR, PROJECT_TYPE_AR

    # Build data rows
    row_num = 1
    for committee in committees_qs:
        # Get all members
        all_doctors = committee.get_all_doctors()
        members_text = '\n'.join([
            f"{'👤 ' if doc['role'] == 'chair' else '• '}{doc['name']}"
            for doc in all_doctors
        ])
        
        # Get all projects
        projects = committee.get_all_projects()
        
        for project in projects:
            row_num += 1
            
            # Format all students (team members)
            students_data = project.get('students', [])
            if students_data:
                students_text = '\n'.join([
                    f"{'👤 ' if student.get('is_leader') else '• '}{student['name']}"
                    for student in students_data
                ])
            else:
                students_text = '—'
            
            # Format all supervisors
            supervisors_data = project.get('supervisors', [])
            if supervisors_data:
                supervisors_text = '\n'.join([
                    f"{'👤 ' if supervisor.get('is_main') else '• '}{supervisor['name']}"
                    for supervisor in supervisors_data
                ])
            else:
                supervisors_text = '—'
            
            row_data = [
                row_num - 1,  # Number
                students_text,  # All team members (leader marked with 👤)
                project.get('title', '—'),
                supervisors_text,  # All supervisors (main marked with 👤)
                f"{COMMITTEE_TYPE_AR.get(committee.committee_type, committee.committee_type)} - {DEPARTMENT_AR.get(committee.department, committee.department)}",
                COMMITTEE_TYPE_AR.get(committee.committee_type, committee.committee_type),
                DEPARTMENT_AR.get(committee.department, committee.department),
                members_text if members_text else '—',
                committee.date.strftime('%Y-%m-%d') if committee.date else '—',
                committee.time.strftime('%H:%M') if committee.time else '—',
                committee.location if committee.location else '—',
            ]
            ws.append(row_data)
            
            # Style cells
            for col_idx in range(1, len(row_data) + 1):
                cell = ws.cell(row=row_num, column=col_idx)
                cell.alignment = align_right
                cell.border = border

    # Column widths
    widths = [6, 20, 35, 20, 30, 15, 18, 35, 14, 10, 20]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    
    # Freeze first row
    ws.freeze_panes = 'A2'

    # If no data
    if ws.max_row == 1:
        ws.append(['لا توجد مشاريع موزعة', '', '', '', '', '', '', '', '', '', ''])

    # Save to buffer
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()

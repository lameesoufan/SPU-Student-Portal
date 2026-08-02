from django.contrib.auth import get_user_model
from django.db import transaction
from django.db import IntegrityError
from django.utils import timezone
from .models import (
    ProjectIdea, StudentIdeaProposal, ProjectApplication,
    IdeaApplication, TeamInvitation, ProposalInvitation,
    ProposalSupervisorDecision,
)
from .participation_services import (
    create_participations_for_idea_application,
    create_participations_for_student_proposal,
    current_registered_participations_for_student,
)
from notifications.utils import notify, notify_many

User = get_user_model()


# ── Shared helper ─────────────────────────────────────────────────────────────

def student_has_registered_project(student):
    participations = current_registered_participations_for_student(student)
    if participations.exists():
        return participations.active().exists()
    if IdeaApplication.objects.filter(student=student, status='registered').exists():
        return True
    if ProjectApplication.objects.filter(student=student, status='accepted').exists():
        return True
    if TeamInvitation.objects.filter(
        invitee=student, status='accepted', application__status='registered',
    ).exists():
        return True
    if ProposalInvitation.objects.filter(
        invitee=student, status='accepted', proposal__status='assigned',
    ).exists():
        return True
    return False


def _member_unavailable_result(member, username, reason):
    """Build a clear, localized error when a selected team member is unavailable."""
    display_name = member.get_full_name().strip() or username
    if reason == 'You already have a registered project.':
        return {
            'ok': False,
            'code': 'member_has_project',
            'student_username': username,
            'error': f'الطالب {display_name} لديه مشروع مسجل بالفعل ولا يمكن إضافته إلى الفريق.',
        }

    reason_map = {
        'You already have an active application on a doctor idea.': 'لديه طلب نشط على فكرة مشروع أخرى.',
        'You already have an active idea proposal.': 'لديه مقترح مشروع نشط بالفعل.',
        'You are already a member of an active team.': 'هو عضو في فريق مشروع نشط بالفعل.',
        'You are already a member of an active proposal team.': 'هو عضو في فريق مقترح مشروع نشط بالفعل.',
    }
    localized_reason = reason_map.get(reason, reason)
    return {
        'ok': False,
        'code': 'member_unavailable',
        'student_username': username,
        'error': f'لا يمكن إضافة الطالب {display_name}: {localized_reason}',
    }


def _student_is_active(student):
    """True if student has any active application/proposal (not yet decided)."""
    if student_has_registered_project(student):
        return True, 'You already have a registered project.'
    if IdeaApplication.objects.select_for_update().filter(
        student=student, status__in=['awaiting_members', 'pending_doctor', 'pending_hod'],
    ).exists():
        return True, 'You already have an active application on a doctor idea.'
    if StudentIdeaProposal.objects.select_for_update().filter(
        student=student, status__in=[
            'awaiting_members', 'pending_supervisor',
            'supervisor_action_required', 'pending_hod',
        ],
    ).exists():
        return True, 'You already have an active idea proposal.'
    if TeamInvitation.objects.select_for_update().filter(
        invitee=student, status='accepted',
        application__status__in=['awaiting_members', 'pending_doctor', 'pending_hod'],
    ).exists():
        return True, 'You are already a member of an active team.'
    if ProposalInvitation.objects.select_for_update().filter(
        invitee=student, status='accepted',
        proposal__status__in=[
            'awaiting_members', 'pending_supervisor',
            'supervisor_action_required', 'pending_hod',
        ],
    ).exists():
        return True, 'You are already a member of an active proposal team.'
    # ↓↓↓ شيلت فحص الدعوات المعلقة — نقلته لـ create_student_proposal و apply_on_idea ↓↓↓
    return False, ''

# ── UC-01 ─────────────────────────────────────────────────────────────────────

def create_project_idea(*, doctor, title, description, department, required_skills, max_team_size):
    # ── Duplicate guard: same doctor + same title within 60 seconds ──
    from django.utils import timezone
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(seconds=60)
    if ProjectIdea.objects.filter(
        doctor=doctor, title=title, created_at__gte=cutoff
    ).exists():
        return {'ok': False, 'error': 'Duplicate idea — you already submitted this recently.'}

    # ── Auto-approve if the submitter is an HoD ──
    initial_status = 'approved' if doctor.role == 'hod' else 'pending_review'

    idea = ProjectIdea.objects.create(
        doctor=doctor, title=title, description=description,
        department=department, required_skills=required_skills,
        max_team_size=max_team_size, status=initial_status,
    )

    if initial_status == 'pending_review':
        # Notify HoD of the department
        hods = User.objects.filter(role='hod', department=department)
        notify_many(hods, 'idea_submitted',
                    'New Project Idea Submitted',
                    f'Dr. {doctor.get_full_name() or doctor.username} submitted a new idea: "{title}".')
    else:
        # HoD's own idea — auto-approved, no notification needed
        pass

    return {'ok': True, 'idea': idea}

# ── UC-02 ─────────────────────────────────────────────────────────────────────

def student_can_propose(student):
    active, msg = _student_is_active(student)
    if active:
        return False, msg
    return True, None


def _display_name(user):
    return user.get_full_name() or user.username


def _active_supervisor_decisions(proposal):
    return proposal.supervisor_decisions.filter(is_active=True).select_related('supervisor')


def _ensure_supervisor_decisions(proposal, default_status='pending'):
    """Create decision rows for legacy/imported proposals that predate this workflow."""
    if proposal.supervisor_decisions.filter(is_active=True).exists():
        return

    selected = []
    if proposal.supervisor_id:
        selected.append((proposal.supervisor_id, True))
    selected.extend((supervisor.id, False) for supervisor in proposal.co_supervisors.all())

    for supervisor_id, is_primary in selected:
        decision, created = ProposalSupervisorDecision.objects.get_or_create(
            proposal=proposal,
            supervisor_id=supervisor_id,
            defaults={
                'is_primary': is_primary,
                'is_active': True,
                'status': default_status,
            },
        )
        if not created:
            decision.is_primary = is_primary
            decision.is_active = True
            decision.status = default_status
            decision.rejection_reason = ''
            decision.responded_at = None
            decision.save(update_fields=[
                'is_primary', 'is_active', 'status', 'rejection_reason',
                'responded_at', 'updated_at',
            ])


def _notify_pending_supervisors(proposal):
    decisions = list(_active_supervisor_decisions(proposal).filter(status='pending'))
    formatted_ptype = proposal.project_type.replace('_', ' ').title()
    for decision in decisions:
        notify(
            decision.supervisor,
            'proposal_submitted',
            f'New Student {formatted_ptype} Proposal',
            f'{_display_name(proposal.student)} submitted the proposal "{proposal.title}" and selected you as '
            f'{"primary supervisor" if decision.is_primary else "co-supervisor"}.',
        )


def _forward_proposal_to_hod(proposal):
    """Move a proposal to HoD review after its active supervisor set is approved."""
    proposal.status = 'pending_hod'
    proposal.rejection_reason = ''
    proposal.save(update_fields=['status', 'rejection_reason', 'updated_at'])

    approved_names = [
        _display_name(decision.supervisor)
        for decision in _active_supervisor_decisions(proposal).filter(status='approved')
    ]
    notify(
        proposal.student,
        'proposal_approved_sup',
        'Proposal Approved by Supervisor',
        f'Your proposal "{proposal.title}" was approved by {"، ".join(approved_names)} and is now pending HoD review.',
    )
    hods = User.objects.filter(role='hod', department=proposal.department)
    notify_many(
        hods,
        'proposal_submitted',
        'Student Proposal Pending Review',
        f'Proposal "{proposal.title}" by {_display_name(proposal.student)} is awaiting your review.',
    )


def create_student_proposal(*, student, supervisors=None, supervisor=None, title, description, department,
                             team_size, team_size_reason, member_ids, project_type='seasonal'):
    supervisors = list(supervisors or ([supervisor] if supervisor else []))
    if not 1 <= len(supervisors) <= 2:
        return {'ok': False, 'error': 'Choose one or two supervisors.'}
    if len({supervisor.pk for supervisor in supervisors}) != len(supervisors):
        return {'ok': False, 'error': 'Duplicate supervisors are not allowed.'}
    if any(supervisor.role not in ('doctor', 'hod') for supervisor in supervisors):
        return {'ok': False, 'error': 'Every supervisor must be a doctor or HoD.'}

    if team_size not in (1, 2, 3, 4):
        return {'ok': False, 'error': 'Team size must be 1, 2, 3, or 4 students.'}

    if team_size in (1, 4) and not team_size_reason.strip():
        return {'ok': False, 'error': f'A justification is required when team size is {team_size}.'}

    expected_members = team_size - 1
    if len(member_ids) != expected_members:
        return {'ok': False, 'error': f'Please provide {expected_members} additional member ID(s).'}

    member_usernames = [str(uid) for uid in member_ids]
    if len(member_usernames) != len(set(member_usernames)):
        return {'ok': False, 'error': 'Duplicate team members are not allowed.'}

    try:
        with transaction.atomic():
            student = User.objects.select_for_update().get(pk=student.pk)
            locked_supervisors = list(
                User.objects.select_for_update().filter(
                    pk__in=[supervisor.pk for supervisor in supervisors],
                    role__in=['doctor', 'hod'],
                )
            )
            locked_map = {supervisor.pk: supervisor for supervisor in locked_supervisors}
            supervisors = [locked_map.get(supervisor.pk) for supervisor in supervisors]
            if any(supervisor is None for supervisor in supervisors):
                return {'ok': False, 'error': 'One of the selected supervisors is no longer available.'}

            allowed, error = student_can_propose(student)
            if not allowed:
                return {'ok': False, 'error': error}

            if StudentIdeaProposal.objects.filter(
                invitations__invitee=student, invitations__status='pending',
            ).exists():
                return {'ok': False, 'error': 'You already have a pending invitation to another proposal. Please respond to it first.'}
            if IdeaApplication.objects.filter(
                invitations__invitee=student, invitations__status='pending',
            ).exists():
                return {'ok': False, 'error': 'You already have a pending invitation to another application. Please respond to it first.'}

            members_by_username = {
                user.username: user
                for user in User.objects.select_for_update().filter(username__in=member_usernames, role='student')
            }

            members = []
            for uid in member_usernames:
                member = members_by_username.get(uid)
                if not member:
                    return {'ok': False, 'error': f'Student with ID "{uid}" not found.'}
                if member.pk == student.pk:
                    return {'ok': False, 'error': 'You cannot add yourself as a team member.'}
                active, err = _student_is_active(member)
                if active:
                    return _member_unavailable_result(member, uid, err)
                members.append(member)

            initial_status = 'pending_supervisor' if team_size == 1 else 'awaiting_members'
            primary_supervisor = supervisors[0]
            proposal = StudentIdeaProposal.objects.create(
                student=student,
                supervisor=primary_supervisor,
                title=title,
                description=description,
                department=department,
                team_size=team_size,
                team_size_reason=team_size_reason,
                project_type=project_type,
                status=initial_status,
            )
            if len(supervisors) == 2:
                proposal.co_supervisors.add(supervisors[1])

            for index, supervisor in enumerate(supervisors):
                ProposalSupervisorDecision.objects.create(
                    proposal=proposal,
                    supervisor=supervisor,
                    is_primary=index == 0,
                    status='pending',
                )

            for member in members:
                ProposalInvitation.objects.create(proposal=proposal, invitee=member, status='pending')
                notify(
                    member,
                    'invitation_received',
                    'Team Invitation Received 📨',
                    f'{_display_name(student)} invited you to join their project proposal "{title}".',
                )

            if initial_status == 'pending_supervisor':
                _notify_pending_supervisors(proposal)

    except IntegrityError:
        return {'ok': False, 'error': 'A database conflict occurred. You may already have an active proposal or a team member is already assigned elsewhere.'}
    except Exception as exc:
        return {'ok': False, 'error': f'An unexpected error occurred: {str(exc)}'}

    return {'ok': True, 'proposal': proposal}


def cancel_proposal(*, proposal, student):
    """Leader cancels their proposal before it's approved."""
    if proposal.student != student:
        return {'ok': False, 'error': 'You are not the owner of this proposal.'}
    if proposal.status == 'assigned':
        return {'ok': False, 'error': 'Cannot cancel an already assigned proposal.'}
    if proposal.status == 'rejected':
        return {'ok': False, 'error': 'Proposal is already rejected.'}

    with transaction.atomic():
        proposal.status = 'rejected'
        proposal.rejection_reason = 'Cancelled by the proposing student.'
        proposal.save(update_fields=['status', 'rejection_reason', 'updated_at'])
        all_invitations = list(proposal.invitations.select_related('invitee'))
        proposal.invitations.update(status='rejected')

    for inv in all_invitations:
        if inv.status == 'accepted':
            notify(inv.invitee, 'proposal_rejected',
                   'Proposal Cancelled',
                   f'The proposal "{proposal.title}" you were part of has been cancelled by the proposer.')
        elif inv.status == 'pending':
            notify(inv.invitee, 'proposal_rejected',
                   'Proposal Cancelled',
                   f'The proposal "{proposal.title}" you were invited to has been cancelled by the proposer.')

    return {'ok': True}


def respond_to_proposal_invitation(*, invitation, action, rejection_reason=''):
    with transaction.atomic():
        invitation = ProposalInvitation.objects.select_for_update(of=('self',)).select_related(
            'proposal__student', 'proposal__supervisor', 'invitee'
        ).get(pk=invitation.pk)
        proposal = StudentIdeaProposal.objects.select_for_update().get(pk=invitation.proposal_id)
        User.objects.select_for_update().filter(pk=invitation.invitee_id).first()

        if invitation.status != 'pending':
            return {'ok': False, 'error': 'Invitation already responded to.'}

        # ═══════════════════════════════════════════
        #  رفض الدعوة
        # ═══════════════════════════════════════════
        if action == 'reject':
            invitation.status = 'rejected'
            invitation.rejection_reason = rejection_reason.strip()
            invitation.save(update_fields=['status', 'rejection_reason', 'updated_at'])

            # ↓↓↓ تحقق هل كل الدعوات انتهت ↓↓↓
            if proposal.status == 'awaiting_members':
                all_invitations = ProposalInvitation.objects.select_for_update().filter(proposal=proposal)
                pending_count = all_invitations.filter(status='pending').count()
                accepted_count = all_invitations.filter(status='accepted').count()

                if pending_count == 0 and accepted_count == 0:
                    # كلهم رُفضوا → نبه الطالب يختار أعضاء جداد أو يلغي
                    notify(proposal.student, 'proposal_rejected',
                           'All Team Members Declined',
                           f'All invited members declined your proposal "{proposal.title}". Please invite new members or cancel.')
                elif pending_count == 0 and accepted_count > 0:
                    # جزء قبل وجزء رفض → نبه الطالب إنو يحتاج يعوض المرفوضين
                    rejected_count = all_invitations.filter(status='rejected').count()
                    notify(proposal.student, 'invitation_rejected',
                           'Team Member Declined - Action Needed',
                           f'{invitation.invitee.get_full_name() or invitation.invitee.username} declined your invitation for "{proposal.title}". '
                           f'You have {accepted_count} accepted and {rejected_count} declined. Replace the declined members to proceed.')

            return {'ok': True, 'invitation': invitation}

        # ═══════════════════════════════════════════
        #  قبول الدعوة
        # ═══════════════════════════════════════════
        active, msg = _student_is_active(invitation.invitee)
        if active:
            invitation.status = 'rejected'
            invitation.save(update_fields=['status', 'updated_at'])
            notify(proposal.student, 'invitation_rejected',
                   'Team Member Unavailable',
                   f'{invitation.invitee.get_full_name() or invitation.invitee.username} is unavailable for "{proposal.title}". You can replace them.')
            return {'ok': False, 'error': f'You cannot accept this invitation: {msg}'}

        invitation.status = 'accepted'
        invitation.save(update_fields=['status', 'updated_at'])

        if proposal.status == 'awaiting_members':
            all_invitations = ProposalInvitation.objects.select_for_update().filter(proposal=proposal)
            pending_count = all_invitations.filter(status='pending').count()
            accepted_count = all_invitations.filter(status='accepted').count()
            rejected_count = all_invitations.filter(status='rejected').count()

            if pending_count == 0 and rejected_count == 0:
                # كلهم accepted → نتقدم للمراجعة
                proposal.status = 'pending_supervisor'
                proposal.save(update_fields=['status', 'updated_at'])
                _notify_pending_supervisors(proposal)

            elif pending_count == 0 and accepted_count == 0:
                # كلهم رُفضوا → نبه الطالب
                notify(proposal.student, 'proposal_rejected',
                       'All Team Members Declined',
                       f'All invited members declined your proposal "{proposal.title}". Please invite new members or cancel.')

            elif pending_count == 0 and accepted_count > 0 and rejected_count > 0:
                # جزء قبل وجزء رفض → نبه الطالب يعوض المرفوضين
                notify(proposal.student, 'invitation_rejected',
                       'Some Team Members Declined - Action Needed',
                       f'{rejected_count} member(s) declined your proposal "{proposal.title}". Replace them to proceed to supervisor review.')

        notify(proposal.student, 'invitation_accepted',
               'Team Member Accepted',
               f'{invitation.invitee.get_full_name() or invitation.invitee.username} accepted your team invitation for "{proposal.title}".')

        return {'ok': True, 'invitation': invitation}


def replace_proposal_member(*, proposal, old_member_id, new_member_id):
    """Leader replaces a rejected invitee with a new one."""
    with transaction.atomic():
        proposal = StudentIdeaProposal.objects.select_for_update(of=('self',)).select_related('student').get(pk=proposal.pk)
        if proposal.status != 'awaiting_members':
            return {'ok': False, 'error': 'Proposal is not in awaiting members state.'}

        try:
            old_inv = proposal.invitations.select_for_update().get(invitee__username=old_member_id, status='rejected')
        except ProposalInvitation.DoesNotExist:
            return {'ok': False, 'error': 'No rejected invitation found for this member.'}

        try:
            new_member = User.objects.select_for_update().get(username=str(new_member_id), role='student')
        except User.DoesNotExist:
            return {'ok': False, 'error': f'Student with ID "{new_member_id}" not found.'}

        if new_member.pk == proposal.student_id:
            return {'ok': False, 'error': 'You cannot add yourself as a team member.'}

        active, err = _student_is_active(new_member)
        if active:
            return {'ok': False, 'error': f'Student "{new_member_id}": {err}'}

        # Remove old rejected invitation and create new one
        old_inv.delete()
        ProposalInvitation.objects.create(proposal=proposal, invitee=new_member, status='pending')
        notify(new_member, 'invitation_received',
               'Team Invitation Received 📨',
               f'{proposal.student.get_full_name() or proposal.student.username} invited you to join their project proposal "{proposal.title}".')

    return {'ok': True}


def remove_rejected_proposal_member(*, proposal, member_id, team_size_reason=''):
    """Remove a rejected invitee and continue with a smaller team."""
    with transaction.atomic():
        proposal = StudentIdeaProposal.objects.select_for_update().select_related('student').get(pk=proposal.pk)
        if proposal.status != 'awaiting_members':
            return {'ok': False, 'error': 'Proposal is not waiting for team members.'}

        try:
            invitation = proposal.invitations.select_for_update().get(
                invitee__username=str(member_id),
                status='rejected',
            )
        except ProposalInvitation.DoesNotExist:
            return {'ok': False, 'error': 'No rejected invitation was found for this member.'}

        new_team_size = max(1, proposal.team_size - 1)
        if new_team_size == 1 and not (team_size_reason or proposal.team_size_reason).strip():
            return {'ok': False, 'error': 'A justification is required to continue as an individual project.'}

        invitation.delete()
        proposal.team_size = new_team_size
        if team_size_reason.strip():
            proposal.team_size_reason = team_size_reason.strip()

        remaining = proposal.invitations.select_for_update().all()
        if not remaining.filter(status__in=['pending', 'rejected']).exists():
            proposal.status = 'pending_supervisor'
        proposal.save(update_fields=['team_size', 'team_size_reason', 'status', 'updated_at'])

        if proposal.status == 'pending_supervisor':
            _notify_pending_supervisors(proposal)

    return {'ok': True, 'proposal': proposal}


def replace_rejected_supervisor(*, proposal, old_supervisor_id, new_supervisor):
    """Replace a rejected supervisor while preserving unaffected approvals."""
    with transaction.atomic():
        proposal = StudentIdeaProposal.objects.select_for_update().get(pk=proposal.pk)
        if proposal.status != 'supervisor_action_required':
            return {'ok': False, 'error': 'The proposal does not currently require a supervisor change.'}
        if new_supervisor.role not in ('doctor', 'hod'):
            return {'ok': False, 'error': 'The replacement supervisor must be a doctor or HoD.'}

        try:
            old_decision = ProposalSupervisorDecision.objects.select_for_update().get(
                proposal=proposal,
                supervisor_id=old_supervisor_id,
                is_active=True,
                status='rejected',
            )
        except ProposalSupervisorDecision.DoesNotExist:
            return {'ok': False, 'error': 'The selected supervisor does not have an active rejected decision.'}

        if ProposalSupervisorDecision.objects.filter(
            proposal=proposal,
            supervisor=new_supervisor,
            is_active=True,
        ).exists():
            return {'ok': False, 'error': 'This supervisor is already selected for the proposal.'}

        old_decision.is_active = False
        old_decision.save(update_fields=['is_active', 'updated_at'])

        if old_decision.is_primary:
            proposal.supervisor = new_supervisor
            proposal.co_supervisors.remove(old_decision.supervisor)
        else:
            proposal.co_supervisors.remove(old_decision.supervisor)
            proposal.co_supervisors.add(new_supervisor)

        replacement_decision = ProposalSupervisorDecision.objects.select_for_update().filter(
            proposal=proposal,
            supervisor=new_supervisor,
        ).first()
        if replacement_decision:
            replacement_decision.is_primary = old_decision.is_primary
            replacement_decision.is_active = True
            replacement_decision.status = 'pending'
            replacement_decision.rejection_reason = ''
            replacement_decision.responded_at = None
            replacement_decision.save(update_fields=[
                'is_primary', 'is_active', 'status', 'rejection_reason',
                'responded_at', 'updated_at',
            ])
        else:
            ProposalSupervisorDecision.objects.create(
                proposal=proposal,
                supervisor=new_supervisor,
                is_primary=old_decision.is_primary,
                status='pending',
            )
        has_other_rejected = ProposalSupervisorDecision.objects.filter(
            proposal=proposal,
            is_active=True,
            status='rejected',
        ).exists()
        proposal.status = 'supervisor_action_required' if has_other_rejected else 'pending_supervisor'
        proposal.rejection_reason = ''
        proposal.save(update_fields=['supervisor', 'status', 'rejection_reason', 'updated_at'])

        notify(
            new_supervisor,
            'proposal_submitted',
            'Student Proposal Requires Your Review',
            f'{_display_name(proposal.student)} selected you to review the proposal "{proposal.title}".',
        )

    return {'ok': True, 'proposal': proposal}


def continue_with_approved_supervisor(*, proposal, approved_supervisor_id):
    """Student confirms continuation with the one supervisor who approved."""
    with transaction.atomic():
        proposal = StudentIdeaProposal.objects.select_for_update().get(pk=proposal.pk)
        if proposal.status != 'supervisor_action_required':
            return {'ok': False, 'error': 'The proposal is not waiting for a supervisor decision from the student.'}

        try:
            approved = ProposalSupervisorDecision.objects.select_for_update().select_related('supervisor').get(
                proposal=proposal,
                supervisor_id=approved_supervisor_id,
                is_active=True,
                status='approved',
            )
        except ProposalSupervisorDecision.DoesNotExist:
            return {'ok': False, 'error': 'Choose an active supervisor who approved the proposal.'}

        active_decisions = ProposalSupervisorDecision.objects.select_for_update().filter(
            proposal=proposal,
            is_active=True,
        )
        if active_decisions.filter(status='pending').exists():
            return {'ok': False, 'error': 'The other supervisor has not responded yet. Wait for their response or replace a rejected supervisor.'}

        rejected_decisions = list(active_decisions.filter(status='rejected').select_related('supervisor'))
        if not rejected_decisions:
            return {'ok': False, 'error': 'There is no rejected supervisor to remove.'}

        active_decisions.exclude(pk=approved.pk).update(is_active=False, updated_at=timezone.now())
        approved.is_primary = True
        approved.save(update_fields=['is_primary', 'updated_at'])

        proposal.supervisor = approved.supervisor
        proposal.co_supervisors.clear()
        proposal.save(update_fields=['supervisor', 'updated_at'])
        _forward_proposal_to_hod(proposal)

        for rejected in rejected_decisions:
            notify(
                rejected.supervisor,
                'proposal_rejected',
                'Removed from Student Proposal',
                f'The student chose to continue proposal "{proposal.title}" with another approved supervisor.',
            )

    return {'ok': True, 'proposal': proposal}


def revise_student_proposal(*, proposal, title, description):
    """Revise a supervisor-rejected proposal and restart affected approvals."""
    title = (title or '').strip()
    description = (description or '').strip()
    if not title or not description:
        return {'ok': False, 'error': 'Title and description are required.'}

    with transaction.atomic():
        proposal = StudentIdeaProposal.objects.select_for_update().select_related('student').get(pk=proposal.pk)
        if proposal.status != 'supervisor_action_required':
            return {'ok': False, 'error': 'Only a proposal returned by a supervisor can be revised here.'}
        if proposal.title.strip() == title and proposal.description.strip() == description:
            return {'ok': False, 'error': 'Change the title or description before resubmitting.'}

        decisions = ProposalSupervisorDecision.objects.select_for_update().filter(
            proposal=proposal,
            is_active=True,
        )
        decisions.update(
            status='pending',
            rejection_reason='',
            responded_at=None,
            updated_at=timezone.now(),
        )

        invitations = proposal.invitations.select_for_update().select_related('invitee')
        members = [invitation.invitee for invitation in invitations]
        if members:
            invitations.update(status='pending', rejection_reason='', updated_at=timezone.now())
            next_status = 'awaiting_members'
        else:
            next_status = 'pending_supervisor'

        proposal.title = title
        proposal.description = description
        proposal.status = next_status
        proposal.rejection_reason = ''
        proposal.save(update_fields=[
            'title', 'description', 'status', 'rejection_reason', 'updated_at',
        ])

        for member in members:
            notify(
                member,
                'invitation_received',
                'Project Proposal Revised',
                f'{_display_name(proposal.student)} revised proposal "{proposal.title}". Please review and confirm your participation again.',
            )

        if next_status == 'pending_supervisor':
            _notify_pending_supervisors(proposal)

    return {'ok': True, 'proposal': proposal}


def replace_application_member(*, application, old_member_id, new_member_id):
    """Leader replaces a rejected invitee with a new one in an IdeaApplication."""
    with transaction.atomic():
        application = IdeaApplication.objects.select_for_update(of=('self',)).select_related('student', 'idea').get(pk=application.pk)
        if application.status != 'awaiting_members':
            return {'ok': False, 'error': 'Application is not in awaiting members state.'}

        try:
            old_inv = application.invitations.select_for_update().get(invitee__username=old_member_id, status='rejected')
        except TeamInvitation.DoesNotExist:
            return {'ok': False, 'error': 'No rejected invitation found for this member.'}

        try:
            new_member = User.objects.select_for_update().get(username=str(new_member_id), role='student')
        except User.DoesNotExist:
            return {'ok': False, 'error': f'Student with ID "{new_member_id}" not found.'}

        if new_member.pk == application.student_id:
            return {'ok': False, 'error': 'You cannot add yourself as a team member.'}

        active, err = _student_is_active(new_member)
        if active:
            return {'ok': False, 'error': f'Student "{new_member_id}": {err}'}

        old_inv.delete()
        TeamInvitation.objects.create(application=application, invitee=new_member, status='pending')
        notify(new_member, 'invitation_received',
               'Team Invitation Received 📨',
               f'{application.student.get_full_name() or application.student.username} invited you to join their application for "{application.idea.title}".')

    return {'ok': True}


def supervisor_review_proposal(*, proposal, reviewer=None, action, rejection_reason=''):
    with transaction.atomic():
        proposal = StudentIdeaProposal.objects.select_for_update().select_related('student').get(pk=proposal.pk)
        if proposal.status not in ('pending_supervisor', 'supervisor_action_required'):
            return {'ok': False, 'error': 'Proposal is not awaiting supervisor approval.'}

        _ensure_supervisor_decisions(proposal, default_status='pending')
        reviewer = reviewer or proposal.supervisor
        if reviewer is None:
            return {'ok': False, 'error': 'No supervisor is available to review this proposal.'}

        try:
            decision = ProposalSupervisorDecision.objects.select_for_update().select_related('supervisor').get(
                proposal=proposal,
                supervisor=reviewer,
                is_active=True,
            )
        except ProposalSupervisorDecision.DoesNotExist:
            return {'ok': False, 'error': 'You are not an active supervisor for this proposal.'}

        if decision.status != 'pending':
            return {'ok': False, 'error': 'You have already responded to this proposal.'}

        if action == 'approve':
            decision.status = 'approved'
            decision.rejection_reason = ''
            decision.responded_at = timezone.now()
            decision.save(update_fields=['status', 'rejection_reason', 'responded_at', 'updated_at'])
            notify(
                proposal.student,
                'proposal_approved_sup',
                'Supervisor Approved Your Proposal',
                f'{_display_name(reviewer)} approved your proposal "{proposal.title}".',
            )
        else:
            decision.status = 'rejected'
            decision.rejection_reason = rejection_reason.strip()
            decision.responded_at = timezone.now()
            decision.save(update_fields=['status', 'rejection_reason', 'responded_at', 'updated_at'])
            proposal.status = 'supervisor_action_required'
            proposal.rejection_reason = rejection_reason.strip()
            proposal.save(update_fields=['status', 'rejection_reason', 'updated_at'])
            notify(
                proposal.student,
                'proposal_rejected',
                'Supervisor Declined Your Proposal',
                f'{_display_name(reviewer)} declined proposal "{proposal.title}". Reason: {rejection_reason}',
            )

        active = ProposalSupervisorDecision.objects.select_for_update().filter(
            proposal=proposal,
            is_active=True,
        )
        pending_count = active.filter(status='pending').count()
        approved_count = active.filter(status='approved').count()
        rejected_count = active.filter(status='rejected').count()

        if approved_count > 0 and rejected_count == 0 and pending_count == 0:
            _forward_proposal_to_hod(proposal)
        elif rejected_count > 0:
            if proposal.status != 'supervisor_action_required':
                proposal.status = 'supervisor_action_required'
                proposal.save(update_fields=['status', 'updated_at'])
        else:
            if proposal.status != 'pending_supervisor':
                proposal.status = 'pending_supervisor'
                proposal.save(update_fields=['status', 'updated_at'])

        return {'ok': True, 'proposal': proposal}


def hod_review_proposal(*, proposal, action, rejection_reason=''):
    with transaction.atomic():
        proposal = StudentIdeaProposal.objects.select_for_update(of=('self',)).select_related('student').get(pk=proposal.pk)
        if proposal.status != 'pending_hod':
            return {'ok': False, 'error': 'Proposal is not awaiting HoD review.'}
        _ensure_supervisor_decisions(proposal, default_status='approved')
        active_decisions = ProposalSupervisorDecision.objects.filter(proposal=proposal, is_active=True)
        if not active_decisions.filter(status='approved').exists() or active_decisions.exclude(status='approved').exists():
            return {'ok': False, 'error': 'Supervisor approvals are incomplete.'}
        if action == 'reject':
            proposal.status = 'rejected'
            proposal.rejection_reason = rejection_reason
            proposal.save(update_fields=['status', 'rejection_reason', 'updated_at'])
            proposal.invitations.update(status='rejected')
            notify(proposal.student, 'proposal_rejected',
                   'Proposal Rejected by HoD',
                   f'Your proposal "{proposal.title}" was rejected by the HoD. Reason: {rejection_reason}')
            return {'ok': True, 'proposal': proposal}
        proposal.status = 'assigned'
        proposal.save(update_fields=['status', 'updated_at'])
        ProjectApplication.objects.create(proposal=proposal, student=proposal.student, status='accepted')
        create_participations_for_student_proposal(proposal)
        notify(proposal.student, 'proposal_assigned',
               'Project Assigned 🎉',
               f'Your proposal "{proposal.title}" has been approved and assigned to you!')
        # Notify accepted members
        accepted_invitees = [inv.invitee for inv in proposal.invitations.filter(status='accepted').select_related('invitee')]
        notify_many(accepted_invitees, 'proposal_assigned',
                    'Project Assigned 🎉',
                    f'The proposal "{proposal.title}" you joined has been approved and registered!')
        return {'ok': True, 'proposal': proposal}


def hod_review_doctor_idea(*, idea, action, rejection_reason=''):
    with transaction.atomic():
        idea = ProjectIdea.objects.select_for_update(of=('self',)).select_related('doctor').get(pk=idea.pk)
        if idea.status != 'pending_review':
            return {'ok': False, 'error': 'Idea is not pending review.'}
        if action == 'approve':
            idea.status = 'approved'
            idea.rejection_reason = ''
            idea.save(update_fields=['status', 'rejection_reason', 'updated_at'])
            notify(idea.doctor, 'idea_approved',
                   'Project Idea Approved ✅',
                   f'Your idea "{idea.title}" has been approved by the HoD and is now visible to students.')
        else:
            idea.status = 'rejected'
            idea.rejection_reason = rejection_reason
            idea.save(update_fields=['status', 'rejection_reason', 'updated_at'])
            notify(idea.doctor, 'idea_rejected',
                   'Project Idea Rejected',
                   f'Your idea "{idea.title}" was rejected by the HoD. Reason: {rejection_reason}')
        return {'ok': True, 'idea': idea}


# ── UC-03: Student applies on a doctor idea ───────────────────────────────────

def student_can_apply(student):
    active, msg = _student_is_active(student)
    if active:
        return False, msg
    return True, None


def apply_on_idea(*, student, idea, team_size, team_size_reason='', member_ids=None, project_type='seasonal'):
    try:
        with transaction.atomic():
            # Lock the idea row to prevent race conditions
            idea = ProjectIdea.objects.select_for_update().get(pk=idea.pk)
            student = User.objects.select_for_update().get(pk=student.pk)

            if idea.status != 'approved':
                return {'ok': False, 'error': 'This idea is not available for applications.'}

            if IdeaApplication.objects.filter(idea=idea, status='registered').exists():
                return {'ok': False, 'error': 'This idea has already been taken by another team.'}

            # Check if student already has an active (non-rejected) application on this idea
            if IdeaApplication.objects.filter(idea=idea, student=student).exclude(status='rejected').exists():
                return {'ok': False, 'error': 'You already have an active application on this idea.'}

            # Soft-delete any previous rejected application so the unique_together constraint works
            IdeaApplication.objects.filter(idea=idea, student=student, status='rejected').delete()

            if team_size not in (1, 2, 3, 4):
                return {'ok': False, 'error': 'Team size must be 1, 2, 3, or 4.'}

            if team_size in (1, 4) and not team_size_reason.strip():
                return {'ok': False, 'error': f'A justification is required when team size is {team_size}.'}
            if team_size > idea.max_team_size:
                return {'ok': False, 'error': f'This idea allows up to {idea.max_team_size} students.'}

            member_ids = member_ids or []
            if len(member_ids) != team_size - 1:
                return {'ok': False, 'error': f'Please provide {team_size - 1} additional member ID(s).'}

            member_usernames = [str(uid) for uid in member_ids]
            if len(member_usernames) != len(set(member_usernames)):
                return {'ok': False, 'error': 'Duplicate team members are not allowed.'}

            allowed, error = student_can_apply(student)
            if not allowed:
                return {'ok': False, 'error': error}
                        # ↓↓↓ أضف هاد الفحص ↓↓↓
            if StudentIdeaProposal.objects.filter(
                invitations__invitee=student, invitations__status='pending',
            ).exists():
                return {'ok': False, 'error': 'You already have a pending invitation to another proposal. Please respond to it first.'}
            if IdeaApplication.objects.filter(
                invitations__invitee=student, invitations__status='pending',
            ).exists():
                return {'ok': False, 'error': 'You already have a pending invitation to another application. Please respond to it first.'}
            # Validate members
            members_by_username = {
                user.username: user
                for user in User.objects.select_for_update().filter(username__in=member_usernames, role='student')
            }
            members = []
            for uid in member_usernames:
                m = members_by_username.get(uid)
                if not m:
                    return {'ok': False, 'error': f'Student with ID "{uid}" not found.'}
                if m.pk == student.pk:
                    return {'ok': False, 'error': 'You cannot add yourself as a team member.'}
                active, err = _student_is_active(m)
                if active:
                    return _member_unavailable_result(m, uid, err)
                members.append(m)

            initial_status = 'pending_doctor' if team_size == 1 else 'awaiting_members'
            app = IdeaApplication.objects.create(
                student=student, idea=idea, team_size=team_size,
                team_size_reason=team_size_reason, project_type=project_type, status=initial_status,
            )
            for m in members:
                TeamInvitation.objects.create(application=app, invitee=m, status='pending')
                notify(m, 'invitation_received',
                       'Team Invitation Received 📨',
                       f'{student.get_full_name() or student.username} invited you to join their application for "{idea.title}".')

    except IntegrityError:
        return {'ok': False, 'error': 'A database conflict occurred. You may already have an application on this idea, or a team member is already assigned elsewhere.'}
    except Exception as e:
        return {'ok': False, 'error': f'An unexpected error occurred: {str(e)}'}
    return {'ok': True, 'application': app}
def respond_to_invitation(*, invitation, action):
    """Member accepts or rejects an invitation."""
    with transaction.atomic():
        invitation = TeamInvitation.objects.select_for_update(of=('self',)).select_related(
            'application__idea__doctor', 'application__student', 'invitee'
        ).get(pk=invitation.pk)
        app = IdeaApplication.objects.select_for_update().get(pk=invitation.application_id)
        User.objects.select_for_update().filter(pk=invitation.invitee_id).first()

        if invitation.status != 'pending':
            return {'ok': False, 'error': 'Invitation already responded to.'}

        # ═══════════════════════════════════════════
        #  رفض الدعوة
        # ═══════════════════════════════════════════
        if action == 'reject':
            invitation.status = 'rejected'
            invitation.save(update_fields=['status', 'updated_at'])

            # ↓↓↓ تحقق هل كل الدعوات انتهت ↓↓↓
            if app.status == 'awaiting_members':
                all_invitations = TeamInvitation.objects.select_for_update().filter(application=app)
                pending_count = all_invitations.filter(status='pending').count()
                accepted_count = all_invitations.filter(status='accepted').count()

                if pending_count == 0 and accepted_count == 0:
                    # كلهم رُفضوا → نبه الطالب يختار أعضاء جداد أو يلغي
                    notify(app.student, 'invitation_rejected',
                           'All Team Members Declined',
                           f'All invited members declined the application for "{app.idea.title}". Please invite new members or cancel.')
                elif pending_count == 0 and accepted_count > 0:
                    # جزء قبل وجزء رفض → نبه الطالب يعوض المرفوضين
                    rejected_count = all_invitations.filter(status='rejected').count()
                    notify(app.student, 'invitation_rejected',
                           'Team Member Declined - Action Needed',
                           f'{invitation.invitee.get_full_name() or invitation.invitee.username} declined your invitation for "{app.idea.title}". '
                           f'You have {accepted_count} accepted and {rejected_count} declined. Replace the declined members to proceed.')

            notify(app.student, 'invitation_rejected',
                   'Team Member Declined',
                   f'{invitation.invitee.get_full_name() or invitation.invitee.username} declined your invitation for "{app.idea.title}". You can replace them.')
            return {'ok': True, 'invitation': invitation}

        # ═══════════════════════════════════════════
        #  قبول الدعوة
        # ═══════════════════════════════════════════
        active, msg = _student_is_active(invitation.invitee)
        if active:
            invitation.status = 'rejected'
            invitation.save(update_fields=['status', 'updated_at'])
            notify(app.student, 'invitation_rejected',
                   'Team Member Unavailable',
                   f'{invitation.invitee.get_full_name() or invitation.invitee.username} is unavailable for "{app.idea.title}". You can replace them.')
            return {'ok': False, 'error': f'You cannot accept this invitation: {msg}'}

        invitation.status = 'accepted'
        invitation.save(update_fields=['status', 'updated_at'])

        if app.status == 'awaiting_members':
            all_invitations = TeamInvitation.objects.select_for_update().filter(application=app)
            pending_count = all_invitations.filter(status='pending').count()
            accepted_count = all_invitations.filter(status='accepted').count()
            rejected_count = all_invitations.filter(status='rejected').count()

            if pending_count == 0 and rejected_count == 0:
                # كلهم accepted → نتقدم للمراجعة
                app.status = 'pending_doctor'
                app.save(update_fields=['status', 'updated_at'])
                notify(app.idea.doctor, 'application_submitted',
                       'New Application Pending Review',
                       f'{app.student.get_full_name() or app.student.username} and their team applied for your idea "{app.idea.title}".')

            elif pending_count == 0 and accepted_count == 0:
                # كلهم رُفضوا → نبه الطالب
                notify(app.student, 'invitation_rejected',
                       'All Team Members Declined',
                       f'All invited members declined the application for "{app.idea.title}". Please invite new members or cancel.')

            elif pending_count == 0 and accepted_count > 0 and rejected_count > 0:
                # ↓↓↓ حالة جديدة: جزء قبل وجزء رفض ↓↓↓
                notify(app.student, 'invitation_rejected',
                       'Some Team Members Declined - Action Needed',
                       f'{rejected_count} member(s) declined the application for "{app.idea.title}". Replace them to proceed to doctor review.')

        notify(app.student, 'invitation_accepted',
               'Team Member Accepted',
               f'{invitation.invitee.get_full_name() or invitation.invitee.username} accepted your team invitation for "{app.idea.title}".')

        return {'ok': True, 'invitation': invitation}


def doctor_review_application(*, application, action, rejection_reason=''):
    with transaction.atomic():
        application = IdeaApplication.objects.select_for_update(of=('self',)).select_related('idea', 'student').get(pk=application.pk)

        if application.status != 'pending_doctor':
            return {'ok': False, 'error': 'Application is not awaiting doctor approval.'}
        if action == 'approve':
            application.status = 'pending_hod'
            application.save(update_fields=['status', 'updated_at'])
            notify(application.student, 'application_approved_doc',
                   'Application Approved by Doctor ✅',
                   f'Your application for "{application.idea.title}" was approved by the doctor and is now pending HoD review.')
            members = [inv.invitee for inv in application.invitations.filter(status='accepted')]
            notify_many(members, 'application_approved_doc',
                        'Application Approved by Doctor ✅',
                        f'The application for "{application.idea.title}" was approved by the doctor and is pending HoD review.')
            # Notify HoD
            from django.contrib.auth import get_user_model
            U = get_user_model()
            hods = U.objects.filter(role='hod', department=application.idea.department)
            notify_many(hods, 'application_submitted',
                        'Application Pending Your Review',
                        f'An application for "{application.idea.title}" is awaiting your approval.')
        else:
            application.status = 'rejected'
            application.rejection_reason = rejection_reason
            application.save(update_fields=['status', 'rejection_reason', 'updated_at'])
            application.invitations.update(status='rejected')
            notify(application.student, 'application_rejected',
                   'Application Rejected',
                   f'Your application for "{application.idea.title}" was rejected. Reason: {rejection_reason}')
            members = [inv.invitee for inv in application.invitations.all()]
            notify_many(members, 'application_rejected',
                        'Application Rejected',
                        f'The application for "{application.idea.title}" was rejected. Reason: {rejection_reason}')
        return {'ok': True, 'application': application}


def hod_review_application(*, application, action, rejection_reason=''):
    with transaction.atomic():
        application = IdeaApplication.objects.select_for_update(of=('self',)).select_related('idea', 'student').get(pk=application.pk)
        ProjectIdea.objects.select_for_update().filter(pk=application.idea_id).first()

        if application.status != 'pending_hod':
            return {'ok': False, 'error': 'Application is not awaiting HoD approval.'}
        if action == 'approve':
            already_registered = IdeaApplication.objects.select_for_update().filter(
                idea_id=application.idea_id,
                status='registered',
            ).exclude(pk=application.pk).exists()
            if already_registered:
                return {'ok': False, 'error': 'This idea has already been registered by another team.'}

            application.status = 'registered'
            try:
                application.save(update_fields=['status', 'updated_at'])
            except IntegrityError:
                return {'ok': False, 'error': 'This idea has already been registered by another team.'}
            create_participations_for_idea_application(application)

            notify(application.student, 'application_registered',
                   'Project Registered 🎉',
                   f'Your application for "{application.idea.title}" has been approved and registered!')
            members = [inv.invitee for inv in application.invitations.filter(status='accepted')]
            notify_many(members, 'application_registered',
                        'Project Registered 🎉',
                        f'The application for "{application.idea.title}" has been approved and registered!')
        else:
            application.status = 'rejected'
            application.rejection_reason = rejection_reason
            application.save(update_fields=['status', 'rejection_reason', 'updated_at'])
            application.invitations.update(status='rejected')
            notify(application.student, 'application_rejected',
                   'Application Rejected by HoD',
                   f'Your application for "{application.idea.title}" was rejected. Reason: {rejection_reason}')
            members = [inv.invitee for inv in application.invitations.all()]
            notify_many(members, 'application_rejected',
                        'Application Rejected by HoD',
                        f'The application for "{application.idea.title}" was rejected. Reason: {rejection_reason}')
        return {'ok': True, 'application': application}

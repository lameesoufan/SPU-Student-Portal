from django.contrib.auth import get_user_model
from django.db import transaction
from django.db import IntegrityError
from .models import (
    ProjectIdea, StudentIdeaProposal, ProjectApplication,
    IdeaApplication, TeamInvitation, ProposalInvitation,
)
from notifications.utils import notify, notify_many

User = get_user_model()


# ── Shared helper ─────────────────────────────────────────────────────────────

def student_has_registered_project(student):
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


def _student_is_active(student):
    """True if student has any active application/proposal (not yet decided)."""
    if student_has_registered_project(student):
        return True, 'You already have a registered project.'
    if IdeaApplication.objects.select_for_update().filter(
        student=student, status__in=['awaiting_members', 'pending_doctor', 'pending_hod'],
    ).exists():
        return True, 'You already have an active application on a doctor idea.'
    if StudentIdeaProposal.objects.select_for_update().filter(
        student=student, status__in=['awaiting_members', 'pending_supervisor', 'pending_hod', 'assigned'],
    ).exists():
        return True, 'You already have an active idea proposal.'
    if TeamInvitation.objects.select_for_update().filter(
        invitee=student, status='accepted',
        application__status__in=['awaiting_members', 'pending_doctor', 'pending_hod', 'registered'],
    ).exists():
        return True, 'You are already a member of an active team.'
    if ProposalInvitation.objects.select_for_update().filter(
        invitee=student, status='accepted',
        proposal__status__in=['awaiting_members', 'pending_supervisor', 'pending_hod', 'assigned'],
    ).exists():
        return True, 'You are already a member of an active proposal team.'
    # ↓↓↓ شيلت فحص الدعوات المعلقة — نقلته لـ create_student_proposal و apply_on_idea ↓↓↓
    return False, ''

# ── UC-01 ─────────────────────────────────────────────────────────────────────

def create_project_idea(*, doctor, title, description, department, required_skills, max_team_size):
    idea = ProjectIdea.objects.create(
        doctor=doctor, title=title, description=description,
        department=department, required_skills=required_skills,
        max_team_size=max_team_size, status='pending_review',
    )
    # Notify HoD of the department
    from django.contrib.auth import get_user_model
    U = get_user_model()
    hods = U.objects.filter(role='hod', department=department)
    notify_many(hods, 'idea_submitted',
                'New Project Idea Submitted',
                f'Dr. {doctor.get_full_name() or doctor.username} submitted a new idea: "{title}".')
    return {'ok': True, 'idea': idea}


# ── UC-02 ─────────────────────────────────────────────────────────────────────

def student_can_propose(student):
    active, msg = _student_is_active(student)
    if active:
        return False, msg
    return True, None


def create_student_proposal(*, student, supervisor, title, description, department,
                             team_size, team_size_reason, member_ids):
    if not supervisor or supervisor.role != 'doctor':
        return {'ok': False, 'error': 'Supervisor must be a doctor.'}

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
            allowed, error = student_can_propose(student)
            if not allowed:
                return {'ok': False, 'error': error}

            # ↓↓↓ فحص الدعوات المعلقة — بس عند إنشاء proposal جديد ↓↓↓
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
                m = members_by_username.get(uid)
                if not m:
                    return {'ok': False, 'error': f'Student with ID "{uid}" not found.'}
                if m.pk == student.pk:
                    return {'ok': False, 'error': 'You cannot add yourself as a team member.'}
                active, err = _student_is_active(m)
                if active:
                    return {'ok': False, 'error': f'Team member "{m.get_full_name() or m.username}" cannot join: {err}'}
                members.append(m)

            if team_size == 1:
                initial_status = 'pending_supervisor'
            else:
                initial_status = 'awaiting_members'

            proposal = StudentIdeaProposal.objects.create(
                student=student, supervisor=supervisor, title=title,
                description=description, department=department,
                team_size=team_size, team_size_reason=team_size_reason,
                status=initial_status,
            )

            for m in members:
                ProposalInvitation.objects.create(proposal=proposal, invitee=m, status='pending')
                notify(m, 'invitation_received',
                       'Team Invitation Received 📨',
                       f'{student.get_full_name() or student.username} invited you to join their project proposal "{title}".')

            if initial_status == 'pending_supervisor':
                notify(supervisor, 'proposal_submitted',
                       'New Student Proposal',
                       f'{student.get_full_name() or student.username} submitted a proposal "{title}" with you as supervisor.')

    except IntegrityError:
        return {'ok': False, 'error': 'A database conflict occurred. You may already have an active proposal or a team member is already assigned elsewhere.'}
    except Exception as e:
        return {'ok': False, 'error': f'An unexpected error occurred: {str(e)}'}

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
        accepted = list(proposal.invitations.filter(status='accepted').select_related('invitee'))
        proposal.invitations.update(status='rejected')

    for inv in accepted:
        notify(inv.invitee, 'proposal_rejected',
               'Proposal Cancelled',
               f'The proposal "{proposal.title}" you were part of has been cancelled by the proposer.')

    return {'ok': True}


def respond_to_proposal_invitation(*, invitation, action):
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
            invitation.save(update_fields=['status', 'updated_at'])

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
                notify(proposal.supervisor, 'proposal_submitted',
                       'New Student Proposal',
                       f'{proposal.student.get_full_name() or proposal.student.username} submitted a proposal "{proposal.title}" with you as supervisor.')

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


def supervisor_review_proposal(*, proposal, action, rejection_reason=''):
    with transaction.atomic():
        proposal = StudentIdeaProposal.objects.select_for_update(of=('self',)).select_related(
            'student', 'supervisor'
        ).get(pk=proposal.pk)
        if proposal.status != 'pending_supervisor':
            return {'ok': False, 'error': 'Proposal is not awaiting supervisor approval.'}
        if action == 'approve':
            proposal.status = 'pending_hod'
            proposal.save(update_fields=['status', 'updated_at'])
            notify(proposal.student, 'proposal_approved_sup',
                   'Proposal Approved by Supervisor',
                   f'Your proposal "{proposal.title}" was approved by the supervisor and is now pending HoD review.')
            # Notify HoD
            from django.contrib.auth import get_user_model
            U = get_user_model()
            hods = U.objects.filter(role='hod', department=proposal.department)
            notify_many(hods, 'proposal_submitted',
                        'Student Proposal Pending Review',
                        f'Proposal "{proposal.title}" by {proposal.student.get_full_name() or proposal.student.username} is awaiting your review.')
        else:
            proposal.status = 'rejected'
            proposal.rejection_reason = rejection_reason
            proposal.save(update_fields=['status', 'rejection_reason', 'updated_at'])
            proposal.invitations.update(status='rejected')
            notify(proposal.student, 'proposal_rejected',
                   'Proposal Rejected',
                   f'Your proposal "{proposal.title}" was rejected by the supervisor. Reason: {rejection_reason}')
        return {'ok': True, 'proposal': proposal}


def hod_review_proposal(*, proposal, action, rejection_reason=''):
    with transaction.atomic():
        proposal = StudentIdeaProposal.objects.select_for_update(of=('self',)).select_related('student').get(pk=proposal.pk)
        if proposal.status != 'pending_hod':
            return {'ok': False, 'error': 'Proposal is not awaiting HoD review.'}
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


def apply_on_idea(*, student, idea, team_size, team_size_reason='', member_ids=None):
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
                active, err = _student_is_active(m)  # ← غيّرنا من student_can_apply لـ _student_is_active
                if active:
                    return {'ok': False, 'error': f'Student "{uid}": {err}'}
                members.append(m)

            initial_status = 'pending_doctor' if team_size == 1 else 'awaiting_members'
            app = IdeaApplication.objects.create(
                student=student, idea=idea, team_size=team_size,
                team_size_reason=team_size_reason, status=initial_status,
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
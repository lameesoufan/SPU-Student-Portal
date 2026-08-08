import logging
import traceback
from rest_framework import status, permissions, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.conf import settings

from .models import GitLabUser, GitLabProject, GitLabCommit
from .serializers import (
    LinkGitLabSerializer, GitLabUserSerializer,
    CreateGitLabProjectSerializer, GitLabProjectSerializer,
    AddMemberSerializer, RemoveMemberSerializer,
    GitLabCommitSerializer, GitLabCommitListSerializer,
    CommitStatsSerializer, GitLabHealthSerializer,
    WebhookProcessResponseSerializer,
    GitLabTokenVerifySerializer, GitLabTokenVerifyResponseSerializer,
)
from . import services

logger = logging.getLogger(__name__)




def _relink_project_to_current_user_namespace(request, board, gitlab_project):
    """Repair stale GitLab links and bind the board to the student's real repository.

    Legacy records may point to ``root/<slug>-<board_id>``.  We first try the
    expected path under the linked GitLab username, then fall back to listing
    projects visible to that user's token and selecting the best namespace/path
    match.  GitLab's response is always treated as the authoritative source.
    """
    # Only the owning student may repair a legacy link. A supervisor or another
    # project member must never be able to repoint the board to their namespace.
    owner_id = None
    if getattr(board, 'proposal', None):
        owner_id = board.proposal.student_id
    elif getattr(board, 'application', None):
        owner_id = board.application.student_id
    if request.user.id != owner_id:
        return gitlab_project

    try:
        linked_user = GitLabUser.objects.get(user=request.user)
    except GitLabUser.DoesNotExist:
        return gitlab_project

    username = (linked_user.gitlab_username or '').strip()
    if not username:
        return gitlab_project

    current_path = (gitlab_project.gitlab_project_path or '').strip('/')
    if current_path.startswith(f'{username}/'):
        return gitlab_project

    suffix = f'-{board.id}'
    stored_slug = current_path.rsplit('/', 1)[-1] if current_path else ''
    if stored_slug.endswith(suffix):
        stored_slug = stored_slug[:-len(suffix)]

    raw_name = getattr(board, 'title', '') or gitlab_project.project_name or stored_slug
    board_slug = services._sanitize_project_path(raw_name)
    if board_slug.endswith(suffix):
        board_slug = board_slug[:-len(suffix)]

    candidate_slugs = []
    for slug in (stored_slug, board_slug, services._sanitize_project_path(gitlab_project.project_name or '')):
        if slug.endswith(suffix):
            slug = slug[:-len(suffix)]
        if slug and slug not in candidate_slugs:
            candidate_slugs.append(slug)

    from urllib.parse import quote
    project_data = None

    # Fast path: resolve exact namespace/path candidates.
    for slug in candidate_slugs:
        candidate = f'{username}/{slug}'
        try:
            project_data = services.gitlab_api_get(
                f"/api/v4/projects/{quote(candidate, safe='')}",
                token=linked_user.access_token,
            )
            break
        except services.GitLabAPIError:
            continue

    # Robust fallback: query all projects visible to the student's token.
    # This handles renamed repositories and old records whose board title differs
    # from the actual GitLab repository path.
    if not project_data:
        search_terms = [slug for slug in candidate_slugs if slug]
        if not search_terms:
            search_terms = ['']

        visible_projects = []
        seen_ids = set()
        for term in search_terms:
            try:
                results = services.gitlab_api_get(
                    '/api/v4/projects',
                    token=linked_user.access_token,
                    params={
                        'membership': 'true',
                        'simple': 'true',
                        'per_page': 100,
                        **({'search': term} if term else {}),
                    },
                )
            except services.GitLabAPIError:
                continue
            if not isinstance(results, list):
                continue
            for item in results:
                if item.get('id') not in seen_ids:
                    visible_projects.append(item)
                    seen_ids.add(item.get('id'))

        username_lower = username.lower()
        normalized_candidates = {slug.lower().replace('_', '-') for slug in candidate_slugs}

        def score(item):
            path_ns = (item.get('path_with_namespace') or '').strip('/')
            namespace, _, path = path_ns.partition('/')
            path_norm = path.lower().replace('_', '-')
            value = 0
            if namespace.lower() == username_lower:
                value += 100
            if path_norm in normalized_candidates:
                value += 80
            if any(path_norm.startswith(c) or c.startswith(path_norm) for c in normalized_candidates if c):
                value += 40
            # Prefer repositories owned by the linked user's namespace.
            owner = ((item.get('namespace') or {}).get('full_path') or '').lower()
            if owner == username_lower:
                value += 30
            return value

        if visible_projects:
            best = max(visible_projects, key=score)
            # Namespace ownership alone is insufficient: require at least a
            # path-prefix match as well, otherwise an unrelated repository in
            # the student's namespace could hijack the local board mapping.
            if score(best) >= 140:
                project_data = best

    if not project_data:
        logger.warning(
            'Could not relink board %s from %s to GitLab namespace %s',
            board.id, current_path, username,
        )
        return gitlab_project

    gitlab_project.gitlab_project_id = project_data['id']
    gitlab_project.project_name = project_data.get('name', gitlab_project.project_name)
    gitlab_project.gitlab_project_path = project_data.get('path_with_namespace', gitlab_project.gitlab_project_path)
    gitlab_project.web_url = services._fix_gitlab_url(project_data.get('web_url', gitlab_project.web_url))
    gitlab_project.ssh_url = project_data.get('ssh_url_to_repo', gitlab_project.ssh_url)
    gitlab_project.http_url = services._fix_gitlab_url(project_data.get('http_url_to_repo', gitlab_project.http_url))
    gitlab_project.default_branch = project_data.get('default_branch', gitlab_project.default_branch)
    gitlab_project.visibility = project_data.get('visibility', gitlab_project.visibility)
    gitlab_project.is_orphaned = False
    gitlab_project.save()
    logger.info('Relinked board %s GitLab project to %s', board.id, gitlab_project.gitlab_project_path)
    return gitlab_project

def _handle_unexpected_error(view_name: str, err: Exception) -> Response:
    """Handle unexpected errors consistently across all views."""
    error_detail = str(err)
    error_type = type(err).__name__
    logger.error(f"Unexpected error in {view_name}: {error_type}: {error_detail}\n{traceback.format_exc()}")
    return Response({
        'success': False,
        'message': 'حدث خطأ داخلي غير متوقع. يرجى المحاولة لاحقاً.',
    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _public_gitlab_error(error: services.GitLabAPIError) -> str:
    """Return a stable client-safe GitLab error without upstream response details."""
    if error.status_code in (401, 403):
        return 'تعذر تنفيذ الطلب بسبب صلاحيات GitLab.'
    if error.status_code == 404:
        return 'المورد المطلوب غير موجود في GitLab.'
    if error.status_code == 409:
        return 'المورد موجود مسبقاً في GitLab.'
    return 'تعذر تنفيذ الطلب على GitLab. يرجى المحاولة لاحقاً.'


def _board_department(board):
    """Resolve the academic department that owns a project board."""
    proposal = getattr(board, 'proposal', None)
    if proposal:
        return getattr(proposal, 'department', None)
    application = getattr(board, 'application', None)
    idea = getattr(application, 'idea', None) if application else None
    return getattr(idea, 'department', None) if idea else None


# M-13 Fix: دالة مساعدة للتحقق من عضوية المستخدم في المشروع
def _assert_board_member(user, board):
    """
    Returns the board if the user is a member/supervisor/admin, else None.
    يُستخدم لحماية views من الوصول غير المصرح به.
    """
    if user.is_staff or user.is_superuser:
        return board
    role = getattr(user, 'role', None)
    if role in ['admin', 'dean']:
        return board
    if role == 'hod':
        return board if getattr(user, 'department', None) == _board_department(board) else None
    if role == 'doctor':
        if hasattr(board, 'proposal') and board.proposal and board.proposal.supervisor_id == user.id:
            return board
        if hasattr(board, 'proposal') and board.proposal and board.proposal.co_supervisors.filter(pk=user.pk).exists():
            return board
        if hasattr(board, 'application') and board.application and board.application.idea.doctor_id == user.id:
            return board
        return None
    if role == 'student':
        if hasattr(board, 'members') and board.members.filter(pk=user.pk).exists():
            return board
        return None
    return None

def _user_is_project_supervisor(user, board):
    """Check if the user is the supervisor (or co-supervisor) of the board's project."""
    if hasattr(board, 'proposal') and board.proposal:
        if board.proposal.supervisor_id == user.id:
            return True
        return board.proposal.co_supervisors.filter(pk=user.pk).exists()
    if hasattr(board, 'application') and board.application and board.application.idea:
        return board.application.idea.doctor_id == user.id
    return False
# ==========================================
# BASE VIEWSETS
# ==========================================

class IsSupervisorOrAdmin(permissions.BasePermission):
    """Allow only supervisors, HoD, Dean, or admin."""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        user = request.user
        return (
            getattr(user, 'role', None) in ['doctor', 'supervisor', 'hod', 'dean', 'admin']
            or user.is_staff
            or user.is_superuser
        )


class IsHoDDeanOrAdmin(permissions.BasePermission):
    """Allow aggregate dashboards only to HoD/Dean/admin users."""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        user = request.user
        return (
            getattr(user, 'role', None) in ['hod', 'dean', 'admin']
            or user.is_staff
            or user.is_superuser
        )


class IsProjectMemberOrSupervisor(permissions.BasePermission):
    """Allow only project members, their supervisor, HoD, Dean, or admin."""
    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_staff or user.is_superuser:
            return True
        if getattr(user, 'role', None) in ['hod', 'dean', 'admin']:
            return True
        board = obj.board
        if hasattr(board, 'members'):
            if board.members.filter(id=user.id).exists():
                return True
        if getattr(user, 'role', None) == 'doctor' and hasattr(board, 'proposal') and board.proposal:
            if board.proposal.supervisor_id == user.id:
                return True
            if board.proposal.co_supervisors.filter(pk=user.pk).exists():
                return True
        if hasattr(board, 'application') and board.application and board.application.idea.doctor_id == user.id:
            return True
        return False


# ==========================================
# GITLAB HEALTH CHECK
# ==========================================

class GitLabConfigView(views.APIView):
    """يرجع رابط GitLab تبع الجامعة عشان الطالب يقدر يفتحو ويعمل Access Token."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            'success': True,
            'gitlab_url': getattr(settings, 'GITLAB_EXTERNAL_URL', settings.GITLAB_URL),
        })


class GitLabHealthView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            result = services.check_gitlab_health()
            serializer = GitLabHealthSerializer(result)
            return Response(serializer.data)
        except Exception as e:
            return _handle_unexpected_error('GitLabHealthView', e)


# ==========================================
# GITLAB ACCOUNT LINKING
# ==========================================

class LinkGitLabAccountView(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LinkGitLabSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        gitlab_token = serializer.validated_data['gitlab_token']
        gitlab_username = serializer.validated_data.get('gitlab_username')

        try:
            gitlab_user = services.link_gitlab_user(
                user=request.user,
                gitlab_token=gitlab_token,
                gitlab_username=gitlab_username,
            )
            return Response({
                'success': True,
                'message': f'تم ربط حسابك بنجاح: {gitlab_user.gitlab_username}',
                'data': GitLabUserSerializer(gitlab_user).data,
            }, status=status.HTTP_200_OK)

        except services.GitLabAPIError as e:
            return Response({
                'success': False,
                'message': _public_gitlab_error(e),
            }, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as e:
            return Response({
                'success': False,
                'message': str(e),
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return _handle_unexpected_error('LinkGitLabAccountView', e)


class UnlinkGitLabAccountView(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        removed = services.unlink_gitlab_user(request.user)
        if removed:
            return Response({
                'success': True,
                'message': 'تم فك ربط حساب GitLab بنجاح',
            })
        return Response({
            'success': False,
            'message': 'لا يوجد حساب GitLab مربوط',
        }, status=status.HTTP_400_BAD_REQUEST)


class GitLabAccountStatusView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            gitlab_user = GitLabUser.objects.get(user=request.user)
            return Response({
                'is_linked': True,
                'data': GitLabUserSerializer(gitlab_user).data,
            })
        except GitLabUser.DoesNotExist:
            return Response({
                'is_linked': False,
                'data': None,
            })


class VerifyGitLabTokenView(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = GitLabTokenVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            gitlab_info = services.verify_gitlab_token(
                serializer.validated_data['gitlab_token']
            )
            return Response({
                'valid': True,
                **gitlab_info,
            })
        except services.GitLabAPIError as e:
            detail = {
                'status_code': e.status_code,
                'gitlab_url': getattr(settings, 'GITLAB_EXTERNAL_URL', settings.GITLAB_URL),
            }
            return Response({
                'valid': False,
                'message': (
                    f'{_public_gitlab_error(e)} تأكد أن التوكن من GitLab الخاص بالجامعة '
                    'وأن الـ scope يحتوي api أو read_user.'
                ),
                'detail': detail,
            }, status=status.HTTP_400_BAD_REQUEST)


# ==========================================
# GITLAB PROJECT (per Board)
# ==========================================

class CreateGitLabProjectView(views.APIView):
    """
    إنشاء مستودع GitLab لمشروع.
    الطالب أو المشرف يقدر يعمل ريبو - المشرف يتضاف تلقائياً كـ Maintainer.
    POST /api/gitlab/board/<board_id>/create-project/
    Body: { "project_name": "optional", "visibility": "private" }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, board_id):
        from project_management.models import ProjectBoard

        try:
            board = ProjectBoard.objects.select_related(
                'proposal__supervisor',
                'application__idea__doctor',
            ).get(id=board_id)
        except ProjectBoard.DoesNotExist:
            return Response({
                'success': False,
                'message': 'المشروع غير موجود',
            }, status=status.HTTP_404_NOT_FOUND)

        # M-13 Fix: التأكد إن المستخدم عضو في المشروع
        if not _assert_board_member(request.user, board):
            return Response({
                'success': False,
                'message': 'أنت لست عضو في هذا المشروع',
            }, status=status.HTTP_403_FORBIDDEN)

        serializer = CreateGitLabProjectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = services.create_gitlab_project(
                board=board,
                project_name=serializer.validated_data.get('project_name'),
                visibility=serializer.validated_data.get('visibility', 'private'),
                initialize_with_readme=serializer.validated_data.get('initialize_with_readme', True),
                creator_user=request.user,
            )

            # Auto-register webhook
            webhook_base = settings.GITLAB_WEBHOOK_BASE_URL if hasattr(settings, 'GITLAB_WEBHOOK_BASE_URL') else None
            if webhook_base:
                webhook_url = f"{webhook_base}/api/gitlab/webhook/"
                try:
                    services.register_webhook(board, webhook_url)
                    result['webhook_registered'] = True
                except Exception as e:
                    logger.warning(f"Failed to register webhook: {e}")
                    result['webhook_registered'] = False

            return Response({
                'success': True,
                'message': f'تم إنشاء المستودع: {result["name"]}',
                'data': result,
            }, status=status.HTTP_201_CREATED)

        except ValueError as e:
            return Response({
                'success': False,
                'message': str(e),
            }, status=status.HTTP_400_BAD_REQUEST)
        except services.GitLabAPIError as e:
            logger.error("GitLab project creation failed: %s", e.message)
            return Response({
                'success': False,
                'message': _public_gitlab_error(e),
                'detail': {'status_code': e.status_code},
            }, status=status.HTTP_400_BAD_REQUEST)


class BoardGitLabInfoView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, board_id):
        from project_management.models import ProjectBoard

        try:
            board = ProjectBoard.objects.select_related(
                'proposal__supervisor',
                'application__idea__doctor',
            ).get(id=board_id)
        except ProjectBoard.DoesNotExist:
            return Response({
                'success': False,
                'message': 'المشروع غير موجود',
            }, status=status.HTTP_404_NOT_FOUND)

        # M-13 Fix: التحقق من العضوية
        if not _assert_board_member(request.user, board):
            return Response({
                'success': False,
                'message': 'غير مصرح — لست عضواً في هذا المشروع',
            }, status=status.HTTP_403_FORBIDDEN)

        try:
            gitlab_project = GitLabProject.objects.get(board=board)
        except GitLabProject.DoesNotExist:
            return Response({
                'success': True,
                'has_gitlab_project': False,
                'data': None,
            })

        # Repair legacy links that point to root/<project>-<board_id> even though
        # the student's actual repository lives under their GitLab namespace.
        gitlab_project = _relink_project_to_current_user_namespace(
            request, board, gitlab_project
        )

        serializer = GitLabProjectSerializer(gitlab_project)
        data = dict(serializer.data)

        # Keep the overview current even after a page refresh. Failure to fetch
        # optional activity must not prevent the repository itself from loading.
        try:
            user_token = None
            try:
                user_token = GitLabUser.objects.get(user=request.user).access_token
            except GitLabUser.DoesNotExist:
                pass

            try:
                activity = services.get_repository_activity(gitlab_project, user_token=user_token)
            except services.GitLabAPIError:
                activity = services.get_repository_activity(gitlab_project, user_token=None)
            data.update(activity)
        except Exception as exc:
            logger.warning("Could not load live GitLab activity for board %s: %s", board_id, exc)
            data.update({
                'branches_count': 1 if gitlab_project.default_branch else 0,
                'branches': [],
                'merge_requests_count': 0,
                'open_merge_requests_count': 0,
                'merge_requests': [],
                'open_issues_count': 0,
            })

        return Response({
            'success': True,
            'has_gitlab_project': True,
            'data': data,
        })

    def post(self, request, board_id):
        """Refresh project info from GitLab and update the database."""
        from project_management.models import ProjectBoard

        try:
            board = ProjectBoard.objects.get(id=board_id)
        except ProjectBoard.DoesNotExist:
            return Response({
                'success': False,
                'message': 'المشروع غير موجود',
            }, status=status.HTTP_404_NOT_FOUND)

        # M-13 Fix: التحقق من العضوية
        if not _assert_board_member(request.user, board):
            return Response({
                'success': False,
                'message': 'غير مصرح — لست عضواً في هذا المشروع',
            }, status=status.HTTP_403_FORBIDDEN)

        try:
            gitlab_project = GitLabProject.objects.get(board=board)
        except GitLabProject.DoesNotExist:
            return Response({
                'success': False,
                'message': 'هذا المشروع غير مرتبط بمستودع GitLab',
            }, status=status.HTTP_404_NOT_FOUND)

        gitlab_project = _relink_project_to_current_user_namespace(
            request, board, gitlab_project
        )

        try:
            # Try to get the user's personal GitLab token
            user_token = None
            try:
                gitlab_user = GitLabUser.objects.get(user=request.user)
                user_token = gitlab_user.access_token
            except GitLabUser.DoesNotExist:
                pass

            # Try fetching from GitLab API with user token first, then admin token
            project_data = None
            if user_token:
                try:
                    project_data = services.gitlab_api_get(
                        f"/api/v4/projects/{gitlab_project.gitlab_project_id}",
                        token=user_token,
                    )
                except services.GitLabAPIError:
                    logger.warning(f"Failed to refresh project info with user token for board {board_id}")

            if not project_data:
                try:
                    project_data = services.gitlab_api_get(
                        f"/api/v4/projects/{gitlab_project.gitlab_project_id}",
                    )
                except services.GitLabAPIError as e:
                    # M-15 Fix: معالجة 404 — المستودع محذوف من GitLab يدوياً
                    if e.status_code == 404:
                        gitlab_project.is_orphaned = True
                        gitlab_project.save(update_fields=['is_orphaned'])
                        return Response({
                            'success': False,
                            'message': 'المستودع محذوف من GitLab. يرجى إنشاء مستودع جديد أو التواصل مع الإدارة.',
                        }, status=status.HTTP_404_NOT_FOUND)
                    return Response({
                        'success': False,
                        'message': _public_gitlab_error(e),
                    }, status=status.HTTP_400_BAD_REQUEST)

            # Fix URLs (replace Docker internal hostname with external URL)
            def fix_url(url):
                if not url:
                    return url
                try:
                    from urllib.parse import urlparse, urlunparse
                    external = getattr(settings, 'GITLAB_EXTERNAL_URL', settings.GITLAB_URL).rstrip('/')
                    if not external:
                        return url
                    parsed = urlparse(url)
                    ext = urlparse(external)
                    return urlunparse((ext.scheme, ext.netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
                except Exception:
                    return url

            # Update database record
            gitlab_project.project_name = project_data.get('name', gitlab_project.project_name)
            gitlab_project.gitlab_project_path = project_data.get('path_with_namespace', gitlab_project.gitlab_project_path)
            gitlab_project.web_url = fix_url(project_data.get('web_url', gitlab_project.web_url))
            gitlab_project.ssh_url = project_data.get('ssh_url_to_repo', gitlab_project.ssh_url)
            gitlab_project.http_url = fix_url(project_data.get('http_url_to_repo', gitlab_project.http_url))
            gitlab_project.default_branch = project_data.get('default_branch', gitlab_project.default_branch)
            gitlab_project.visibility = project_data.get('visibility', gitlab_project.visibility)
            gitlab_project.save()

            serializer = GitLabProjectSerializer(gitlab_project)
            return Response({
                'success': True,
                'message': 'تم تحديث معلومات المشروع من GitLab',
                'data': serializer.data,
            })
        except Exception as e:
            return _handle_unexpected_error('BoardGitLabInfoView.post', e)


class FixBoardGitLabAccessView(views.APIView):
    """Fix admin access to a GitLab project by adding the admin as a member."""
    permission_classes = [IsAuthenticated]

    def post(self, request, board_id):
        from project_management.models import ProjectBoard

        try:
            board = ProjectBoard.objects.get(id=board_id)
        except ProjectBoard.DoesNotExist:
            return Response({
                'success': False,
                'message': 'المشروع غير موجود',
            }, status=status.HTTP_404_NOT_FOUND)

        # Board-scoped auth: only members/supervisors/admins may fix access
        if not _assert_board_member(request.user, board):
            return Response({
                'success': False,
                'message': 'غير مصرح — لست عضواً في هذا المشروع',
            }, status=status.HTTP_403_FORBIDDEN)

        try:
            gitlab_project = GitLabProject.objects.get(board=board)
        except GitLabProject.DoesNotExist:
            return Response({
                'success': False,
                'message': 'هذا المشروع غير مرتبط بمستودع GitLab',
            }, status=status.HTTP_404_NOT_FOUND)

        try:
            # Get user's personal token (needed as owner token to add admin)
            user_token = None
            try:
                gitlab_user = GitLabUser.objects.get(user=request.user)
                user_token = gitlab_user.access_token
            except GitLabUser.DoesNotExist:
                return Response({
                    'success': False,
                    'message': 'يجب ربط حسابك بـ GitLab أولاً لإصلاح الصلاحيات',
                }, status=status.HTTP_400_BAD_REQUEST)

            # Try to ensure admin access
            try:
                result = services.ensure_admin_access(
                    gitlab_project.gitlab_project_id,
                    owner_token=user_token,
                )
                if result:
                    return Response({
                        'success': True,
                        'message': 'تم إصلاح صلاحيات الوصول - تمت إضافة الـ admin كعضو في المشروع',
                    })
                else:
                    return Response({
                        'success': False,
                        'message': 'لم يتم إصلاح الصلاحيات. تأكد أن حسابك هو مالك المشروع في GitLab.',
                    }, status=status.HTTP_400_BAD_REQUEST)
            except services.GitLabAPIError as e:
                return Response({
                    'success': False,
                    'message': _public_gitlab_error(e),
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return _handle_unexpected_error('FixBoardGitLabAccessView', e)


class BoardGitLabMembersView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, board_id):
        from project_management.models import ProjectBoard

        try:
            board = ProjectBoard.objects.select_related(
                'proposal__supervisor',
                'application__idea__doctor',
            ).get(id=board_id)
        except ProjectBoard.DoesNotExist:
            return Response({
                'success': False,
                'message': 'المشروع غير موجود',
            }, status=status.HTTP_404_NOT_FOUND)

        # M-13 Fix: التحقق من أن المستخدم عضو في هذا المشروع قبل عرض الأعضاء
        if not _assert_board_member(request.user, board):
            return Response({
                'success': False,
                'message': 'غير مصرح — لست عضواً في هذا المشروع',
            }, status=status.HTTP_403_FORBIDDEN)

        try:
            # Try to get the user's personal GitLab token
            user_token = None
            try:
                gitlab_user = GitLabUser.objects.get(user=request.user)
                user_token = gitlab_user.access_token
            except GitLabUser.DoesNotExist:
                pass

            # Try with user token first, then admin token
            if user_token:
                try:
                    members = services.get_project_members(board, user_token=user_token)
                    return Response({
                        'success': True,
                        'data': members,
                    })
                except (services.GitLabAPIError, ValueError) as e:
                    logger.warning("Member listing failed with user token for board %s: %s", board_id, e)

            # Try to ensure admin access before using admin token
            try:
                gitlab_project = GitLabProject.objects.get(board=board)
                # Try to fix admin access if user_token is available
                if user_token:
                    try:
                        services.ensure_admin_access(gitlab_project.gitlab_project_id, owner_token=user_token)
                    except Exception as e:
                        logger.warning("Could not ensure admin access for board %s: %s", board_id, e)
            except GitLabProject.DoesNotExist:
                return Response({
                    'success': False,
                    'message': 'هذا المشروع غير مرتبط بمستودع GitLab',
                }, status=status.HTTP_400_BAD_REQUEST)

            # Fallback: try with admin token
            try:
                members = services.get_project_members(board, user_token=None)
                return Response({
                    'success': True,
                    'data': members,
                })
            except ValueError as e:
                return Response({
                    'success': False,
                    'message': str(e),
                }, status=status.HTTP_400_BAD_REQUEST)
            except services.GitLabAPIError as e:
                logger.warning("Member listing failed with admin token for board %s: %s", board_id, e.message)
                return Response({
                    'success': False,
                    'message': _public_gitlab_error(e),
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return _handle_unexpected_error('BoardGitLabMembersView', e)


class AddBoardMemberView(views.APIView):
    permission_classes = [IsAuthenticated, IsSupervisorOrAdmin]

    def post(self, request, board_id):
        from project_management.models import ProjectBoard

        try:
            board = ProjectBoard.objects.get(id=board_id)
        except ProjectBoard.DoesNotExist:
            return Response({
                'success': False,
                'message': 'المشروع غير موجود',
            }, status=status.HTTP_404_NOT_FOUND)

        # Board-scoped auth: only the project supervisor, HoD, dean or admin may add members
        if not _assert_board_member(request.user, board):
            return Response({
                'success': False,
                'message': 'غير مصرح — لست عضواً في هذا المشروع',
            }, status=status.HTTP_403_FORBIDDEN)
        if request.user.role not in ('dean', 'admin', 'hod') and not _user_is_project_supervisor(request.user, board):
            return Response({
                'success': False,
                'message': 'فقط المشرف على المشروع يمكنه إدارة أعضاء GitLab.',
            }, status=status.HTTP_403_FORBIDDEN)

        serializer = AddMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_username = serializer.validated_data['gitlab_username']
        target_links = GitLabUser.objects.select_related('user').filter(gitlab_username=target_username)
        if target_links.count() != 1:
            return Response({
                'success': False,
                'message': 'يجب أن يكون المستخدم مربوطاً بحساب محلي ومشاركاً في المشروع.',
            }, status=status.HTTP_400_BAD_REQUEST)
        target_link = target_links.first()

        target_user = target_link.user
        is_project_member = board.members.filter(pk=target_user.pk).exists()
        is_supervisor = _user_is_project_supervisor(target_user, board)
        if not (is_project_member or is_supervisor):
            return Response({
                'success': False,
                'message': 'لا يمكن إضافة مستخدم غير مشارك في هذا المشروع.',
            }, status=status.HTTP_403_FORBIDDEN)

        # Try to get the user's personal GitLab token
        user_token = None
        try:
            gitlab_user = GitLabUser.objects.get(user=request.user)
            user_token = gitlab_user.access_token
        except GitLabUser.DoesNotExist:
            pass

        # Try with user token first, then admin token
        if user_token:
            try:
                result = services.add_project_member(
                    board=board,
                    gitlab_username=target_username,
                    access_level=serializer.validated_data.get('access_level', 30),
                    user_token=user_token,
                )
                return Response({
                    'success': True,
                    'message': f'تمت إضافة {result["name"]} ({result["access_level_name"]})',
                    'data': result,
                })
            except (services.GitLabAPIError, ValueError) as e:
                logger.warning(f"add_project_member failed with user token for board {board_id}: {e}")

        try:
            result = services.add_project_member(
                board=board,
                gitlab_username=target_username,
                access_level=serializer.validated_data.get('access_level', 30),
                user_token=None,
            )
            return Response({
                'success': True,
                'message': f'تمت إضافة {result["name"]} ({result["access_level_name"]})',
                'data': result,
            })
        except ValueError as e:
            return Response({
                'success': False,
                'message': str(e),
            }, status=status.HTTP_400_BAD_REQUEST)
        except services.GitLabAPIError as e:
            return Response({
                'success': False,
                'message': _public_gitlab_error(e),
            }, status=status.HTTP_400_BAD_REQUEST)


class RemoveBoardMemberView(views.APIView):
    permission_classes = [IsAuthenticated, IsSupervisorOrAdmin]

    def post(self, request, board_id):
        from project_management.models import ProjectBoard

        try:
            board = ProjectBoard.objects.get(id=board_id)
        except ProjectBoard.DoesNotExist:
            return Response({
                'success': False,
                'message': 'المشروع غير موجود',
            }, status=status.HTTP_404_NOT_FOUND)

        # Board-scoped auth: only the project supervisor, HoD, dean or admin may remove members
        if not _assert_board_member(request.user, board):
            return Response({
                'success': False,
                'message': 'غير مصرح — لست عضواً في هذا المشروع',
            }, status=status.HTTP_403_FORBIDDEN)
        if request.user.role not in ('dean', 'admin', 'hod') and not _user_is_project_supervisor(request.user, board):
            return Response({
                'success': False,
                'message': 'فقط المشرف على المشروع يمكنه إدارة أعضاء GitLab.',
            }, status=status.HTTP_403_FORBIDDEN)

        serializer = RemoveMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_gitlab_user_id = serializer.validated_data['gitlab_user_id']
        target_links = GitLabUser.objects.select_related('user').filter(gitlab_user_id=target_gitlab_user_id)
        if target_links.count() != 1:
            return Response({
                'success': False,
                'message': 'لا يمكن حذف مستخدم GitLab غير مرتبط بحساب محلي معروف.',
            }, status=status.HTTP_400_BAD_REQUEST)
        target_link = target_links.first()

        target_user = target_link.user
        if not board.members.filter(pk=target_user.pk).exists():
            return Response({
                'success': False,
                'message': 'لا يمكن حذف مستخدم غير مشارك كطالب في هذا المشروع.',
            }, status=status.HTTP_403_FORBIDDEN)

        # Try to get the user's personal GitLab token
        user_token = None
        try:
            gitlab_user = GitLabUser.objects.get(user=request.user)
            user_token = gitlab_user.access_token
        except GitLabUser.DoesNotExist:
            pass

        # Try with user token first, then admin token
        if user_token:
            try:
                services.remove_project_member(
                    board=board,
                    gitlab_user_id=target_gitlab_user_id,
                    user_token=user_token,
                )
                return Response({
                    'success': True,
                    'message': 'تم حذف العضو من المستودع',
                })
            except (services.GitLabAPIError, ValueError) as e:
                logger.warning(f"remove_project_member failed with user token for board {board_id}: {e}")

        try:
            services.remove_project_member(
                board=board,
                gitlab_user_id=target_gitlab_user_id,
                user_token=None,
            )
            return Response({
                'success': True,
                'message': 'تم حذف العضو من المستودع',
            })
        except ValueError as e:
            return Response({
                'success': False,
                'message': str(e),
            }, status=status.HTTP_400_BAD_REQUEST)
        except services.GitLabAPIError as e:
            return Response({
                'success': False,
                'message': _public_gitlab_error(e),
            }, status=status.HTTP_400_BAD_REQUEST)


# ==========================================
# COMMITS
# ==========================================

class BoardCommitStatsView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, board_id):
        from project_management.models import ProjectBoard

        try:
            board = ProjectBoard.objects.select_related(
                'proposal__supervisor',
                'application__idea__doctor',
            ).get(id=board_id)
        except ProjectBoard.DoesNotExist:
            return Response({
                'success': False,
                'message': 'المشروع غير موجود',
            }, status=status.HTTP_404_NOT_FOUND)

        # M-13 Fix: التحقق من العضوية
        if not _assert_board_member(request.user, board):
            return Response({
                'success': False,
                'message': 'غير مصرح — لست عضواً في هذا المشروع',
            }, status=status.HTTP_403_FORBIDDEN)

        stats = services.get_commit_stats(board)
        return Response({
            'success': True,
            'data': stats,
        })


class BoardCommitsView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, board_id):
        from project_management.models import ProjectBoard

        try:
            board = ProjectBoard.objects.select_related(
                'proposal__supervisor',
                'application__idea__doctor',
            ).get(id=board_id)
        except ProjectBoard.DoesNotExist:
            return Response({
                'success': False,
                'message': 'المشروع غير موجود',
            }, status=status.HTTP_404_NOT_FOUND)

        # M-13 Fix: التحقق من أن المستخدم عضو في المشروع قبل عرض الـ commits
        if not _assert_board_member(request.user, board):
            return Response({
                'success': False,
                'message': 'غير مصرح — لست عضواً في هذا المشروع',
            }, status=status.HTTP_403_FORBIDDEN)

        try:
            gitlab_project = GitLabProject.objects.get(board=board)
        except GitLabProject.DoesNotExist:
            return Response({
                'success': True,
                'has_commits': False,
                'message': 'المشروع غير مرتبط بمستودع GitLab',
                'data': [],
                'total': 0,
            })

        queryset = GitLabCommit.objects.filter(project=gitlab_project)

        author = request.query_params.get('author')
        if author:
            queryset = queryset.filter(author_name=author)

        try:
            page = max(1, int(request.query_params.get('page', 1)))
            limit = min(100, max(1, int(request.query_params.get('limit', 20))))
        except (TypeError, ValueError):
            return Response({
                'success': False,
                'message': 'page and limit must be valid integers',
            }, status=status.HTTP_400_BAD_REQUEST)

        total = queryset.count()
        start = (page - 1) * limit
        end = start + limit
        commits = queryset.order_by('-committed_date')[start:end]

        serializer = GitLabCommitListSerializer(commits, many=True)

        authors = list(
            GitLabCommit.objects.filter(project=gitlab_project)
            .values_list('author_name', flat=True)
            .distinct()
        )

        return Response({
            'success': True,
            'has_commits': total > 0,
            'data': serializer.data,
            'total': total,
            'page': page,
            'limit': limit,
            'total_pages': (total + limit - 1) // limit,
            'authors': authors,
        })


class BoardCommitDetailView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, board_id, commit_id):
        # M-13 Fix: التحقق من العضوية في commit detail أيضاً
        from project_management.models import ProjectBoard
        try:
            board = ProjectBoard.objects.select_related(
                'proposal__supervisor',
                'application__idea__doctor',
            ).get(id=board_id)
        except ProjectBoard.DoesNotExist:
            return Response({
                'success': False,
                'message': 'المشروع غير موجود',
            }, status=status.HTTP_404_NOT_FOUND)

        if not _assert_board_member(request.user, board):
            return Response({
                'success': False,
                'message': 'غير مصرح — لست عضواً في هذا المشروع',
            }, status=status.HTTP_403_FORBIDDEN)

        try:
            gitlab_project = GitLabProject.objects.get(board_id=board_id)
        except GitLabProject.DoesNotExist:
            return Response({
                'success': False,
                'message': 'المشروع غير مرتبط بمستودع GitLab',
            }, status=status.HTTP_404_NOT_FOUND)

        try:
            commit = GitLabCommit.objects.get(
                project=gitlab_project,
                id=commit_id,
            )
            serializer = GitLabCommitSerializer(commit)
            return Response({
                'success': True,
                'data': serializer.data,
            })
        except GitLabCommit.DoesNotExist:
            return Response({
                'success': False,
                'message': 'الـ Commit غير موجود',
            }, status=status.HTTP_404_NOT_FOUND)


class SyncCommitsView(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, board_id):
        from project_management.models import ProjectBoard

        try:
            board = ProjectBoard.objects.select_related(
                'proposal__supervisor',
                'application__idea__doctor',
            ).get(id=board_id)
        except ProjectBoard.DoesNotExist:
            return Response({
                'success': False,
                'message': 'المشروع غير موجود',
            }, status=status.HTTP_404_NOT_FOUND)

        # M-13 Fix: التحقق من العضوية قبل السماح بـ sync
        if not _assert_board_member(request.user, board):
            return Response({
                'success': False,
                'message': 'غير مصرح — لست عضواً في هذا المشروع',
            }, status=status.HTTP_403_FORBIDDEN)

        try:
            # Try to get the user's personal GitLab token
            user_token = None
            try:
                gitlab_user = GitLabUser.objects.get(user=request.user)
                user_token = gitlab_user.access_token
            except GitLabUser.DoesNotExist:
                pass

            # Try syncing with user token first, then fall back to admin token
            last_error = None

            # Attempt 1: User's personal token
            if user_token:
                try:
                    result = services.sync_commits_from_gitlab(board, user_token=user_token)
                    result['used_token'] = 'user'
                    return Response({
                        'success': True,
                        'message': f'تمت المزامنة: {result["new_commits"]} commits جديدة من أصل {result["total_fetched"]}',
                        'data': result,
                    })
                except (services.GitLabAPIError, ValueError) as e:
                    last_error = e
                    logger.warning(f"Sync failed with user token for board {board_id}: {e}")

            # Attempt 2: Admin token (fallback)
            try:
                result = services.sync_commits_from_gitlab(board, user_token=None)
                result['used_token'] = 'admin'
                if not user_token:
                    result['warning'] = 'لم يتم ربط حسابك بـ GitLab - تمت المزامنة بحساب النظام'
                return Response({
                    'success': True,
                    'message': f'تمت المزامنة: {result["new_commits"]} commits جديدة من أصل {result["total_fetched"]}',
                    'data': result,
                })
            except ValueError as e:
                return Response({
                    'success': False,
                    'message': str(e),
                }, status=status.HTTP_400_BAD_REQUEST)
            except services.GitLabAPIError as e:
                return Response({
                    'success': False,
                    'message': _public_gitlab_error(e),
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return _handle_unexpected_error('SyncCommitsView', e)


# ==========================================
# ALL BOARDS STATS (for HoD/Dean Dashboard)
# ==========================================

class AllBoardsStatsView(views.APIView):
    permission_classes = [IsAuthenticated, IsHoDDeanOrAdmin]

    def get(self, request):
        gitlab_projects = GitLabProject.objects.select_related('board').all()

        if getattr(request.user, 'role', None) == 'hod' and not request.user.is_superuser:
            department = getattr(request.user, 'department', None)
            gitlab_projects = [
                gp for gp in gitlab_projects
                if _board_department(gp.board) == department
            ]

        boards_stats = []
        for gp in gitlab_projects:
            stats = services.get_commit_stats(gp.board)
            boards_stats.append({
                'board_id': gp.board.id,
                'board_title': gp.board.title,
                'has_gitlab_project': True,
                'project_name': gp.project_name,
                'web_url': gp.web_url,
                'is_orphaned': gp.is_orphaned,  # M-15 Fix: إظهار حالة orphaned في الإحصائيات
                'total_commits': stats.get('total_commits', 0),
                'total_authors': stats.get('total_authors', 0),
                'last_commit': stats.get('last_commit'),
            })

        boards_stats.sort(key=lambda x: x['total_commits'], reverse=True)

        return Response({
            'success': True,
            'total_boards': len(boards_stats),
            'data': boards_stats,
        })

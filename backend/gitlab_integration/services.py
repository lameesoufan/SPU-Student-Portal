import requests
import hmac
import hashlib
import logging
import re
import json as json_module
from datetime import datetime
from typing import Optional, List, Dict, Any
from django.conf import settings

logger = logging.getLogger(__name__)


class GitLabAPIError(Exception):
    """Custom exception for GitLab API errors."""
    def __init__(self, message: str, status_code: int = None, response: dict = None):
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(self.message)


def _get_gitlab_config():
    """Get GitLab configuration from settings."""
    return {
        'url': settings.GITLAB_URL.rstrip('/'),
        'token': settings.GITLAB_TOKEN,
        'webhook_secret': settings.GITLAB_WEBHOOK_SECRET,
    }


def _gitlab_headers(token: str = None) -> dict:
    """Get headers for GitLab API requests."""
    config = _get_gitlab_config()
    access_token = token or config['token']
    return {
        'PRIVATE-TOKEN': access_token,
        'Content-Type': 'application/json',
    }


def _safe_json_parse(response) -> dict:
    """Safely parse JSON from a response, handling empty or non-JSON responses."""
    if not response.content:
        return {}
    try:
        return response.json()
    except (json_module.JSONDecodeError, ValueError):
        # Response is not valid JSON (could be HTML error page, empty, etc.)
        return {}
    except Exception:
        return {}


def _gitlab_api_get_all_pages(endpoint: str, token: str = None, params: dict = None) -> list:
    config = _get_gitlab_config()
    url = f"{config['url']}{endpoint}"
    headers = _gitlab_headers(token)
    results = []
    page = 1
    params = dict(params or {})
    params.setdefault('per_page', 100)

    while True:
        params['page'] = page
        try:
            response = requests.get(url, headers=headers, params=params, timeout=15)
        except requests.exceptions.ConnectionError:
            raise GitLabAPIError("لا يمكن الاتصال بـ GitLab. تأكد أن الخادم يعمل.")
        except requests.exceptions.Timeout:
            raise GitLabAPIError("انتهت مهلة الاتصال بـ GitLab.")

        if response.status_code == 200:
            page_data = _safe_json_parse(response)
            if isinstance(page_data, dict) and 'items' in page_data:
                results.extend(page_data['items'])
            elif isinstance(page_data, list):
                results.extend(page_data)
            else:
                break

            next_page = response.headers.get('X-Next-Page')
            if next_page:
                try:
                    next_page = int(next_page)
                except ValueError:
                    break
                if next_page == 0:
                    break
                page = next_page
                continue

            link_header = response.headers.get('Link', '')
            if 'rel="next"' in link_header:
                page += 1
                continue
            break
        elif response.status_code == 401:
            raise GitLabAPIError("Token غير صالح أو منتهي الصلاحية", status_code=401)
        elif response.status_code == 404:
            raise GitLabAPIError("المورد غير موجود", status_code=404)
        else:
            error_detail = _extract_gitlab_error_message(response)
            raise GitLabAPIError(
                f"خطأ في GitLab API: {response.status_code} - {error_detail}",
                status_code=response.status_code,
                response=_safe_json_parse(response)
            )

    return results


def _extract_gitlab_error_message(response) -> str:
    """Extract a readable error message from GitLab API response."""
    data = _safe_json_parse(response)
    
    # If we couldn't parse JSON, try to show raw text (truncated)
    if not data and response.content:
        raw = response.text[:200] if response.text else ''
        if raw:
            return f"HTTP {response.status_code} - Response: {raw}"
    
    # GitLab returns errors in different formats
    if isinstance(data, dict):
        # Format 1: {"message": {"field": ["error1", "error2"]}}
        if 'message' in data:
            msg = data['message']
            if isinstance(msg, dict):
                parts = []
                for field, errors in msg.items():
                    if isinstance(errors, list):
                        parts.append(f"{field}: {', '.join(errors)}")
                    else:
                        parts.append(f"{field}: {errors}")
                return '; '.join(parts)
            return str(msg)
        # Format 2: {"error": "message"}
        if 'error' in data:
            return str(data['error'])
    return f"HTTP {response.status_code}"


def gitlab_api_get(endpoint: str, token: str = None, params: dict = None) -> dict:
    config = _get_gitlab_config()
    url = f"{config['url']}{endpoint}"
    headers = _gitlab_headers(token)

    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)

        if response.status_code == 200:
            return _safe_json_parse(response)
        elif response.status_code == 401:
            raise GitLabAPIError("Token غير صالح أو منتهي الصلاحية", status_code=401)
        elif response.status_code == 404:
            raise GitLabAPIError("المورد غير موجود", status_code=404)
        else:
            error_detail = _extract_gitlab_error_message(response)
            raise GitLabAPIError(
                f"خطأ في GitLab API: {response.status_code} - {error_detail}",
                status_code=response.status_code,
                response=_safe_json_parse(response)
            )
    except GitLabAPIError:
        raise  # Re-raise our own errors
    except requests.exceptions.ConnectionError:
        raise GitLabAPIError("لا يمكن الاتصال بـ GitLab. تأكد أن الخادم يعمل.")
    except requests.exceptions.Timeout:
        raise GitLabAPIError("انتهت مهلة الاتصال بـ GitLab.")


def gitlab_api_post(endpoint: str, data: dict = None, token: str = None) -> dict:
    config = _get_gitlab_config()
    url = f"{config['url']}{endpoint}"
    headers = _gitlab_headers(token)

    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)

        if response.status_code in [200, 201, 202]:
            return _safe_json_parse(response)
        elif response.status_code == 401:
            raise GitLabAPIError("Token غير صالح أو منتهي الصلاحية", status_code=401)
        elif response.status_code == 409:
            raise GitLabAPIError("المورد موجود مسبقاً", status_code=409)
        else:
            error_detail = _extract_gitlab_error_message(response)
            raise GitLabAPIError(
                f"خطأ في GitLab API: {response.status_code} - {error_detail}",
                status_code=response.status_code,
                response=_safe_json_parse(response)
            )
    except GitLabAPIError:
        raise  # Re-raise our own errors
    except requests.exceptions.ConnectionError:
        raise GitLabAPIError("لا يمكن الاتصال بـ GitLab. تأكد أن الخادم يعمل.")
    except requests.exceptions.Timeout:
        raise GitLabAPIError("انتهت مهلة الاتصال بـ GitLab.")


def gitlab_api_delete(endpoint: str, token: str = None) -> bool:
    config = _get_gitlab_config()
    url = f"{config['url']}{endpoint}"
    headers = _gitlab_headers(token)

    try:
        response = requests.delete(url, headers=headers, timeout=15)

        if response.status_code in [200, 201, 202, 204]:
            return True
        else:
            error_detail = _extract_gitlab_error_message(response)
            raise GitLabAPIError(
                f"خطأ في GitLab API: {response.status_code} - {error_detail}",
                status_code=response.status_code,
            )
    except GitLabAPIError:
        raise  # Re-raise our own errors
    except requests.exceptions.ConnectionError:
        raise GitLabAPIError("لا يمكن الاتصال بـ GitLab.")
    except requests.exceptions.Timeout:
        raise GitLabAPIError("انتهت مهلة الاتصال بـ GitLab.")


def gitlab_api_put(endpoint: str, data: dict = None, token: str = None) -> dict:
    config = _get_gitlab_config()
    url = f"{config['url']}{endpoint}"
    headers = _gitlab_headers(token)

    try:
        response = requests.put(url, headers=headers, json=data, timeout=15)

        if response.status_code in [200, 201, 202]:
            return _safe_json_parse(response)
        else:
            error_detail = _extract_gitlab_error_message(response)
            raise GitLabAPIError(
                f"خطأ في GitLab API: {response.status_code} - {error_detail}",
                status_code=response.status_code,
                response=_safe_json_parse(response)
            )
    except GitLabAPIError:
        raise  # Re-raise our own errors
    except requests.exceptions.ConnectionError:
        raise GitLabAPIError("لا يمكن الاتصال بـ GitLab.")
    except requests.exceptions.Timeout:
        raise GitLabAPIError("انتهت مهلة الاتصال بـ GitLab.")


# ==========================================
# USER LINKING FUNCTIONS
# ==========================================

def verify_gitlab_token(gitlab_token: str) -> dict:
    user_data = gitlab_api_get('/api/v4/user', token=gitlab_token)
    return {
        'id': user_data.get('id'),
        'username': user_data.get('username'),
        'name': user_data.get('name'),
        'email': user_data.get('email'),
        'avatar_url': user_data.get('avatar_url'),
    }


def link_gitlab_user(user, gitlab_token: str, gitlab_username: str = None):
    from .models import GitLabUser

    gitlab_info = verify_gitlab_token(gitlab_token)

    if gitlab_username and gitlab_info['username'] != gitlab_username:
        raise ValueError(
            f"اسم المستخدم لا يتطابق. القيمة المدخلة: {gitlab_username}, "
            f"القيمة الفعلية في GitLab: {gitlab_info['username']}"
        )

    gitlab_user, created = GitLabUser.objects.update_or_create(
        user=user,
        defaults={
            'gitlab_user_id': gitlab_info['id'],
            'gitlab_username': gitlab_info['username'],
            'gitlab_name': gitlab_info.get('name', ''),
            'gitlab_email': gitlab_info.get('email', ''),
            'avatar_url': gitlab_info.get('avatar_url', ''),
            'access_token': gitlab_token,
        }
    )

    if created:
        logger.info(f"Linked GitLab account: {user.username} -> {gitlab_info['username']}")
    else:
        logger.info(f"Updated GitLab link: {user.username} -> {gitlab_info['username']}")

    return gitlab_user


def unlink_gitlab_user(user) -> bool:
    from .models import GitLabUser

    try:
        gitlab_user = GitLabUser.objects.get(user=user)
        gitlab_user.delete()
        logger.info(f"Unlinked GitLab account for user: {user.username}")
        return True
    except GitLabUser.DoesNotExist:
        return False


# ==========================================
# PROJECT FUNCTIONS
# ==========================================

def _fix_gitlab_url(url: str) -> str:
    if not url:
        return url
    try:
        from urllib.parse import urlparse, urlunparse
        external = getattr(settings, 'GITLAB_URL', '').rstrip('/')
        if not external:
            return url
        parsed = urlparse(url)
        ext = urlparse(external)
        return urlunparse((ext.scheme, ext.netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
    except Exception:
        return url


def _sanitize_project_path(name: str) -> str:
    """
    Sanitize project name for use as GitLab project path.
    Only allows lowercase ASCII letters, numbers, hyphens, underscores, and dots.
    """
    name = re.sub(r'[^\u0000-\u007F]+', '', name or '')
    name = re.sub(r'[^a-zA-Z0-9._-]+', '-', name)
    name = name.strip('-._')
    name = name.lower()
    name = re.sub(r'-{2,}', '-', name)
    name = re.sub(r'\.{2,}', '.', name)
    name = re.sub(r'[-.]{2,}', '-', name)
    return name


def _generate_project_slug(board_title: str, board_id: int) -> str:
    slug = _sanitize_project_path(board_title)
    if not slug:
        slug = f'project-{board_id}'
    if len(slug) > 200:
        slug = slug[:200].rstrip('-._')
    if not slug:
        slug = f'project-{board_id}'
    return slug


def _prepare_project_payload(display_name: str, project_path: str, description: str,
                             visibility: str, initialize_with_readme: bool) -> dict:
    return {
        'name': display_name,
        'path': project_path,
        'description': description,
        'visibility': visibility,
        'initialize_with_readme': initialize_with_readme,
        'issues_enabled': True,
        'merge_requests_enabled': True,
        'wiki_enabled': True,
        'snippets_enabled': True,
    }


def _is_path_conflict_error(exc: GitLabAPIError) -> bool:
    return exc.status_code in (400, 409) and 'already been taken' in str(exc.message).lower()


def _create_gitlab_project_with_fallback(data: dict, creator_token: str = None, board_id: int = None, display_name: str = None) -> dict:
    """Try creating the project with creator token first, then fallback to admin token."""
    first_error = None

    if creator_token:
        try:
            return gitlab_api_post('/api/v4/projects', data=data, token=creator_token)
        except GitLabAPIError as exc:
            first_error = exc
            logger.warning(f"Failed to create project with user token: {exc.message}")
            if _is_path_conflict_error(exc) and board_id is not None and display_name is not None:
                data = _prepare_project_payload(
                    display_name=f"{display_name}-{board_id}",
                    project_path=f"{data['path']}-{board_id}",
                    description=data.get('description', ''),
                    visibility=data.get('visibility', 'private'),
                    initialize_with_readme=data.get('initialize_with_readme', True),
                )
                try:
                    return gitlab_api_post('/api/v4/projects', data=data, token=creator_token)
                except GitLabAPIError:
                    pass

    try:
        return gitlab_api_post('/api/v4/projects', data=data)
    except GitLabAPIError as exc:
        if _is_path_conflict_error(exc) and board_id is not None and display_name is not None:
            data = _prepare_project_payload(
                display_name=f"{display_name}-{board_id}",
                project_path=f"{data['path']}-{board_id}",
                description=data.get('description', ''),
                visibility=data.get('visibility', 'private'),
                initialize_with_readme=data.get('initialize_with_readme', True),
            )
            return gitlab_api_post('/api/v4/projects', data=data)

        if first_error:
            raise GitLabAPIError(
                f"Failed to create GitLab project with user token ({first_error.message}) and admin token ({exc.message})",
                status_code=exc.status_code,
                response=exc.response,
            )
        raise


def create_gitlab_project(board, project_name: str = None, visibility: str = 'private',
                          initialize_with_readme: bool = True, creator_user=None) -> dict:
    """
    Create a new GitLab project for a ProjectBoard.
    The creator can be a student or a supervisor.
    If a student creates it, the supervisor and team members are auto-added.
    """
    from .models import GitLabProject, GitLabUser

    if GitLabProject.objects.filter(board=board).exists():
        raise ValueError("هذا المشروع مرتبط بمستودع GitLab بالفعل")

    display_name = project_name if project_name else board.title or f'Project {board.id}'
    project_path = _generate_project_slug(display_name, board.id)
    description = f"SPU Project: {board.title or display_name}"
    if hasattr(board, 'description') and board.description:
        description = f"{description} - {board.description[:200]}"

    creator_token = None
    creator_gitlab = None
    if creator_user:
        try:
            creator_gitlab = GitLabUser.objects.get(user=creator_user)
            creator_token = creator_gitlab.access_token
        except GitLabUser.DoesNotExist:
            pass

    data = _prepare_project_payload(
        display_name=display_name,
        project_path=project_path,
        description=description,
        visibility=visibility,
        initialize_with_readme=initialize_with_readme,
    )

    result = _create_gitlab_project_with_fallback(
        data=data,
        creator_token=creator_token,
        board_id=board.id,
        display_name=display_name,
    )

    # M-09 Fix: Rollback - حذف المستودع من GitLab لو فشل الحفظ بقاعدة البيانات
    try:
        gitlab_project = GitLabProject.objects.create(
            board=board,
            gitlab_project_id=result['id'],
            project_name=result['name'],
            gitlab_project_path=result.get('path_with_namespace', ''),
            web_url=_fix_gitlab_url(result['web_url']),
            ssh_url=result.get('ssh_url_to_repo', ''),
            http_url=_fix_gitlab_url(result.get('http_url_to_repo', '')),
            visibility=visibility,
            default_branch=result.get('default_branch', 'main'),
        )
    except Exception as db_error:
        # فشل الحفظ بقاعدة البيانات → احذف المستودع من GitLab
        try:
            gitlab_api_delete(f"/api/v4/projects/{result['id']}")
            logger.error(f"Rolled back GitLab project {result['id']} after DB error: {db_error}")
        except Exception as cleanup_error:
            logger.critical(
                f"ORPHANED GitLab project {result['id']} — manual cleanup needed! "
                f"DB error: {db_error}, Cleanup error: {cleanup_error}"
            )
        raise

    logger.info(f"Created GitLab project '{result['name']}' (ID: {result['id']}) for board: {board.title}")

    member_add_token = creator_token if creator_token else None
    ensure_admin_access(result['id'], member_add_token)

    # IMPORTANT: Add the creator as Maintainer so they can access their own project.
    # When the project is created with the admin token (fallback), the admin becomes
    # the Owner, but the student who created it has NO access. We must add them.
    if creator_gitlab:
        try:
            gitlab_api_post(
                f"/api/v4/projects/{result['id']}/members",
                data={
                    'user_id': creator_gitlab.gitlab_user_id,
                    'access_level': 40,  # Maintainer
                },
                token=member_add_token,
            )
            logger.info(f"Added creator {creator_gitlab.gitlab_username} as Maintainer to project {result['id']}")
        except GitLabAPIError as e:
            # Member might already exist if created with user token under their namespace
            if 'already exists' in str(e.message).lower():
                logger.info(f"Creator {creator_gitlab.gitlab_username} already has access to project")
            else:
                logger.warning(f"Could not add creator {creator_gitlab.gitlab_username} as member: {e.message}")

    supervisor = getattr(board, 'supervisor', None)
    if supervisor:
        try:
            supervisor_gitlab = GitLabUser.objects.get(user=supervisor)
            creator_gitlab_id = creator_gitlab.gitlab_user_id if creator_gitlab else None
            if supervisor_gitlab.gitlab_user_id != creator_gitlab_id:
                try:
                    gitlab_api_post(
                        f"/api/v4/projects/{result['id']}/members",
                        data={
                            'user_id': supervisor_gitlab.gitlab_user_id,
                            'access_level': 40,
                        },
                        token=member_add_token,
                    )
                    logger.info(f"Auto-added supervisor {supervisor_gitlab.gitlab_username} as Maintainer")
                except GitLabAPIError as e:
                    logger.warning(f"Could not add supervisor to project: {e.message}")
        except GitLabUser.DoesNotExist:
            logger.warning(f"Supervisor has no linked GitLab account")

    if hasattr(board, 'members'):
        for member in board.members.all():
            if creator_user and member.id == creator_user.id:
                continue
            try:
                member_gitlab = GitLabUser.objects.get(user=member)
                try:
                    gitlab_api_post(
                        f"/api/v4/projects/{result['id']}/members",
                        data={
                            'user_id': member_gitlab.gitlab_user_id,
                            'access_level': 30,
                        },
                        token=member_add_token,
                    )
                    logger.info(f"Auto-added member {member_gitlab.gitlab_username} as Developer")
                except GitLabAPIError as e:
                    logger.warning(f"Could not add member {member_gitlab.gitlab_username}: {e.message}")
            except GitLabUser.DoesNotExist:
                logger.warning(f"Project member {member.username} has no linked GitLab account")

    return {
        'id': gitlab_project.id,
        'gitlab_project_id': result['id'],
        'name': result['name'],
        'gitlab_project_path': result.get('path_with_namespace', ''),
        'web_url': _fix_gitlab_url(result['web_url']),
        'ssh_url': result.get('ssh_url_to_repo', ''),
        'http_url': _fix_gitlab_url(result.get('http_url_to_repo', '')),
        'default_branch': result.get('default_branch', 'main'),
    }


def ensure_admin_access(gitlab_project_id: int, owner_token: str = None) -> bool:
    """
    Ensure the admin user (GITLAB_TOKEN owner) has Maintainer access to the project.

    This is critical for projects created under user namespaces - without this,
    the admin token cannot access the project's members, commits, etc.

    Args:
        gitlab_project_id: The GitLab project ID
        owner_token: Token of the project owner (used to add admin as member)

    Returns:
        True if admin already has access or was successfully added
    """
    config = _get_gitlab_config()
    admin_token = config['token']

    try:
        admin_user = gitlab_api_get('/api/v4/user', token=admin_token)
        admin_user_id = admin_user.get('id')
    except GitLabAPIError as e:
        logger.warning(f"Unable to retrieve admin user info: {e.message}")
        admin_user_id = None

    if admin_user_id:
        try:
            members = gitlab_api_get(
                f"/api/v4/projects/{gitlab_project_id}/members",
                token=admin_token,
            )
            for member in members:
                if member.get('id') == admin_user_id:
                    logger.info(f"Admin user (ID: {admin_user_id}) already has access to project {gitlab_project_id}")
                    return True
        except GitLabAPIError as e:
            logger.warning(f"Cannot access project {gitlab_project_id} members with admin token: {e.message}")

    if admin_user_id and owner_token:
        try:
            gitlab_api_post(
                f"/api/v4/projects/{gitlab_project_id}/members",
                data={
                    'user_id': admin_user_id,
                    'access_level': 40,
                },
                token=owner_token,
            )
            logger.info(f"Added admin user (ID: {admin_user_id}) as Maintainer to project {gitlab_project_id}")
            return True
        except GitLabAPIError as e:
            logger.warning(f"Could not add admin to project {gitlab_project_id}: {e.message}")
    elif not owner_token:
        logger.warning(f"No owner_token provided - cannot add admin to project {gitlab_project_id}")

    return False


def add_project_member(board, gitlab_username: str, access_level: int = 30, user_token: str = None) -> dict:
    from .models import GitLabProject

    try:
        gitlab_project = GitLabProject.objects.get(board=board)
    except GitLabProject.DoesNotExist:
        raise ValueError("هذا المشروع غير مرتبط بمستودع GitLab")

    try:
        user_data = gitlab_api_get(
            f'/api/v4/users',
            params={'username': gitlab_username},
            token=user_token,
        )
    except GitLabAPIError as e:
        raise ValueError(f"خطأ في البحث عن المستخدم: {e.message}")

    if not user_data:
        raise ValueError(f"المستخدم '{gitlab_username}' غير موجود في GitLab. "
                        "تأكد أن الطالب سجل حسابه في GitLab.")

    gitlab_user_id = user_data[0]['id']

    try:
        result = gitlab_api_post(
            f"/api/v4/projects/{gitlab_project.gitlab_project_id}/members",
            data={
                'user_id': gitlab_user_id,
                'access_level': access_level,
            },
            token=user_token,
        )
    except GitLabAPIError as e:
        if e.status_code == 409:
            raise ValueError(f"المستخدم '{gitlab_username}' عضو في المشروع بالفعل")
        raise ValueError(f"خطأ في إضافة العضو: {e.message}")

    logger.info(f"Added {gitlab_username} (ID: {gitlab_user_id}) to project {gitlab_project.project_name} "
                f"with access level {access_level}")

    return {
        'id': result.get('id'),
        'username': result.get('username'),
        'name': result.get('name'),
        'access_level': access_level,
        'access_level_name': _access_level_name(access_level),
    }


def remove_project_member(board, gitlab_user_id: int, user_token: str = None) -> bool:
    from .models import GitLabProject

    try:
        gitlab_project = GitLabProject.objects.get(board=board)
    except GitLabProject.DoesNotExist:
        raise ValueError("هذا المشروع غير مرتبط بمستودع GitLab")

    gitlab_api_delete(
        f"/api/v4/projects/{gitlab_project.gitlab_project_id}/members/{gitlab_user_id}",
        token=user_token,
    )

    logger.info(f"Removed GitLab user {gitlab_user_id} from project {gitlab_project.project_name}")
    return True


def get_project_members(board, user_token: str = None) -> List[dict]:
    from .models import GitLabProject

    try:
        gitlab_project = GitLabProject.objects.get(board=board)
    except GitLabProject.DoesNotExist:
        raise ValueError("هذا المشروع غير مرتبط بمستودع GitLab")

    members = gitlab_api_get(
        f"/api/v4/projects/{gitlab_project.gitlab_project_id}/members",
        token=user_token,
    )

    result = []
    for m in members:
        result.append({
            'id': m['id'],
            'username': m['username'],
            'name': m['name'],
            'access_level': m['access_level'],
            'access_level_name': _access_level_name(m['access_level']),
            'avatar_url': m.get('avatar_url', ''),
        })

    return result


def _access_level_name(level: int) -> str:
    levels = {
        10: 'ضيف (Guest)',
        20: 'مراقب (Reporter)',
        30: 'مطور (Developer)',
        40: 'مسؤول (Maintainer)',
        50: 'مالك (Owner)',
    }
    return levels.get(level, f'مستوى {level}')


# ==========================================
# WEBHOOK FUNCTIONS
# ==========================================

def register_webhook(board, webhook_url: str) -> dict:
    from .models import GitLabProject

    try:
        gitlab_project = GitLabProject.objects.get(board=board)
    except GitLabProject.DoesNotExist:
        raise ValueError("هذا المشروع غير مرتبط بمستودع GitLab")

    config = _get_gitlab_config()

    # Delete existing webhook if any
    try:
        existing_webhooks = gitlab_api_get(
            f"/api/v4/projects/{gitlab_project.gitlab_project_id}/hooks"
        )
        for hook in existing_webhooks:
            if hook.get('url') == webhook_url:
                gitlab_api_delete(
                    f"/api/v4/projects/{gitlab_project.gitlab_project_id}/hooks/{hook['id']}"
                )
                logger.info(f"Removed existing webhook {hook['id']} from project {gitlab_project.project_name}")
    except GitLabAPIError:
        pass

    data = {
        'url': webhook_url,
        'token': config['webhook_secret'],
        'push_events': True,
        'issues_events': False,
        'merge_requests_events': False,
        'wiki_page_events': False,
        'pipeline_events': False,
        'tag_push_events': False,
        'note_events': False,
        'job_events': False,
        'deployment_events': False,
        'releases_events': False,
        'enable_ssl_verification': False,
    }

    result = gitlab_api_post(
        f"/api/v4/projects/{gitlab_project.gitlab_project_id}/hooks",
        data=data,
    )

    gitlab_project.webhook_id = result['id']
    gitlab_project.save(update_fields=['webhook_id'])

    logger.info(f"Registered webhook (ID: {result['id']}) for project {gitlab_project.project_name}")

    return {
        'id': result['id'],
        'url': result['url'],
        'push_events': result.get('push_events', True),
        'project_id': gitlab_project.gitlab_project_id,
    }


# ==========================================
# COMMIT FUNCTIONS
# ==========================================

def process_push_webhook(payload: dict) -> dict:
    from .models import GitLabProject, GitLabCommit, GitLabCommitFile

    project_id = payload.get('project', {}).get('id')
    if not project_id:
        raise ValueError("Webhook payload missing project ID")

    try:
        gitlab_project = GitLabProject.objects.get(gitlab_project_id=project_id)
    except GitLabProject.DoesNotExist:
        logger.warning(f"Received webhook for unknown GitLab project ID: {project_id}")
        raise ValueError(f"مشروع GitLab غير مسجل في النظام: {project_id}")

    commits_data = payload.get('commits', [])
    new_commits = 0
    saved_commits = []

    for commit_data in commits_data:
        sha = commit_data.get('id')
        if not sha:
            continue

        if GitLabCommit.objects.filter(project=gitlab_project, sha=sha).exists():
            continue

        authored_date = None
        if commit_data.get('timestamp'):
            try:
                authored_date = datetime.fromisoformat(
                    commit_data['timestamp'].replace('Z', '+00:00')
                )
            except (ValueError, TypeError):
                authored_date = datetime.now()

        commit = GitLabCommit.objects.create(
            project=gitlab_project,
            sha=sha,
            message=commit_data.get('message', '').strip(),
            author_name=commit_data.get('author', {}).get('name', ''),
            author_email=commit_data.get('author', {}).get('email', ''),
            author_username=commit_data.get('author', {}).get('username', ''),
            ref=payload.get('ref', ''),
            authored_date=authored_date,
            committed_date=authored_date,
            web_url=commit_data.get('url', ''),
            added_lines=0,
            removed_lines=0,
            total_lines=0,
        )

        for file_path in commit_data.get('added', []):
            GitLabCommitFile.objects.create(
                commit=commit,
                file_path=file_path,
                status='added',
            )

        for file_path in commit_data.get('removed', []):
            GitLabCommitFile.objects.create(
                commit=commit,
                file_path=file_path,
                status='removed',
            )

        for file_path in commit_data.get('modified', []):
            GitLabCommitFile.objects.create(
                commit=commit,
                file_path=file_path,
                status='modified',
            )

        new_commits += 1
        saved_commits.append({
            'sha': sha[:8],
            'message': commit.message.split('\n')[0],
            'author': commit.author_name,
        })

    ref = payload.get('ref', '')
    pusher = payload.get('user_username', '')
    logger.info(
        f"Webhook processed: project={gitlab_project.project_name}, "
        f"ref={ref}, pusher={pusher}, "
        f"commits_received={len(commits_data)}, new_commits={new_commits}"
    )

    return {
        'total_commits': len(commits_data),
        'new_commits': new_commits,
        'gitlab_project_id': project_id,
        'board_id': gitlab_project.board.id,
        'project_name': gitlab_project.project_name,
        'ref': ref,
        'pusher': pusher,
        'commits': saved_commits,
    }


def sync_commits_from_gitlab(board, user_token: str = None) -> dict:
    """
    Sync commits from GitLab to the local database.
    
    If user_token is provided, it will be used for the API call.
    If user_token is None, the admin token from settings will be used.
    
    Args:
        board: ProjectBoard instance
        user_token: Optional personal GitLab access token
    
    Returns:
        dict with sync statistics
    
    Raises:
        ValueError: If the board has no linked GitLab project
        GitLabAPIError: If the GitLab API call fails
    """
    from .models import GitLabProject, GitLabCommit, GitLabCommitFile

    try:
        gitlab_project = GitLabProject.objects.get(board=board)
    except GitLabProject.DoesNotExist:
        raise ValueError("هذا المشروع غير مرتبط بمستودع GitLab")

    # Use the provided token (user's personal or None for admin fallback)
    # When user_token is None, _gitlab_headers() will use the admin token from settings
    token = user_token
    
    logger.info(f"Syncing commits for project {gitlab_project.project_name} "
                f"(GitLab ID: {gitlab_project.gitlab_project_id}) "
                f"using {'user token' if token else 'admin token'}")
    
    try:
        commits_data = _gitlab_api_get_all_pages(
            f"/api/v4/projects/{gitlab_project.gitlab_project_id}/repository/commits",
            params={'per_page': 100, 'with_stats': True},
            token=token,
        )
    except GitLabAPIError as e:
        if token and e.status_code == 401:
            logger.warning(
                "User GitLab token expired during commit sync. "
                "Retrying with admin token."
            )
            commits_data = _gitlab_api_get_all_pages(
                f"/api/v4/projects/{gitlab_project.gitlab_project_id}/repository/commits",
                params={'per_page': 100, 'with_stats': True},
                token=None,
            )
        else:
            raise

    new_commits = 0

    for commit_data in commits_data:
        sha = commit_data.get('id')
        if not sha:
            continue

        if GitLabCommit.objects.filter(project=gitlab_project, sha=sha).exists():
            continue

        authored_date = None
        if commit_data.get('authored_date'):
            try:
                authored_date = datetime.fromisoformat(
                    commit_data['authored_date'].replace('Z', '+00:00')
                )
            except (ValueError, TypeError):
                authored_date = datetime.now()

        committed_date = None
        if commit_data.get('committed_date'):
            try:
                committed_date = datetime.fromisoformat(
                    commit_data['committed_date'].replace('Z', '+00:00')
                )
            except (ValueError, TypeError):
                committed_date = datetime.now()

        stats = commit_data.get('stats', {})

        commit = GitLabCommit.objects.create(
            project=gitlab_project,
            sha=sha,
            message=commit_data.get('message', '').strip(),
            author_name=commit_data.get('author_name', ''),
            author_email=commit_data.get('author_email', ''),
            author_username=commit_data.get('author_username', ''),
            ref='',
            authored_date=authored_date,
            committed_date=committed_date or authored_date,
            web_url=commit_data.get('web_url', ''),
            added_lines=stats.get('additions', 0),
            removed_lines=stats.get('deletions', 0),
            total_lines=stats.get('total', 0),
        )

        new_commits += 1

    logger.info(f"Synced commits for {gitlab_project.project_name}: "
                f"fetched={len(commits_data)}, new={new_commits}")

    return {
        'total_fetched': len(commits_data),
        'new_commits': new_commits,
        'project_name': gitlab_project.project_name,
    }


# ==========================================
# STATISTICS FUNCTIONS
# ==========================================

def get_commit_stats(board) -> dict:
    from .models import GitLabProject, GitLabCommit
    from django.db.models import Count, Max, Sum, Q
    from django.db.models.functions import TruncDate

    try:
        gitlab_project = GitLabProject.objects.get(board=board)
    except GitLabProject.DoesNotExist:
        return {
            'has_gitlab_project': False,
            'total_commits': 0,
        }

    commits = GitLabCommit.objects.filter(project=gitlab_project)

    total_commits = commits.count()
    total_authors = commits.values('author_name').distinct().count()

    line_stats = commits.aggregate(
        total_added=Sum('added_lines'),
        total_removed=Sum('removed_lines'),
    )

    last_commit = commits.order_by('-committed_date').first()

    author_stats = commits.values('author_name').annotate(
        commit_count=Count('id'),
        added=Sum('added_lines', default=0),
        removed=Sum('removed_lines', default=0),
    ).order_by('-commit_count')

    recent = commits.order_by('-committed_date')[:10]
    recent_list = [{
        'sha': c.sha[:8],
        'message': c.message.split('\n')[0] if c.message else '',
        'author': c.author_name,
        'date': c.committed_date.isoformat() if c.committed_date else None,
    } for c in recent]

    return {
        'has_gitlab_project': True,
        'project_name': gitlab_project.project_name,
        'web_url': gitlab_project.web_url,
        'total_commits': total_commits,
        'total_authors': total_authors,
        'total_lines_added': line_stats['total_added'] or 0,
        'total_lines_removed': line_stats['total_removed'] or 0,
        'last_commit': {
            'sha': last_commit.sha[:8] if last_commit else None,
            'message': last_commit.message.split('\n')[0] if last_commit and last_commit.message else None,
            'author': last_commit.author_name if last_commit else None,
            'date': last_commit.committed_date.isoformat() if last_commit and last_commit.committed_date else None,
        },
        'authors': list(author_stats),
        'recent_commits': recent_list,
    }


def verify_webhook_signature(payload_body: bytes, token_header: str) -> bool:
    config = _get_gitlab_config()
    expected_token = config['webhook_secret']

    if not token_header or not expected_token:   # ← أضفنا فحص expected_token
        return False

    return hmac.compare_digest(token_header, expected_token)


def check_gitlab_health() -> dict:
    try:
        result = gitlab_api_get('/api/v4/version')
        return {
            'status': True,
            'version': result.get('version', 'unknown'),
            'message': 'GitLab متصل ويعمل بشكل طبيعي',
        }
    except GitLabAPIError as e:
        return {
            'status': False,
            'version': None,
            'message': f'مشكلة في الاتصال: {e.message}',
        }
    except Exception as e:
        return {
            'status': False,
            'version': None,
            'message': 'خطأ غير متوقع أثناء الاتصال بـ GitLab',
        }
def check_gitlab_project_exists(board) -> dict:
    """
    M-15 Fix: التحقق إن مستودع GitLab لسه موجود.
    إذا انحذف يدوياً → نحذف سجل GitLabProject من قاعدة البيانات.
    """
    from .models import GitLabProject
    try:
        gitlab_project = GitLabProject.objects.get(board=board)
    except GitLabProject.DoesNotExist:
        return {'exists': False, 'reason': 'لا يوجد مستودع مرتبط'}

    try:
        result = gitlab_api_get(f"/api/v4/projects/{gitlab_project.gitlab_project_id}")
        return {
            'exists': True,
            'project_name': result.get('name', ''),
            'web_url': result.get('web_url', ''),
        }
    except GitLabAPIError as e:
        if e.status_code == 404:
            # المستودع انحذف من GitLab → نحذف السجل من DB
            gitlab_project.delete()
            return {
                'exists': False,
                'reason': 'المستودع انحذف من GitLab - تم تنظيف قاعدة البيانات',
            }
        return {
            'exists': False,
            'reason': f'خطأ في الاتصال: {e.message}',
        }
    except Exception as e:
        return {
            'exists': False,
            'reason': 'خطأ غير متوقع أثناء الاتصال بـ GitLab',
        }


def cleanup_deleted_gitlab_projects():
    """
    M-15 Fix: فحص كل مستودعات GitLab وتنظيف يلي انحذف يدوياً.
    ممكن تشغيلها من Celery task أو يدوياً.
    """
    from .models import GitLabProject
    cleaned = []
    for gp in GitLabProject.objects.all():
        try:
            gitlab_api_get(f"/api/v4/projects/{gp.gitlab_project_id}")
        except GitLabAPIError as e:
            if e.status_code == 404:
                gp.delete()
                cleaned.append({
                    'board_id': gp.board_id,
                    'gitlab_project_id': gp.gitlab_project_id,
                    'action': 'deleted_from_db',
                })
        except Exception:
            pass  # خطأ شبكة - نتخطاه
    return {
        'total_checked': GitLabProject.objects.count(),
        'cleaned': len(cleaned),
        'details': cleaned,
    }
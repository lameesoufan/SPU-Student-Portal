"""
Fix existing GitLab projects: ensure the creator and all board members
have access to the repository.

This fixes the bug where projects were created with the admin token,
making the admin the Owner, but the student who created it had NO access.

Run: python fix_repo_access.py
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from gitlab_integration.models import GitLabProject, GitLabUser
from gitlab_integration import services
from project_management.models import ProjectBoard


def get_existing_member_ids(gitlab_project_id):
    """Get set of GitLab user IDs that are already members of the project."""
    try:
        members = services.gitlab_api_get(f"/api/v4/projects/{gitlab_project_id}/members")
        return {m['id'] for m in members}
    except services.GitLabAPIError:
        return set()


def add_member_to_project(gitlab_project_id, gitlab_user_id, gitlab_username, access_level, existing_ids):
    """Add a member to the project if they're not already a member."""
    if gitlab_user_id in existing_ids:
        print(f"    ✓ {gitlab_username} (ID: {gitlab_user_id}) already has access")
        return True

    try:
        services.gitlab_api_post(
            f"/api/v4/projects/{gitlab_project_id}/members",
            data={
                'user_id': gitlab_user_id,
                'access_level': access_level,
            },
        )
        level_name = {10: 'Guest', 20: 'Reporter', 30: 'Developer', 40: 'Maintainer', 50: 'Owner'}
        print(f"    ✓ Added {gitlab_username} (ID: {gitlab_user_id}) as {level_name.get(access_level, access_level)}")
        existing_ids.add(gitlab_user_id)
        return True
    except services.GitLabAPIError as e:
        print(f"    ✗ Failed to add {gitlab_username}: {e.message}")
        return False


def fix_project(gitlab_project):
    """Fix access for a single GitLab project."""
    board = gitlab_project.board
    gitlab_project_id = gitlab_project.gitlab_project_id
    project_path = gitlab_project.gitlab_project_path

    print(f"\n{'='*60}")
    print(f"Fixing: {project_path} (GitLab ID: {gitlab_project_id})")
    print(f"  Board: {board.title} (ID: {board.id})")

    # Get current members
    existing_ids = get_existing_member_ids(gitlab_project_id)
    print(f"  Current members on GitLab: {len(existing_ids)}")

    added = 0

    # 1. Add the board creator (the student who made the project)
    creator = getattr(board, 'created_by', None) or getattr(board, 'creator', None)
    if creator:
        try:
            creator_gitlab = GitLabUser.objects.get(user=creator)
            if add_member_to_project(gitlab_project_id, creator_gitlab.gitlab_user_id,
                                     creator_gitlab.gitlab_username, 40, existing_ids):
                added += 1
        except GitLabUser.DoesNotExist:
            print(f"    ⚠ Board creator '{creator.username}' has no linked GitLab account")
    else:
        print(f"    ⚠ No creator found for this board")

    # 2. Add the supervisor
    supervisor = getattr(board, 'supervisor', None)
    if supervisor:
        try:
            sup_gitlab = GitLabUser.objects.get(user=supervisor)
            if add_member_to_project(gitlab_project_id, sup_gitlab.gitlab_user_id,
                                     sup_gitlab.gitlab_username, 40, existing_ids):
                added += 1
        except GitLabUser.DoesNotExist:
            print(f"    ⚠ Supervisor '{supervisor.username}' has no linked GitLab account")

    # 3. Add all board members (students)
    if hasattr(board, 'members'):
        for member in board.members.all():
            try:
                member_gitlab = GitLabUser.objects.get(user=member)
                if add_member_to_project(gitlab_project_id, member_gitlab.gitlab_user_id,
                                         member_gitlab.gitlab_username, 30, existing_ids):
                    added += 1
            except GitLabUser.DoesNotExist:
                print(f"    ⚠ Member '{member.username}' has no linked GitLab account")

    print(f"  → Added {added} new member(s)")
    return added


def main():
    print("=" * 60)
    print("FIX GITLAB REPO ACCESS")
    print("This will add missing members to all GitLab projects.")
    print("=" * 60)

    projects = GitLabProject.objects.all()
    total = projects.count()
    print(f"Found {total} GitLab project(s)\n")

    total_added = 0

    for gp in projects:
        try:
            added = fix_project(gp)
            total_added += added
        except Exception as e:
            print(f"  ✗ ERROR fixing {gp.gitlab_project_path}: {e}")

    print(f"\n{'='*60}")
    print(f"DONE! Added {total_added} member(s) across {total} project(s)")
    print("=" * 60)


if __name__ == '__main__':
    main()

"""
Check which GitLab projects still exist on GitLab and which are orphaned.
Run: python check_repos.py
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from gitlab_integration.models import GitLabProject
from gitlab_integration import services

print("=" * 60)
print("Checking GitLab repositories...")
print("=" * 60)

existing = []
orphaned = []
errors = []

for p in GitLabProject.objects.all():
    print(f"\nChecking: {p.gitlab_project_path} (GitLab ID: {p.gitlab_project_id})...")
    try:
        result = services.gitlab_api_get(f"/api/v4/projects/{p.gitlab_project_id}")
        print(f"  ✓ EXISTS - {result.get('path_with_namespace', '?')}")
        existing.append(p)
    except services.GitLabAPIError as e:
        if e.status_code == 404:
            print(f"  ✗ NOT FOUND (404) - This repo was deleted from GitLab")
            orphaned.append(p)
        else:
            print(f"  ✗ ERROR ({e.status_code}): {e.message}")
            errors.append((p, e))
    except Exception as e:
        print(f"  ✗ CONNECTION ERROR: {e}")
        errors.append((p, e))

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"Total projects in DB: {GitLabProject.objects.count()}")
print(f"Existing on GitLab:    {len(existing)}")
print(f"Orphaned (deleted):    {len(orphaned)}")
print(f"Errors:                {len(errors)}")

if orphaned:
    print("\n--- ORPHANED PROJECTS (exist in DB but NOT on GitLab) ---")
    for p in orphaned:
        print(f"  ID={p.id} | board_id={p.board_id} | path={p.gitlab_project_path} | web_url={p.web_url}")

    print("\nTo clean up orphaned projects, run:")
    print("  python manage.py shell")
    print("  from gitlab_integration.models import GitLabProject")
    print("  GitLabProject.objects.filter(id__in=[%s]).delete()" % ', '.join(str(p.id) for p in orphaned))

    # Also offer auto-cleanup
    answer = input("\nDo you want to auto-delete orphaned records from DB? (yes/no): ").strip().lower()
    if answer == 'yes':
        for p in orphaned:
            print(f"  Deleting DB record for orphaned project: {p.gitlab_project_path}")
            p.delete()
        print("Cleanup complete!")
    else:
        print("Skipped cleanup. You can do it manually later.")

if errors:
    print("\n--- ERRORS ---")
    for p, e in errors:
        print(f"  {p.gitlab_project_path}: {e}")
    print("\nIf all projects show CONNECTION ERROR, make sure GitLab is running at the configured URL.")
    print(f"Current GITLAB_URL: {os.getenv('GITLAB_URL', 'http://localhost:8080')}")
s
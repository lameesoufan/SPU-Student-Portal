from django.test import TestCase

from .services import _sanitize_project_path, _generate_project_slug


class GitLabProjectPathTests(TestCase):
    def test_sanitize_project_path_removes_invalid_characters(self):
        raw_name = "My Project! @2026 #GitLab"
        sanitized = _sanitize_project_path(raw_name)
        self.assertEqual(sanitized, "my-project-2026-gitlab")

    def test_sanitize_project_path_collapses_repeated_symbols(self):
        raw_name = "Project..Name---With__Repeats"
        sanitized = _sanitize_project_path(raw_name)
        self.assertEqual(sanitized, "project.name-with__repeats")


class GitLabProjectSlugTests(TestCase):
    def test_generate_project_slug_uses_board_id_for_empty_title(self):
        slug = _generate_project_slug("", 42)
        self.assertEqual(slug, "project-42")

    def test_generate_project_slug_truncates_long_names(self):
        long_title = "A" * 250
        slug = _generate_project_slug(long_title, 100)
        self.assertTrue(len(slug) <= 200)
        self.assertTrue(slug.startswith("a"))
"""
Unit tests for chaos_tester.spa_detection.

Verifies that is_spa_catchall correctly identifies SPA shell responses
and does NOT flag real server content as a catch-all.

Run: python -m pytest tests/test_spa_detection.py -v
"""

from __future__ import annotations

import pytest

from chaos_tester.spa_detection import is_spa_catchall, _extension, _last_segment


# -------------------------------------------------------------------
# Realistic SPA shell bodies used in multiple tests.
# -------------------------------------------------------------------

REACT_SHELL = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"/><title>My App</title></head>
<body><div id="root"></div><script src="/static/js/main.abc123.js"></script></body>
</html>"""

VUE_SHELL = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Vue App</title></head>
<body><div id="app"></div><script type="module" src="/src/main.ts"></script></body>
</html>"""

ANGULAR_SHELL = """<!doctype html>
<html lang="en">
<head><title>Angular App</title></head>
<body><app-root></app-root><script src="runtime.js"></script></body>
</html>"""

NEXTJS_SHELL = """<!DOCTYPE html>
<html><head><title>Next App</title></head>
<body><div id="__next"></div><script src="/_next/static/chunks/main.js"></script></body>
</html>"""

NUXT_SHELL = """<!DOCTYPE html>
<html><head><title>Nuxt App</title></head>
<body><div id="__nuxt"></div><script src="/_nuxt/entry.js"></script></body>
</html>"""

SVELTEKIT_SHELL = """<!DOCTYPE html>
<html><head><title>Svelte App</title></head>
<body><div id="svelte"></div><script type="module" src="/_app/immutable/entry.js"></script></body>
</html>"""


# -------------------------------------------------------------------
# Non-SPA responses -- should NOT be treated as catch-all.
# -------------------------------------------------------------------

REAL_ENV_FILE = """APP_KEY=base64:xyzzy
DB_HOST=127.0.0.1
DB_PASSWORD=secret
"""

REAL_GIT_CONFIG = """[core]
    repositoryformatversion = 0
    filemode = true
"""

REAL_ADMIN_PAGE = """<!doctype html>
<html><head><title>Admin Panel</title></head>
<body><h1>Admin Dashboard</h1><table>...</table></body>
</html>"""

REAL_SWAGGER_JSON = '{"openapi":"3.0.0","info":{"title":"API","version":"1.0"}}'

REAL_PHPINFO = """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN">
<html><head><title>phpinfo()</title></head>
<body><h1>PHP Version 8.1.2</h1><table>...</table></body>
</html>"""


# ===================================================================
# Tests: Sensitive file paths with SPA shell -> catch-all
# ===================================================================

class TestSpaDetectionSensitiveFiles:
    """SPA shells served for file paths that should never return HTML."""

    @pytest.mark.parametrize("shell", [REACT_SHELL, VUE_SHELL, ANGULAR_SHELL,
                                       NEXTJS_SHELL, NUXT_SHELL, SVELTEKIT_SHELL])
    @pytest.mark.parametrize("path", [
        "/.env", "/.env.local", "/.env.production",
        "/.git/config", "/.git/HEAD",
        "/backup.sql", "/dump.sql",
        "/phpinfo.php", "/info.php",
        "/wp-config.php", "/config.php", "/settings.py",
        "/.htaccess", "/.htpasswd",
        "/.DS_Store",
        "/elmah.axd", "/trace.axd",
    ])
    def test_spa_shell_for_sensitive_file(self, shell, path):
        assert is_spa_catchall(shell, path) is True

    @pytest.mark.parametrize("path", [
        "/swagger.json", "/openapi.json",
    ])
    def test_spa_shell_for_json_endpoint(self, path):
        assert is_spa_catchall(REACT_SHELL, path) is True


# ===================================================================
# Tests: Protected route paths with SPA shell -> catch-all
# ===================================================================

class TestSpaDetectionRoutes:
    """SPA shells served for route-style paths like /admin, /dashboard."""

    @pytest.mark.parametrize("shell", [REACT_SHELL, VUE_SHELL, ANGULAR_SHELL])
    @pytest.mark.parametrize("path", [
        "/admin", "/dashboard", "/settings", "/account",
        "/api/users", "/api/admin", "/internal", "/manage",
    ])
    def test_spa_shell_for_protected_route(self, shell, path):
        assert is_spa_catchall(shell, path) is True

    def test_spa_shell_for_graphql(self):
        """GraphQL endpoint returning SPA shell is a catch-all."""
        assert is_spa_catchall(REACT_SHELL, "/graphql") is True


# ===================================================================
# Tests: Real content -- should NOT be flagged as catch-all
# ===================================================================

class TestNotCatchAll:
    """Real file content or server-rendered pages should not be suppressed."""

    def test_real_env_file(self):
        assert is_spa_catchall(REAL_ENV_FILE, "/.env") is False

    def test_real_git_config(self):
        assert is_spa_catchall(REAL_GIT_CONFIG, "/.git/config") is False

    def test_real_admin_page(self):
        """A server-rendered admin page with path in <title> is real."""
        # The title contains "Admin" which matches the /admin path segment
        page = '<!doctype html><html><head><title>admin panel</title></head><body><h1>Admin</h1></body></html>'
        assert is_spa_catchall(page, "/admin") is False

    def test_real_swagger_json(self):
        assert is_spa_catchall(REAL_SWAGGER_JSON, "/swagger.json") is False

    def test_real_phpinfo(self):
        assert is_spa_catchall(REAL_PHPINFO, "/phpinfo.php") is False

    def test_empty_response(self):
        assert is_spa_catchall("", "/.env") is False

    def test_none_response(self):
        assert is_spa_catchall(None, "/.env") is False

    def test_plain_html_no_spa_marker(self):
        """Regular HTML without SPA markers is not a catch-all."""
        html = "<html><body><h1>Hello</h1></body></html>"
        assert is_spa_catchall(html, "/admin") is False

    def test_page_with_title_matching_path(self):
        """If a page's <title> matches the path segment, it's probably real content."""
        html = '''<!doctype html><html><head><title>dashboard</title></head>
        <body><div id="root"></div><script src="/app.js"></script></body></html>'''
        assert is_spa_catchall(html, "/dashboard") is False


# ===================================================================
# Tests: Helper functions
# ===================================================================

class TestHelpers:

    @pytest.mark.parametrize("path,expected", [
        ("/.env", "env"),
        ("/.git/config", ""),  # "config" is a filename, not an extension
        ("/backup.sql", "sql"),
        ("/admin", ""),
        ("/api/users", ""),
        ("/swagger.json?v=2", "json"),
        ("/path#frag", ""),
        ("/file.tar.gz", "gz"),
    ])
    def test_extension(self, path, expected):
        assert _extension(path) == expected

    @pytest.mark.parametrize("path,expected", [
        ("/admin", "admin"),
        ("/api/users", "users"),
        ("/.env", ".env"),
        ("/", ""),
        ("", ""),
        ("/a/b/c/", "c"),
    ])
    def test_last_segment(self, path, expected):
        assert _last_segment(path) == expected

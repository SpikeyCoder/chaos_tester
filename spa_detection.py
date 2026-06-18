"""
SPA catch-all detection utility.

Single-page applications (React, Vue, Angular, Next.js, Nuxt, SvelteKit, etc.)
typically configure their server to return the same ``index.html`` shell for
*every* URL that does not match a real static asset.  This means probes like
``/.env`` or ``/admin`` receive HTTP 200 with an HTML body that contains the
SPA bootstrap markup -- **not** the actual file or route content.

The helpers in this module detect that pattern so the security and auth
scanners can suppress false positives without weakening detection for
traditional server-rendered sites.
"""

from __future__ import annotations

# Common root-element markers emitted by popular SPA frameworks.
SPA_MARKERS = [
    '<div id="root"',        # React (Create React App, Vite)
    "<div id='root'",
    '<div id="app"',         # Vue CLI / Vite
    "<div id='app'",
    "<app-root",             # Angular
    '<div id="__next"',      # Next.js
    "<div id='__next'",
    '<div id="__nuxt"',      # Nuxt
    "<div id='__nuxt'",
    '<div id="svelte"',      # SvelteKit
    "<div id='svelte'",
    '<div id="gatsby-focus-wrapper"',  # Gatsby
]

# File extensions that should never legitimately be served as an HTML page.
# If a path with one of these extensions returns an SPA shell, it is
# definitely a catch-all response.
_NON_HTML_EXTENSIONS = frozenset({
    "env", "sql", "py", "php", "config", "htaccess", "htpasswd",
    "db", "axd", "bak", "log", "yml", "yaml", "toml", "ini",
    "json", "xml",
})


def is_spa_catchall(response_text: str, requested_path: str) -> bool:
    """Return ``True`` if *response_text* looks like a generic SPA shell
    served for *requested_path* via catch-all routing.

    The function is intentionally conservative: it only returns ``True``
    when there is strong evidence that the response is the SPA's
    ``index.html`` rather than real content specific to the path.
    """
    if not response_text:
        return False

    text_lower = response_text.lower()

    # 1. Must contain at least one known SPA root-element marker.
    has_spa_marker = any(marker.lower() in text_lower for marker in SPA_MARKERS)
    if not has_spa_marker:
        return False

    # 2. If the requested path has a non-HTML file extension that would
    #    never legitimately return an HTML document, this is a catch-all.
    ext = _extension(requested_path)
    if ext in _NON_HTML_EXTENSIONS:
        return True

    # 3. For extension-less paths (e.g. /admin, /dashboard), look for
    #    additional signals that this is just the SPA shell:
    #    - It must contain a <script tag (the SPA JS bundle).
    #    - The last path segment should NOT appear in the <title> tag
    #      (server-rendered pages almost always set a page-specific title).
    if "<script" in text_lower:
        path_segment = _last_segment(requested_path)
        if path_segment and f"<title>{path_segment}" not in text_lower:
            return True

    return False


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _extension(path: str) -> str:
    """Extract the lowercase file extension from a URL path, or ''."""
    # Strip query string / fragment first
    clean = path.split("?", 1)[0].split("#", 1)[0]
    # Only look at the last path segment (filename)
    filename = clean.rsplit("/", 1)[-1] if "/" in clean else clean
    if "." in filename:
        return filename.rsplit(".", 1)[-1].lower()
    return ""


def _last_segment(path: str) -> str:
    """Return the last non-empty segment of a URL path, lowercased."""
    clean = path.split("?", 1)[0].split("#", 1)[0]
    parts = [p for p in clean.strip("/").split("/") if p]
    return parts[-1].lower() if parts else ""

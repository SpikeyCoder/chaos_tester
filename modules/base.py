"""
Base module — shared helpers for all test modules.
"""

import time
import logging
import requests
from urllib.parse import urljoin, urlparse
from typing import List
from ..models import TestResult, TestStatus, Severity
from ..config import ChaosConfig

logger = logging.getLogger("chaos_tester")


class BaseModule:
    """Common infrastructure for every test module."""

    MODULE_NAME = "base"

    def __init__(self, config: ChaosConfig, session: requests.Session = None):
        self.config = config
        self.session = session or self._build_session()
        self.results: List[TestResult] = []

    def _build_session(self) -> requests.Session:
        s = requests.Session()
        s.headers.update({"User-Agent": self.config.user_agent})
        if self.config.auth_header:
            s.headers["Authorization"] = self.config.auth_header
        s.verify = True
        return s

    def _url(self, path: str) -> str:
        if path.startswith(("http://", "https://")):
            return path
        return urljoin(self.config.base_url.rstrip("/") + "/", path.lstrip("/"))

    def _is_same_domain(self, url: str) -> bool:
        base = urlparse(self.config.base_url).netloc
        target = urlparse(url).netloc
        return target == base or target == ""

    def _get(self, url: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.config.request_timeout)
        kwargs.setdefault("allow_redirects", True)
        return self.session.get(url, **kwargs)

    def _post(self, url: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.config.request_timeout)
        return self.session.post(url, **kwargs)

    def _timed(self, func, *args, **kwargs):
        """Run func, return (result, duration_ms)."""
        t0 = time.perf_counter()
        result = func(*args, **kwargs)
        dt = (time.perf_counter() - t0) * 1000
        return result, dt

    def add_result(self, **kwargs):
        kwargs.setdefault("module", self.MODULE_NAME)
        self.results.append(TestResult(**kwargs))

    def run(self, discovered_pages: list = None) -> List[TestResult]:
        """Override in subclass."""
        raise NotImplementedError

    def _short_path(self, url: str) -> str:
        """Return just the path component of a URL for display purposes."""
        return urlparse(url).path or "/"

    def _safe_request(self, method, url, **kwargs):
        """Make a request and return (response, error_string)."""
        try:
            resp, dt = self._timed(getattr(self.session, method), url, **kwargs)
            return resp, None, dt
        except requests.ConnectionError as e:
            return None, f"Connection error: {e}", 0
        except requests.Timeout:
            return None, "Request timed out", 0
        except requests.RequestException as e:
            return None, f"Request error: {e}", 0

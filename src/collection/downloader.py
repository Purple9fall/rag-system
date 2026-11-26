from __future__ import annotations
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from .config_loader import load_collection

log = logging.getLogger(__name__)

class SourceAccessDenied(Exception):
    """A source denied automated access; do not keep requesting the host."""


class Downloader:
    def __init__(self, config: dict | None = None) -> None:
        self.config = config or load_collection()
        self.settings = self.config["settings"]
        self.constraints = self.config["constraints"]
        self._last_request: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}
        self._blocked_hosts: set[str] = set()
        self.user_agent = self.settings["run"]["user_agent"]
        contact = os.getenv(self.settings["run"]["contact_email_env"], "").strip()
        if contact:
            self.user_agent = f"rag-system-collection/0.1 (mailto:{contact})"

    def _allowed(self, url: str, source: dict | None = None) -> bool:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https":
            return False
        if source and source.get("api_access_policy") == "documented_public_api":
            endpoint = urllib.parse.urlparse(source["endpoint"])
            if (parsed.scheme, parsed.netloc, parsed.path) == (
                endpoint.scheme, endpoint.netloc, endpoint.path
            ):
                return True
        if not self.constraints["download"]["respect_robots_txt"]:
            return True
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._robots:
            robots = urllib.robotparser.RobotFileParser(origin + "/robots.txt")
            try:
                with urllib.request.urlopen(
                    urllib.request.Request(robots.url, headers={"User-Agent": self.user_agent}),
                    timeout=self.settings["run"]["request_timeout_seconds"],
                ) as response:
                    robots.parse(response.read(1_000_000).decode("utf-8", "replace").splitlines())
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    robots.parse(["User-agent: *", "Allow: /"])
                else:
                    log.warning("Cannot read robots.txt for %s: HTTP %s", origin, exc.code)
                    return False
            except (OSError, urllib.error.URLError):
                log.warning("Cannot read robots.txt for %s; skipping", origin)
                return False
            self._robots[origin] = robots
        return self._robots[origin].can_fetch(self.user_agent, url)

    def _fetch(self, url: str, source: dict) -> tuple[bytes, str, str]:
        host = urllib.parse.urlparse(url).netloc
        if host in self._blocked_hosts:
            raise SourceAccessDenied(f"Host {host} already returned HTTP 403")
        if not self._allowed(url, source):
            raise ValueError(f"Disallowed by robots.txt or URL policy: {url}")
        wait = source["min_interval_seconds"] - (time.monotonic() - self._last_request.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        limit = self.constraints["download"]["max_file_size_mb"] * 1024 * 1024
        headers = {"User-Agent": self.user_agent, "Accept": "application/json, application/atom+xml, text/html, application/pdf"}
        if source.get("api_key_env"):
            api_key = os.getenv(source["api_key_env"], "").strip()
            if not api_key:
                raise ValueError(f"Missing {source['api_key_env']} for {source['id']}")
            headers["Authorization"] = f"Bearer {api_key}"
        request = urllib.request.Request(url, headers=headers)
        retries = self.settings["run"]["retries"]
        for attempt in range(retries + 1):
            try:
                self._last_request[host] = time.monotonic()
                with urllib.request.urlopen(request, timeout=self.settings["run"]["request_timeout_seconds"]) as response:
                    final_url = response.geturl()
                    if not self._allowed(final_url, source):
                        raise ValueError(f"Redirect target disallowed: {final_url}")
                    data = response.read(limit + 1)
                    if len(data) > limit:
                        raise ValueError(f"File exceeds {limit} bytes")
                    return data, response.headers.get_content_type(), final_url
            except urllib.error.HTTPError as exc:
                if exc.code == 403:
                    self._blocked_hosts.add(host)
                    raise SourceAccessDenied(f"Host {host} returned HTTP 403") from exc
                if exc.code not in {429, 500, 502, 503, 504} or attempt == retries:
                    raise
            except (TimeoutError, urllib.error.URLError):
                if attempt == retries:
                    raise
            time.sleep(self.settings["run"]["retry_backoff_seconds"] * (2 ** attempt))
        raise RuntimeError("Unreachable retry state")

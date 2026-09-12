import re
from urllib.parse import urlparse, urlunparse


def normalize_linkedin_url(url: str) -> str:
    if not url:
        return ""

    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url

    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        host = re.sub(r"^(www\.|ar\.|cl\.|mx\.|es\.|uk\.)", "", host)
        if "linkedin.com" not in host:
            return ""

        path = parsed.path.rstrip("/")
        if "/in/" not in path.lower():
            return ""

        return urlunparse(("https", "www.linkedin.com", path, "", "", ""))
    except Exception:
        return ""

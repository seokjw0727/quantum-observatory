"""Load and validate editor-reviewed, repository-owned site content."""

import json
import re
from pathlib import Path
from urllib.parse import urlparse

from .model import ROOT, day


ARTICLE_TYPES = {"analysis", "guide"}
ARTICLE_STATUSES = {"published"}
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PUBLISHER_ID = re.compile(r"^pub-\d{16}$")
ADS_TXT = re.compile(r"^google\.com, (pub-\d{16}), DIRECT, f08c47fec0942fa0$")


def load_site_config():
    config = json.loads((ROOT / "config/site.json").read_text(encoding="utf-8"))
    origin = urlparse(config.get("canonical_origin", ""))
    if origin.scheme != "https" or not origin.netloc or origin.path not in {"", "/"}:
        raise ValueError("canonical_origin must be an HTTPS origin without a path")
    if config.get("ads", {}).get("mode") not in {"off", "verification", "live"}:
        raise ValueError("ads.mode must be off, verification, or live")
    ads = config["ads"]
    if ads["mode"] != "off":
        publisher_id = ads.get("publisher_id", "")
        record = ADS_TXT.fullmatch(ads.get("ads_txt", ""))
        if not PUBLISHER_ID.fullmatch(publisher_id) or not record or record.group(1) != publisher_id:
            raise ValueError("Advertising verification requires a matching publisher_id and ads.txt record")
    for key in ["publisher_name", "repository_url", "contact_url"]:
        if not config.get(key):
            raise ValueError(f"Missing site setting: {key}")
    return config


def load_articles():
    path = ROOT / "content/editorial.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    articles = payload.get("articles", [])
    if not articles:
        raise ValueError("No editorial articles are configured")
    seen = set()
    for article in articles:
        required = ["slug", "type", "title", "description", "summary", "author", "published_at", "updated_at", "status", "sections", "sources"]
        missing = [key for key in required if not article.get(key)]
        if missing:
            raise ValueError(f"Article is missing fields: {', '.join(missing)}")
        slug = article["slug"]
        if slug in seen or not SLUG.fullmatch(slug):
            raise ValueError(f"Invalid or duplicate article slug: {slug}")
        seen.add(slug)
        if article["type"] not in ARTICLE_TYPES or article["status"] not in ARTICLE_STATUSES:
            raise ValueError(f"Invalid article type or status: {slug}")
        if day(article["updated_at"]) < day(article["published_at"]):
            raise ValueError(f"Article update date precedes publication date: {slug}")
        if len(article["sections"]) < 3 or len(article["sources"]) < 2:
            raise ValueError(f"Article needs substantive sections and multiple sources: {slug}")
        words = sum(len(paragraph.split()) for section in article["sections"] for paragraph in section.get("paragraphs", []))
        words += sum(len(item.split()) for section in article["sections"] for item in section.get("bullets", []))
        # This guards against empty summaries; editorial completeness is assessed by
        # the question, evidence, and review criteria rather than a public word quota.
        if words < 350:
            raise ValueError(f"Article is too thin for its stated question: {slug} ({words} words)")
        for source in article["sources"]:
            parsed = urlparse(source.get("url", ""))
            if parsed.scheme != "https" or not parsed.netloc:
                raise ValueError(f"Article source must use HTTPS: {slug}")
    return articles

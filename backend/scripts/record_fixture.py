"""Record a trimmed, scrubbed test fixture from a real public board.

    python scripts/record_fixture.py greenhouse gitlab tests/fixtures/greenhouse.json
    python scripts/record_fixture.py jobvite q6NaVfwI/tylertech tests/fixtures/jobvite.xml

Goes through the same polite HttpClient as the app (honest User-Agent,
robots.txt, throttle). Keeps the first --keep postings and drops descriptions,
free text and anything that names a person (recruiter, hiring manager, email),
so fixtures hold listing metadata only. Review the file before committing it.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from job_radar.http import HttpClient

DROP_KEYS = re.compile(
    r"description|content|additional|lists|opening|closing|body|summary|requirements|"
    r"benefits|email|recruit|hiring|manager|contact|creator|owner|user|employee|salary|"
    r"apply.?(form|questions)|questions|compliance|metadata|departments|custom",
    re.IGNORECASE,
)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")

URLS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
    "lever": "https://api.lever.co/v0/postings/{slug}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{slug}",
    "workable": "https://apply.workable.com/api/v1/widget/accounts/{slug}",
    "teamtailor": "https://{slug}/jobs.json",
    "breezy": "https://{slug}.breezy.hr/json",
    "recruitee": "https://{slug}.recruitee.com/api/offers/",
    "jobvite": "https://app.jobvite.com/CompanyJobs/Xml.aspx?c={slug}",
    "jsonld": "{slug}",
}


def scrub(node: Any) -> Any:
    if isinstance(node, dict):
        return {k: scrub(v) for k, v in node.items() if not DROP_KEYS.search(k)}
    if isinstance(node, list):
        return [scrub(v) for v in node]
    if isinstance(node, str):
        return EMAIL_RE.sub("redacted@example.com", node)
    return node


def trim_json(payload: Any, keep: int) -> Any:
    if isinstance(payload, list):
        return payload[:keep]
    for key in ("jobs", "items", "offers"):
        if isinstance(payload, dict) and isinstance(payload.get(key), list):
            return {**payload, key: payload[key][:keep]}
    return payload


def trim_xml(text: str, keep: int) -> str:
    root = ET.fromstring(text)  # noqa: S314 - a public feed of job metadata
    for i, job in enumerate(list(root.iter("job"))):
        if i >= keep:
            root.remove(job)
            continue
        for child in list(job):
            if DROP_KEYS.search(child.tag) or child.tag in ("detail-url", "apply-url"):
                job.remove(child)
    return ET.tostring(root, encoding="unicode")


def trim_html(html: str) -> str:
    """Keep only the ld+json JobPosting blocks, without descriptions."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    blocks = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(script.get_text() or "")
        except ValueError:
            continue
        if "JobPosting" in json.dumps(data):
            blocks.append(json.dumps(scrub(data), indent=2))
    scripts = "\n".join(f'<script type="application/ld+json">{b}</script>' for b in blocks)
    return f"<!doctype html>\n<html><head>{scripts}</head><body></body></html>\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("platform", choices=sorted(URLS))
    parser.add_argument("slug")
    parser.add_argument("output", type=Path)
    parser.add_argument("--keep", type=int, default=4)
    args = parser.parse_args()

    client = HttpClient()
    company = args.slug.split("/")[0] if args.platform == "jobvite" else args.slug
    response = client.get(URLS[args.platform].format(slug=company), timeout=120)
    if args.platform == "jobvite":
        out = trim_xml(response.text, args.keep)
    elif args.platform == "jsonld":
        out = trim_html(response.text)
    else:
        out = json.dumps(scrub(trim_json(response.json(), args.keep)), indent=2) + "\n"
    args.output.write_text(out, encoding="utf-8")
    print(f"wrote {args.output} ({len(out)} bytes); review it before committing")


if __name__ == "__main__":
    main()

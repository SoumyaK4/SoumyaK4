#!/usr/bin/env python3
"""Track rendered sitemap pages and notify IndexNow after a deployment."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


ENDPOINT = "https://api.indexnow.org/indexnow"


def page_digest(path):
    head, separator, body = path.read_text(encoding="utf-8").partition("</head>")
    # Chirpy uses build time as the SEO date on undated collection pages.
    # Ignore those date fields while retaining page content and other metadata.
    head = re.sub(r'<meta\s+property="article:(?:published|modified)_time"[^>]*>', "", head)
    head = re.sub(r'"date(?:Published|Modified)"\s*:\s*"[^"]*"', "", head)
    return hashlib.sha256((head + separator + body).encode("utf-8")).hexdigest()


def snapshot(site_dir, site_url):
    root = site_dir.resolve()
    origin = urlsplit(site_url)
    pages = {}
    sitemap = ET.parse(root / "sitemap.xml")
    for loc in sitemap.findall("{*}url/{*}loc"):
        url = loc.text.strip()
        parsed = urlsplit(url)
        if (parsed.scheme, parsed.netloc) != (origin.scheme, origin.netloc):
            raise ValueError(f"Sitemap URL does not match site: {url}")
        path = root / unquote(parsed.path).lstrip("/")
        if not path.resolve().is_relative_to(root):
            raise ValueError(f"Sitemap URL escapes site directory: {url}")
        if parsed.path.endswith("/"):
            path = path / "index.html"
        # Notify about pages, rather than feeds and other sitemap resources.
        if path.suffix.lower() not in (".html", ".htm"):
            continue
        pages[url] = page_digest(path)
    if not pages:
        raise ValueError("No HTML pages found in sitemap")
    return {"site_url": site_url.rstrip("/"), "pages": pages}


def changed_urls(current, previous):
    if current["site_url"] != previous["site_url"]:
        raise ValueError("Previous snapshot belongs to a different site")
    before, after = previous["pages"], current["pages"]
    return sorted(url for url in before.keys() | after.keys()
                  if before.get(url) != after.get(url))


def download_previous(site_url, output):
    """Keep a deployed fallback because GitHub may evict inactive caches."""
    try:
        with urlopen(f"{site_url.rstrip('/')}/assets/indexnow-state.json", timeout=30) as response:
            state = json.load(response)
    except HTTPError as error:
        if error.code == 404:
            return
        raise
    if state["site_url"] != site_url.rstrip("/") or not isinstance(state["pages"], dict):
        raise ValueError("Invalid deployed IndexNow snapshot")
    output.write_text(json.dumps(state, sort_keys=True) + "\n", encoding="utf-8")


def submit(current, previous_path, key_file):
    if not previous_path.exists():
        print("Established IndexNow baseline; future page changes will be submitted.")
        return
    urls = changed_urls(current, json.loads(previous_path.read_text()))
    if not urls:
        print("No page changes to submit to IndexNow.")
        return

    key = key_file.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"[A-Za-z0-9-]{8,128}", key) or key_file.name != f"{key}.txt":
        raise ValueError("Invalid IndexNow key file or filename")
    site_url = current["site_url"]
    key_url = f"{site_url}/{key_file.name}"
    # Pages can take a short time to propagate after deploy-pages completes.
    for attempt in range(6):
        try:
            with urlopen(key_url, timeout=20) as response:
                if response.read().decode("utf-8").strip() == key:
                    break
        except (HTTPError, URLError, TimeoutError):
            pass
        if attempt == 5:
            raise RuntimeError(f"Deployed IndexNow key is not available: {key_url}")
        time.sleep(10)

    for start in range(0, len(urls), 10000):
        batch = urls[start:start + 10000]
        payload = {
            "host": urlsplit(site_url).netloc,
            "key": key,
            "keyLocation": key_url,
            "urlList": batch,
        }
        request = Request(ENDPOINT, data=json.dumps(payload).encode("utf-8"),
                          headers={"Content-Type": "application/json; charset=utf-8"})
        with urlopen(request, timeout=30) as response:
            if response.status not in (200, 202):
                raise RuntimeError(f"Unexpected IndexNow response: {response.status}")
            print(f"IndexNow received {len(batch)} URLs (HTTP {response.status}).")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("snapshot")
    build.add_argument("--site-dir", type=Path, required=True)
    build.add_argument("--site-url", required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--previous-output", type=Path)
    notify = commands.add_parser("submit")
    notify.add_argument("--current", type=Path, required=True)
    notify.add_argument("--previous", type=Path, required=True)
    notify.add_argument("--fallback", type=Path)
    notify.add_argument("--key-file", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "snapshot":
        state = snapshot(args.site_dir, args.site_url)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(state, sort_keys=True) + "\n", encoding="utf-8")
        # Published state survives cache eviction and covers infrequent updates.
        public_state = args.site_dir / "assets" / "indexnow-state.json"
        public_state.parent.mkdir(parents=True, exist_ok=True)
        public_state.write_text(args.output.read_text(), encoding="utf-8")
        if args.previous_output:
            download_previous(args.site_url, args.previous_output)
        print(f"Recorded {len(state['pages'])} sitemap pages.")
    else:
        previous = args.previous
        if not previous.exists() and args.fallback:
            previous = args.fallback
        submit(json.loads(args.current.read_text()), previous, args.key_file)


if __name__ == "__main__":
    main()

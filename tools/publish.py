"""Publish the next due carousel to Instagram.

Looks for posts/*/post.json with status "approved" and publish_at in the past,
publishes the oldest one, and writes the result back into its post.json.
One post per run, so a backlog never floods the feed.

Env:  IG_ACCESS_TOKEN   Instagram Login token (instagram_business_content_publish)
      GITHUB_REPOSITORY, GITHUB_SHA   set by Actions; used to build jsDelivr image URLs
Flags: --dry-run  print what would be published, call nothing
       --check    confirm the token works and show the publishing quota
"""
import datetime as dt
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://graph.instagram.com/v26.0"
ROOT = pathlib.Path(__file__).resolve().parent.parent
MAX_ATTEMPTS = 3
DRY = "--dry-run" in sys.argv


def call(method, path, **params):
    params["access_token"] = os.environ["IG_ACCESS_TOKEN"]
    data = urllib.parse.urlencode(params).encode()
    url = f"{API}/{path}"
    req = urllib.request.Request(url, data=data) if method == "POST" else urllib.request.Request(f"{url}?{data.decode()}")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {path}: {e.read().decode(errors='replace')}") from None


def wait_ready(container):
    # Meta's guidance: poll once a minute, at most five minutes. Images are usually ready at once.
    for _ in range(6):
        status = call("GET", container, fields="status_code")["status_code"]
        if status == "FINISHED":
            return
        if status in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"container {container} is {status}")
        time.sleep(60)
    raise RuntimeError(f"container {container} not ready after 5 minutes")


def due_posts():
    now = dt.datetime.now(dt.timezone.utc)
    found = []
    for meta_file in sorted(ROOT.glob("posts/*/post.json")):
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        if meta.get("status") != "approved" or not meta.get("publish_at"):
            continue
        when = dt.datetime.fromisoformat(meta["publish_at"])
        if when.tzinfo is None:
            sys.exit(f"{meta_file}: publish_at needs a timezone offset, e.g. 2026-10-27T18:00:00+05:00")
        if when <= now:
            found.append((when, meta_file, meta))
    return sorted(found, key=lambda x: x[0])


def image_urls(post):
    repo = os.environ.get("GITHUB_REPOSITORY", "Hasnan42/havixa-instagram")
    sha = os.environ.get("GITHUB_SHA") or subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    # Pinning to the commit keeps jsDelivr from serving a stale cached copy.
    rel = post.relative_to(ROOT).as_posix()
    slides = sorted(post.glob("slide-*.jpg"), key=lambda p: int(p.stem.split("-")[1]))
    return [f"https://cdn.jsdelivr.net/gh/{repo}@{sha}/{rel}/{s.name}" for s in slides]


def publish(post, caption):
    urls = image_urls(post)
    if not 2 <= len(urls) <= 20:
        raise RuntimeError(f"need 2 to 20 slides, found {len(urls)} (did you run tools/render.py?)")
    if DRY:
        print("\n".join(urls))
        print(f"--- caption ({len(caption)} chars) ---\n{caption}")
        return None
    me = call("GET", "me", fields="user_id,username")
    ig = me["user_id"]
    children = [call("POST", f"{ig}/media", image_url=u, is_carousel_item="true")["id"] for u in urls]
    for c in children:
        wait_ready(c)
    carousel = call("POST", f"{ig}/media", media_type="CAROUSEL", children=",".join(children), caption=caption)["id"]
    wait_ready(carousel)
    media_id = call("POST", f"{ig}/media_publish", creation_id=carousel)["id"]
    permalink = call("GET", media_id, fields="permalink").get("permalink")
    print(f"published @{me['username']}: {permalink}")
    return {"media_id": media_id, "permalink": permalink}


def main():
    if "--check" in sys.argv:
        me = call("GET", "me", fields="user_id,username,account_type")
        quota = call("GET", f"{me['user_id']}/content_publishing_limit", fields="quota_usage,config")
        print(f"token ok: @{me['username']} ({me.get('account_type')}), publishing quota {quota}")
        return
    posts = due_posts()
    if not posts:
        print("nothing due")
        return
    _, meta_file, meta = posts[0]
    post = meta_file.parent
    caption = (post / "caption.txt").read_text(encoding="utf-8").strip()
    if len(caption) > 2200 or caption.count("#") > 30:
        sys.exit(f"{post.name}: caption over Instagram limits (2200 chars, 30 hashtags)")
    print(f"publishing {post.name}")
    try:
        result = publish(post, caption)
    except Exception as e:
        meta["attempts"] = meta.get("attempts", 0) + 1
        meta["last_error"] = str(e)[:500]
        if meta["attempts"] >= MAX_ATTEMPTS:
            meta["status"] = "failed"
        meta_file.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        sys.exit(f"failed: {e}")
    if result:
        meta.update(status="published", published_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), **result)
        meta.pop("last_error", None)
        meta_file.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


main()

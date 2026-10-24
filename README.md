# Havixa Instagram

Carousels for [@havixa](https://tryhavixa.com), drawn in code and published on a schedule.

- `posts/<date-slug>/` holds one post: `slides.html`, rendered `slide-N.jpg`, `caption.txt`, `post.json`
- `templates/carousel.css` + `brand/` hold the shared look
- `tools/render.py <post>` renders slides to 1080×1350 JPEGs
- `tools/publish.py` publishes the oldest approved post whose `publish_at` has passed

`post.json`:

```json
{ "status": "approved", "publish_at": "2026-10-27T18:00:00+05:00" }
```

Status moves `draft` → `approved` → `published` (or `failed` after 3 attempts).
The `Publish due posts` workflow runs hourly; `Refresh Instagram token` runs weekly.

Secrets: `IG_ACCESS_TOKEN`, `SECRETS_PAT` (fine-grained, this repo, Secrets read/write).

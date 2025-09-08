# Web Crawler Plan

## Components Needed

1. **Seed + URL Frontier**

    - Queue structure that stores `(url, depth, discovered_from)`.
    - Switchable **BFS/DFS**: queue (BFS) vs stack (DFS).
    - Per-domain queues to throttle politely.

2. **Normalizer & Deduper**

    - Canonicalize URLs (strip fragments, resolve relatives, sort query params if safe).
    - Maintain a **seen set** (e.g., Redis set or Bloom filter) to avoid repeats.
    - Optional content dedupe by **hash** (MD5/SHA-256) of body.

3. **Robots.txt + Allowlist**

    - Parse `robots.txt` before fetching.
    - Maintain an explicit allowlist of domains; skip disallowed pages.
    - Optional sitemap discovery for breadth.

4. **Fetcher**

    - Use `httpx` or `aiohttp` (async), robust timeouts, redirect limits, retry with backoff.
    - Respect **ETag / If-Modified-Since** headers for revisits.
    - Politeness: per-host rate limit, jitter, concurrency caps.

5. **Renderer (only when needed)**

    - **Playwright** headless for JS-rendered pages (fallback if HTML fails).
    - Avoid Selenium for large crawling (too heavy).

6. **Parser & Link Extractor**

    - `lxml` or `BeautifulSoup` for HTML parsing.
    - Extract and normalize links (`href`, `src`).
    - Detect MIME types for non-HTML.

7. **Depth & Budget Control**

    - Enforce `max_depth_dfs = 3`.
    - For BFS, define a **global budget** (max pages per domain).
    - Apply page caps, byte limits, and wall-clock crawl timeout.

8. **Downloader for Assets**

    - Allowlist MIME types (HTML, PDF, images).
    - Stream downloads, validate size, compute hash.
    - Store with manifest (SQLite/Postgres): URL → file path, hash, type, timestamp.

9. **Error Handling & Observability**

    - Structured logs (JSON), metrics (Prometheus).
    - Track fetch counts, status codes, robots blocks, queue size.
    - Crawl report at the end.

10. **Config & Extensibility**

-   YAML/TOML config for seeds, domain rules, MIME allowlist, budgets, concurrency, user-agent string, storage paths.

---

## BFS vs DFS

-   **DFS**: Use stack, enforce depth ≤ 3.
-   **BFS**: Use queue, allow wide exploration but set crawl budget.
-   Scrapy: `DEPTH_LIMIT = 3` and `DEPTH_PRIORITY = 1` approximates BFS.

---

## Tech Choices

| Need                             | Best fit                          |
| -------------------------------- | --------------------------------- |
| Scalable crawling, depth control | **Scrapy**                        |
| JS rendering                     | **scrapy-playwright**             |
| Simple async                     | `aiohttp` + `lxml`                |
| UI automation/forms              | Playwright (Selenium if required) |
| File/media downloads             | Scrapy pipelines                  |

---

## Compliance

-   Identify crawler with **User-Agent** string.
-   Obey `robots.txt` and site terms.
-   Use polite throttling and conditional requests.
-   Do not attempt to bypass detection/security systems.

---

## Example Scrapy Settings

```python
ROBOTSTXT_OBEY = True
DEPTH_LIMIT = 3
DEPTH_PRIORITY = 1

USER_AGENT = "RohanCrawler/1.0 (+contact@example.com)"
CONCURRENT_REQUESTS = 16
CONCURRENT_REQUESTS_PER_DOMAIN = 8
DOWNLOAD_DELAY = 0.3
AUTOTHROTTLE_ENABLED = True
```

---

## Summary

-   Use **Scrapy** with optional Playwright for heavy JS sites.
-   Enforce DFS depth ≤ 3, BFS with page budget.
-   Download HTML, images, PDFs with hash-based dedupe and manifest storage.
-   Respect robots.txt, throttle politely, and identify crawler clearly.

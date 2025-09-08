ROBOTSTXT_OBEY = True
DEPTH_LIMIT = 3  # applies to DFS-like behavior unless you push BFS
DEPTH_PRIORITY = 1  # prioritize shallow requests first (BFS-ish)
SCHEDULER_DISK_QUEUE = "scrapy.s queues.PickleFifoDiskQueue"
SCHEDULER_MEMORY_QUEUE = "scrapy.s queues.FifoMemoryQueue"

USER_AGENT = "RohanCrawler/1.0 (+contact@example.com)"
CONCURRENT_REQUESTS = 16
CONCURRENT_REQUESTS_PER_DOMAIN = 8
DOWNLOAD_DELAY = 0.3  # plus jitter in middleware if desired
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 0.5
AUTOTHROTTLE_MAX_DELAY = 5.0

# Enable media pipelines or your custom pipeline
ITEM_PIPELINES = {
    "crawler.pipelines.FileDownloadPipeline": 300,
}

# If JS rendering is needed:
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
DOWNLOADER_MIDDLEWARES = {
    "scrapy_playwright.middleware.ScrapyPlaywrightDownloaderMiddleware": 543,
}
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 20000

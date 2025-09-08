# Scrapy settings for web crawler project

# Basic settings
ROBOTSTXT_OBEY = True
DEPTH_LIMIT = 3  # applies to DFS-like behavior unless you push BFS
DEPTH_PRIORITY = 1  # prioritize shallow requests first (BFS-ish)
SCHEDULER_DISK_QUEUE = "scrapy.squeues.PickleFifoDiskQueue"
SCHEDULER_MEMORY_QUEUE = "scrapy.squeues.FifoMemoryQueue"

# User agent
USER_AGENT = "RohanCrawler/1.0 (+contact@example.com)"

# Concurrency settings
CONCURRENT_REQUESTS = 16
CONCURRENT_REQUESTS_PER_DOMAIN = 8

# Download delays
DOWNLOAD_DELAY = 0.3  # plus jitter in middleware if desired
RANDOMIZE_DOWNLOAD_DELAY = 0.5  # random delay between 0.5 * DOWNLOAD_DELAY and 1.5 * DOWNLOAD_DELAY

# Auto throttling
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 0.5
AUTOTHROTTLE_MAX_DELAY = 5.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0
AUTOTHROTTLE_DEBUG = False

# Enable and configure pipelines
ITEM_PIPELINES = {
    "pipelines.ValidationPipeline": 100,
    "pipelines.ContentHashPipeline": 200,
    "pipelines.FileDownloadPipeline": 300,
}

# File download settings
FILES_STORE = "./downloads"
IMAGES_STORE = "./downloads"
FILES_EXPIRES = 90
IMAGES_EXPIRES = 90

# Media pipeline settings
MEDIA_ALLOW_REDIRECTS = True

# If JS rendering is needed (Playwright)
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
DOWNLOADER_MIDDLEWARES = {
    "scrapy_playwright.middleware.ScrapyPlaywrightDownloaderMiddleware": 543,
}
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 20000

# Logging
LOG_LEVEL = 'INFO'
LOG_FILE = './crawler.log'

# Memory usage
MEMDEBUG_ENABLED = True
MEMUSAGE_ENABLED = True
MEMUSAGE_LIMIT_MB = 2048
MEMUSAGE_WARNING_MB = 1024

# Request settings
DOWNLOAD_TIMEOUT = 30
DOWNLOAD_MAXSIZE = 1073741824  # 1GB
DOWNLOAD_WARNSIZE = 33554432   # 32MB

# Retry settings
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# Cache settings (optional)
HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 3600  # 1 hour
HTTPCACHE_DIR = 'httpcache'
HTTPCACHE_IGNORE_HTTP_CODES = [503, 504, 505, 500, 403, 404, 408, 429]

# Telnet console
TELNETCONSOLE_ENABLED = True
TELNETCONSOLE_PORT = [6023, 6073]

# Stats collection
STATS_CLASS = 'scrapy.statscollectors.MemoryStatsCollector'

import scrapy
import re
import yaml
import logging
import asyncio
from urllib.parse import urljoin, urldefrag, urlparse
from scrapy.exceptions import DropItem

class CrawlItem(scrapy.Item):
    url = scrapy.Field()
    referrer = scrapy.Field()
    content_type = scrapy.Field()
    body = scrapy.Field()  # optional; or store to disk in pipeline
    file_urls = scrapy.Field()  # for media pipeline
    image_urls = scrapy.Field()
    title = scrapy.Field()
    depth = scrapy.Field()
    domain = scrapy.Field()
    content_hash = scrapy.Field()  # Add content hash field

    def __repr__(self):
        """Redact large/binary fields like body from log output."""
        safe = {}
        for k, v in self.items():
            if k == 'body' and v is not None:
                try:
                    size = len(v)
                except Exception:
                    size = '?'
                safe[k] = f"<bytes: {size} bytes>"
            else:
                safe[k] = v
        return f"CrawlItem({safe})"

class SiteSpider(scrapy.Spider):
    name = "site"
    
    def __init__(self, allowed_domains=None, start_urls=None, exclude_patterns=None, 
                 download_file_types=None, page_download_types=None, max_pages_per_domain=None, 
                 max_file_size_mb=None, max_retries=None, use_playwright=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Load configuration
        self.load_config()
        
        # Override with provided parameters
        merged_allowed = set(self.config.get('allowed_domains', []) or [])
        if allowed_domains:
            merged_allowed.update(allowed_domains)
        self.allowed_domains = sorted(merged_allowed)
        self.start_urls = start_urls or [self.config.get('base_url', 'https://example.com')]
        self.exclude_patterns = exclude_patterns or self.config.get('exclude_patterns', [])
        self.download_file_types = download_file_types or self.config.get('download_file_types', [])
        self.page_download_types = page_download_types or self.config.get('page_download_types', ['html'])
        self.max_pages_per_domain = max_pages_per_domain or self.config.get('max_pages_per_domain', 100)
        self.max_file_size_mb = max_file_size_mb or self.config.get('max_file_size_mb', 50)
        self.max_retries = max_retries or self.config.get('max_retries', 3)
        self.use_playwright = use_playwright
        
        # Timeout settings
        self.timeout_settings = self.config.get('timeout_settings', {})
        self.page_load_timeout = self.timeout_settings.get('page_load_timeout', 60)
        self.network_idle_timeout = self.timeout_settings.get('network_idle_timeout', 20)
        self.javascript_timeout = self.timeout_settings.get('javascript_timeout', 30)
        self.request_timeout = self.timeout_settings.get('request_timeout', 120)
        
        # Track pages per domain
        self.pages_per_domain = {}
        
        # Track visited URLs to avoid infinite loops
        self.visited_urls = set()
        
        # Track crawling progress
        self.crawled_count = 0
        self.failed_count = 0
        
        # Track retry attempts per URL
        self.retry_attempts = {}
        
        self.logger.info(f"Spider initialized with {len(self.start_urls)} start URLs")
        self.logger.info(f"Allowed domains: {self.allowed_domains}")
        self.logger.info(f"Exclude patterns: {len(self.exclude_patterns)} patterns")
        self.logger.info(f"Page download types: {self.page_download_types}")
        self.logger.info(f"Max retries: {self.max_retries}")
        self.logger.info(f"Playwright mode: {self.use_playwright}")
        self.logger.info(f"Timeout settings: {self.timeout_settings}")
    
    def load_config(self):
        """Load configuration from YAML file"""
        try:
            with open('config.yml', 'r') as f:
                config = yaml.safe_load(f)
                self.config = config.get('crawler', {})
        except FileNotFoundError:
            self.logger.warning("config.yml not found, using default configuration")
            self.config = {}
    
    def should_exclude_url(self, url):
        """Check if URL should be excluded based on patterns"""
        for pattern in self.exclude_patterns:
            if re.search(pattern, url):
                return True
        return False
    
    def is_allowed_domain(self, url):
        """Check if URL belongs to allowed domains (merge-config aware)."""
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        for allowed in self.allowed_domains:
            a = allowed.lower()
            if domain == a or domain.endswith('.' + a):
                return True
            if a.startswith('www.') and domain == a[4:]:
                return True
        return False
    
    def check_domain_limit(self, url):
        """Check if domain has reached page limit"""
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        
        if domain in self.pages_per_domain:
            if self.pages_per_domain[domain] >= self.max_pages_per_domain:
                return False
        
        return True
    
    def increment_domain_count(self, url):
        """Increment page count for domain"""
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        self.pages_per_domain[domain] = self.pages_per_domain.get(domain, 0) + 1
    
    def should_download_page_type(self, content_type, url):
        """Check if page type should be downloaded based on configuration"""
        if not self.page_download_types:
            return True  # Download all if no specific types configured
        
        # Check content type
        ct = content_type.lower()
        
        # Check file extension
        parsed_url = urlparse(url)
        path = parsed_url.path.lower()
        
        for page_type in self.page_download_types:
            page_type = page_type.lower()
            
            # Check content type matches
            if page_type == 'html' and 'text/html' in ct:
                return True
            elif page_type == 'pdf' and ('application/pdf' in ct or path.endswith('.pdf')):
                return True
            elif page_type == 'doc' and ('application/msword' in ct or path.endswith('.doc')):
                return True
            elif page_type == 'docx' and ('application/vnd.openxmlformats-officedocument.wordprocessingml.document' in ct or path.endswith('.docx')):
                return True
            elif page_type == 'txt' and ('text/plain' in ct or path.endswith('.txt')):
                return True
            elif page_type == 'xml' and ('application/xml' in ct or 'text/xml' in ct or path.endswith('.xml')):
                return True
            elif page_type == 'json' and ('application/json' in ct or path.endswith('.json')):
                return True
            elif page_type == 'csv' and ('text/csv' in ct or path.endswith('.csv')):
                return True
        
        return False
    
    def start_requests(self):
        """Generate initial requests with optional Playwright support"""
        for url in self.start_urls:
            if self.use_playwright:
                yield scrapy.Request(
                    url=url,
                    callback=self.parse,
                    meta={
                        "playwright": True,
                        "playwright_page_methods": [
                            {"method": "wait_for_load_state", "args": ["networkidle"], "timeout": self.network_idle_timeout * 1000},
                            {"method": "wait_for_timeout", "args": [self.javascript_timeout * 1000]},
                        ],
                        "playwright_page_goto_kwargs": {
                            "timeout": self.page_load_timeout * 1000,
                            "wait_until": "networkidle"
                        },
                        "download_timeout": self.request_timeout
                    },
                    errback=self.handle_error
                )
            else:
                yield scrapy.Request(
                    url=url, 
                    callback=self.parse,
                    meta={"download_timeout": self.request_timeout},
                    errback=self.handle_error
                )
    
    def handle_error(self, failure):
        """Handle request errors with retry logic"""
        url = failure.request.url
        self.failed_count += 1
        
        # Track retry attempts
        if url not in self.retry_attempts:
            self.retry_attempts[url] = 0
        
        self.retry_attempts[url] += 1
        
        self.logger.error(f"Request failed: {url} - {failure.value} (Attempt {self.retry_attempts[url]})")
        
        # Retry logic for failed requests
        if self.retry_attempts[url] <= self.max_retries:
            retry_delay = self.timeout_settings.get('retry_timeout', 10)
            self.logger.info(f"Retrying {url} in {retry_delay} seconds... (Attempt {self.retry_attempts[url]}/{self.max_retries})")
            
            # Create new request with same parameters
            if self.use_playwright:
                return scrapy.Request(
                    url,
                    callback=failure.request.callback,
                    meta={
                        "playwright": True,
                        "playwright_page_methods": [
                            {"method": "wait_for_load_state", "args": ["networkidle"], "timeout": self.network_idle_timeout * 1000},
                            {"method": "wait_for_timeout", "args": [self.javascript_timeout * 1000]},
                        ],
                        "playwright_page_goto_kwargs": {
                            "timeout": self.page_load_timeout * 1000,
                            "wait_until": "networkidle"
                        },
                        "download_timeout": self.request_timeout
                    },
                    errback=self.handle_error,
                    dont_filter=True
                )
            else:
                return scrapy.Request(
                    url,
                    callback=failure.request.callback,
                    meta={"download_timeout": self.request_timeout},
                    errback=self.handle_error,
                    dont_filter=True
                )
        else:
            self.logger.error(f"Max retries ({self.max_retries}) exceeded for {url}")
    
    def parse(self, response):
        """Parse response and extract links and content"""
        # Check if URL was already visited
        if response.url in self.visited_urls:
            self.logger.debug(f"URL already visited: {response.url}")
            return
        
        # Add to visited URLs
        self.visited_urls.add(response.url)
        self.crawled_count += 1
        
        # Check domain limit
        if not self.check_domain_limit(response.url):
            self.logger.info(f"Domain limit reached for {urlparse(response.url).netloc}")
            return
        
        # Increment domain count
        self.increment_domain_count(response.url)
        
        # Get content type
        ct = response.headers.get("Content-Type", b"").decode().lower()
        
        # Check if we should download this page type
        if not self.should_download_page_type(ct, response.url):
            self.logger.info(f"Skipping page type not in download list: {response.url} (Content-Type: {ct})")
            return
        
        # Create item
        item = CrawlItem(
            url=response.url,
            referrer=response.request.headers.get("Referer"),
            content_type=ct,
            depth=response.meta.get('depth', 0),
            domain=urlparse(response.url).netloc
        )
        
        # Extract title if HTML
        if "text/html" in ct:
            title = response.css('title::text').get()
            if title:
                item['title'] = title.strip()
        
        # Store body for content hashing (optional) - but don't log it
        if "text/html" in ct:
            item['body'] = response.body
        
        # Process HTML content
        if "text/html" in ct:
            # Extract and follow links
            links_found = 0
            for href in response.css("a::attr(href)").getall():
                if href:
                    u = urljoin(response.url, href)
                    u, _ = urldefrag(u)  # Remove fragments
                    
                    # Check if URL should be excluded
                    if self.should_exclude_url(u):
                        continue
                    
                    # Check if domain is allowed (STRICT domain checking)
                    if not self.is_allowed_domain(u):
                        self.logger.debug(f"Skipping external domain: {u}")
                        continue
                    
                    # Check domain limit
                    if not self.check_domain_limit(u):
                        continue
                    
                    # Check if already visited
                    if u in self.visited_urls:
                        continue
                    
                    # Follow the link
                    if self.use_playwright:
                        yield response.follow(
                            u, 
                            callback=self.parse,
                            meta={
                                "playwright": True,
                                "playwright_page_methods": [
                                    {"method": "wait_for_load_state", "args": ["networkidle"], "timeout": self.network_idle_timeout * 1000},
                                    {"method": "wait_for_timeout", "args": [self.javascript_timeout * 1000]},
                                ],
                                "playwright_page_goto_kwargs": {
                                    "timeout": self.page_load_timeout * 1000,
                                    "wait_until": "networkidle"
                                },
                                "download_timeout": self.request_timeout
                            },
                            errback=self.handle_error
                        )
                    else:
                        yield response.follow(
                            u, 
                            callback=self.parse,
                            meta={"download_timeout": self.request_timeout},
                            errback=self.handle_error
                        )
                    
                    links_found += 1
            
            self.logger.info(f"Found {links_found} links on {response.url} (Total crawled: {self.crawled_count}, Failed: {self.failed_count})")
            
            # Extract image URLs
            image_urls = []
            for img_src in response.css("img::attr(src)").getall():
                if img_src:
                    img_url = urljoin(response.url, img_src)
                    if not self.should_exclude_url(img_url) and self.is_allowed_domain(img_url):
                        image_urls.append(img_url)
            
            item["image_urls"] = image_urls
            
            # Extract downloadable files
            file_urls = []
            
            # PDF files
            for link in response.css('a[href$=".pdf"]::attr(href)').getall():
                if link:
                    file_url = urljoin(response.url, link)
                    if not self.should_exclude_url(file_url) and self.is_allowed_domain(file_url):
                        file_urls.append(file_url)
            
            # Other file types based on content type
            for link in response.css('a::attr(href)').getall():
                if link:
                    file_url = urljoin(response.url, link)
                    if not self.should_exclude_url(file_url) and self.is_allowed_domain(file_url):
                        # Check for common file extensions
                        parsed_url = urlparse(file_url)
                        path = parsed_url.path.lower()
                        
                        # Check for common file extensions
                        if any(path.endswith(ext) for ext in ['.doc', '.docx', '.txt', '.rtf', '.odt']):
                            file_urls.append(file_url)
            
            item["file_urls"] = file_urls
        
        # For non-HTML content, handle as downloadable file
        else:
            # Check if content type is in allowed download types
            if ct in self.download_file_types:
                item["file_urls"] = [response.url]
            else:
                # Skip non-allowed content types
                self.logger.info(f"Skipping non-allowed content type: {ct} for {response.url}")
                return
        
        yield item
    
    def save_file(self, response):
        """Handle file downloads"""
        # Check file size
        content_length = response.headers.get('Content-Length')
        if content_length:
            size_mb = int(content_length) / (1024 * 1024)
            if size_mb > self.max_file_size_mb:
                self.logger.warning(f"File too large ({size_mb:.2f}MB): {response.url}")
                return
        
        # Create item for file download
        item = CrawlItem(
            url=response.url,
            content_type=response.headers.get("Content-Type", b"").decode().lower(),
            domain=urlparse(response.url).netloc
        )
        item["file_urls"] = [response.url]
        
        yield item
    
    def closed(self, reason):
        """Called when spider is closed"""
        self.logger.info(f"Spider closed: {reason}")
        self.logger.info(f"Pages crawled per domain: {self.pages_per_domain}")
        self.logger.info(f"Total unique URLs visited: {len(self.visited_urls)}")
        self.logger.info(f"Total pages crawled: {self.crawled_count}")
        self.logger.info(f"Total failed requests: {self.failed_count}")
        self.logger.info(f"Retry attempts: {sum(self.retry_attempts.values())}")

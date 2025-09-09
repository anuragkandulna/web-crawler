import scrapy
import re
import yaml
import logging
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

class SiteSpider(scrapy.Spider):
    name = "site"
    
    def __init__(self, allowed_domains=None, start_urls=None, exclude_patterns=None, 
                 download_file_types=None, max_pages_per_domain=None, max_file_size_mb=None, 
                 use_playwright=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Load configuration
        self.load_config()
        
        # Override with provided parameters
        self.allowed_domains = allowed_domains or self.config.get('allowed_domains', [])
        self.start_urls = start_urls or [self.config.get('base_url', 'https://example.com')]
        self.exclude_patterns = exclude_patterns or self.config.get('exclude_patterns', [])
        self.download_file_types = download_file_types or self.config.get('download_file_types', [])
        self.max_pages_per_domain = max_pages_per_domain or self.config.get('max_pages_per_domain', 100)
        self.max_file_size_mb = max_file_size_mb or self.config.get('max_file_size_mb', 50)
        self.use_playwright = use_playwright
        
        # Track pages per domain
        self.pages_per_domain = {}
        
        # Track visited URLs to avoid infinite loops
        self.visited_urls = set()
        
        self.logger.info(f"Spider initialized with {len(self.start_urls)} start URLs")
        self.logger.info(f"Allowed domains: {self.allowed_domains}")
        self.logger.info(f"Exclude patterns: {len(self.exclude_patterns)} patterns")
        self.logger.info(f"Playwright mode: {self.use_playwright}")
    
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
        """Check if URL belongs to allowed domains"""
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        
        for allowed_domain in self.allowed_domains:
            if domain == allowed_domain.lower() or domain.endswith('.' + allowed_domain.lower()):
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
    
    def start_requests(self):
        """Generate initial requests with optional Playwright support"""
        for url in self.start_urls:
            if self.use_playwright:
                yield scrapy.Request(
                    url=url,
                    callback=self.parse,
                    meta={
                        "playwright": True,
                        "playwright_include_page": True,
                        "playwright_page_methods": [
                            {"method": "wait_for_load_state", "args": ["networkidle"]},
                            {"method": "wait_for_timeout", "args": [5000]},  # Wait 5 seconds for JS
                            {"method": "evaluate", "args": ["() => document.readyState"]},  # Check if page is fully loaded
                        ]
                    }
                )
            else:
                yield scrapy.Request(url=url, callback=self.parse)
    
    def parse(self, response):
        """Parse response and extract links and content"""
        # Check if URL was already visited
        if response.url in self.visited_urls:
            self.logger.debug(f"URL already visited: {response.url}")
            return
        
        # Add to visited URLs
        self.visited_urls.add(response.url)
        
        # Check domain limit
        if not self.check_domain_limit(response.url):
            self.logger.info(f"Domain limit reached for {urlparse(response.url).netloc}")
            return
        
        # Increment domain count
        self.increment_domain_count(response.url)
        
        # Get content type
        ct = response.headers.get("Content-Type", b"").decode().lower()
        
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
        
        # Store body for content hashing (optional)
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
                    
                    # Check if domain is allowed
                    if not self.is_allowed_domain(u):
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
                                "playwright_include_page": True,
                                "playwright_page_methods": [
                                    {"method": "wait_for_load_state", "args": ["networkidle"]},
                                    {"method": "wait_for_timeout", "args": [3000]},  # Wait 3 seconds for JS
                                    {"method": "evaluate", "args": ["() => document.readyState"]},
                                ]
                            }
                        )
                    else:
                        yield response.follow(u, callback=self.parse)
                    
                    links_found += 1
            
            self.logger.info(f"Found {links_found} links on {response.url}")
            
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

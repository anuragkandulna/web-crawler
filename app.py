#!/usr/bin/env python3
"""
Web Crawler Application
Main entry point for running the web crawler
"""

import os
import sys
import yaml
import logging
import argparse
from urllib.parse import urlparse
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from crawler import SiteSpider

def setup_logging(config):
    """Setup logging configuration"""
    log_file = config.get('storage', {}).get('log_file', './crawler.log')
    log_level = logging.INFO
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return logging.getLogger(__name__)

def load_config(config_file='config.yml'):
    """Load configuration from YAML file"""
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        return config['crawler']
    except FileNotFoundError:
        print(f"Configuration file {config_file} not found!")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing configuration file: {e}")
        sys.exit(1)

def create_output_directories(config):
    """Create necessary output directories"""
    output_dir = config.get('storage', {}).get('output_dir', './downloads')
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")

def extract_domain_from_url(url):
    """Extract domain from URL"""
    parsed = urlparse(url)
    return parsed.netloc.lower()

def update_scrapy_settings(config, use_playwright=False):
    """Update Scrapy settings based on configuration"""
    settings = get_project_settings()
    
    # Update settings from config
    settings.set('USER_AGENT', config.get('user_agent', 'RohanCrawler/1.0'))
    settings.set('CONCURRENT_REQUESTS', config.get('concurrent_requests', 8))
    settings.set('CONCURRENT_REQUESTS_PER_DOMAIN', config.get('concurrent_requests_per_domain', 4))
    settings.set('DOWNLOAD_DELAY', config.get('delay_between_requests', 0.5))
    settings.set('DEPTH_LIMIT', config.get('max_depth', 3))
    
    # Timeout settings
    timeout_settings = config.get('timeout_settings', {})
    settings.set('DOWNLOAD_TIMEOUT', timeout_settings.get('request_timeout', 60))
    settings.set('DOWNLOAD_WARNSIZE', 33554432)  # 32MB
    settings.set('DOWNLOAD_MAXSIZE', 1073741824)  # 1GB
    
    # Retry settings
    settings.set('RETRY_TIMES', config.get('max_retries', 3))
    settings.set('RETRY_HTTP_CODES', [500, 502, 503, 504, 408, 429])
    
    # File download settings
    output_dir = config.get('storage', {}).get('output_dir', './downloads')
    settings.set('FILES_STORE', output_dir)
    settings.set('IMAGES_STORE', output_dir)
    
    # Playwright settings for SPA support
    if use_playwright:
        settings.set('DOWNLOAD_HANDLERS', {
            'http': 'scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler',
            'https': 'scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler',
        })
        settings.set('TWISTED_REACTOR', 'twisted.internet.asyncioreactor.AsyncioSelectorReactor')
        settings.set('PLAYWRIGHT_BROWSER_TYPE', 'chromium')
        settings.set('PLAYWRIGHT_LAUNCH_OPTIONS', {
            'headless': True,
            'args': ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
        })
        
        # Playwright timeout settings
        settings.set('PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT', timeout_settings.get('page_load_timeout', 30) * 1000)
        settings.set('PLAYWRIGHT_PAGE_METHODS_TIMEOUT', timeout_settings.get('javascript_timeout', 15) * 1000)
        
    # Downloader middleware settings for dynamic slowdown and user agent rotation
    downloader_middlewares = {
        'middlewares.DynamicSlowdownMiddleware': 543,
        'middlewares.RandomUserAgentMiddleware': 544,
    }
    
    settings.set('DOWNLOADER_MIDDLEWARES', downloader_middlewares)

    # Pipeline settings - Include PageDownloadPipeline
    settings.set('ITEM_PIPELINES', {
        'pipelines.ValidationPipeline': 100,
        'pipelines.ContentHashPipeline': 200,
        'pipelines.PageDownloadPipeline': 300,  # Download HTML pages
        'pipelines.FileDownloadPipeline': 400,  # Download other files
    })
    
    return settings

def run_crawler(config, custom_url=None, use_playwright=False):
    """Run the web crawler"""
    logger = setup_logging(config)
    logger.info("Starting web crawler...")
    
    # Create output directories
    create_output_directories(config)
    
    # Update Scrapy settings
    settings = update_scrapy_settings(config, use_playwright)
    
    # Determine allowed domains - STRICT domain checking
    allowed_domains = []
    start_urls = []
    
    if custom_url:
        start_urls = [custom_url]
        # Extract domain from custom URL and add to allowed domains
        custom_domain = extract_domain_from_url(custom_url)
        allowed_domains.append(custom_domain)
        # Also add www variant
        if not custom_domain.startswith('www.'):
            allowed_domains.append(f'www.{custom_domain}')
        else:
            allowed_domains.append(custom_domain[4:])  # Remove www.
    else:
        start_urls = [config.get('base_url')]
        if config.get('base_url'):
            base_domain = extract_domain_from_url(config.get('base_url'))
            allowed_domains.append(base_domain)
            # Also add www variant
            if not base_domain.startswith('www.'):
                allowed_domains.append(f'www.{base_domain}')
            else:
                allowed_domains.append(base_domain[4:])  # Remove www.
    
    # Prepare spider arguments
    spider_args = {
        'allowed_domains': allowed_domains,
        'start_urls': start_urls,
        'exclude_patterns': config.get('exclude_patterns', []),
        'download_file_types': config.get('download_file_types', []),
        'page_download_types': config.get('page_download_types', ['html']),
        'max_pages_per_domain': config.get('max_pages_per_domain', 100),
        'max_file_size_mb': config.get('max_file_size_mb', 50),
        'max_retries': config.get('max_retries', 3),
        'use_playwright': use_playwright
    }
    
    # Start crawler process
    process = CrawlerProcess(settings)
    process.crawl(SiteSpider, **spider_args)
    
    logger.info("Crawler process started...")
    process.start()

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Web Crawler Application')
    parser.add_argument('--config', '-c', default='config.yml', 
                       help='Configuration file path (default: config.yml)')
    parser.add_argument('--url', '-u', 
                       help='Custom URL to crawl (overrides config)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--playwright', '-p', action='store_true',
                       help='Use Playwright for JavaScript-heavy sites (SPAs)')
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    # Override URL if provided
    if args.url:
        config['base_url'] = args.url
        print(f"Using custom URL: {args.url}")
    
    # Set verbose logging if requested
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Determine allowed domains for display
    allowed_domains = []
    if args.url:
        custom_domain = extract_domain_from_url(args.url)
        allowed_domains.append(custom_domain)
        if not custom_domain.startswith('www.'):
            allowed_domains.append(f'www.{custom_domain}')
        else:
            allowed_domains.append(custom_domain[4:])
    else:
        if config.get('base_url'):
            base_domain = extract_domain_from_url(config.get('base_url'))
            allowed_domains.append(base_domain)
            if not base_domain.startswith('www.'):
                allowed_domains.append(f'www.{base_domain}')
            else:
                allowed_domains.append(base_domain[4:])
    
    # Print configuration summary
    print("=" * 50)
    print("Web Crawler Configuration")
    print("=" * 50)
    print(f"Base URL: {config.get('base_url')}")
    print(f"Allowed Domains: {', '.join(allowed_domains)}")
    print(f"Max Depth: {config.get('max_depth', 3)}")
    print(f"Max Pages per Domain: {config.get('max_pages_per_domain', 100)}")
    print(f"Max Retries: {config.get('max_retries', 3)}")
    print(f"Page Download Types: {', '.join(config.get('page_download_types', ['html']))}")
    print(f"Output Directory: {config.get('storage', {}).get('output_dir', './downloads')}")
    print(f"Exclude Patterns: {len(config.get('exclude_patterns', []))} patterns")
    print(f"Playwright Mode: {'Enabled' if args.playwright else 'Disabled'}")
    
    # Print timeout configuration
    timeout_settings = config.get("timeout_settings", {})
    if timeout_settings:
        print(f"Timeout Settings:")
        print(f"  Page Load: {timeout_settings.get('page_load_timeout', 30)}s")
        print(f"  Network Idle: {timeout_settings.get('network_idle_timeout', 10)}s")
        print(f"  JavaScript: {timeout_settings.get('javascript_timeout', 15)}s")
        print(f"  Request: {timeout_settings.get('request_timeout', 60)}s")
        print(f"  Retry Timeout: {timeout_settings.get('retry_timeout', 5)}s")
    
    # Print dynamic slowdown configuration
    dynamic_slowdown = config.get("dynamic_slowdown", {})
    if dynamic_slowdown.get("enabled", False):
        print(f"Dynamic Slowdown: {dynamic_slowdown.get("min_delay", 0)}-{dynamic_slowdown.get("max_delay", 5)}s")
    else:
        print("Dynamic Slowdown: Disabled")
    print("=" * 50)
    
    try:
        run_crawler(config, args.url, args.playwright)
    except KeyboardInterrupt:
        print("\nCrawler interrupted by user")
    except Exception as e:
        print(f"Error running crawler: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()

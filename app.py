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

def update_scrapy_settings(config):
    """Update Scrapy settings based on configuration"""
    settings = get_project_settings()
    
    # Update settings from config
    settings.set('USER_AGENT', config.get('user_agent', 'RohanCrawler/1.0'))
    settings.set('CONCURRENT_REQUESTS', config.get('concurrent_requests', 8))
    settings.set('CONCURRENT_REQUESTS_PER_DOMAIN', config.get('concurrent_requests_per_domain', 4))
    settings.set('DOWNLOAD_DELAY', config.get('delay_between_requests', 0.5))
    settings.set('DEPTH_LIMIT', config.get('max_depth', 3))
    
    # File download settings
    output_dir = config.get('storage', {}).get('output_dir', './downloads')
    settings.set('FILES_STORE', output_dir)
    settings.set('IMAGES_STORE', output_dir)
    
    # Pipeline settings
    settings.set('ITEM_PIPELINES', {
        'pipelines.ValidationPipeline': 100,
        'pipelines.ContentHashPipeline': 200,
        'pipelines.FileDownloadPipeline': 300,
    })
    
    return settings

def run_crawler(config, custom_url=None):
    """Run the web crawler"""
    logger = setup_logging(config)
    logger.info("Starting web crawler...")
    
    # Create output directories
    create_output_directories(config)
    
    # Update Scrapy settings
    settings = update_scrapy_settings(config)
    
    # Prepare spider arguments
    spider_args = {
        'allowed_domains': config.get('allowed_domains', []),
        'start_urls': [custom_url] if custom_url else [config.get('base_url')],
        'exclude_patterns': config.get('exclude_patterns', []),
        'download_file_types': config.get('download_file_types', []),
        'max_pages_per_domain': config.get('max_pages_per_domain', 100),
        'max_file_size_mb': config.get('max_file_size_mb', 50)
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
    
    # Print configuration summary
    print("=" * 50)
    print("Web Crawler Configuration")
    print("=" * 50)
    print(f"Base URL: {config.get('base_url')}")
    print(f"Allowed Domains: {', '.join(config.get('allowed_domains', []))}")
    print(f"Max Depth: {config.get('max_depth', 3)}")
    print(f"Max Pages per Domain: {config.get('max_pages_per_domain', 100)}")
    print(f"Output Directory: {config.get('storage', {}).get('output_dir', './downloads')}")
    print(f"Exclude Patterns: {len(config.get('exclude_patterns', []))} patterns")
    print("=" * 50)
    
    try:
        run_crawler(config, args.url)
    except KeyboardInterrupt:
        print("\nCrawler interrupted by user")
    except Exception as e:
        print(f"Error running crawler: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()

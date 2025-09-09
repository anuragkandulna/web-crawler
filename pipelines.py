import os
import json
import hashlib
import logging
from urllib.parse import urlparse, urljoin
from scrapy.pipelines.files import FilesPipeline
from scrapy.pipelines.images import ImagesPipeline
from scrapy.http import Request
from scrapy.exceptions import DropItem
import yaml
from datetime import datetime

class FileDownloadPipeline(FilesPipeline):
    """Custom pipeline for downloading files with hash-based deduplication"""
    
    @classmethod
    def from_crawler(cls, crawler):
        """Create pipeline instance from crawler"""
        store_uri = crawler.settings.get("FILES_STORE")
        return cls(store_uri, crawler=crawler)
    
    def __init__(self, store_uri, download_func=None, settings=None, crawler=None):
        super().__init__(store_uri, download_func, settings)
        self.manifest = {}
        self.crawler = crawler
        self.load_config()
        self.setup_logging()
        
    def load_config(self):
        """Load configuration from YAML file"""
        try:
            with open('config.yml', 'r') as f:
                self.config = yaml.safe_load(f)['crawler']
        except FileNotFoundError:
            self.config = {
                'storage': {
                    'output_dir': './downloads',
                    'manifest_file': './crawl_manifest.json'
                },
                'max_file_size_mb': 50
            }
    
    def setup_logging(self):
        """Setup logging for the pipeline"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def get_media_requests(self, item, info):
        """Generate requests for file downloads"""
        file_urls = item.get('file_urls', [])
        image_urls = item.get('image_urls', [])
        
        all_urls = file_urls + image_urls
        
        for url in all_urls:
            # Check if URL should be excluded
            if self.should_exclude_url(url):
                continue
                
            yield Request(url, meta={'item': item})
    
    def should_exclude_url(self, url):
        """Check if URL should be excluded based on patterns"""
        exclude_patterns = self.config.get('exclude_patterns', [])
        
        for pattern in exclude_patterns:
            import re
            if re.search(pattern, url):
                return True
        return False
    
    def file_path(self, request, response=None, info=None, *, item=None):
        """Generate file path for downloaded file"""
        url = request.url
        parsed_url = urlparse(url)
        
        domain = parsed_url.netloc.replace("www.", "")
        path = parsed_url.path.strip("/")
        domain_folder = domain
        
        if not path:
            path = 'index'
        
        # Clean path for filesystem
        path = path.replace('/', '_').replace('\\', '_')
        
        # Get file extension
        ext = os.path.splitext(path)[1]
        if not ext:
            # Try to get extension from content type
            content_type = response.headers.get('Content-Type', b'').decode()
            if 'pdf' in content_type:
                ext = '.pdf'
            elif 'image' in content_type:
                ext = '.jpg'  # default image extension
        
        filename = f"{path}{ext}" if path != "index" else f"index{ext}"
        return f"{domain_folder}/{filename}"
    
    def item_completed(self, results, item, info):
        """Called when item processing is completed"""
        file_paths = []
        
        for success, result in results:
            if success:
                file_path = result['path']
                file_paths.append(file_path)
                
                # Calculate file hash
                file_hash = self.calculate_file_hash(result['path'])
                
                # Add to manifest
                self.manifest[item['url']] = {
                    'file_path': file_path,
                    'hash': file_hash,
                    'content_type': item.get('content_type', ''),
                    'timestamp': result.get('checksum', ''),
                    'size': result.get('size', 0)
                }
        
        if file_paths:
            item['file_paths'] = file_paths
        
        # Save manifest periodically
        self.save_manifest()
        
        return item
    
    def calculate_file_hash(self, file_path):
        """Calculate SHA-256 hash of file"""
        try:
            full_path = os.path.join(self.store.basedir, file_path)
            with open(full_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception as e:
            self.logger.error(f"Error calculating hash for {file_path}: {e}")
            return ""
    
    def save_manifest(self):
        """Save crawl manifest to JSON file"""
        try:
            manifest_file = self.config['storage']['manifest_file']
            with open(manifest_file, 'w') as f:
                json.dump(self.manifest, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving manifest: {e}")
    
    def close_spider(self, spider):
        """Called when spider is closed"""
        self.save_manifest()
        self.logger.info(f"Crawl completed. {len(self.manifest)} files downloaded.")

class ContentHashPipeline:
    """Pipeline for content-based deduplication"""
    
    def __init__(self):
        self.content_hashes = set()
        self.load_config()
    
    def load_config(self):
        """Load configuration from YAML file"""
        try:
            with open('config.yml', 'r') as f:
                self.config = yaml.safe_load(f)['crawler']
        except FileNotFoundError:
            self.config = {}
    
    def process_item(self, item, spider):
        """Process item and check for content duplication"""
        if 'body' in item and item['body']:
            content_hash = hashlib.md5(item['body']).hexdigest()
            
            if content_hash in self.content_hashes:
                raise DropItem(f"Duplicate content found: {item['url']}")
            
            self.content_hashes.add(content_hash)
            item['content_hash'] = content_hash
        
        return item

class ValidationPipeline:
    """Pipeline for validating crawled items"""
    
    def __init__(self):
        self.load_config()
        self.setup_logging()
    
    def load_config(self):
        """Load configuration from YAML file"""
        try:
            with open('config.yml', 'r') as f:
                self.config = yaml.safe_load(f)['crawler']
        except FileNotFoundError:
            self.config = {}
    
    def setup_logging(self):
        """Setup logging for the pipeline"""
        self.logger = logging.getLogger(__name__)
    
    def process_item(self, item, spider):
        """Validate item before processing"""
        # Check URL validity
        if not item.get('url'):
            raise DropItem("Item missing URL")
        
        # Check content type
        content_type = item.get('content_type', '')
        allowed_types = self.config.get('download_file_types', [])
        
        if allowed_types and content_type not in allowed_types:
            # Allow HTML content even if not in allowed types
            if 'text/html' not in content_type:
                raise DropItem(f"Content type not allowed: {content_type}")
        
        return item

class PageDownloadPipeline:
    """Pipeline for downloading HTML pages with proper directory structure"""
    
    def __init__(self):
        self.load_config()
        self.setup_logging()
        self.domain_manifests = {}
        
    def load_config(self):
        """Load configuration from YAML file"""
        try:
            with open('config.yml', 'r') as f:
                self.config = yaml.safe_load(f)['crawler']
        except FileNotFoundError:
            self.config = {
                'storage': {
                    'output_dir': './downloads'
                }
            }
    
    def setup_logging(self):
        """Setup logging for the pipeline"""
        self.logger = logging.getLogger(__name__)
    
    def process_item(self, item, spider):
        """Download HTML pages and save them with proper directory structure"""
        if not item.get('body') or not item.get('url'):
            return item
        
        try:
            # Parse URL to get domain and path
            parsed_url = urlparse(item['url'])
            domain = parsed_url.netloc.replace('www.', '')
            # Keep domain as-is for folder name (e.g., theciso.org, example.com)
            domain_folder = domain
            
            # Create output directory structure
            output_dir = self.config['storage']['output_dir']
            domain_path = os.path.join(output_dir, domain_folder)
            os.makedirs(domain_path, exist_ok=True)
            path = parsed_url.path.strip("/")
            # Create directory hierarchy based on URL path
            if path:
                # Split path into components
                path_parts = path.split('/')
                current_path = domain_path
                
                # Create subdirectories for each path component
                for part in path_parts[:-1]:  # Exclude the last part (filename)
                    if part:
                        current_path = os.path.join(current_path, part)
                        os.makedirs(current_path, exist_ok=True)
                
                # Determine filename
                if path_parts[-1]:
                    filename = path_parts[-1]
                    if not filename.endswith(('.html', '.htm')):
                        filename += '.html'
                else:
                    filename = 'index.html'
            else:
                current_path = domain_path
                filename = 'index.html'
            
            # Full file path
            file_path = os.path.join(current_path, filename)
            
            # Save the HTML content
            with open(file_path, 'wb') as f:
                f.write(item['body'])
            
            # Calculate file hash
            file_hash = hashlib.sha256(item['body']).hexdigest()
            
            # Get relative path for manifest
            relative_path = os.path.relpath(file_path, output_dir)
            
            # Add to domain manifest
            if domain_folder not in self.domain_manifests:
                self.domain_manifests[domain_folder] = {}
            
            self.domain_manifests[domain_folder][item['url']] = {
                'file_path': relative_path,
                'hash': file_hash,
                'content_type': item.get('content_type', ''),
                'title': item.get('title', ''),
                'depth': item.get('depth', 0),
                'timestamp': datetime.now().isoformat(),
                'size': len(item['body'])
            }
            
            # Save domain manifest
            self.save_domain_manifest(domain_folder, domain_path)
            
            self.logger.info(f"Downloaded page: {item['url']} -> {relative_path}")
            
        except Exception as e:
            self.logger.error(f"Error downloading page {item['url']}: {e}")
        
        return item
    
    def save_domain_manifest(self, domain_folder, domain_path):
        """Save manifest file for specific domain"""
        try:
            manifest_file = os.path.join(domain_path, 'crawl_manifest.json')
            with open(manifest_file, 'w') as f:
                json.dump(self.domain_manifests[domain_folder], f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving domain manifest for {domain_folder}: {e}")
    
    def close_spider(self, spider):
        """Called when spider is closed"""
        self.logger.info(f"Page download completed. Downloaded pages for {len(self.domain_manifests)} domains.")
        for domain in self.domain_manifests:
            self.logger.info(f"Domain {domain}: {len(self.domain_manifests[domain])} pages downloaded")

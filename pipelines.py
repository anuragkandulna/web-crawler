import os
import json
import hashlib
import logging
from urllib.parse import urlparse
from scrapy.pipelines.files import FilesPipeline
from scrapy.pipelines.images import ImagesPipeline
from scrapy.http import Request
from scrapy.exceptions import DropItem
import yaml

class FileDownloadPipeline(FilesPipeline):
    """Custom pipeline for downloading files with hash-based deduplication"""
    
    def __init__(self, store_uri, download_func=None, settings=None):
        super().__init__(store_uri, download_func, settings)
        self.manifest = {}
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
        
        # Create directory structure based on domain and path
        domain = parsed_url.netloc.replace('www.', '')
        path = parsed_url.path.strip('/')
        
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
        
        filename = f"{domain}_{path}{ext}"
        return f"{domain}/{filename}"
    
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

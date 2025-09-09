"""
Custom Scrapy Middlewares
"""

import time
import random
import logging
from urllib.parse import urlparse
from scrapy.exceptions import NotConfigured
import yaml


class DynamicSlowdownMiddleware:
    """
    Middleware that implements dynamic slowdown to bypass rate limiters
    """
    
    def __init__(self, settings):
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        self.domain_request_counts = {}
        self.domain_last_request = {}
        
        # Load configuration
        self.load_config()
        
        # Check if dynamic slowdown is enabled
        if not self.dynamic_slowdown.get('enabled', False):
            raise NotConfigured('Dynamic slowdown is disabled')
        
        self.min_delay = float(self.dynamic_slowdown.get('min_delay', 0.0))
        self.max_delay = float(self.dynamic_slowdown.get('max_delay', 5.0))
        self.progressive = self.dynamic_slowdown.get('progressive', True)
        self.per_domain = self.dynamic_slowdown.get('per_domain', True)
        
        self.logger.info(f"Dynamic slowdown enabled: {self.min_delay}-{self.max_delay}s range")
    
    @classmethod
    def from_crawler(cls, crawler):
        """Create middleware instance from crawler"""
        return cls(crawler.settings)
    
    def load_config(self):
        """Load configuration from config.yml"""
        try:
            with open('config.yml', 'r') as f:
                config = yaml.safe_load(f)
            self.dynamic_slowdown = config['crawler'].get('dynamic_slowdown', {})
        except (FileNotFoundError, KeyError, yaml.YAMLError) as e:
            self.logger.warning(f"Could not load dynamic slowdown config: {e}")
            self.dynamic_slowdown = {'enabled': False}
    
    def calculate_delay(self, domain):
        """Calculate delay for a given domain"""
        base_delay = random.uniform(self.min_delay, self.max_delay)
        
        if not self.progressive or not self.per_domain:
            return base_delay
        
        # Progressive delay: increase delay based on request count for this domain
        request_count = self.domain_request_counts.get(domain, 0)
        
        # Add progressive component (up to 2x the base delay)
        progressive_multiplier = min(1 + (request_count * 0.1), 2.0)
        calculated_delay = base_delay * progressive_multiplier
        
        # Ensure we don't exceed max_delay
        return min(calculated_delay, self.max_delay)
    
    def process_request(self, request, spider):
        """Process request and apply dynamic slowdown"""
        # Extract domain from request URL
        parsed_url = urlparse(request.url)
        domain = parsed_url.netloc.lower()
        
        # Calculate delay for this domain
        delay = self.calculate_delay(domain)
        
        # Track request count for this domain
        if self.per_domain:
            self.domain_request_counts[domain] = self.domain_request_counts.get(domain, 0) + 1
        
        # Check last request time for this domain to avoid too frequent requests
        current_time = time.time()
        last_request_time = self.domain_last_request.get(domain, 0)
        time_since_last = current_time - last_request_time
        
        # If we need to wait longer, sleep for the remaining time
        if time_since_last < delay:
            sleep_time = delay - time_since_last
            self.logger.debug(f"Dynamic slowdown: sleeping {sleep_time:.2f}s for {domain} "
                            f"(request #{self.domain_request_counts.get(domain, 1)})")
            time.sleep(sleep_time)
        
        # Update last request time
        self.domain_last_request[domain] = time.time()
        
        # Log the delay applied
        self.logger.info(f"Applied {delay:.2f}s delay for {domain} "
                        f"(request #{self.domain_request_counts.get(domain, 1)})")
        
        return None  # Continue processing the request


class RandomUserAgentMiddleware:
    """
    Middleware that rotates user agents randomly
    """
    
    def __init__(self):
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (X11; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/91.0.864.59',
        ]
        self.logger = logging.getLogger(__name__)
    
    @classmethod
    def from_crawler(cls, crawler):
        """Create middleware instance from crawler"""
        return cls()
    
    def process_request(self, request, spider):
        """Randomly assign user agent to request"""
        user_agent = random.choice(self.user_agents)
        request.headers['User-Agent'] = user_agent
        self.logger.debug(f"Using User-Agent: {user_agent[:50]}...")
        return None

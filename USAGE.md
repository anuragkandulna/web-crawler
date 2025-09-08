# Web Crawler Usage Guide

## Overview

This web crawler application is built with Scrapy and provides a comprehensive solution for crawling websites, downloading files, and managing content with proper politeness and respect for robots.txt.

## Features

- **Configurable crawling**: YAML-based configuration
- **Politeness**: Respects robots.txt, rate limiting, and domain limits
- **File downloads**: Downloads images, PDFs, and other specified file types
- **Content deduplication**: Hash-based content deduplication
- **Depth control**: Configurable crawling depth
- **Domain management**: Per-domain page limits and allowed domains
- **Exception handling**: Exclude unwanted URLs with regex patterns
- **Manifest generation**: JSON manifest of all downloaded files

## Quick Start

### 1. Setup

```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies (if not already done)
pip install -r requirements.txt
```

### 2. Configuration

Edit `config.yml` to set your target website and preferences:

```yaml
crawler:
  base_url: "https://example.com"
  allowed_domains:
    - "example.com"
    - "www.example.com"
  exclude_patterns:
    - ".*/about.*"
    - ".*/ads.*"
    - ".*\\.(css|js|ico)$"
  max_depth: 3
  max_pages_per_domain: 100
```

### 3. Run the Crawler

```bash
# Basic usage
python app.py

# With custom URL
python app.py --url "https://example.com"

# With verbose logging
python app.py --verbose

# With custom config file
python app.py --config my_config.yml
```

## Configuration Options

### Basic Settings

- `base_url`: Starting URL for crawling
- `allowed_domains`: List of domains to crawl
- `exclude_patterns`: Regex patterns for URLs to skip
- `max_depth`: Maximum crawling depth (default: 3)
- `max_pages_per_domain`: Maximum pages per domain (default: 100)

### File Download Settings

- `download_file_types`: MIME types to download
- `max_file_size_mb`: Maximum file size in MB

### Politeness Settings

- `delay_between_requests`: Delay between requests in seconds
- `concurrent_requests`: Number of concurrent requests
- `concurrent_requests_per_domain`: Concurrent requests per domain

### Storage Settings

- `output_dir`: Directory for downloaded files
- `manifest_file`: JSON file with download manifest
- `log_file`: Log file path

## Command Line Options

```bash
python app.py [OPTIONS]

Options:
  -h, --help            Show help message
  -c, --config CONFIG   Configuration file path (default: config.yml)
  -u, --url URL         Custom URL to crawl (overrides config)
  -v, --verbose         Enable verbose logging
```

## Examples

### Example 1: Crawl a Documentation Site

```bash
# Create config for documentation site
cat > doc_config.yml << 'YAML_EOF'
crawler:
  base_url: "https://docs.example.com"
  allowed_domains:
    - "docs.example.com"
  exclude_patterns:
    - ".*/search.*"
    - ".*/api/.*"
    - ".*\\.(css|js|ico|png|jpg)$"
  download_file_types:
    - "application/pdf"
    - "text/plain"
  max_depth: 2
  max_pages_per_domain: 50
YAML_EOF

# Run crawler
python app.py --config doc_config.yml --verbose
```

### Example 2: Download Images from a Gallery

```bash
# Create config for image gallery
cat > gallery_config.yml << 'YAML_EOF'
crawler:
  base_url: "https://gallery.example.com"
  allowed_domains:
    - "gallery.example.com"
  exclude_patterns:
    - ".*/thumbnails/.*"
    - ".*/admin/.*"
  download_file_types:
    - "image/jpeg"
    - "image/png"
    - "image/gif"
  max_depth: 1
  max_pages_per_domain: 200
YAML_EOF

# Run crawler
python app.py --config gallery_config.yml
```

### Example 3: Quick Test with Custom URL

```bash
# Test with a specific URL
python app.py --url "https://httpbin.org" --verbose
```

## Output Structure

After running the crawler, you'll find:

```
downloads/
├── example.com/
│   ├── page1.html
│   ├── image1.jpg
│   └── document1.pdf
└── www.example.com/
    └── page2.html

crawl_manifest.json    # Download manifest
crawler.log           # Detailed logs
```

## Manifest File

The `crawl_manifest.json` contains metadata about all downloaded files:

```json
{
  "https://example.com/image.jpg": {
    "file_path": "example.com/image.jpg",
    "hash": "sha256_hash_here",
    "content_type": "image/jpeg",
    "timestamp": "2025-01-01T12:00:00Z",
    "size": 12345
  }
}
```

## Best Practices

### 1. Respectful Crawling

- Always check robots.txt compliance
- Use appropriate delays between requests
- Set reasonable domain limits
- Identify your crawler with proper User-Agent

### 2. Configuration

- Start with small limits and increase gradually
- Use specific exclude patterns to avoid unwanted content
- Set appropriate file size limits
- Configure allowed domains carefully

### 3. Monitoring

- Use verbose logging for debugging
- Monitor the manifest file for download status
- Check logs for any errors or warnings
- Use depth limits to control crawl scope

## Troubleshooting

### Common Issues

1. **Permission Denied**: Check file permissions for output directory
2. **Memory Issues**: Reduce concurrent requests or page limits
3. **Rate Limiting**: Increase delays between requests
4. **Domain Blocked**: Check robots.txt and site policies

### Debug Mode

```bash
# Enable debug logging
python app.py --verbose

# Check logs
tail -f crawler.log
```

## Advanced Usage

### Custom Pipelines

You can extend the crawler by adding custom pipelines in `pipelines.py`:

```python
class CustomPipeline:
    def process_item(self, item, spider):
        # Custom processing logic
        return item
```

### Custom Middleware

Add custom middleware in `settings.py`:

```python
DOWNLOADER_MIDDLEWARES = {
    'myproject.middleware.CustomMiddleware': 543,
}
```

## Legal and Ethical Considerations

- Always respect robots.txt
- Follow website terms of service
- Use appropriate delays and limits
- Don't overload servers
- Respect copyright and intellectual property
- Consider reaching out to site owners for large crawls

## Support

For issues or questions:
1. Check the logs in `crawler.log`
2. Review the configuration in `config.yml`
3. Test with a small scope first
4. Ensure all dependencies are installed

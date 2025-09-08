import scrapy
from urllib.parse import urljoin, urldefrag

class CrawlItem(scrapy.Item):
    url = scrapy.Field()
    referrer = scrapy.Field()
    content_type = scrapy.Field()
    body = scrapy.Field()  # optional; or store to disk in pipeline
    file_urls = scrapy.Field()  # for media pipeline
    image_urls = scrapy.Field()

class SiteSpider(scrapy.Spider):
    name = "site"
    allowed_domains = ["example.com"]  # or configure per run
    start_urls = ["https://example.com"]

    def parse(self, response):
        ct = response.headers.get("Content-Type", b"").decode().lower()
        item = CrawlItem(url=response.url, referrer=response.request.headers.get("Referer"), content_type=ct)

        # Collect downloadable assets
        if "text/html" in ct:
            # Extract links and media
            for href in response.css("a::attr(href)").getall():
                u = urljoin(response.url, href)
                u, _ = urldefrag(u)
                yield response.follow(u, callback=self.parse)
            item["image_urls"] = [urljoin(response.url, s) for s in response.css("img::attr(src)").getall()]
            # PDFs or other files linked:
            for link in response.css('a[href$=".pdf"]::attr(href)').getall():
                u = urljoin(response.url, link)
                yield scrapy.Request(u, callback=self.save_file)
        else:
            # Non-HTML handled elsewhere if you want
            pass

        yield item

    def save_file(self, response):
        # Hand off to pipeline (either via file_urls or custom)
        i = CrawlItem(url=response.url, content_type=response.headers.get("Content-Type", b"").decode().lower())
        i["file_urls"] = [response.url]
        yield i

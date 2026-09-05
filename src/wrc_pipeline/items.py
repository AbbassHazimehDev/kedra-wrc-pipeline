"""Structured item passed from the spider to the landing pipeline."""

import scrapy


class WrcDecisionItem(scrapy.Item):
    """A source decision plus the original bytes to be landed."""

    identifier = scrapy.Field()
    title = scrapy.Field()
    description = scrapy.Field()
    published_date = scrapy.Field()
    body = scrapy.Field()
    source_url = scrapy.Field()
    document_url = scrapy.Field()
    partition_date = scrapy.Field()
    partition_start = scrapy.Field()
    partition_end = scrapy.Field()
    source_identity = scrapy.Field()
    raw_bytes = scrapy.Field()
    source_content_type = scrapy.Field()
    file_extension = scrapy.Field()

"""Tests for verified WRC request and result parsing behavior."""

from datetime import date

from scrapy.http import HtmlResponse, Response

from wrc_pipeline.spiders.decisions import DecisionsSpider, WRC_BODIES
from wrc_pipeline.utils.dates import DatePartition


RESULT_HTML = b"""
<html><body>
<div class="searchhead">Shows 1 to 10 of 234 results</div>
<div class="item-list search-list"><ul>
  <li class="each-item clearfix">
    <h2 class="title">
      <a title="ADJ-00047352"
         href="/en/cases/2024/january/adj-00047352.html">ADJ-00047352</a>
    </h2>
    <span class="date">31/01/2024</span>
    <p class="description" title="Car Valet V Motor Garage">Car Valet V Motor Garage</p>
  </li>
</ul></div>
<ul class="pager">
  <li class="current"><a href="?body=15376&amp;pageNumber=1">1</a></li>
  <li><a href="?body=15376&amp;pageNumber=2">2</a></li>
</ul>
</body></html>
"""


def make_spider():
    return DecisionsSpider("2024-01-01", "2024-01-31")


def test_search_url_uses_site_date_format_and_body_value():
    spider = make_spider()
    partition = DatePartition(date(2024, 1, 1), date(2024, 1, 31))

    url = spider.build_search_url(partition, "15376", 2)

    assert "decisions=1" in url
    assert "from=01%2F01%2F2024" in url
    assert "to=31%2F01%2F2024" in url
    assert "body=15376" in url
    assert "pageNumber=2" in url


def test_all_confirmed_bodies_are_configured():
    assert WRC_BODIES == {
        "Employment Appeals Tribunal": "2",
        "Equality Tribunal": "1",
        "Labour Court": "3",
        "Workplace Relations Commission": "15376",
    }


def test_result_count_and_result_metadata_are_parsed():
    spider = make_spider()
    response = HtmlResponse(
        url="https://www.workplacerelations.ie/en/search/?body=15376",
        body=RESULT_HTML,
        encoding="utf-8",
    )
    node = response.css("li.each-item")[0]

    assert spider._result_count(response) == 234
    record = spider._parse_result(
        node,
        response,
        spider.partitions[0],
        "Workplace Relations Commission",
    )
    assert record["identifier"] == "ADJ-00047352"
    assert record["published_date"] == "2024-01-31"
    assert record["description"] == "Car Valet V Motor Garage"
    assert record["source_url"].endswith("adj-00047352.html")
    assert record["partition_date"] == "2024-01"


def test_next_page_is_taken_from_pager():
    spider = make_spider()
    response = HtmlResponse(url="https://example.test/search", body=RESULT_HTML)
    assert spider._next_page(response, 1).endswith("pageNumber=2")
    assert spider._next_page(response, 2) is None


def test_document_type_uses_pdf_magic_bytes():
    response = Response(
        url="https://example.test/document",
        body=b"%PDF-1.7\nsource",
        headers={b"Content-Type": b"application/octet-stream"},
    )
    assert DecisionsSpider._file_details(response) == (
        "application/octet-stream",
        "pdf",
    )


def test_document_type_supports_docx_content_type():
    response = Response(
        url="https://example.test/document",
        body=b"PK\x03\x04source",
        headers={
            b"Content-Type": (
                b"application/vnd.openxmlformats-officedocument."
                b"wordprocessingml.document"
            )
        },
    )
    assert DecisionsSpider._file_details(response)[1] == "docx"

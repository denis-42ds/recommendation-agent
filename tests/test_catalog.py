import gzip
from pathlib import Path

from openpyxl import Workbook

from scripts.build_catalog import (
    build_url_pattern,
    iter_feed,
    load_sales_items,
    normalize,
    url_article_key,
)


def test_normalize_sku():
    assert normalize("CR15-1S1W01") == "CR151S1W01"
    assert normalize(" cr15-1s1w01 ") == "CR151S1W01"
    assert normalize(None) == ""


def test_url_article_key():
    url = "https://store.softline.ru/vendor/cr15-1s1w01-324027/"
    assert url_article_key(url) == "CR151S1W01324027"


def test_url_pattern_matches_sku_and_numeric_suffix():
    pattern = build_url_pattern({"CR151S1W01", "ABC123"})

    match = pattern.fullmatch("CR151S1W01324027")

    assert match is not None
    assert match.group("sku") == "CR151S1W01"
    assert match.group("suffix") == "324027"


def test_url_pattern_rejects_non_numeric_suffix():
    pattern = build_url_pattern({"CR151S1W01"})

    assert pattern.fullmatch("CR151S1W01ABC") is None


def test_url_pattern_without_skus():
    assert build_url_pattern(set()) is None


def test_iter_feed_reads_offers_and_categories(tmp_path: Path):
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <yml_catalog>
      <shop>
        <categories>
          <category id="10">Software</category>
          <category id="11" parentId="10">Security</category>
        </categories>
        <offers>
          <offer id="123" available="true">
            <name>Antivirus</name>
            <vendor>Vendor</vendor>
            <vendorCode>AV-001</vendorCode>
            <url>https://example.com/av-001-123/</url>
            <categoryId>11</categoryId>
            <description>Antivirus product</description>
            <param name="Тип продукта">ПО</param>
            <param name="Тип лицензии">Подписка</param>
          </offer>
        </offers>
      </shop>
    </yml_catalog>
    """

    feed_path = tmp_path / "feed.yml.gz"
    with gzip.open(feed_path, "wb") as file:
        file.write(xml.encode("utf-8"))

    products = list(iter_feed(feed_path))

    assert len(products) == 1

    product = products[0]
    assert product["offer_id"] == "123"
    assert product["available"] is True
    assert product["vendor_code"] == "AV-001"
    assert product["category_path"] == ["Software", "Security"]
    assert product["params"]["Тип продукта"] == ["ПО"]
    assert product["params"]["Тип лицензии"] == ["Подписка"]


def test_load_sales_items_preserves_conflicting_records(tmp_path):
    workbook_path = tmp_path / "sales.xlsx"

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Продажи"

    sheet.append(["item_id", "sku", "item_name"])
    sheet.append(["ITEM-1", "SKU-1", "Product A"])
    sheet.append(["ITEM-1", "SKU-1", "Product A"])
    sheet.append(["ITEM-2", "SKU-2", "Product B"])
    sheet.append(["ITEM-2", "SKU-3", "Product B"])

    workbook.save(workbook_path)

    items = load_sales_items(workbook_path)

    assert items["ITEM-1"]["status"] == "ok"
    assert items["ITEM-1"]["sku"] == "SKU-1"

    assert items["ITEM-2"]["status"] == "ambiguous_source"
    assert len(items["ITEM-2"]["source_variants"]) == 2

import gzip
import json
from pathlib import Path

from openpyxl import Workbook

from scripts.build_catalog import (
    build_catalog,
    iter_feed,
    load_sales_items,
    normalize,
    url_article_match,
)


def create_workbook(path: Path, rows: list[tuple]) -> None:
    """Create a minimal workbook with the sales sheet."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Продажи"

    sheet.append(["item_id", "sku", "item_name"])

    for row in rows:
        sheet.append(list(row))

    workbook.save(path)
    workbook.close()


def create_feed(path: Path, offers: list[dict]) -> None:
    """Create a minimal gzipped YML feed."""
    offer_xml = []

    for offer in offers:
        offer_xml.append(
            f"""
            <offer id="{offer['id']}" available="true">
              <name>{offer.get('name', '')}</name>
              <vendor>{offer.get('vendor', '')}</vendor>
              <vendorCode>{offer.get('vendor_code', '')}</vendorCode>
              <url>{offer.get('url', '')}</url>
              <categoryId>10</categoryId>
              <description>Test product</description>
            </offer>
            """
        )

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
    <yml_catalog>
      <shop>
        <categories>
          <category id="10">Software</category>
        </categories>
        <offers>
          {''.join(offer_xml)}
        </offers>
      </shop>
    </yml_catalog>
    """

    with gzip.open(path, "wb") as file:
        file.write(xml.encode("utf-8"))


def test_url_article_match_accepts_exact_sku_and_offer_id():
    url = "https://store.softline.ru/vendor/cr15-1s1w01-324027/"

    assert url_article_match(url, "324027", "CR151S1W01")


def test_url_article_match_rejects_wrong_offer_id():
    url = "https://store.softline.ru/vendor/cr15-1s1w01-324027/"

    assert not url_article_match(url, "324028", "CR151S1W01")


def test_url_article_match_rejects_numeric_prefix_collision():
    url = "https://store.softline.ru/vendor/53063-477516/"

    assert not url_article_match(url, "477516", "5306")


def test_url_article_match_rejects_unrelated_numeric_offer():
    url = "https://store.softline.ru/vendor/-53063/"

    assert not url_article_match(url, "53063", "53063")


def test_url_article_match_rejects_empty_arguments():
    assert not url_article_match("", "123", "SKU")
    assert not url_article_match("https://example.com/SKU-123/", "", "SKU")
    assert not url_article_match("https://example.com/SKU-123/", "123", "")


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


def test_load_sales_items_accepts_same_normalized_sku_with_different_names(
    tmp_path: Path,
):
    workbook_path = tmp_path / "sales.xlsx"

    create_workbook(
        workbook_path,
        [
            ("ITEM-1", "SKU-001", "Product A"),
            ("ITEM-1", "sku001", "Product A - License"),
            ("ITEM-1", "SKU-001", "Product A"),
        ],
    )

    items = load_sales_items(workbook_path)

    assert items["ITEM-1"]["status"] == "ok"
    assert items["ITEM-1"]["sku_key"] == "SKU001"
    assert items["ITEM-1"]["match_key_type"] == "sku"
    assert len(items["ITEM-1"]["source_variants"]) == 2


def test_load_sales_items_preserves_conflicting_skus(tmp_path: Path):
    workbook_path = tmp_path / "sales.xlsx"

    create_workbook(
        workbook_path,
        [
            ("ITEM-1", "SKU-1", "Product A"),
            ("ITEM-1", "SKU-2", "Product A"),
        ],
    )

    items = load_sales_items(workbook_path)

    assert items["ITEM-1"]["status"] == "ambiguous_source"
    assert len(items["ITEM-1"]["source_variants"]) == 2


def test_load_sales_items_matches_n_item_by_normalized_name(
    tmp_path: Path,
):
    workbook_path = tmp_path / "sales.xlsx"

    create_workbook(
        workbook_path,
        [
            ("N-001", "", "Product A"),
            ("N-001", "", "Product-A"),
            ("N-001", "", "Product A!"),
        ],
    )

    items = load_sales_items(workbook_path)

    assert items["N-001"]["status"] == "ok"
    assert items["N-001"]["match_key_type"] == "name"
    assert items["N-001"]["sku_key"] == "PRODUCTA"


def test_load_sales_items_rejects_conflicting_names_for_n_item(
    tmp_path: Path,
):
    workbook_path = tmp_path / "sales.xlsx"

    create_workbook(
        workbook_path,
        [
            ("N-001", "", "Product A"),
            ("N-001", "", "Product B"),
        ],
    )

    items = load_sales_items(workbook_path)

    assert items["N-001"]["status"] == "ambiguous_source"


def test_load_sales_items_rejects_non_n_item_without_sku(
    tmp_path: Path,
):
    workbook_path = tmp_path / "sales.xlsx"

    create_workbook(
        workbook_path,
        [
            ("ITEM-1", "", "Product A"),
        ],
    )

    items = load_sales_items(workbook_path)

    assert items["ITEM-1"]["status"] == "ambiguous_source"


def test_build_catalog_maps_multiple_offers_for_same_sku(
    tmp_path: Path,
):
    workbook_path = tmp_path / "sales.xlsx"
    feed_path = tmp_path / "feed.yml.gz"
    output_dir = tmp_path / "catalog"

    create_workbook(
        workbook_path,
        [
            ("ITEM-1", "LHW-BK-12M-2-A3", "Dr.Web Security Space"),
        ],
    )

    create_feed(
        feed_path,
        [
            {
                "id": "231539",
                "name": "Dr.Web Security Space",
                "vendor_code": "LHW-BK-12M-2-A3",
                "url": "https://example.com/product-231539/",
            },
            {
                "id": "332767",
                "name": "Dr.Web Security Space Special",
                "vendor_code": "LHW-BK-12M-2-A3",
                "url": "https://example.com/product-332767/",
            },
        ],
    )

    report = build_catalog(
        workbook_path,
        feed_path,
        output_dir,
    )

    mapping = json.loads(
        (output_dir / "item_mapping.json").read_text(encoding="utf-8")
    )

    item = mapping["ITEM-1"]

    assert item["status"] == "matched"
    assert item["offer_ids"] == ["231539", "332767"]
    assert item["match_count"] == 2
    assert item["match_method"] == "vendorCode"

    assert report["matched_item_count"] == 1
    assert report["multi_offer_item_count"] == 1

    matched_products = json.loads(
        (output_dir / "matched_products.json").read_text(encoding="utf-8")
    )

    assert len(matched_products) == 2
    assert {
        product["offer_id"] for product in matched_products
    } == {"231539", "332767"}

    assert all(
        product["item_id"] == "ITEM-1"
        for product in matched_products
    )

    assert all(
        product["available"] is True
        for product in matched_products
    )

    assert report["matched_offer_count"] == 2


def test_build_catalog_matches_exact_url_article_53063(
    tmp_path: Path,
):
    workbook_path = tmp_path / "sales.xlsx"
    feed_path = tmp_path / "feed.yml.gz"
    output_dir = tmp_path / "catalog"

    create_workbook(
        workbook_path,
        [
            ("ITEM-53063", "53063", "ФИКС продление лицензии"),
        ],
    )

    create_feed(
        feed_path,
        [
            {
                "id": "477516",
                "name": "ЦБИ ФИКС продление на 3 года",
                "url": "https://example.com/product/53063-477516/",
            },
            {
                "id": "477517",
                "name": "ЦБИ ФИКС продление на 2 года",
                "url": "https://example.com/product/53063-477517/",
            },
            {
                "id": "53063",
                "name": "Unrelated product",
                "url": "https://example.com/product/-53063/",
            },
        ],
    )

    build_catalog(
        workbook_path,
        feed_path,
        output_dir,
    )

    mapping = json.loads(
        (output_dir / "item_mapping.json").read_text(encoding="utf-8")
    )

    item = mapping["ITEM-53063"]

    assert item["status"] == "matched"
    assert item["offer_ids"] == ["477516", "477517"]
    assert item["match_count"] == 2
    assert item["match_method"] == "url_article"


def test_build_catalog_vendor_code_has_priority_over_url(
    tmp_path: Path,
):
    workbook_path = tmp_path / "sales.xlsx"
    feed_path = tmp_path / "feed.yml.gz"
    output_dir = tmp_path / "catalog"

    create_workbook(
        workbook_path,
        [
            ("ITEM-A", "SKU-A", "Product A"),
            ("ITEM-B", "SKU-B", "Product B"),
        ],
    )

    create_feed(
        feed_path,
        [
            {
                "id": "100",
                "name": "Product A",
                "vendor_code": "SKU-A",
                "url": "https://example.com/SKU-B-100/",
            },
        ],
    )

    build_catalog(
        workbook_path,
        feed_path,
        output_dir,
    )

    mapping = json.loads(
        (output_dir / "item_mapping.json").read_text(encoding="utf-8")
    )

    assert mapping["ITEM-A"]["offer_ids"] == ["100"]
    assert mapping["ITEM-A"]["match_method"] == "vendorCode"

    assert mapping["ITEM-B"]["status"] == "unmatched"


def test_build_catalog_matches_n_item_by_exact_name(
    tmp_path: Path,
):
    workbook_path = tmp_path / "sales.xlsx"
    feed_path = tmp_path / "feed.yml.gz"
    output_dir = tmp_path / "catalog"

    create_workbook(
        workbook_path,
        [
            ("N-001", "", "Product A"),
        ],
    )

    create_feed(
        feed_path,
        [
            {
                "id": "200",
                "name": "Product-A",
                "url": "https://example.com/product-200/",
            },
        ],
    )

    build_catalog(
        workbook_path,
        feed_path,
        output_dir,
    )

    mapping = json.loads(
        (output_dir / "item_mapping.json").read_text(encoding="utf-8")
    )

    assert mapping["N-001"]["status"] == "matched"
    assert mapping["N-001"]["offer_ids"] == ["200"]
    assert mapping["N-001"]["match_method"] == "exact_name"


def test_normalize_sku():
    assert normalize("CR15-1S1W01") == "CR151S1W01"
    assert normalize(" cr15-1s1w01 ") == "CR151S1W01"
    assert normalize(None) == ""

    assert normalize("КриптоАРМ Про") == "КРИПТОАРМПРО"
    assert normalize("Асмо-графический редактор") == (
        "АСМОГРАФИЧЕСКИЙРЕДАКТОР"
    )


def test_load_sales_items_accepts_cyrillic_names_for_n_items(
    tmp_path: Path,
):
    workbook_path = tmp_path / "sales.xlsx"

    create_workbook(
        workbook_path,
        [
            (
                "N-b1331d2b",
                "",
                "Лицензия на право использования ПО КриптоАРМ версии Про "
                "на одном рабочем месте, бессрочная",
            ),
            (
                "N-9b11db3f",
                "",
                "Неисключительная лицензия на право использования "
                "программного обеспечения Инструментальное средство "
                "разработки графических схем Асмо-графический редак",
            ),
            (
                "N-3c22f561",
                "",
                "Лицензия на право использования ПО КриптоАРМ версии "
                "Подпись и шифрование на одном рабочем месте, бессрочная",
            ),
        ],
    )

    items = load_sales_items(workbook_path)

    for item_id in (
        "N-b1331d2b",
        "N-9b11db3f",
        "N-3c22f561",
    ):
        assert items[item_id]["status"] == "ok"
        assert items[item_id]["match_key_type"] == "name"
        assert items[item_id]["sku_key"]

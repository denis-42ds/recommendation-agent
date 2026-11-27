from __future__ import annotations

import argparse
import gzip
import json
import re
import shutil
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from openpyxl import load_workbook

FEED_URL = "https://store.softline.ru/feeds/Mindbox.yml.gz"
WORKBOOK_PATH = Path("docs/source-materials/Датасет_Рекомендации_ЛК_v5.xlsx")
FEED_PATH = Path("docs/source-materials/Mindbox.yml.gz")
OUTPUT_DIR = Path("artifacts/catalog")


def normalize(value: object) -> str:
    if value is None:
        return ""
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].split(":")[-1]


def child_text(element: ET.Element, name: str) -> str:
    for child in element:
        if local_name(child.tag) == name:
            return (child.text or "").strip()
    return ""


def download_feed(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "RecommendationAgent-MVP/1.0"},
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            with temporary.open("wb") as output:
                shutil.copyfileobj(response, output, length=1024 * 1024)

        if temporary.stat().st_size == 0:
            raise ValueError("Downloaded feed is empty")

        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)



def load_sales_items(workbook_path: Path) -> dict[str, dict]:
    """Load unique item IDs and preserve conflicting source representations."""
    workbook = load_workbook(
        workbook_path,
        read_only=True,
        data_only=True,
    )

    try:
        sheet = workbook["Продажи"]
        rows = sheet.iter_rows(values_only=True)
        headers = [
            str(value).strip() if value is not None else ""
            for value in next(rows)
        ]

        required = {"item_id", "sku", "item_name"}
        missing = required - set(headers)
        if missing:
            raise ValueError(
                f"Missing columns in Продажи: {sorted(missing)}"
            )

        indexes = {name: headers.index(name) for name in required}

        representations: dict[str, set[tuple[str, str]]] = defaultdict(set)

        for row in rows:
            item_id = str(row[indexes["item_id"]] or "").strip()
            if not item_id:
                continue

            sku = str(row[indexes["sku"]] or "").strip()
            item_name = str(row[indexes["item_name"]] or "").strip()

            representations[item_id].add((sku, item_name))

        items: dict[str, dict] = {}

        for item_id, variants in representations.items():
            sorted_variants = sorted(variants)

            if len(sorted_variants) == 1:
                sku, item_name = sorted_variants[0]
                items[item_id] = {
                    "item_id": item_id,
                    "sku": sku,
                    "item_name": item_name,
                    "status": "ok",
                }
            else:
                items[item_id] = {
                    "item_id": item_id,
                    "sku": "",
                    "item_name": "",
                    "status": "ambiguous_source",
                    "source_variants": [
                        {"sku": sku, "item_name": name}
                        for sku, name in sorted_variants
                    ],
                }

        return items

    finally:
        workbook.close()


def category_path(
    category_id: str,
    categories: dict[str, dict[str, str]],
) -> list[str]:
    result: list[str] = []
    visited: set[str] = set()
    current = category_id

    while current and current in categories and current not in visited:
        visited.add(current)
        category = categories[current]
        result.append(category["name"])
        current = category["parent_id"]

    return list(reversed(result))


def parse_offer(
    element: ET.Element,
    categories: dict[str, dict[str, str]],
) -> dict:
    params: dict[str, list[str]] = defaultdict(list)

    for child in element:
        if local_name(child.tag) == "param":
            name = child.attrib.get("name", "").strip()
            value = (child.text or "").strip()
            if name and value:
                params[name].append(value)

    category_id = child_text(element, "categoryId")

    return {
        "offer_id": element.attrib.get("id", "").strip(),
        "available": element.attrib.get("available", "").lower() == "true",
        "name": child_text(element, "name"),
        "vendor": child_text(element, "vendor"),
        "vendor_code": child_text(element, "vendorCode"),
        "url": child_text(element, "url"),
        "category_id": category_id,
        "category_path": category_path(category_id, categories),
        "description": child_text(element, "description"),
        "params": dict(params),
    }


def iter_feed(feed_path: Path):
    """Yield one offer at a time. The full XML tree is never retained."""
    categories: dict[str, dict[str, str]] = {}

    with gzip.open(feed_path, "rb") as source:
        for _, element in ET.iterparse(source, events=("end",)):
            tag = local_name(element.tag)

            if tag == "category":
                category_id = element.attrib.get("id", "").strip()
                if category_id:
                    categories[category_id] = {
                        "name": (element.text or "").strip(),
                        "parent_id": element.attrib.get("parentId", "").strip(),
                    }
                element.clear()

            elif tag == "offer":
                yield parse_offer(element, categories)
                element.clear()


def build_url_pattern(sku_keys: set[str]) -> re.Pattern | None:
    if not sku_keys:
        return None

    alternatives = "|".join(
        re.escape(key)
        for key in sorted(sku_keys, key=len, reverse=True)
    )
    return re.compile(rf"^(?P<sku>{alternatives})(?P<suffix>[0-9]+)$")


def url_article_key(url: str) -> str:
    path = urlsplit(url).path.rstrip("/")
    return normalize(path.rsplit("/", 1)[-1]) if path else ""


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def build_catalog(
    workbook_path: Path,
    feed_path: Path,
    output_dir: Path,
    download_url: str = FEED_URL,
) -> dict:
    if not workbook_path.exists():
        raise FileNotFoundError(f"Workbook not found: {workbook_path}")

    if not feed_path.exists():
        print(f"Downloading feed from {download_url}")
        download_feed(download_url, feed_path)

    print("Reading sales items...")
    sales_items = load_sales_items(workbook_path)

    sku_to_items: dict[str, list[str]] = defaultdict(list)
    name_to_items: dict[str, list[str]] = defaultdict(list)

    ambiguous_source_ids = {
        item_id
        for item_id, item in sales_items.items()
        if item["status"] == "ambiguous_source"
    }
    
    for item_id, item in sales_items.items():
        if item["status"] != "ok":
            continue
    
        sku_key = normalize(item["sku"])

        if sku_key:
            sku_to_items[sku_key].append(item_id)

        if item_id.startswith("N-"):
            name_key = normalize(item["item_name"])
            if name_key:
                name_to_items[name_key].append(item_id)

    url_pattern = build_url_pattern(set(sku_to_items))
    candidates: dict[str, dict[str, str]] = defaultdict(dict)
    methods: dict[str, int] = defaultdict(int)

    output_dir.mkdir(parents=True, exist_ok=True)
    products_path = output_dir / "products.json"

    print("Streaming YML offers and writing products.json...")
    offer_count = 0

    with products_path.open("w", encoding="utf-8") as output:
        output.write("[\n")

        for product in iter_feed(feed_path):
            if offer_count:
                output.write(",\n")

            output.write(json.dumps(product, ensure_ascii=False))
            offer_count += 1

            # Prefer exact vendorCode match.
            vendor_key = normalize(product["vendor_code"])
            matched_item_ids = sku_to_items.get(vendor_key, [])

            if matched_item_ids:
                method = "vendorCode"
            else:
                # URL article format: normalized SKU + numeric offer ID.
                slug = url_article_key(product["url"])
                url_match = url_pattern.fullmatch(slug) if url_pattern else None

                if url_match:
                    matched_item_ids = sku_to_items.get(
                        url_match.group("sku"), []
                    )
                    method = "url_article"
                else:
                    matched_item_ids = []
                    method = ""

            # Name matching is reserved for N-* items.
            if not matched_item_ids:
                name_key = normalize(product["name"])
                matched_item_ids = name_to_items.get(name_key, [])
                method = "exact_name" if matched_item_ids else ""

            for item_id in matched_item_ids:
                offer_id = product["offer_id"]
                if offer_id:
                    candidates[item_id][offer_id] = method

        output.write("\n]\n")

    mapping: dict[str, dict] = {}

    for item_id in sales_items:
        if item_id in ambiguous_source_ids:
            mapping[item_id] = {
                "status": "ambiguous_source",
                "match_method": "conflicting_sales_rows",
                "offer_id": None,
            }
            methods["ambiguous_source"] += 1
            continue
    
        matches = candidates.get(item_id, {})

        if len(matches) == 1:
            offer_id, method = next(iter(matches.items()))
            # Availability is read from the product JSON by offer_id later.
            mapping[item_id] = {
                "status": "matched",
                "match_method": method,
                "offer_id": offer_id,
            }
            methods[method] += 1
        elif len(matches) > 1:
            mapping[item_id] = {
                "status": "ambiguous",
                "match_method": "multiple_offers",
                "offer_id": None,
            }
            methods["ambiguous"] += 1
        else:
            mapping[item_id] = {
                "status": "unmatched",
                "match_method": "no_match",
                "offer_id": None,
            }
            methods["unmatched"] += 1

    matched_count = sum(
        1 for value in mapping.values() if value["status"] == "matched"
    )
    ambiguous_count = sum(
        1 for value in mapping.values() if value["status"] == "ambiguous"
    )
    total = len(mapping)

    report = {
        "sales_item_count": total,
        "feed_offer_count": offer_count,
        "matched_item_count": matched_count,
        "ambiguous_item_count": ambiguous_count,
        "unmatched_item_count": total - matched_count - ambiguous_count,
        "match_rate": round(matched_count / total, 4) if total else 0.0,
        "match_methods": dict(sorted(methods.items())),
        "ambiguous_source_count": len(ambiguous_source_ids),
    }

    write_json(output_dir / "item_mapping.json", mapping)
    write_json(output_dir / "match_report.json", report)

    print("\nCatalog build completed.")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Output: {output_dir}")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a product catalog from the Softline YML feed."
    )
    parser.add_argument("--workbook", type=Path, default=WORKBOOK_PATH)
    parser.add_argument("--feed", type=Path, default=FEED_PATH)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    build_catalog(args.workbook, args.feed, args.output_dir)


if __name__ == "__main__":
    main()

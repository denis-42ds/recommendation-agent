from __future__ import annotations

import argparse
import gzip
import json
import shutil
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from openpyxl import load_workbook

FEED_URL = "https://store.softline.ru/feeds/Mindbox.yml.gz"
WORKBOOK_PATH = Path("docs/source-materials/Датасет_Рекомендации_ЛК_v5.xlsx")
FEED_PATH = Path("docs/source-materials/Mindbox.yml.gz")
OUTPUT_DIR = Path("artifacts/catalog")


def normalize(value: object) -> str:
    """Normalize SKU/name: uppercase Unicode letters and digits only."""
    if value is None:
        return ""

    return "".join(
        char
        for char in str(value).upper()
        if char.isalnum()
    )


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
    """
    Load one record per item_id.

    Different names do not create ambiguity when all rows have the same
    normalized SKU. For N-* items without SKU, normalized names are used.
    """
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
            normalized_skus = {
                normalize(sku)
                for sku, _ in sorted_variants
                if normalize(sku)
            }

            base = {
                "item_id": item_id,
                "source_variants": [
                    {"sku": sku, "item_name": name}
                    for sku, name in sorted_variants
                ],
            }

            if len(normalized_skus) == 1:
                # All non-empty SKUs are equivalent after normalization.
                # Keep a deterministic original representation for reporting.
                sku = next(
                    sku
                    for sku, _ in sorted_variants
                    if normalize(sku)
                )
                item_name = next(
                    (name for _, name in sorted_variants if name),
                    "",
                )
                items[item_id] = {
                    **base,
                    "sku": sku,
                    "item_name": item_name,
                    "sku_key": next(iter(normalized_skus)),
                    "match_key_type": "sku",
                    "status": "ok",
                }
                continue

            if not normalized_skus and item_id.startswith("N-"):
                normalized_names = {
                    normalize(name)
                    for _, name in sorted_variants
                    if normalize(name)
                }

                if len(normalized_names) == 1:
                    item_name = next(
                        name
                        for _, name in sorted_variants
                        if normalize(name)
                    )
                    items[item_id] = {
                        **base,
                        "sku": "",
                        "item_name": item_name,
                        "sku_key": next(iter(normalized_names)),
                        "match_key_type": "name",
                        "status": "ok",
                    }
                    continue

            items[item_id] = {
                **base,
                "sku": "",
                "item_name": "",
                "sku_key": "",
                "match_key_type": "",
                "status": "ambiguous_source",
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
    """Yield offers incrementally; do not retain the full XML tree."""
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


def url_article_match(url: str, offer_id: str, sku_key: str) -> bool:
    """
    Match only URLs shaped like <SKU>-<exact offer_id>.

    The offer ID must be the exact final URL component suffix. This prevents
    a numeric SKU from matching an unrelated numeric offer ID.
    """
    if not url or not offer_id or not sku_key:
        return False

    slug = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]
    suffix = f"-{offer_id}"

    if not slug.endswith(suffix):
        return False

    sku_part = slug[: -len(suffix)]
    return normalize(sku_part) == sku_key


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

    for item_id, item in sales_items.items():
        if item["status"] != "ok":
            continue

        key = item["sku_key"]
        if not key:
            continue

        if item["match_key_type"] == "sku":
            sku_to_items[key].append(item_id)
        elif item["match_key_type"] == "name":
            name_to_items[key].append(item_id)

    candidates: dict[str, dict[str, str]] = defaultdict(dict)
    methods: Counter[str] = Counter()

    output_dir.mkdir(parents=True, exist_ok=True)

    products_path = output_dir / "products.json"
    matched_products_path = output_dir / "matched_products.json"

    temporary_products_path = products_path.with_suffix(".json.part")
    temporary_matched_path = matched_products_path.with_suffix(".json.part")

    print("Streaming YML offers and writing catalog files...")

    offer_count = 0
    matched_offer_count = 0

    try:
        with (
            temporary_products_path.open("w", encoding="utf-8") as output,
            temporary_matched_path.open("w", encoding="utf-8") as matched_output,
        ):
            output.write("[\n")
            matched_output.write("[\n")

            for product in iter_feed(feed_path):
                if offer_count:
                    output.write(",\n")

                output.write(json.dumps(product, ensure_ascii=False))
                offer_count += 1

                offer_id = product["offer_id"]
                if not offer_id:
                    continue

                # 1. Exact normalized vendorCode match has priority.
                vendor_key = normalize(product["vendor_code"])
                matched_item_ids = sku_to_items.get(vendor_key, [])

                if matched_item_ids:
                    method = "vendorCode"
                else:
                    # 2. Exact URL structure: <SKU>-<this offer's ID>.
                    slug = (
                        urlsplit(product["url"]).path.rstrip("/").rsplit("/", 1)[-1]
                        if product["url"]
                        else ""
                    )
                    suffix = f"-{offer_id}"

                    if slug.endswith(suffix):
                        url_sku_key = normalize(slug[: -len(suffix)])
                        matched_item_ids = sku_to_items.get(url_sku_key, [])
                    else:
                        matched_item_ids = []

                    if matched_item_ids:
                        method = "url_article"
                    else:
                        # 3. Name matching is reserved for N-* items.
                        name_key = normalize(product["name"])
                        matched_item_ids = name_to_items.get(name_key, [])
                        method = "exact_name" if matched_item_ids else ""

                for item_id in matched_item_ids:
                    # Avoid duplicate item_id + offer_id records.
                    is_new_offer = offer_id not in candidates[item_id]
                    candidates[item_id][offer_id] = method

                    if not is_new_offer:
                        continue

                    if matched_offer_count:
                        matched_output.write(",\n")

                    matched_record = {
                        "item_id": item_id,
                        **product,
                    }

                    matched_output.write(
                        json.dumps(matched_record, ensure_ascii=False)
                    )
                    matched_offer_count += 1

            # Close both JSON arrays only after successful iteration.
            output.write("\n]\n")
            matched_output.write("\n]\n")

        # Publish only fully written files.
        temporary_products_path.replace(products_path)
        temporary_matched_path.replace(matched_products_path)

    finally:
        temporary_products_path.unlink(missing_ok=True)
        temporary_matched_path.unlink(missing_ok=True)

    mapping: dict[str, dict] = {}
    matched_count = 0
    multi_offer_count = 0
    unmatched_count = 0
    ambiguous_source_count = 0

    for item_id, item in sales_items.items():
        if item["status"] != "ok":
            mapping[item_id] = {
                "status": "ambiguous_source",
                "match_method": "conflicting_match_keys",
                "offer_ids": [],
                "match_count": 0,
            }
            ambiguous_source_count += 1
            continue

        item_candidates = candidates.get(item_id, {})
        offer_ids = sorted(
            item_candidates,
            key=lambda value: (not value.isdigit(), int(value) if value.isdigit() else value),
        )

        if offer_ids:
            item_methods = sorted(set(item_candidates.values()))
            mapping[item_id] = {
                "status": "matched",
                "match_method": (
                    item_methods[0]
                    if len(item_methods) == 1
                    else "multiple_methods"
                ),
                "match_methods": item_methods,
                "offer_ids": offer_ids,
                "match_count": len(offer_ids),
            }
            matched_count += 1
            if len(offer_ids) > 1:
                multi_offer_count += 1

            for method in item_methods:
                methods[method] += 1
        else:
            mapping[item_id] = {
                "status": "unmatched",
                "match_method": "no_match",
                "offer_ids": [],
                "match_count": 0,
            }
            unmatched_count += 1
            methods["unmatched"] += 1

    total = len(mapping)
    report = {
        "sales_item_count": total,
        "feed_offer_count": offer_count,
        "matched_offer_count": matched_offer_count,
        "matched_item_count": matched_count,
        "multi_offer_item_count": multi_offer_count,
        "ambiguous_item_count": 0,
        "ambiguous_source_count": ambiguous_source_count,
        "unmatched_item_count": unmatched_count + ambiguous_source_count,
        "unmatched_without_source_conflict_count": unmatched_count,
        "match_rate": round(matched_count / total, 4) if total else 0.0,
        "match_methods": dict(sorted(methods.items())),
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

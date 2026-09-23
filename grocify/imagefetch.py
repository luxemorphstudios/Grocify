"""Fetch product photos from open databases.

Two sources, both openly licensed:

* **Open Food Facts** (and its Open Beauty Facts / Open Products Facts
  siblings) - real packshots of branded groceries, the same kind of picture a
  shopping app shows. Photos there are CC BY-SA 3.0.
* **Wikimedia Commons** - for loose items like vegetables and fruit, which have
  no barcode and so are not in a product database.

Every download records where the photo came from and under which licence, so
the project can credit them. Run it with:

    python -m flask --app run.py fetch-images
"""
import io
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from .db import execute, query

API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "Grocify/1.0 (college project; product catalogue images)"

# Wikimedia asks for a polite request rate.
REQUEST_PAUSE = 1.1

THUMB_WIDTH = 700
OUTPUT_SIZE = 600

# Licences we are allowed to reuse as long as we credit the author.
OK_LICENCES = ("cc0", "cc by", "cc-by", "public domain", "pd-", "no restrictions")
BAD_LICENCES = ("fair use", "non-free", "all rights reserved")

# Search terms per product, best first. A product not listed here falls back to
# its own name, so the command still works for items you add yourself.
SEARCH_TERMS = {
    "Amul Gold Milk 1L":         ["milk pouch india", "milk packet"],
    "Amul Butter 500g":          ["amul butter", "butter pack"],
    "Fresh Paneer 200g":         ["paneer cheese", "paneer"],
    "Curd Cup 400g":             ["dahi curd bowl", "yogurt cup"],
    "Cheese Slices 200g":        ["cheese slices", "processed cheese slice"],
    "Tomato":                    ["tomato fruit", "tomatoes"],
    "Onion":                     ["mixed onions", "onion bulb"],
    "Potato":                    ["potatoes tubers", "potato"],
    "Spinach Bunch":             ["spinach leaves bunch", "spinach"],
    "Green Chilli":              ["green chili peppers", "green chilli"],
    "Banana":                    ["bananas fruit", "banana bunch"],
    "Apple Shimla":              ["red apples", "apple fruit"],
    "Orange":                    ["orange fruit citrus", "oranges"],
    "Parle-G Biscuit 250g":      ["parle-g", "glucose biscuits"],
    "Lays Classic 52g":          ["potato crisps bag", "potato chips packet"],
    "Haldiram Bhujia 200g":      ["bhujia namkeen", "sev namkeen"],
    "Marie Gold 300g":           ["marie biscuit", "tea biscuits"],
    "Tata Tea Gold 500g":        ["tea leaves loose", "black tea leaves"],
    "Nescafe Classic 100g":      ["instant coffee jar", "coffee granules jar"],
    "Real Mixed Fruit 1L":       ["fruit juice carton", "juice tetra pak"],
    "Coca Cola 750ml":           ["coca-cola bottle", "cola bottle"],
    "India Gate Basmati 5kg":    ["basmati rice bag", "basmati rice"],
    "Aashirvaad Atta 5kg":       ["wheat flour packet", "atta wheat flour"],
    "Toor Dal 1kg":              ["toor dal pigeon pea", "yellow lentils dal"],
    "Sugar 1kg":                 ["white sugar crystals", "sugar bowl"],
    "Sunflower Oil 1L":          ["sunflower oil bottle", "cooking oil bottle"],
    "Dove Soap 100g":            ["dove soap bar", "soap bar"],
    "Colgate Strong Teeth 200g": ["colgate toothpaste", "toothpaste tube"],
    "Clinic Plus Shampoo 340ml": ["shampoo bottle", "hair shampoo bottle"],
    "Surf Excel 1kg":            ["detergent powder packet", "washing powder"],
    "Vim Dishwash Bar":          ["dishwashing soap bar", "dish soap bar"],
    "Harpic 500ml":              ["toilet cleaner bottle", "cleaning liquid bottle"],
    "Garbage Bags (30 pcs)":     ["bin bags roll", "garbage bag"],
    "Steel Scrubber":            ["steel wool scourer", "scouring pad"],
    "Eggs":                      ["chicken eggs carton", "eggs"],
}


# Branded, barcoded products: look for a real packshot first.
# Each entry is (search term, which database: 0 food, 1 beauty, 2 other products).
PACKSHOT_TERMS = {
    "Amul Gold Milk 1L":         [("Amul gold milk", 0), ("Amul taaza milk", 0)],
    "Amul Butter 500g":          [("Amul butter", 0)],
    "Cheese Slices 200g":        [("Amul cheese slices", 0), ("cheese slices", 0)],
    "Parle-G Biscuit 250g":      [("Parle-G glucose biscuits", 0), ("Parle G", 0)],
    "Lays Classic 52g":          [("Lay's classic salted", 0)],
    "Haldiram Bhujia 200g":      [("Haldiram bhujia", 0), ("Haldiram namkeen", 0)],
    "Marie Gold 300g":           [("Britannia Marie Gold", 0), ("Marie Gold biscuits", 0)],
    "Tata Tea Gold 500g":        [("Tata Tea Gold", 0), ("Tata tea", 0)],
    "Nescafe Classic 100g":      [("Nescafe classic", 0)],
    "Real Mixed Fruit 1L":       [("Real fruit power mixed fruit", 0)],
    "Coca Cola 750ml":           [("Coca-Cola original bottle", 0)],
    "India Gate Basmati 5kg":    [("India Gate basmati rice", 0)],
    "Aashirvaad Atta 5kg":       [("Aashirvaad atta", 0), ("Aashirvaad whole wheat", 0)],
    "Sunflower Oil 1L":          [("Fortune sunflower oil", 0), ("sunflower oil", 0)],
    "Toor Dal 1kg":              [("toor dal", 0), ("tur dal", 0)],
    "Sugar 1kg":                 [("sugar 1kg", 0)],
    "Colgate Strong Teeth 200g": [("Colgate strong teeth", 1), ("Colgate toothpaste", 1)],
    "Dove Soap 100g":            [("Dove beauty bar soap", 1), ("Dove soap", 1)],
    "Clinic Plus Shampoo 340ml": [("Clinic Plus shampoo", 1), ("clinic plus", 1)],
    "Surf Excel 1kg":            [("Surf Excel", 2), ("Surf Excel detergent", 0)],
    "Vim Dishwash Bar":          [("Vim dishwash bar", 2), ("Vim bar", 0)],
    "Harpic 500ml":              [("Harpic toilet cleaner", 2), ("Harpic", 0)],
    "Garbage Bags (30 pcs)":     [("garbage bags", 2), ("bin liners", 2)],
}


def _request(url, timeout=25, tries=4):
    """GET with a polite user agent and a retry when Wikimedia rate-limits us."""
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < tries - 1:
                time.sleep(4 * (attempt + 1))
                continue
            raise
    raise RuntimeError("request failed: " + url)


def _licence_ok(text):
    low = (text or "").lower()
    if not low or any(bad in low for bad in BAD_LICENCES):
        return False
    return any(ok in low for ok in OK_LICENCES)


def _strip_html(text):
    out, skip = [], False
    for ch in text or "":
        if ch == "<":
            skip = True
        elif ch == ">":
            skip = False
        elif not skip:
            out.append(ch)
    return " ".join("".join(out).split())


def search(term, limit=6):
    """Return candidate pictures for a search term, best match first."""
    params = urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": "filetype:bitmap " + term, "gsrlimit": limit, "gsrnamespace": 6,
        "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": THUMB_WIDTH,
    })
    data = json.loads(_request(API + "?" + params))
    pages = ((data.get("query") or {}).get("pages") or {}).values()

    results = []
    for page in sorted(pages, key=lambda p: p.get("index", 99)):
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        licence = meta.get("LicenseShortName", {}).get("value", "")
        if not _licence_ok(licence):
            continue
        url = info.get("thumburl") or info.get("url")
        if not url:
            continue
        results.append({
            "title": page["title"].replace("File:", ""),
            "url": url,
            "page": info.get("descriptionurl", ""),
            "licence": _strip_html(licence),
            "author": _strip_html(meta.get("Artist", {}).get("value", "")) or "Unknown",
        })
    return results


# The Open Food Facts family. Food first, then cosmetics, then everything else.
OFF_DOMAINS = (
    ("Open Food Facts", "https://world.openfoodfacts.org"),
    ("Open Beauty Facts", "https://world.openbeautyfacts.org"),
    ("Open Products Facts", "https://world.openproductsfacts.org"),
)

OFF_PAUSE = 1.5


def off_search(term, domain_index=0, limit=4):
    """Search one Open Food Facts database for a branded product packshot."""
    label, base = OFF_DOMAINS[domain_index]
    params = urllib.parse.urlencode({
        "search_terms": term, "search_simple": 1, "action": "process", "json": 1,
        "page_size": limit,
        "fields": "code,product_name,brands,quantity,image_front_url",
    })
    data = json.loads(_request(base + "/cgi/search.pl?" + params))

    results = []
    for product in data.get("products", []):
        image = product.get("image_front_url")
        if not image:
            continue
        name = (product.get("product_name") or "").strip() or term
        brand = (product.get("brands") or "").strip()
        results.append({
            "title": ("%s %s" % (brand, name)).strip(),
            "url": image,
            "page": "%s/product/%s" % (base, product.get("code", "")),
            "licence": "CC BY-SA 3.0",
            "author": label + " contributors",
            "quantity": (product.get("quantity") or "").strip(),
        })
    return results


def to_square_jpeg(raw, size=OUTPUT_SIZE, pad=False):
    """Centre-crop to a square and shrink, so every tile looks consistent.

    Pillow decoding the file is also our proof that it really is an image.
    """
    from PIL import Image

    image = Image.open(io.BytesIO(raw))
    image.load()
    if image.mode != "RGB":
        image = image.convert("RGB")

    if pad:
        # Packshots are tall and narrow; cropping would slice the packet in
        # half, so fit the whole thing on a white square instead.
        image.thumbnail((size, size), Image.LANCZOS)
        canvas = Image.new("RGB", (size, size), "white")
        canvas.paste(image, ((size - image.width) // 2, (size - image.height) // 2))
        image = canvas
    else:
        width, height = image.size
        side = min(width, height)
        left, top = (width - side) // 2, (height - side) // 2
        image = image.crop((left, top, left + side, top + side))
        if side > size:
            image = image.resize((size, size), Image.LANCZOS)

    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=82, optimize=True, progressive=True)
    return buffer.getvalue()


def fetch_for(name, terms=None, candidate=0):
    """Find a picture for one product name. Returns (jpeg_bytes, credit) or None.

    Branded groceries try Open Food Facts first, because a real packshot looks
    far more like a shop than a stock photo does. Loose produce, and anything
    the product databases do not know, falls back to Wikimedia Commons.
    """
    if terms is None:
        packshot = _fetch_packshot(name, candidate)
        if packshot is not None:
            return packshot

    for term in (terms or SEARCH_TERMS.get(name) or [name]):
        try:
            results = search(term)
        except Exception:
            time.sleep(REQUEST_PAUSE)
            continue
        time.sleep(REQUEST_PAUSE)

        for result in results[candidate:]:
            try:
                raw = _request(result["url"])
                jpeg = to_square_jpeg(raw)
            except Exception:
                continue
            credit = "%s by %s (%s) - %s" % (
                result["title"], result["author"], result["licence"], result["page"])
            return jpeg, credit
    return None


def _fetch_packshot(name, candidate=0):
    """Try the Open Food Facts family for a real photo of the packaging."""
    for term, domain_index in PACKSHOT_TERMS.get(name, []):
        try:
            results = off_search(term, domain_index=domain_index)
        except Exception:
            time.sleep(OFF_PAUSE)
            continue
        time.sleep(OFF_PAUSE)

        for result in results[candidate:]:
            try:
                jpeg = to_square_jpeg(_request(result["url"]), pad=True)
            except Exception:
                continue
            credit = "%s from %s (%s) - %s" % (
                result["title"], result["author"], result["licence"], result["page"])
            return jpeg, credit
    return None


def store(product_id, jpeg, credit, upload_dir):
    """Write the picture next to the other uploads and point the product at it."""
    import os

    from .uploads import delete_image

    old = query("SELECT image FROM products WHERE id = ?", (product_id,), one=True)
    filename = uuid.uuid4().hex + ".jpg"
    os.makedirs(upload_dir, exist_ok=True)
    with open(os.path.join(upload_dir, filename), "wb") as fh:
        fh.write(jpeg)

    execute("UPDATE products SET image = ?, image_credit = ? WHERE id = ?",
            (filename, credit, product_id))
    if old and old["image"]:
        delete_image(old["image"])
    return filename


MANIFEST = "manifest.json"


def write_manifest(upload_dir):
    """Remember which photo belongs to which product name.

    ``seed-db`` drops every table, so without this the downloaded photos would
    be orphaned every time the demo data is reset. The manifest lets seeding
    re-attach them by product name - no re-downloading.
    """
    import os

    rows = query("""SELECT name, image, image_credit FROM products
                     WHERE image IS NOT NULL AND image <> ''""")
    data = {r["name"]: {"image": r["image"], "credit": r["image_credit"]} for r in rows}
    with open(os.path.join(upload_dir, MANIFEST), "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, sort_keys=True)
    return len(data)


def write_credits(path):
    """Regenerate CREDITS.md from whatever is currently in the database."""
    rows = query("""SELECT name, image, image_credit FROM products
                     WHERE image_credit IS NOT NULL AND image IS NOT NULL
                     ORDER BY name COLLATE NOCASE""")
    lines = [
        "# Photo credits",
        "",
        "Product photos in this folder come from **Wikimedia Commons** and are used",
        "under the licence shown next to each one. Each entry lists the file name,",
        "the photographer and a link to the original page.",
        "",
    ]
    for r in rows:
        lines.append("- **%s** (`%s`) - %s" % (r["name"], r["image"], r["image_credit"]))
    if not rows:
        lines.append("_No downloaded photos yet._")
    lines.append("")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return len(rows)

# Grocify — Grocery Store Management System

A complete grocery shop management system: billing counter, inventory with
low-stock and expiry alerts, supplier records, staff accounts and sales reports.

**Stack:** Python **Flask** · **SQLite** (single file database) · **Bootstrap 5** +
Jinja2 templates · **Chart.js** for graphs. No ORM, no build step, no Node.js.

---

## 1. Run it (3 steps)

```bash
pip install -r requirements.txt
```

```bash
python -m flask --app run.py seed-db
```

```bash
python run.py
```

Then open **http://127.0.0.1:5000**

| Role | Username | Password |
|---|---|---|
| Administrator | `admin` | `admin123` |
| Staff / Cashier | `priya` | `staff123` |
| Staff / Cashier | `rahul` | `staff123` |

These seeded accounts are **not** shown on the sign-in page. Anyone can also
create their own account with **Create an account** on that page - see
*Accounts and passwords* below.

`seed-db` creates the tables **and** fills them with demo data (34 products,
8 categories, 4 suppliers and ~140 bills spread over the last 30 days) so every
screen and chart has something to show during your demo.

Want to start completely empty instead? Use `python -m flask --app run.py init-db`
— same tables, no data. Both commands **erase everything** that was there before.

---

## 2. What each page does

| Page | Who can open it | What it does |
|---|---|---|
| **Dashboard** | everyone | Today's sales, stock value, low-stock and expiry counts, 7-day sales chart, top sellers, recent bills |
| **Billing counter** | everyone | Pick products from a picture grid, build a cart, apply discount + GST, save the bill and print it |
| **Bills** | everyone | Search bills by invoice/customer/date; admins can cancel a bill (stock goes back) |
| **Products** | everyone (admin can edit) | Add/edit/delete products **with a photo**; filter by category, low stock, out of stock, expiring, expired |
| **Categories** | admin | Group products; shows product count and stock value per category |
| **Stock in** | admin | Record goods received from a supplier — quantity is added to the product automatically |
| **Suppliers** | admin | Supplier contact details and how much has been purchased from each |
| **Reports** | admin | Date-range sales report with charts, best sellers, sales per cashier, payment mix, CSV export |
| **Staff accounts** | admin | Create/edit/disable/delete staff and admin logins |
| **Settings** | admin | Shop name, address, phone (printed on bills), currency, default GST rate, expiry warning days |

Staff who try to open an admin page are redirected with a message — the check is
on the server (`@admin_required`), not just hidden menu links.

### Accounts and passwords

The sign-in page has a **Create an account** link. Anyone can register as
**Staff / Cashier** and sign in straight afterwards. Registering as an
**Administrator** also requires an administrator code (see below). An
administrator can create accounts of either kind from the *Staff accounts*
page without needing the code.

A new password must be:

- at least **8 characters** long, and
- contain at least **one special character** (anything that is not a letter or
  a digit, such as `! @ # $ % &`).

The rules are checked twice: in the browser while you type, for instant
feedback, and again on the server in `validate_password()`, which is the check
that actually decides. Anything done in the browser can be bypassed by editing
the page, so the server always has the final say.

The seeded `admin` / `admin123` account predates these rules and still works --
existing passwords are not forced to change. The moment that account sets a new
password, the new rules apply.

### The administrator code

Staff sign-up is open, but nobody should be able to hand themselves full
control of prices, stock and staff just by picking "Administrator" from a
dropdown. So administrator sign-up is gated by a code:

| Situation | What happens |
|---|---|
| The database has no administrator yet | The first account may be created as an administrator with no code. Without this, a fresh clone could never get its first admin. |
| An administrator exists but no code is set | Administrator sign-up is refused entirely. Admins can still be created from the *Staff accounts* page. |
| A code is set | It must be entered on the sign-up form and must match. |

An administrator sets, replaces or clears the code in **Settings -> Administrator
sign-up**. Clearing it turns administrator sign-up off again.

Three details worth knowing, and worth saying in a viva:

- **The code is stored as a hash**, using the same function as passwords. It is
  never kept as readable text, so reading the database file does not reveal it.
  It can be replaced but never read back - if it is forgotten, set a new one.
- **It is not in the source code.** Putting a fixed code in a Python file would
  be pointless here, because this repository is public - anyone could read it on
  GitHub. Keeping it in the database means the secret never leaves the shop.
- **Settings ending in `_hash` are filtered out** of the data passed to
  templates, so the hash cannot be printed onto a page by accident.

If you would rather not have public administrator sign-up at all, leave the code
unset: the form then refuses every administrator registration, and admins are
created only from the *Staff accounts* page.

### Product photos

Admins can attach a photo when adding or editing a product (PNG, JPG, GIF or
WEBP, up to 2 MB). Photos appear in the product table, the dashboard alert
lists and the billing counter's product grid.

Products **without** a photo are not left blank — they show a coloured tile with
the first letter of the name, and the colour is derived from the name, so the
same product always looks the same on every screen. The app looks complete
before you have uploaded a single picture.

The seeded catalogue already ships with a **real photo for every product**,
downloaded from Wikimedia Commons (see *Where the photos came from* below).

How uploads are handled:

- Files are saved in `grocify/static/uploads/products/` under a **random name**
  (`a1b2c3....png`), so nothing a user types ever becomes a file path.
- The extension must be an image extension **and** the first bytes of the file
  must really be a PNG/JPG/GIF/WEBP — renaming `virus.exe` to `photo.png` is
  rejected.
- Replacing or removing a photo, or deleting the product, deletes the old file
  so the folder does not fill up with orphans.

### Where the photos came from

The catalogue photos were downloaded with a built-in command:

```bash
python -m flask --app run.py fetch-images
```

It uses two open sources:

- **Open Food Facts** (plus its Open Beauty Facts and Open Products Facts
  siblings) for branded, barcoded groceries - these are real packshots of the
  actual packaging, the same kind of picture a shopping app shows. Photos there
  are CC BY-SA 3.0.
- **Wikimedia Commons** for loose items like vegetables and fruit, which have no
  barcode and so are not in a product database. Only openly licensed pictures
  are kept (public domain, CC0, CC BY, CC BY-SA).

Packshots are padded onto a white 600x600 square (so a tall packet is not sliced
in half) and produce photos are centre-cropped to the same size, so every tile
lines up. The source and licence of each photo are recorded.
Every photo is credited in
[`grocify/static/uploads/products/CREDITS.md`](grocify/static/uploads/products/CREDITS.md)
— keep that file if you publish the project, because CC BY / CC BY-SA require
attribution.

Useful options:

```bash
python -m flask --app run.py fetch-images --only "Eggs"
```

| Option | What it does |
|---|---|
| *(no options)* | Fetch a photo for every product that does not have one |
| `--only "Name"` | Just that one product |
| `--terms "brown eggs"` | Use your own search words instead of the built-in ones |
| `--candidate 1` | Skip the first search hit and take the next one |
| `--force` | Replace photos that are already set |

**Check what you get.** A search engine is not a shop catalogue. When this
catalogue was built, roughly a third of the first Wikimedia results were wrong
or unsuitable (a loaf of bread for wheat flour, an unrelated portrait for
butter, and a set of early-1900s adverts with racist caricatures for washing
powder). Every photo in this project was looked at before being kept. Do the
same after a fetch and re-run the odd ones with `--terms`.

Photos are **not** taken from Zepto, Blinkit, Amazon or BigBasket: those images
are the retailers' copyrighted assets and scraping them breaches their terms.
Open Food Facts gives the same packshot look, openly licensed.

Downloaded photos are listed in `manifest.json` next to them, so running
`seed-db` again **keeps every picture** instead of orphaning the files.

---

## 3. Project structure

```
Grocify/
├── run.py                  # start the dev server
├── requirements.txt
├── instance/
│   └── grocify.sqlite      # THE DATABASE — one file, submit this with your project
└── grocify/
    ├── __init__.py         # create_app(): config, blueprints, error pages
    ├── schema.sql          # all CREATE TABLE statements
    ├── db.py               # sqlite3 connection + query/execute helpers + CLI commands
    ├── seed.py             # demo data
    ├── helpers.py          # login_required / admin_required, money & date filters
    ├── uploads.py          # product photo saving, validation and cleanup
    ├── imagefetch.py       # downloads openly licensed photos from Wikimedia Commons
    ├── views/
    │   ├── auth.py         # login, logout, change password
    │   ├── dashboard.py    # home page
    │   ├── products.py     # products, categories, stock-in, /api/products
    │   ├── billing.py      # POS, checkout, bills, invoice
    │   ├── people.py       # suppliers, staff accounts, settings
    │   └── reports.py      # reports + CSV export
    ├── templates/          # Jinja2 pages (base.html holds the layout)
    └── static/
        ├── uploads/products/   # product photos + CREDITS.md + manifest.json
        ├── css/style.css   # design tokens, app shell, components, print styles
        └── js/
            ├── app.js      # theme switch, confirm dialogs, modal filling
            └── pos.js      # billing counter: search, cart, live totals
```

---

## 4. Database tables

`users`, `categories`, `suppliers`, `products`, `stock_entries`, `sales`,
`sale_items`, `settings` — see [`grocify/schema.sql`](grocify/schema.sql).

Two design details worth mentioning in a viva:

- **`sale_items` stores a copy of `product_name`, `unit` and `price`.** An old
  bill still prints correctly even after the product is renamed, repriced or
  deleted. That is how real billing systems work.
- **Stock is never trusted from the browser.** On checkout the server re-reads
  every price and quantity from the database, refuses the sale if stock is
  short, and writes the sale + reduces stock in one transaction that is rolled
  back if anything fails.

---

## 5. Things you may want to do manually

1. **Internet is needed the first time a page loads.** Bootstrap, Bootstrap
   Icons, Chart.js and the Inter font come from a CDN. The browser caches them,
   but if you have to demo on a machine with no internet at all, tell me and I
   will download those four files into `static/vendor/` and point the templates
   at them instead.
2. **Nothing else is required to install** — Flask is the only dependency and it
   was already present on this machine, so `pip install` may print
   "Requirement already satisfied".
3. **Back up / submit your data** by copying `instance/grocify.sqlite` **and**
   `grocify/static/uploads/products/` (the database stores only the file name,
   the pictures themselves live in that folder). Deleting the database file and
   re-running `seed-db` gives you a fresh start.
4. **Before the demo, re-run `seed-db`** if you have been clicking around — it
   resets the shop to clean, believable data, and the product photos are
   re-attached automatically.
5. **Change the demo passwords** from *Staff accounts* if your college expects
   it - note the new password rules apply, so `admin123` will not be accepted
   as a replacement. Set a real `SECRET_KEY` (environment variable `GROCIFY_SECRET_KEY`)
   if you ever host this publicly. For a local college project the built-in
   default is fine.
6. **Put it on GitHub** so your team can work together:

```bash
git init && git add . && git commit -m "Grocify: grocery store management system"
```

`.gitignore` already excludes `instance/` and `__pycache__/`, so the database
does not fight you in merges. Uploaded photos *are* committed, so your
teammates see the same catalogue. If you *want* to hand the data in through Git,
run `git add -f instance/grocify.sqlite`.

---

## 6. Ideas if you have extra time

- PDF bills (add `reportlab` or use the browser's "Save as PDF" in the print dialog — already works)
- Customer records with purchase history (the bills already store name + phone)
- Barcode scanning at the billing counter (a scanner types into the search box, so it nearly works already)
- Automatic resizing of *uploaded* photos (downloaded ones are already resized to 600x600 with Pillow)
- Profit report using `cost_price`, which is already recorded for every product

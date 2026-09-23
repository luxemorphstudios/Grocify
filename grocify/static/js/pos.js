/* Billing counter: product search, cart, live totals. */
(function () {
  "use strict";

  var root = document.getElementById("pos");
  if (!root) return;

  var CURRENCY = root.dataset.currency || "₹";
  var IMAGE_BASE = root.dataset.imageBase || "";

  var els = {
    search:   document.getElementById("posSearch"),
    category: document.getElementById("posCategory"),
    grid:     document.getElementById("posGrid"),
    cart:     document.getElementById("cartItems"),
    count:    document.getElementById("cartCount"),
    subtotal: document.getElementById("sumSubtotal"),
    gstLabel: document.getElementById("sumGstLabel"),
    gstValue: document.getElementById("sumGst"),
    total:    document.getElementById("sumTotal"),
    discount: document.getElementById("discountInput"),
    gstRate:  document.getElementById("gstRateInput"),
    payload:  document.getElementById("cartPayload"),
    submit:   document.getElementById("checkoutBtn"),
    form:     document.getElementById("checkoutForm"),
    clear:    document.getElementById("clearCart")
  };

  var products = [];
  var cart = [];          // [{id, name, price, unit, stock, qty}]

  function money(value) {
    var n = Number(value || 0);
    var sign = n < 0 ? "-" : "";
    var parts = Math.abs(n).toFixed(2).split(".");
    var whole = parts[0], tail = "";
    if (whole.length > 3) {
      tail = whole.slice(-3);
      var head = whole.slice(0, -3), groups = [];
      while (head.length > 2) { groups.unshift(head.slice(-2)); head = head.slice(0, -2); }
      if (head) groups.unshift(head);
      whole = groups.join(",") + "," + tail;
    }
    return sign + CURRENCY + whole + "." + parts[1];
  }

  function qtyText(value) {
    return Number(value) % 1 === 0 ? String(Number(value)) : String(value);
  }

  // Same formula as hue() in grocify/helpers.py, so a product without a photo
  // gets the same colour here as it does in the product table.
  function hueOf(text) {
    var total = 0;
    for (const ch of String(text || "")) {
      total = (total * 31 + ch.codePointAt(0)) % 360;
    }
    return total;
  }

  function thumbHtml(product, extraClass) {
    if (product.image) {
      return '<img class="thumb ' + extraClass + '" loading="lazy" alt="" src="' +
             IMAGE_BASE + encodeURIComponent(product.image) + '">';
    }
    return '<span class="thumb thumb-fallback ' + extraClass + '" aria-hidden="true" ' +
           'style="--hue:' + hueOf(product.name) + '">' +
           escapeHtml(product.name.charAt(0).toUpperCase()) + '</span>';
  }

  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  // ------------------------------------------------------------ catalogue
  function visibleProducts() {
    var term = (els.search.value || "").trim().toLowerCase();
    var category = els.category.value;
    return products.filter(function (p) {
      if (category && p.category !== category) return false;
      if (!term) return true;
      return p.name.toLowerCase().indexOf(term) !== -1 ||
             p.category.toLowerCase().indexOf(term) !== -1;
    });
  }

  function renderGrid() {
    var list = visibleProducts();
    if (!list.length) {
      els.grid.innerHTML =
        '<div class="empty" style="grid-column:1/-1">' +
        '<i class="bi bi-search"></i><p>No product matches that search.</p></div>';
      return;
    }
    els.grid.innerHTML = list.slice(0, 200).map(function (p) {
      var out = p.quantity <= 0;
      return '<button type="button" class="product-tile" data-id="' + p.id + '"' +
             (out ? " disabled" : "") + '>' +
             thumbHtml(p, "p-thumb") +
             '<span class="p-name">' + escapeHtml(p.name) + '</span>' +
             '<span class="p-meta">' + escapeHtml(p.category) + '</span>' +
             '<span class="p-price">' + money(p.price) +
             ' <span class="p-meta">/ ' + escapeHtml(p.unit) + '</span></span>' +
             '<span class="p-meta">' + (out
               ? '<span class="chip chip-danger">Out of stock</span>'
               : 'In stock: ' + qtyText(p.quantity)) + '</span>' +
             '</button>';
    }).join("");
  }

  // ----------------------------------------------------------------- cart
  function addToCart(id) {
    var product = products.find(function (p) { return p.id === id; });
    if (!product || product.quantity <= 0) return;

    var line = cart.find(function (c) { return c.id === id; });
    if (line) {
      if (line.qty + 1 > product.quantity) { flashLimit(product); return; }
      line.qty += 1;
    } else {
      cart.push({
        id: product.id, name: product.name, price: product.price,
        unit: product.unit, stock: product.quantity, image: product.image, qty: 1
      });
    }
    renderCart();
  }

  function setQty(id, value) {
    var line = cart.find(function (c) { return c.id === id; });
    if (!line) return;
    var next = Number(value);
    if (isNaN(next) || next <= 0) { cart = cart.filter(function (c) { return c.id !== id; }); }
    else if (next > line.stock) { line.qty = line.stock; flashLimit(line); }
    else { line.qty = next; }
    renderCart();
  }

  function flashLimit(product) {
    var note = document.getElementById("stockNote");
    if (!note) return;
    note.textContent = "Only " + qtyText(product.stock || product.quantity) + " " +
                       product.unit + " of " + product.name + " left in stock.";
    note.classList.remove("d-none");
    clearTimeout(flashLimit.timer);
    flashLimit.timer = setTimeout(function () { note.classList.add("d-none"); }, 3500);
  }

  function renderCart() {
    if (!cart.length) {
      els.cart.innerHTML =
        '<div class="empty"><i class="bi bi-cart3"></i>' +
        '<p>Cart is empty.<br><small>Tap a product to add it.</small></p></div>';
    } else {
      els.cart.innerHTML = cart.map(function (c) {
        return '<div class="cart-row" data-id="' + c.id + '">' +
          thumbHtml(c, "cart-thumb") +
          '<div class="min-w-0">' +
            '<div class="cart-name">' + escapeHtml(c.name) + '</div>' +
            '<div class="cart-sub">' + money(c.price) + ' / ' + escapeHtml(c.unit) + '</div>' +
            '<div class="cart-controls mt-1">' +
              '<button type="button" class="qty-btn" data-step="-1">&minus;</button>' +
              '<input class="qty-input" type="number" min="0" step="any" value="' + c.qty + '">' +
              '<button type="button" class="qty-btn" data-step="1">+</button>' +
              '<button type="button" class="qty-btn text-danger ms-1" data-remove="1" ' +
                'title="Remove"><i class="bi bi-trash"></i></button>' +
            '</div>' +
          '</div>' +
          '<div class="cart-line-total">' + money(c.qty * c.price) + '</div>' +
        '</div>';
      }).join("");
    }

    els.count.textContent = cart.length;
    recalculate();
  }

  function recalculate() {
    var subtotal = cart.reduce(function (sum, c) { return sum + c.qty * c.price; }, 0);
    var discount = Math.min(Math.max(Number(els.discount.value) || 0, 0), subtotal);
    var rate = Math.max(Number(els.gstRate.value) || 0, 0);
    var gst = (subtotal - discount) * rate / 100;

    els.subtotal.textContent = money(subtotal);
    els.gstLabel.textContent = "GST (" + rate + "%)";
    els.gstValue.textContent = money(gst);
    els.total.textContent = money(subtotal - discount + gst);
    els.submit.disabled = cart.length === 0;
  }

  // -------------------------------------------------------------- events
  els.grid.addEventListener("click", function (e) {
    var tile = e.target.closest(".product-tile");
    if (tile) addToCart(Number(tile.dataset.id));
  });

  els.cart.addEventListener("click", function (e) {
    var row = e.target.closest(".cart-row");
    if (!row) return;
    var id = Number(row.dataset.id);
    var line = cart.find(function (c) { return c.id === id; });
    if (!line) return;

    if (e.target.closest("[data-remove]")) {
      cart = cart.filter(function (c) { return c.id !== id; });
      renderCart();
      return;
    }
    var stepper = e.target.closest("[data-step]");
    if (stepper) setQty(id, line.qty + Number(stepper.dataset.step));
  });

  els.cart.addEventListener("change", function (e) {
    if (!e.target.classList.contains("qty-input")) return;
    var row = e.target.closest(".cart-row");
    setQty(Number(row.dataset.id), e.target.value);
  });

  els.search.addEventListener("input", renderGrid);
  els.category.addEventListener("change", renderGrid);
  els.discount.addEventListener("input", recalculate);
  els.gstRate.addEventListener("input", recalculate);

  // Enter in the search box adds the first matching product.
  els.search.addEventListener("keydown", function (e) {
    if (e.key !== "Enter") return;
    e.preventDefault();
    var first = visibleProducts().filter(function (p) { return p.quantity > 0; })[0];
    if (first) {
      addToCart(first.id);
      els.search.value = "";
      renderGrid();
    }
  });

  if (els.clear) {
    els.clear.addEventListener("click", function () {
      cart = [];
      renderCart();
    });
  }

  els.form.addEventListener("submit", function (e) {
    if (!cart.length) { e.preventDefault(); return; }
    els.payload.value = JSON.stringify(cart.map(function (c) {
      return { id: c.id, qty: c.qty };
    }));
    els.submit.disabled = true;
    els.submit.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Saving...';
  });

  // ---------------------------------------------------------------- load
  fetch(root.dataset.url, { headers: { "Accept": "application/json" } })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      products = data;
      renderGrid();
      renderCart();
      els.search.focus();
    })
    .catch(function () {
      els.grid.innerHTML =
        '<div class="empty" style="grid-column:1/-1"><i class="bi bi-exclamation-triangle"></i>' +
        '<p>Could not load products. Refresh the page.</p></div>';
    });
})();

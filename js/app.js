(() => {
  const DATA_URL = "data/links.json";
  const PREVIEW_COUNT = 8;
  const STORE_FILTERS = [
    "Todas",
    "AliExpress",
    "Mercado Livre",
    "Shopee",
    "Amazon",
    "Outros",
  ];

  const app = document.getElementById("app");
  const searchInput = document.getElementById("search");
  const sectionNav = document.getElementById("section-nav");
  const categoryNav = document.getElementById("category-nav");
  const helpOpen = document.getElementById("help-open");
  const helpModal = document.getElementById("help-modal");
  const bookmarklet = document.getElementById("bookmarklet");
  const editDataLink = document.getElementById("edit-data-link");
  const themeToggle = document.getElementById("theme-toggle");
  const THEME_KEY = "favoritos-theme";

  /** @type {null | object} */
  let data = null;
  /** @type {Map<string, boolean>} */
  const expanded = new Map();
  let searchTimer = 0;
  let storeFilter = "Todas";
  let priceSort = "none"; // none | asc | desc

  function currentTheme() {
    const attr = document.documentElement.getAttribute("data-theme");
    if (attr === "light" || attr === "dark") return attr;
    return "dark";
  }

  function applyTheme(theme) {
    const next = theme === "light" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
      /* ignore */
    }
    if (themeToggle) {
      themeToggle.textContent = next === "dark" ? "Tema claro" : "Tema escuro";
      themeToggle.setAttribute(
        "aria-label",
        next === "dark" ? "Ativar tema claro" : "Ativar tema escuro"
      );
    }
  }

  function initTheme() {
    applyTheme(currentTheme());
    themeToggle?.addEventListener("click", () => {
      applyTheme(currentTheme() === "dark" ? "light" : "dark");
    });
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function hostnameOf(url) {
    try {
      return new URL(url).hostname;
    } catch {
      return "";
    }
  }

  function faviconUrl(item) {
    if (item.icon) return item.icon;
    const host = hostnameOf(item.url);
    if (!host || item.url === "#") return "";
    return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(host)}&sz=128`;
  }

  function editUrl(meta) {
    const gh = meta?.github;
    if (!gh) {
      return "https://github.com/erlancassiano/favoritos/edit/main/data/links.json";
    }
    return `https://github.com/${gh.owner}/${gh.repo}/edit/${gh.branch}/${gh.dataPath}`;
  }

  function buildBookmarklet(meta) {
    const gh = meta?.github || {
      owner: "erlancassiano",
      repo: "favoritos",
    };
    return `javascript:(function(){var t=document.title||location.hostname;var u=location.href;var body=['## Novo link','','- **Título:** '+t,'- **URL:** '+u,'- **Seção:** favoritos | compras | desejos','- **Categoria:** (id existente)','','Cole em data/links.json → items:','','\`\`\`json',JSON.stringify({title:t,url:u,section:'favoritos',category:'geral',store:'',price:'',note:'',tags:[]},null,2),'\`\`\`'].join('\\n');var q=new URLSearchParams({title:'Link: '+t,body:body});open('https://github.com/${gh.owner}/${gh.repo}/issues/new?'+q.toString(),'_blank');})();`;
  }

  function itemHaystack(item) {
    return [
      item.title,
      item.title_full,
      item.url,
      item.note,
      item.store,
      item.price,
      ...(item.tags || []),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
  }

  function matchesQuery(item, query) {
    if (!query) return true;
    return itemHaystack(item).includes(query);
  }

  function itemStore(item) {
    return item.store || "Outros";
  }

  function matchesStore(item) {
    if (storeFilter === "Todas") return true;
    return itemStore(item) === storeFilter;
  }

  function priceValue(item) {
    if (item.price_value != null) return Number(item.price_value);
    if (!item.price) return null;
    let s = String(item.price).replace(/[^\d.,]/g, "");
    if (!s) return null;
    if (s.includes(",") && s.includes(".")) s = s.replace(/\./g, "").replace(",", ".");
    else if (s.includes(",")) s = s.replace(",", ".");
    const n = Number(s);
    return Number.isFinite(n) ? n : null;
  }

  function sortItems(items) {
    if (priceSort === "none") return items;
    const copy = items.slice();
    copy.sort((a, b) => {
      const pa = priceValue(a);
      const pb = priceValue(b);
      if (pa == null && pb == null) return 0;
      if (pa == null) return 1;
      if (pb == null) return -1;
      return priceSort === "asc" ? pa - pb : pb - pa;
    });
    return copy;
  }

  function renderDialTile(item) {
    const icon = faviconUrl(item);
    const missing = !item.url || item.url === "#";
    const href = missing ? "#" : item.url;
    const letter = escapeHtml((item.title || "?").slice(0, 1).toUpperCase());
    const note = item.note
      ? `<span class="dial__note">${escapeHtml(item.note)}</span>`
      : "";
    return `
      <a class="dial__tile${missing ? " dial__tile--pending" : ""}" href="${escapeHtml(href)}" ${
        missing ? "" : 'target="_blank" rel="noopener noreferrer"'
      } title="${escapeHtml(item.title)}">
        <span class="dial__icon" aria-hidden="true">
          ${
            icon
              ? `<img src="${escapeHtml(icon)}" alt="" width="40" height="40" loading="lazy" decoding="async" />`
              : `<span class="dial__letter">${letter}</span>`
          }
        </span>
        <span class="dial__label">${escapeHtml(item.title)}</span>
        ${note}
      </a>
    `;
  }

  function renderCard(item) {
    const icon = faviconUrl(item);
    const unavailable = item.available === false;
    const metaBits = [];
    if (item.price) metaBits.push(escapeHtml(item.price));
    else if (unavailable) metaBits.push("Indisponível");
    if (item.store) metaBits.push(escapeHtml(item.store));
    const tags = (item.tags || [])
      .map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`)
      .join("");
    const host = hostnameOf(item.url);
    const badges = [];
    if (item.in_cart) {
      badges.push('<span class="badge badge--cart">no carrinho</span>');
    }
    if (item.saved_for_later) {
      badges.push('<span class="badge badge--saved">salvo p/ depois</span>');
    }
    if (unavailable) {
      badges.push('<span class="badge badge--unavailable">indisponível</span>');
    }
    const titleAttr = escapeHtml(item.title_full || item.title || "");

    return `
      <a class="card${unavailable ? " card--unavailable" : ""}" href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer" title="${titleAttr}">
        <span class="card__icon" aria-hidden="true">
          ${
            icon
              ? `<img src="${escapeHtml(icon)}" alt="" width="20" height="20" loading="lazy" decoding="async" />`
              : `<span>${escapeHtml((item.title || "?").slice(0, 1).toUpperCase())}</span>`
          }
        </span>
        <span>
          <h3 class="card__title">${escapeHtml(item.title)}${badges.join("")}</h3>
          ${
            metaBits.length
              ? `<p class="card__meta">${metaBits.join(" · ")}</p>`
              : host
                ? `<p class="card__meta">${escapeHtml(host)}</p>`
                : ""
          }
          ${item.note && item.available !== false ? `<p class="card__note">${escapeHtml(item.note)}</p>` : ""}
          ${tags ? `<div class="card__tags">${tags}</div>` : ""}
        </span>
      </a>
    `;
  }

  function renderCategory(category, items, query) {
    const id = category.id;
    const forceOpen = Boolean(query) || priceSort !== "none" || storeFilter !== "Todas";
    const isOpen = forceOpen || expanded.get(id) === true;
    const visible = isOpen ? items : items.slice(0, PREVIEW_COUNT);
    const remaining = items.length - visible.length;
    const openAttr = isOpen ? "true" : "false";

    let footer = "";
    if (!forceOpen && remaining > 0) {
      footer = `<button type="button" class="btn btn--ghost category__more" data-toggle-cat="${escapeHtml(id)}">Ver mais (${remaining})</button>`;
    } else if (!forceOpen && isOpen && items.length > PREVIEW_COUNT) {
      footer = `<button type="button" class="btn btn--ghost category__more" data-toggle-cat="${escapeHtml(id)}">Recolher</button>`;
    }

    return `
      <div class="category" id="cat-${escapeHtml(id)}" data-cat="${escapeHtml(id)}">
        <button type="button" class="category__toggle" data-toggle-cat="${escapeHtml(id)}" aria-expanded="${openAttr}">
          <span class="category__chevron" aria-hidden="true"></span>
          <span class="category__title">${escapeHtml(category.title)}</span>
          <span class="category__count">${items.length}</span>
        </button>
        <div class="category__body">
          <div class="grid">
            ${visible.map(renderCard).join("")}
          </div>
          ${footer}
        </div>
      </div>
    `;
  }

  function renderComprasToolbar() {
    const storeChips = STORE_FILTERS.map((name) => {
      const active = storeFilter === name ? " is-active" : "";
      return `<button type="button" class="chip chip--btn${active}" data-store-filter="${escapeHtml(name)}">${escapeHtml(name)}</button>`;
    }).join("");

    const sortLabel =
      priceSort === "asc"
        ? "Preço: menor → maior"
        : priceSort === "desc"
          ? "Preço: maior → menor"
          : "Ordenar por preço";

    return `
      <div class="compras-toolbar">
        <div class="compras-toolbar__stores" role="group" aria-label="Filtrar por loja">
          ${storeChips}
        </div>
        <button type="button" class="btn btn--ghost" id="price-sort-btn" data-price-sort>
          ${escapeHtml(sortLabel)}
        </button>
      </div>
    `;
  }

  function render(query = "") {
    if (!data) return;
    const q = query.trim().toLowerCase();
    const parts = [];

    const diarios = (data.diarios || []).filter((item) => matchesQuery(item, q));
    if (!q || diarios.length) {
      parts.push(`
        <section class="section section--diarios" id="diarios">
          <header class="section__head">
            <h2 class="section__title">Links diários</h2>
            <p class="section__desc">Atalhos fixos — edite o array <code>diarios</code> em data/links.json</p>
          </header>
          <div class="dial">
            ${diarios.map(renderDialTile).join("")}
          </div>
        </section>
      `);
    }

    for (const section of data.sections) {
      const sectionCategories = data.categories.filter(
        (c) => c.section === section.id
      );
      let sectionItems = data.items.filter(
        (item) => item.section === section.id && matchesQuery(item, q)
      );

      if (section.id === "compras") {
        sectionItems = sectionItems.filter(matchesStore);
        sectionItems = sortItems(sectionItems);
      }

      if (!sectionItems.length && section.id !== "compras") continue;
      if (!sectionItems.length && section.id === "compras" && q) continue;

      const categoryBlocks = [];
      const used = new Set();

      for (const category of sectionCategories) {
        let items = sectionItems.filter((item) => item.category === category.id);
        if (!items.length) continue;
        used.add(category.id);
        if (section.id === "compras") items = sortItems(items);
        categoryBlocks.push(renderCategory(category, items, q));
      }

      const orphans = sectionItems.filter((item) => !used.has(item.category));
      if (orphans.length) {
        categoryBlocks.push(
          renderCategory(
            { id: `${section.id}-outros`, title: "Outros" },
            section.id === "compras" ? sortItems(orphans) : orphans,
            q
          )
        );
      }

      if (!categoryBlocks.length && section.id !== "compras") continue;

      parts.push(`
        <section class="section" id="${escapeHtml(section.id)}">
          <header class="section__head">
            <h2 class="section__title">${escapeHtml(section.title)}</h2>
            ${
              section.description
                ? `<p class="section__desc">${escapeHtml(section.description)} · ${sectionItems.length} links</p>`
                : ""
            }
          </header>
          ${section.id === "compras" ? renderComprasToolbar() : ""}
          ${
            categoryBlocks.length
              ? categoryBlocks.join("")
              : `<p class="empty">Nenhum item nesta loja${q ? " / busca" : ""}.</p>`
          }
        </section>
      `);
    }

    if (!parts.length) {
      app.innerHTML = `<p class="empty">Nenhum item encontrado${
        q ? ` para “${escapeHtml(query.trim())}”` : ""
      }.</p>`;
      return;
    }

    app.innerHTML = parts.join("");
  }

  function renderNav() {
    if (!data) return;
    const links = [
      `<a href="#diarios">Links diários</a>`,
      ...data.sections.map(
        (section) =>
          `<a href="#${escapeHtml(section.id)}">${escapeHtml(section.title)}</a>`
      ),
    ];
    sectionNav.innerHTML = links.join("");

    if (categoryNav) {
      const chips = data.categories
        .filter((c) => c.section === "favoritos" || c.section === "compras")
        .map((c) => {
          const count = data.items.filter((i) => i.category === c.id).length;
          if (!count) return "";
          return `<a class="chip" href="#cat-${escapeHtml(c.id)}" title="${escapeHtml(c.title)}">${escapeHtml(c.title)} <span>${count}</span></a>`;
        })
        .filter(Boolean);
      categoryNav.innerHTML = chips.join("");
    }
  }

  function onAppClick(event) {
    const storeBtn = event.target.closest("[data-store-filter]");
    if (storeBtn) {
      storeFilter = storeBtn.getAttribute("data-store-filter") || "Todas";
      render(searchInput?.value || "");
      document.getElementById("compras")?.scrollIntoView({ block: "nearest" });
      return;
    }

    const sortBtn = event.target.closest("[data-price-sort]");
    if (sortBtn) {
      priceSort =
        priceSort === "none" ? "asc" : priceSort === "asc" ? "desc" : "none";
      render(searchInput?.value || "");
      document.getElementById("compras")?.scrollIntoView({ block: "nearest" });
      return;
    }

    const btn = event.target.closest("[data-toggle-cat]");
    if (!btn) return;
    const id = btn.getAttribute("data-toggle-cat");
    if (!id) return;
    const next = !(expanded.get(id) === true);
    expanded.set(id, next);
    render(searchInput?.value || "");
    document.getElementById(`cat-${id}`)?.scrollIntoView({ block: "nearest" });
  }

  function wireHelp() {
    helpOpen?.addEventListener("click", () => {
      if (typeof helpModal.showModal === "function") helpModal.showModal();
    });
  }

  async function init() {
    initTheme();
    wireHelp();
    app?.addEventListener("click", onAppClick);

    try {
      const res = await fetch(DATA_URL, { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      data = await res.json();

      document.title = `${data.meta?.owner || "Erlan"} · ${data.meta?.title || "Favoritos"}`;
      const brand = document.querySelector(".hero__brand");
      if (brand && data.meta?.owner) brand.textContent = data.meta.owner;

      if (editDataLink) editDataLink.href = editUrl(data.meta);

      if (bookmarklet) {
        bookmarklet.setAttribute("href", buildBookmarklet(data.meta));
        bookmarklet.addEventListener("click", (event) => {
          event.preventDefault();
          alert(
            "Arraste este botão para a barra de favoritos do navegador.\n\nDepois, em qualquer site, clique no favorito para abrir um issue já preenchido."
          );
        });
      }

      renderNav();
      render();

      searchInput?.addEventListener("input", () => {
        window.clearTimeout(searchTimer);
        searchTimer = window.setTimeout(() => {
          render(searchInput.value);
        }, 80);
      });
    } catch (err) {
      console.error(err);
      app.innerHTML = `
        <p class="status">
          Não foi possível carregar <code>data/links.json</code>.
          Use um servidor estático local — por exemplo:
          <code>python3 -m http.server 8080</code>
        </p>
      `;
    }
  }

  init();
})();

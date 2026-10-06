(() => {
  const DATA_URL = "data/links.json";
  const PREVIEW_COUNT = 24;
  const STORE_FILTERS = [
    "Todas",
    "AliExpress",
    "Mercado Livre",
    "Shopee",
    "Amazon",
    "Amazon EUA",
    "Outros",
  ];
  /** Fixed USD→BRL rate for cross-currency price sort (documented in README). */
  const USD_TO_BRL = 5.5;
  const THEME_KEY = "favoritos-theme";
  const COLLAPSE_KEY = "favoritos-collapse";

  const app = document.getElementById("app");
  const searchInput = document.getElementById("search");
  const sectionNav = document.getElementById("section-nav");
  const categoryNav = document.getElementById("category-nav");
  const helpOpen = document.getElementById("help-open");
  const helpModal = document.getElementById("help-modal");
  const bookmarklet = document.getElementById("bookmarklet");
  const editDataLink = document.getElementById("edit-data-link");
  const themeToggle = document.getElementById("theme-toggle");

  /** @type {null | object} */
  let data = null;
  /** @type {{ sections: Record<string, boolean>, cats: Record<string, "preview"|"open"|"closed"> }} */
  let collapseState = { sections: {}, cats: {} };
  let searchTimer = 0;
  let storeFilter = "Todas";
  let listFilter = "Todas"; // Todas | Comprar em Miami | …
  let cheaperAltFilter = false;
  let priceSort = "none"; // none | asc | desc

  function loadCollapse() {
    try {
      const raw = JSON.parse(localStorage.getItem(COLLAPSE_KEY) || "{}");
      return {
        sections: raw.sections && typeof raw.sections === "object" ? raw.sections : {},
        cats: raw.cats && typeof raw.cats === "object" ? raw.cats : {},
      };
    } catch {
      return { sections: {}, cats: {} };
    }
  }

  function saveCollapse() {
    try {
      localStorage.setItem(COLLAPSE_KEY, JSON.stringify(collapseState));
    } catch {
      /* ignore */
    }
  }

  function sectionCollapsed(id) {
    return collapseState.sections[id] === true;
  }

  function catMode(id) {
    const m = collapseState.cats[id];
    return m === "open" || m === "closed" ? m : "preview";
  }

  function setCatMode(id, mode) {
    if (mode === "preview") delete collapseState.cats[id];
    else collapseState.cats[id] = mode;
    saveCollapse();
  }

  function toggleSection(id) {
    collapseState.sections[id] = !sectionCollapsed(id);
    if (!collapseState.sections[id]) delete collapseState.sections[id];
    saveCollapse();
  }

  function currentForceExpand() {
    return Boolean((searchInput?.value || "").trim()) || filtersForceExpand();
  }

  /** Toggle collapse in-place — no full re-render (avoids flicker / favicon reload). */
  function applySectionDom(sectionEl, collapsed) {
    if (!sectionEl) return;
    sectionEl.classList.toggle("section--collapsed", collapsed);
    const btn = sectionEl.querySelector("[data-toggle-section]");
    const body = sectionEl.querySelector(".section__body");
    if (btn) btn.setAttribute("aria-expanded", collapsed ? "false" : "true");
    if (body) body.hidden = collapsed;
  }

  function applyCategoryDom(catEl, mode, forceExpand) {
    if (!catEl) return;
    const count = Number(catEl.dataset.count || 0);
    const closed = mode === "closed";
    const fullyOpen = !closed && (mode === "open" || forceExpand);
    catEl.classList.toggle("category--collapsed", closed);
    catEl.classList.toggle("category--preview", !closed && !fullyOpen);
    catEl.classList.toggle("category--open", fullyOpen);
    const btn = catEl.querySelector("[data-toggle-cat]");
    const body = catEl.querySelector(".category__body");
    if (btn) btn.setAttribute("aria-expanded", closed ? "false" : "true");
    if (body) body.hidden = closed;
    const more = catEl.querySelector("[data-cat-more]");
    const collapse = catEl.querySelector("[data-cat-collapse]");
    if (more) more.hidden = !(!closed && !fullyOpen && count > PREVIEW_COUNT);
    if (collapse) collapse.hidden = !(!closed && fullyOpen && count > PREVIEW_COUNT);
  }

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
    const altBits = (item.alternativas || []).flatMap((a) => [
      a.store,
      a.url,
      displayAltStore(a.store),
    ]);
    return [
      item.title,
      item.title_full,
      item.url,
      item.note,
      item.store,
      item.price,
      ...(item.tags || []),
      ...altBits,
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

  function itemList(item) {
    return item.list || "";
  }

  function matchesList(item) {
    if (listFilter === "Todas") return true;
    return itemList(item) === listFilter;
  }

  function displayAltStore(store) {
    if (store === "Amazon US" || store === "Amazon.com") return "Amazon EUA";
    if (store === "Amazon BR" || store === "Amazon.com.br") return "Amazon";
    return store || "Loja";
  }

  function altPriceBrl(alt) {
    const n = Number(alt?.price);
    if (!Number.isFinite(n)) return null;
    return alt.currency === "USD" ? n * USD_TO_BRL : n;
  }

  function formatAltPrice(price, currency) {
    const n = Number(price);
    if (!Number.isFinite(n)) return "";
    const formatted = n.toLocaleString("pt-BR", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    return currency === "USD" ? `US$ ${formatted}` : `R$ ${formatted}`;
  }

  function hasCheaperAlt(item) {
    const base = priceValue(item);
    if (base == null) return false;
    return (item.alternativas || []).some((alt) => {
      const brl = altPriceBrl(alt);
      return brl != null && brl < base - 0.005;
    });
  }

  function matchesCheaperAlt(item) {
    if (!cheaperAltFilter) return true;
    return hasCheaperAlt(item);
  }

  function renderAlternativas(item) {
    const alts = item.alternativas;
    if (!Array.isArray(alts) || !alts.length) return "";
    const base = priceValue(item);
    const parts = alts.map((alt) => {
      if (!alt?.url) return "";
      const brl = altPriceBrl(alt);
      const cheaper = base != null && brl != null && brl < base - 0.005;
      const storeLabel = displayAltStore(alt.store);
      const priceLabel = formatAltPrice(alt.price, alt.currency);
      const checked = alt.checked ? ` Conferido em ${alt.checked}.` : "";
      const tip =
        alt.currency === "USD"
          ? `Preço nos EUA — sem frete nem imposto de importação.${checked}`
          : checked.trim() || storeLabel;
      let hint = "";
      if (cheaper) {
        const save = (base - brl).toLocaleString("pt-BR", {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        });
        hint = `<span class="card__alt-save">↓ R$ ${save} mais barato</span>`;
      }
      return `<a class="card__alt${cheaper ? " card__alt--cheaper" : ""}" href="${escapeHtml(alt.url)}" target="_blank" rel="noopener noreferrer" title="${escapeHtml(tip)}">${escapeHtml(storeLabel)} ${escapeHtml(priceLabel)}</a>${hint}`;
    }).filter(Boolean);
    if (!parts.length) return "";
    return `<div class="card__alts"><span class="card__alts-label">também em:</span> ${parts.join('<span class="card__alts-sep"> · </span>')}</div>`;
  }

  function listFiltersAvailable() {
    if (!data) return ["Todas"];
    const names = new Set();
    for (const item of data.items) {
      if (item.section === "compras" && item.list) names.add(item.list);
    }
    return ["Todas", ...[...names].sort((a, b) => a.localeCompare(b, "pt-BR"))];
  }

  function priceValue(item) {
    // Imports store BRL-comparable numbers in price_value (USD rows already × USD_TO_BRL).
    if (item.price_value != null) {
      const n = Number(item.price_value);
      return Number.isFinite(n) ? n : null;
    }
    if (item.price_usd != null) {
      const n = Number(item.price_usd);
      return Number.isFinite(n) ? n * USD_TO_BRL : null;
    }
    if (!item.price) return null;
    const raw = String(item.price);
    let s = raw.replace(/[^\d.,]/g, "");
    if (!s) return null;
    if (s.includes(",") && s.includes(".")) s = s.replace(/\./g, "").replace(",", ".");
    else if (s.includes(",")) s = s.replace(",", ".");
    const n = Number(s);
    if (!Number.isFinite(n)) return null;
    if (/us\$|usd|\$/i.test(raw) && !/r\$/i.test(raw)) return n * USD_TO_BRL;
    return n;
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
    else if (item.no_br_delivery) metaBits.push("ver nos EUA");
    else if (unavailable) metaBits.push("Indisponível");
    if (item.store) metaBits.push(escapeHtml(item.store));
    if (item.note && item.available !== false) metaBits.push(escapeHtml(item.note));
    const host = hostnameOf(item.url);
    const badges = [];
    if (item.list === "Comprar em Miami") {
      badges.push('<span class="badge badge--miami">Miami</span>');
    }
    if (item.in_cart) {
      badges.push('<span class="badge badge--cart">carrinho</span>');
    }
    if (item.saved_for_later) {
      badges.push('<span class="badge badge--saved">salvo</span>');
    }
    if (item.no_br_delivery) {
      badges.push('<span class="badge badge--no-br">ver nos EUA</span>');
    } else if (unavailable) {
      badges.push('<span class="badge badge--unavailable">indisponível</span>');
    }
    const titleAttr = escapeHtml(item.title_full || item.title || "");
    const meta =
      metaBits.length
        ? metaBits.join(" · ")
        : host
          ? escapeHtml(host)
          : "";

    const body = `
        <span class="card__icon" aria-hidden="true">
          ${
            icon
              ? `<img src="${escapeHtml(icon)}" alt="" width="14" height="14" loading="lazy" decoding="async" />`
              : `<span>${escapeHtml((item.title || "?").slice(0, 1).toUpperCase())}</span>`
          }
        </span>
        <span class="card__main">
          <span class="card__title">${escapeHtml(item.title)}</span>
          ${badges.length ? `<span class="card__badges">${badges.join("")}</span>` : ""}
          ${meta ? `<span class="card__meta">${meta}</span>` : ""}
        </span>`;

    const altsHtml = item.section === "compras" ? renderAlternativas(item) : "";
    // Nested <a> is invalid — stack primary link + alt links when alternatives exist.
    if (altsHtml) {
      return `
      <div class="card card--stack${unavailable ? " card--unavailable" : ""}${hasCheaperAlt(item) ? " card--has-cheaper" : ""}">
        <a class="card__link" href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer" title="${titleAttr}">
          ${body}
        </a>
        ${altsHtml}
      </div>`;
    }

    return `
      <a class="card${unavailable ? " card--unavailable" : ""}" href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer" title="${titleAttr}">
        ${body}
      </a>
    `;
  }

  function filtersForceExpand() {
    return (
      priceSort !== "none" ||
      storeFilter !== "Todas" ||
      listFilter !== "Todas" ||
      cheaperAltFilter
    );
  }

  function renderCategory(category, items, query) {
    const id = category.id;
    const mode = catMode(id);
    const forceExpand = Boolean(query) || filtersForceExpand();
    // Explicit closed always wins — collapse must work with search/filters.
    const closed = mode === "closed";
    const fullyOpen = !closed && (mode === "open" || forceExpand);
    const remaining = Math.max(0, items.length - PREVIEW_COUNT);
    const openAttr = closed ? "false" : "true";
    const modeClass = closed
      ? " category--collapsed"
      : fullyOpen
        ? " category--open"
        : " category--preview";

    // Always mount all cards; footers only when preview/open toggles matter.
    const moreHidden = !(!closed && !fullyOpen && remaining > 0);
    const collapseHidden = !(!closed && fullyOpen && remaining > 0);
    const footers =
      remaining > 0
        ? `<button type="button" class="btn btn--ghost category__more" data-cat-more="${escapeHtml(id)}"${moreHidden ? " hidden" : ""}>Ver mais (${remaining})</button>
          <button type="button" class="btn btn--ghost category__more" data-cat-collapse="${escapeHtml(id)}"${collapseHidden ? " hidden" : ""}>Recolher</button>`
        : "";

    return `
      <div class="category${modeClass}" id="cat-${escapeHtml(id)}" data-cat="${escapeHtml(id)}" data-count="${items.length}">
        <button type="button" class="category__toggle" data-toggle-cat="${escapeHtml(id)}" aria-expanded="${openAttr}">
          <span class="chevron" aria-hidden="true"></span>
          <span class="category__title">${escapeHtml(category.title)}</span>
          <span class="category__count">${items.length}</span>
        </button>
        <div class="category__body"${closed ? " hidden" : ""}>
          <div class="grid">
            ${items.map(renderCard).join("")}
          </div>
          ${footers}
        </div>
      </div>
    `;
  }

  function renderSectionShell(id, title, description, bodyHtml, extraHead = "") {
    const collapsed = sectionCollapsed(id);
    const openAttr = collapsed ? "false" : "true";
    return `
      <section class="section${collapsed ? " section--collapsed" : ""}" id="${escapeHtml(id)}">
        <header class="section__head">
          <button type="button" class="section__toggle" data-toggle-section="${escapeHtml(id)}" aria-expanded="${openAttr}">
            <span class="chevron" aria-hidden="true"></span>
            <h2 class="section__title">${escapeHtml(title)}</h2>
          </button>
          ${description ? `<p class="section__desc">${description}</p>` : ""}
          ${extraHead}
        </header>
        <div class="section__body"${collapsed ? " hidden" : ""}>${bodyHtml}</div>
      </section>
    `;
  }

  function renderComprasToolbar() {
    const storeChips = STORE_FILTERS.map((name) => {
      const active = storeFilter === name ? " is-active" : "";
      return `<button type="button" class="chip chip--btn${active}" data-store-filter="${escapeHtml(name)}">${escapeHtml(name)}</button>`;
    }).join("");

    const listChips = listFiltersAvailable()
      .map((name) => {
        const active = listFilter === name ? " is-active" : "";
        const label = name === "Todas" ? "Todas as listas" : name;
        return `<button type="button" class="chip chip--btn chip--list${active}" data-list-filter="${escapeHtml(name)}">${escapeHtml(label)}</button>`;
      })
      .join("");

    const sortLabel =
      priceSort === "asc"
        ? "Preço: menor → maior"
        : priceSort === "desc"
          ? "Preço: maior → menor"
          : "Ordenar por preço";

    const cheaperActive = cheaperAltFilter ? " is-active" : "";

    return `
      <div class="compras-toolbar">
        <div class="compras-toolbar__stores" role="group" aria-label="Filtrar por loja">
          ${storeChips}
        </div>
        <div class="compras-toolbar__lists" role="group" aria-label="Filtrar por lista">
          ${listChips}
        </div>
        <div class="compras-toolbar__extras" role="group" aria-label="Filtros extras">
          <button type="button" class="chip chip--btn chip--cheaper${cheaperActive}" data-cheaper-alt-filter title="Itens com alternativa mais barata (USD × ${USD_TO_BRL}; EUA sem frete/imposto)">
            Mais barato em outra loja
          </button>
          <button type="button" class="btn btn--ghost" id="price-sort-btn" data-price-sort title="Ordenação compara BRL e USD (USD × ${USD_TO_BRL})">
            ${escapeHtml(sortLabel)}
          </button>
        </div>
      </div>
    `;
  }

  function render(query = "") {
    if (!data) return;
    const q = query.trim().toLowerCase();
    const parts = [];

    const diarios = (data.diarios || []).filter((item) => matchesQuery(item, q));
    if (!q || diarios.length) {
      parts.push(
        renderSectionShell(
          "diarios",
          "Links diários",
          `Atalhos fixos — edite o array <code>diarios</code> em data/links.json`,
          `<div class="dial">${diarios.map(renderDialTile).join("")}</div>`
        )
      );
    }

    for (const section of data.sections) {
      const sectionCategories = data.categories.filter(
        (c) => c.section === section.id
      );
      let sectionItems = data.items.filter(
        (item) => item.section === section.id && matchesQuery(item, q)
      );

      if (section.id === "compras") {
        sectionItems = sectionItems
          .filter(matchesStore)
          .filter(matchesList)
          .filter(matchesCheaperAlt);
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

      const desc = section.description
        ? `${escapeHtml(section.description)} · ${sectionItems.length} links`
        : `${sectionItems.length} links`;
      const body = `${section.id === "compras" ? renderComprasToolbar() : ""}${
        categoryBlocks.length
          ? categoryBlocks.join("")
          : `<p class="empty">Nenhum item nesta loja${q ? " / busca" : ""}.</p>`
      }`;
      parts.push(renderSectionShell(section.id, section.title, desc, body));
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

    const listBtn = event.target.closest("[data-list-filter]");
    if (listBtn) {
      listFilter = listBtn.getAttribute("data-list-filter") || "Todas";
      render(searchInput?.value || "");
      document.getElementById("compras")?.scrollIntoView({ block: "nearest" });
      return;
    }

    const cheaperBtn = event.target.closest("[data-cheaper-alt-filter]");
    if (cheaperBtn) {
      cheaperAltFilter = !cheaperAltFilter;
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

    const sectionBtn = event.target.closest("[data-toggle-section]");
    if (sectionBtn) {
      const id = sectionBtn.getAttribute("data-toggle-section");
      if (!id) return;
      toggleSection(id);
      applySectionDom(document.getElementById(id), sectionCollapsed(id));
      return;
    }

    const moreBtn = event.target.closest("[data-cat-more]");
    if (moreBtn) {
      const id = moreBtn.getAttribute("data-cat-more");
      if (!id) return;
      setCatMode(id, "open");
      applyCategoryDom(document.getElementById(`cat-${id}`), "open", currentForceExpand());
      return;
    }

    const collapseBtn = event.target.closest("[data-cat-collapse]");
    if (collapseBtn) {
      const id = collapseBtn.getAttribute("data-cat-collapse");
      if (!id) return;
      // With active filters/search, "Recolher" fully closes; otherwise back to preview.
      const next = currentForceExpand() ? "closed" : "preview";
      setCatMode(id, next);
      applyCategoryDom(document.getElementById(`cat-${id}`), next, currentForceExpand());
      return;
    }

    const btn = event.target.closest("[data-toggle-cat]");
    if (!btn) return;
    const id = btn.getAttribute("data-toggle-cat");
    if (!id) return;
    const next = catMode(id) === "closed" ? "open" : "closed";
    setCatMode(id, next);
    applyCategoryDom(document.getElementById(`cat-${id}`), next, currentForceExpand());
  }

  function wireHelp() {
    helpOpen?.addEventListener("click", () => {
      if (typeof helpModal.showModal === "function") helpModal.showModal();
    });
  }

  async function init() {
    initTheme();
    collapseState = loadCollapse();
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

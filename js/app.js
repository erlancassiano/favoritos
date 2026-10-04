(() => {
  const DATA_URL = "data/links.json";
  const app = document.getElementById("app");
  const searchInput = document.getElementById("search");
  const sectionNav = document.getElementById("section-nav");
  const helpOpen = document.getElementById("help-open");
  const helpModal = document.getElementById("help-modal");
  const bookmarklet = document.getElementById("bookmarklet");
  const editDataLink = document.getElementById("edit-data-link");

  /** @type {null | {meta: object, sections: array, categories: array, items: array}} */
  let data = null;

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
    if (!host) return "";
    return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(host)}&sz=64`;
  }

  function editUrl(meta) {
    const gh = meta?.github;
    if (!gh) return "https://github.com/erlancassiano/favoritos/edit/main/data/links.json";
    return `https://github.com/${gh.owner}/${gh.repo}/edit/${gh.branch}/${gh.dataPath}`;
  }

  function buildBookmarklet(meta) {
    const gh = meta?.github || {
      owner: "erlancassiano",
      repo: "favoritos",
    };
    // Opens a prefilled GitHub issue — no token, works from any page when logged into GitHub.
    const code = `javascript:(function(){var t=document.title||location.hostname;var u=location.href;var body=['## Novo link','','- **Título:** '+t,'- **URL:** '+u,'- **Seção:** favoritos | compras | desejos','- **Categoria:** (id existente)','','Cole em data/links.json → items:','','\`\`\`json',JSON.stringify({title:t,url:u,section:'favoritos',category:'produtividade',note:'',tags:[],added:new Date().toISOString().slice(0,10)},null,2),'\`\`\`'].join('\\n');var q=new URLSearchParams({title:'Link: '+t,body:body});open('https://github.com/${gh.owner}/${gh.repo}/issues/new?'+q.toString(),'_blank');})();`;
    return code;
  }

  function matchesQuery(item, query) {
    if (!query) return true;
    const hay = [
      item.title,
      item.url,
      item.note,
      item.store,
      item.price,
      ...(item.tags || []),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return hay.includes(query);
  }

  function renderCard(item, index) {
    const icon = faviconUrl(item);
    const metaBits = [];
    if (item.price) metaBits.push(escapeHtml(item.price));
    if (item.store) metaBits.push(escapeHtml(item.store));
    const tags = (item.tags || [])
      .map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`)
      .join("");
    const priority =
      item.priority != null
        ? `<span class="priority" title="Prioridade">P${escapeHtml(item.priority)}</span>`
        : "";

    return `
      <a class="card" href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer" style="animation-delay:${Math.min(index * 30, 240)}ms">
        <span class="card__icon" aria-hidden="true">
          ${
            icon
              ? `<img src="${escapeHtml(icon)}" alt="" width="20" height="20" loading="lazy" decoding="async" />`
              : `<span>${escapeHtml((item.title || "?").slice(0, 1).toUpperCase())}</span>`
          }
        </span>
        <span>
          <h3 class="card__title">${escapeHtml(item.title)}${priority}</h3>
          ${
            metaBits.length
              ? `<p class="card__meta">${metaBits.join(" · ")}</p>`
              : `<p class="card__meta">${escapeHtml(hostnameOf(item.url))}</p>`
          }
          ${item.note ? `<p class="card__note">${escapeHtml(item.note)}</p>` : ""}
          ${tags ? `<div class="card__tags">${tags}</div>` : ""}
        </span>
      </a>
    `;
  }

  function render(query = "") {
    if (!data) return;
    const q = query.trim().toLowerCase();
    const fragments = [];

    for (const section of data.sections) {
      const sectionCategories = data.categories.filter(
        (c) => c.section === section.id
      );
      const sectionItems = data.items.filter(
        (item) => item.section === section.id && matchesQuery(item, q)
      );

      if (!sectionItems.length) continue;

      const categoryBlocks = [];
      const usedCategoryIds = new Set();

      for (const category of sectionCategories) {
        const items = sectionItems.filter((item) => item.category === category.id);
        if (!items.length) continue;
        usedCategoryIds.add(category.id);
        categoryBlocks.push(`
          <div class="category">
            <h3 class="category__title">${escapeHtml(category.title)}</h3>
            <div class="grid">
              ${items.map((item, i) => renderCard(item, i)).join("")}
            </div>
          </div>
        `);
      }

      // Items whose category id isn't listed still show under "Outros".
      const orphans = sectionItems.filter(
        (item) => !usedCategoryIds.has(item.category)
      );
      if (orphans.length) {
        categoryBlocks.push(`
          <div class="category">
            <h3 class="category__title">Outros</h3>
            <div class="grid">
              ${orphans.map((item, i) => renderCard(item, i)).join("")}
            </div>
          </div>
        `);
      }

      fragments.push(`
        <section class="section" id="${escapeHtml(section.id)}">
          <header class="section__head">
            <h2 class="section__title">${escapeHtml(section.title)}</h2>
            ${
              section.description
                ? `<p class="section__desc">${escapeHtml(section.description)}</p>`
                : ""
            }
          </header>
          ${categoryBlocks.join("")}
        </section>
      `);
    }

    if (!fragments.length) {
      app.innerHTML = `<p class="empty">Nenhum item encontrado${
        q ? ` para “${escapeHtml(query.trim())}”` : ""
      }.</p>`;
      return;
    }

    app.innerHTML = fragments.join("");
  }

  function renderNav() {
    if (!data) return;
    sectionNav.innerHTML = data.sections
      .map(
        (section) =>
          `<a href="#${escapeHtml(section.id)}">${escapeHtml(section.title)}</a>`
      )
      .join("");
  }

  function wireHelp() {
    helpOpen?.addEventListener("click", () => {
      if (typeof helpModal.showModal === "function") helpModal.showModal();
    });
  }

  async function init() {
    wireHelp();
    try {
      const res = await fetch(DATA_URL, { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      data = await res.json();

      document.title = `${data.meta?.owner || "Erlan"} · ${data.meta?.title || "Favoritos"}`;
      const brand = document.querySelector(".hero__brand");
      if (brand && data.meta?.owner) brand.textContent = data.meta.owner;

      const editHref = editUrl(data.meta);
      if (editDataLink) editDataLink.href = editHref;

      if (bookmarklet) {
        bookmarklet.setAttribute("href", buildBookmarklet(data.meta));
        bookmarklet.addEventListener("click", (event) => {
          // Keep the javascript: URL for drag-to-bookmarks; block accidental click navigation.
          event.preventDefault();
          alert(
            "Arraste este botão para a barra de favoritos do navegador.\n\nDepois, em qualquer site, clique no favorito para abrir um issue já preenchido."
          );
        });
      }

      renderNav();
      render();
      searchInput?.addEventListener("input", () => render(searchInput.value));
    } catch (err) {
      console.error(err);
      app.innerHTML = `
        <p class="status">
          Não foi possível carregar <code>data/links.json</code>.
          Se você abriu o arquivo direto no navegador (file://), use um servidor
          estático local — por exemplo:
          <code>python3 -m http.server 8080</code>
        </p>
      `;
      // Fallback bookmarklet / edit links still useful offline.
      if (bookmarklet) {
        bookmarklet.setAttribute("href", buildBookmarklet(null));
        bookmarklet.addEventListener("click", (event) => {
          event.preventDefault();
          alert(
            "Arraste este botão para a barra de favoritos do navegador."
          );
        });
      }
    }
  }

  init();
})();

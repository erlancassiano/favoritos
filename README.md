# Favoritos — página inicial do Erlan

Site estático (HTML/CSS/JS) servido pelo **GitHub Pages** a partir da raiz do branch `main`.  
Três seções: **Favoritos**, **Compras** e **Lista de desejos**. Tudo vem de um único arquivo de dados.

---

## Exemplo de entrada (copiar e colar)

Arquivo: [`data/links.json`](data/links.json)

```json
{
  "title": "Exemplo: Meu site",
  "url": "https://www.example.com",
  "section": "favoritos",
  "category": "produtividade",
  "icon": "",
  "price": "R$ —",
  "store": "Loja exemplo",
  "note": "Observação opcional",
  "tags": ["exemplo"],
  "priority": 1,
  "added": "2026-10-04"
}
```

### Campos

| Campo | Obrigatório? | Descrição |
| --- | --- | --- |
| `title` | sim | Nome exibido no card |
| `url` | sim | Link de destino |
| `section` | sim | `favoritos`, `compras` ou `desejos` |
| `category` | sim | `id` de uma categoria em `categories` |
| `icon` | não | URL de ícone; se vazio, usa o favicon do site |
| `price` | não | Preço (útil em Compras / Desejos) |
| `store` | não | Loja |
| `note` | não | Nota curta |
| `tags` | não | Lista de palavras para busca |
| `priority` | não | Número (menor = mais importante) |
| `added` | não | Data `AAAA-MM-DD` |

Para uma **categoria nova**, adicione também em `categories`:

```json
{ "id": "minha-categoria", "title": "Minha categoria", "section": "favoritos" }
```

---

## Como adicionar um link (editor do GitHub no celular)

1. Abra o repositório no GitHub e vá em **`data/links.json`**.
2. Toque no ícone de **lápis** (Edit this file).
3. Role até o array `"items"`.
4. Copie um bloco de exemplo (os que começam com `"Exemplo: ..."`) e cole **mais um** objeto, lembrando da vírgula entre objetos.
5. Altere `title`, `url`, `section` e `category`. Preencha `price` / `store` se for compra ou desejo.
6. Toque em **Commit changes…** → confirme o commit no branch `main`.
7. Aguarde o GitHub Pages publicar (geralmente 1–2 minutos) e atualize o site.

Dica: mantenha os exemplos até se sentir confortável com o formato; depois pode apagá-los.

---

## Bookmarklet

No site, abra **Como adicionar** e arraste **Salvar no Favoritos** para a barra de favoritos.

Em qualquer página da web, clique no bookmarklet: ele abre um **issue novo** no GitHub já preenchido com o título e a URL da página (e um JSON pronto para colar).  
Você ainda precisa copiar esse JSON para `data/links.json` e fazer o commit — não há backend nem token.

Alternativa manual: editar direto  
https://github.com/erlancassiano/favoritos/edit/main/data/links.json

---

## Rodar localmente

Sem build. Qualquer servidor estático serve:

```bash
python3 -m http.server 8080
```

Abra http://localhost:8080  

Abrir só o `index.html` via `file://` pode falhar ao carregar o JSON (restrição do navegador). Use o servidor acima.

---

## GitHub Pages

- Fonte: branch **`main`**, pasta **/ (root)**
- Arquivo [`.nojekyll`](.nojekyll) desativa o processamento Jekyll
- Após o commit em `main`, ative Pages em **Settings → Pages** se ainda não estiver ativo

---

## Estrutura

```
index.html       → página
css/styles.css   → visual (escuro por padrão; botão alterna e salva em localStorage)
js/app.js        → lê o JSON e monta o grid
data/links.json  → único arquivo para editar no dia a dia
.nojekyll
README.md
```

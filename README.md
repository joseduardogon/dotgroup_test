# Virtual Library API

> **Autor:** José Eduardo Gontijo de Carvalho - GitHub [@joseduardogon](https://github.com/joseduardogon)
>
> **Contexto:** Questão 1 do teste técnico da **Dot Group** para a vaga de
> *Senior Developer* com foco em **IA e Backend**.

---

## English summary

A production-grade REST API (FastAPI, SQLAlchemy 2, Alembic, SQLite, Poetry >= 2,
Docker) that registers books and searches them by title, author, or free text
(accent- and case-insensitive). It follows a layered architecture, returns RFC 9457
problem documents, ships versioned migrations, health probes and JSON logs with request
correlation, and is covered by unit, API and integration tests (including a concurrency
test for the duplicate guarantee). Run it with `docker compose up --build` and open
<http://localhost:8000/docs>. Design rationale lives in `docs/adr/`; deliberate
non-goals (auth, CORS, rate limiting, ISBN) are listed in ADR 0003. Sample requests:
`requests.http`.

---

## 1. A questão

**Questão 1 - Desenvolvimento de API com Django/Flask/FastAPI**

> Desenvolva uma API simples que permite aos usuários cadastrar e consultar livros
> em uma biblioteca virtual. A API deve incluir as seguintes funcionalidades:
>
> 1. Cadastro de livros com os campos: título, autor, data de publicação e resumo.
> 2. Consulta de livros por título ou autor.
> 3. Implemente a API utilizando um dos frameworks: Django, Flask ou FastAPI.
>
> Certifique-se de:
>
> - Criar endpoints claros e bem documentados.
> - Utilizar um banco de dados SQLite para armazenamento.
> - Implementar testes unitários para os endpoints criados.

**Escolhas do candidato:** FastAPI, Poetry para dependências, Docker para execução,
e um acabamento de "projeto pronto para produção" indo além do mínimo pedido.

### Requisitos x entrega

| Requisito | Entrega |
|---|---|
| Cadastro (título, autor, data de publicação, resumo) | `POST /api/v1/books` |
| Consulta por título ou autor | `GET /api/v1/books?title=` · `?author=` · `?q=` (título **ou** autor) |
| FastAPI | `src/library_api` |
| Endpoints claros e documentados | OpenAPI/Swagger em `/docs`, ReDoc em `/redoc`, docstrings Google |
| SQLite | SQLAlchemy 2 + Alembic (migrations versionadas) |
| Testes dos endpoints | Suítes unit, API e integração; cobertura mínima de 95% imposta pelo pytest |
| Docker | `Dockerfile` multi-stage + `docker-compose.yml` |

Extras: `GET/PATCH/DELETE /books/{id}`, paginação, ordenação, busca insensível a
acentos e caixa, erros RFC 9457, health checks, logs JSON com `X-Request-ID`, CI,
ADRs, tipagem estrita (mypy) e lint (ruff).

---

## 2. Como executar

### Docker

```bash
docker compose up --build
```

Abra <http://localhost:8000/docs>. As migrations rodam na inicialização e o banco
SQLite fica no volume `library-data`.

### Local (Poetry >= 2.0)

```bash
poetry install
make run      # aplica migrations e sobe com reload em http://localhost:8000
make check    # ruff + mypy --strict + pytest com cobertura
```

O Poetry está configurado (`poetry.toml`) para criar o virtualenv em `.venv/` e
usar o cache em `.poetry-cache/`, ambos dentro do projeto e ignorados pelo git.

### Exemplos

Há também um arquivo [requests.http](requests.http) para clientes REST (VS Code,
JetBrains) com todas as chamadas.

```bash
curl -X POST localhost:8000/api/v1/books -H 'content-type: application/json' -d '{
  "title": "Dom Casmurro",
  "author": "Machado de Assis",
  "published_date": "1899-12-01",
  "summary": "Bentinho narra a dúvida sobre a fidelidade de Capitu."
}'

curl "localhost:8000/api/v1/books?author=machado"
curl "localhost:8000/api/v1/books?title=casmurro"
curl "localhost:8000/api/v1/books?q=assis&sort=published_date&order=desc&limit=10"
```

### Referência da API

| Método | Rota | Descrição | Status |
|---|---|---|---|
| POST | `/api/v1/books` | Cadastra livro (`Location` relativo no header) | 201, 409, 422 |
| GET | `/api/v1/books` | Busca, ordena e pagina | 200, 422 |
| GET | `/api/v1/books/{id}` | Detalha | 200, 404, 422 |
| PATCH | `/api/v1/books/{id}` | Atualização parcial | 200, 404, 409, 422 |
| DELETE | `/api/v1/books/{id}` | Remove | 204, 404 |
| GET | `/health/live` · `/health/ready` | Probes | 200, 503 |

Parâmetros de `GET /books`: `q`, `title`, `author` (substring, combinados com AND),
`sort` (`title`, `author`, `published_date`, `created_at`), `order` (`asc`/`desc`),
`limit` (1-100, padrão 20), `offset`.

Resposta paginada: `{ "items": [...], "total": 42, "limit": 20, "offset": 0 }`.

Erros seguem [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457)
(`application/problem+json`):

```json
{
  "type": "urn:library-api:problem:book-not-found",
  "title": "Book not found",
  "status": 404,
  "detail": "No book exists with id '...'.",
  "instance": "/api/v1/books/...",
  "code": "book-not-found",
  "request_id": "3f0c5d0e7a5d4a1f9b0d2d8f6a1c2b3e"
}
```

Erros de validação (422) incluem `errors: [{location, message, type}]`. O
`request_id` e o header `X-Request-ID` estão presentes em **todas** as respostas de erro,
inclusive 500.

---

## 3. Como foi implementado

### 3.1 Arquitetura

Camadas com dependências apontando sempre para dentro
([ADR 0001](docs/adr/0001-layered-architecture.md)):

```
HTTP ──► api (routers, deps) ──► services (casos de uso, transação)
                                      │
                                      ▼
                              repositories (SQL) ──► models / db (ORM, SQLite)
transversal: core (config, logging, erros, middleware) · schemas (contratos Pydantic)
```

DDD completo, CQRS ou hexagonal seriam excesso para um CRUD de uma entidade; o ADR
documenta quando e como evoluir. É uma decisão de julgamento, não de falta de
conhecimento.

### 3.2 Estrutura de pastas

```
src/library_api/
  main.py               factory create_app(settings), lifespan, OpenAPI
  api/                  deps.py (injeção), health.py, v1/books.py
  services/book.py      BookService: casos de uso + commit/rollback
  repositories/book.py  BookRepository + BookSearchCriteria (SQL vive só aqui)
  models/book.py        Book (ORM), enums de ordenação
  db/                   base (naming convention), session (engine), types (UTCDateTime)
  schemas/              book.py (contratos de entrada/saída), common.py (Page, ProblemDetail)
  core/                 config, logging, middleware, errors, exceptions, text
migrations/             Alembic (env.py, versions/0001_create_books.py)
tests/                  unit/ · api/ · integration/
docs/adr/               decisões de arquitetura (camadas, busca, escopo/concorrência)
requests.http           coleção de chamadas de exemplo
```

### 3.3 Modelo de dados (`models/book.py`)

| Coluna | Descrição |
|---|---|
| `id` | UUID v4 (seguro para expor; não enumerável) |
| `title`, `author`, `published_date`, `summary` | campos do enunciado |
| `title_search`, `author_search` | **colunas-sombra** normalizadas (ver 3.4) |
| `created_at`, `updated_at` | UTC, tipo `UTCDateTime` |

Restrição `uq_books_identity` em (`title_search`, `author_search`, `published_date`)
e índices nas colunas de busca. Nomes de constraints seguem uma *naming convention*
explícita, o que torna migrations no SQLite (batch mode) confiáveis.

`UTCDateTime` (`db/types.py`) resolve o fato de o SQLite descartar fuso horário:
grava UTC ingênuo, devolve `datetime` com `tzinfo=UTC` e recusa datetimes ingênuos.

### 3.4 Busca (`core/text.py`, `repositories/book.py`, [ADR 0002](docs/adr/0002-search-strategy.md))

O `LIKE` do SQLite só ignora caixa em ASCII e desconhece acentos (`joao` não acharia
`João`). Solução: `normalize_for_search` aplica NFKD, remove marcas combinantes,
`casefold` e colapsa espaços. O resultado é persistido nas colunas-sombra (mantidas
por `@validates` no modelo) e a consulta do usuário passa pela mesma função.

- `title` e `author`: "contém" (substring), combinados com **AND**.
- `q`: título **ou** autor. Cobre as duas interpretações do enunciado.
- `%` e `_` digitados pelo usuário são escapados (`autoescape=True`).
- A ordenação sempre termina no `id` (desempate), garantindo paginação estável.
- Duas queries: página e `COUNT` com os mesmos filtros.

### 3.5 Camada de serviço e transações (`services/book.py`)

O `BookService` é a fronteira transacional (unit of work): cada operação de escrita
faz `commit` ou `rollback`. O repositório apenas `flush`a e traduz em
`DuplicateBookError` (409) **somente** violações de unicidade
(`SQLITE_CONSTRAINT_UNIQUE`); outras violações (ex.: `NOT NULL`) propagam como erro de
programação. A duplicidade é garantida por constraint no banco, não por "checar antes
de inserir", o que a torna segura contra condições de corrida; o teste
`test_concurrency.py` dispara 8 POSTs simultâneos e exige exatamente um 201.
`PATCH` aplica só os campos enviados (`exclude_unset`), e a atualização das colunas
de busca acontece automaticamente pelos validators.

### 3.6 Contratos (`schemas/`)

Pydantic v2 com tipos anotados reutilizáveis (`Title`, `Author`, `PublishedDate`,
`Summary`), `strip_whitespace`, limites de tamanho, rejeição de caracteres de controle
(NUL etc.; quebras de linha são permitidas), `extra="forbid"` e data de publicação não
futura. `BookUpdate` rejeita corpo vazio e `null` explícito. Os
parâmetros de query formam o modelo `BookSearchParams`, o que documenta e valida a
listagem no OpenAPI.

### 3.7 Erros (`core/exceptions.py`, `core/errors.py`)

Hierarquia `AppError → NotFoundError/ConflictError → BookNotFoundError/DuplicateBookError`.
Handlers globais convertem domínio, validação, erros HTTP do framework e exceções
inesperadas em `problem+json`. O 500 nunca vaza detalhes internos: o traceback vai
para o log e o cliente recebe apenas o `request_id`. O id é propagado por
`request.state` (o handler de 500 roda fora do middleware, onde o `ContextVar` já foi
restaurado). O header `Location` do POST é um caminho relativo, então nunca reflete o
`Host` enviado pelo cliente.

### 3.8 Observabilidade (`core/middleware.py`, `core/logging.py`)

Middleware ASGI puro (sem `BaseHTTPMiddleware`) que aceita `X-Request-ID` apenas se
for seguro (regex), senão gera UUID; expõe o id via `ContextVar`, devolve no header e
emite um log de acesso por requisição (método, path, status, `duration_ms`). Logs em
texto no desenvolvimento e JSON de uma linha em produção. `/health/live` (processo) e
`/health/ready` (consulta `SELECT 1`, 503 se o banco falhar).

### 3.9 Banco e migrations (`db/session.py`, `migrations/`)

Engine SQLite com `PRAGMA foreign_keys=ON`, `busy_timeout` e WAL (só em arquivo).
Banco em memória usa `StaticPool`. O schema é criado **apenas via Alembic**; um teste
de integração executa `upgrade head`, compara as migrations com os models
(`compare_metadata` deve ser vazio), roda o `downgrade` e valida o modo offline (`--sql`).

### 3.10 Configuração (`core/config.py`)

`pydantic-settings`, prefixo `LIBRARY_`, aceita `.env`. A aplicação nasce de
`create_app(settings)`: sem estado global, o que permite testes isolados.

### 3.11 Testes (`tests/`)

- **unit/**: normalização, schemas, tipo de data, engine/pragmas, logging, settings,
  tradução de erros de integridade no repositório.
- **api/**: cadastro (201, duplicata, validação), busca (acentos, AND/OR, wildcards,
  ordenação, paginação, parâmetros inválidos), item (404, PATCH, rollback em 409,
  DELETE), plataforma (health, request-id, log de acesso, erros, OpenAPI).
- **integration/**: migrations reais e concorrência de escritas em SQLite de arquivo.

Cada teste usa uma aplicação nova com SQLite em memória. `filterwarnings = error`
transforma warnings em falhas; cobertura mínima de 95% é imposta pelo pytest.

### 3.12 Qualidade e entrega

- `ruff` (E, F, I, N, UP, B, D com convenção Google, S, ANN, DTZ, entre outros),
  `mypy --strict`, pre-commit e CI (GitHub Actions: lint, tipos, testes e build/smoke
  test da imagem, executado com filesystem read-only), Dependabot.
- **Docstrings Google são a única forma de comentário** no código Python.
- **Dockerfile** multi-stage: o builder instala o Poetry e as dependências (camada
  cacheada pelo `poetry.lock`); o runtime é `python:slim` com `.venv` copiado, usuário
  não-root (uid 10001), `HEALTHCHECK` em `/health/ready`, volume `/data` e entrypoint que executa
  `alembic upgrade head` antes do `uvicorn`. O `compose` roda com filesystem
  read-only e `no-new-privileges` (a imagem também funciona com `--read-only --tmpfs /tmp`).

---

## 4. Configuração

Variáveis `LIBRARY_*` (ver `.env.example`): `DATABASE_URL`, `LOG_LEVEL`, `LOG_JSON`,
`DOCS_ENABLED`. Em produção, desligue a documentação com `LIBRARY_DOCS_ENABLED=false`.

## 4.1 Fora do escopo

Autenticação, CORS, rate limiting, ISBN e controle otimista (`ETag`) foram
deliberadamente omitidos e estão justificados, com o caminho de evolução, no
[ADR 0003](docs/adr/0003-scope-and-non-goals.md). `PATCH` é *last-write-wins*.

## 5. Licença

MIT - veja [LICENSE](LICENSE).

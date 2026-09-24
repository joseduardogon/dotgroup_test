# Virtual Library API

API REST para cadastrar e consultar livros de uma biblioteca virtual.
Desafio técnico - **Questão 1** (FastAPI + SQLite + testes).

## Requisitos atendidos

| Requisito | Onde |
|---|---|
| Cadastro com título, autor, data de publicação e resumo | `POST /api/v1/books` |
| Consulta por título ou autor | `GET /api/v1/books?title=`, `?author=`, `?q=` (título **ou** autor) |
| FastAPI | `src/library_api` |
| SQLite | SQLAlchemy 2 + Alembic |
| Endpoints documentados | Swagger em `/docs`, ReDoc em `/redoc` |
| Testes unitários dos endpoints | `tests/` (63 testes, cobertura ~99%, mínimo exigido 95%) |
| Docker | `Dockerfile` multi-stage + `docker-compose.yml` |

Além do pedido: `GET/PATCH/DELETE /books/{id}`, paginação, ordenação, busca
insensível a acentos e caixa, erros RFC 9457, migrations, health checks, logs JSON
com `X-Request-ID`, CI, ADRs.

## Executando

### Docker

```bash
docker compose up --build
```

Acesse <http://localhost:8000/docs>. As migrations rodam na inicialização e o banco
fica no volume `library-data`.

### Local (Poetry)

```bash
poetry install
make run          # migra o banco e sobe com reload em http://localhost:8000
make check        # ruff + mypy --strict + pytest com cobertura
```

## Exemplos

```bash
curl -X POST localhost:8000/api/v1/books -H 'content-type: application/json' -d '{
  "title": "Dom Casmurro",
  "author": "Machado de Assis",
  "published_date": "1899-12-01",
  "summary": "Bentinho narra a dúvida sobre a fidelidade de Capitu."
}'

curl "localhost:8000/api/v1/books?author=machado"          # por autor
curl "localhost:8000/api/v1/books?title=casmurro"          # por título
curl "localhost:8000/api/v1/books?q=assis&sort=published_date&order=desc&limit=10"
```

### Endpoints

| Método | Rota | Descrição | Status |
|---|---|---|---|
| POST | `/api/v1/books` | Cadastra livro | 201, 409, 422 |
| GET | `/api/v1/books` | Busca, ordena e pagina | 200, 422 |
| GET | `/api/v1/books/{id}` | Detalha | 200, 404 |
| PATCH | `/api/v1/books/{id}` | Atualização parcial | 200, 404, 409, 422 |
| DELETE | `/api/v1/books/{id}` | Remove | 204, 404 |
| GET | `/health/live`, `/health/ready` | Probes | 200, 503 |

Resposta de listagem: `{ "items": [...], "total": 42, "limit": 20, "offset": 0 }`.

Erros seguem `application/problem+json`:

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

## Decisões de design

* **Camadas** `api -> services -> repositories -> models` ([ADR 0001](docs/adr/0001-layered-architecture.md)).
  Para este escopo, DDD completo seria excesso; o caminho de evolução está descrito no ADR.
* **Busca** em colunas normalizadas (sem acento, `casefold`) com escape de `%`/`_`
  ([ADR 0002](docs/adr/0002-search-strategy.md)).
* **Identidade do livro**: (título, autor, data) normalizados; duplicata retorna 409,
  garantida por constraint no banco (à prova de corrida), não por checagem prévia.
* **Transações** pertencem ao service; o repositório só faz `flush`.
* **Datas** de publicação não podem estar no futuro; timestamps são UTC.
* **Testes** isolados com SQLite em memória por teste, mais um teste de integração que
  executa as migrations reais e garante que não há divergência com os models.
* **Segurança do container**: usuário não-root, filesystem read-only, healthcheck.

## Configuração

Variáveis com prefixo `LIBRARY_` (ver `.env.example`): `DATABASE_URL`, `LOG_LEVEL`,
`LOG_JSON`, `DOCS_ENABLED`, `ENVIRONMENT`.

## Estrutura

```
src/library_api/
  api/            routers, dependências, health
  services/       casos de uso e transações
  repositories/   acesso a dados
  models/ db/     ORM, tipos, engine SQLite (WAL, foreign keys)
  schemas/        contratos Pydantic
  core/           config, logging, erros, middleware
migrations/       Alembic
tests/            unit, api, integration
docs/adr/         decisões de arquitetura
```

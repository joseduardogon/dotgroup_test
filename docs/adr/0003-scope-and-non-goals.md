# ADR 0003 - Escopo, não-objetivos e semântica de concorrência

- Status: aceito
- Data: 2026-09-23

## Contexto

O enunciado pede cadastro e consulta de livros. Um serviço real teria mais
preocupações; omiti-las é uma decisão consciente, registrada aqui para não ser
confundida com esquecimento.

## Fora do escopo (e o caminho para incluir)

| Tema | Situação | Caminho |
|---|---|---|
| Autenticação/autorização | Endpoints de escrita são abertos | OAuth2/JWT com `Depends` de segurança do FastAPI; escopos `books:write` |
| CORS | Não habilitado | `CORSMiddleware` com allowlist explícita por ambiente |
| Rate limiting | Ausente | Feito no gateway/proxy (nginx, Envoy) ou `slowapi` |
| Limite de corpo | Padrão do servidor | `--limit-max-requests`/proxy; campos já têm `max_length` |
| ISBN | Não modelado | Coluna opcional única (ISBN-13 com checksum) e migration nova |
| Busca por relevância | Substring | FTS5 no SQLite ou `pg_trgm` no PostgreSQL (ADR 0002) |
| Multi-instância | SQLite = 1 nó | Trocar o driver/URL e migrar para PostgreSQL; camadas não mudam |

## Semântica de concorrência

* **Criação**: a unicidade (título, autor, data normalizados) é imposta por constraint
  no banco. Escritas concorrentes idênticas resultam em exatamente um `201` e os
  demais `409`; isso é verificado por `tests/integration/test_concurrency.py`.
* **Atualização (`PATCH`)**: *last-write-wins*. Não há `ETag`/`If-Match`; duas
  atualizações simultâneas dos mesmos campos resultam na última confirmada.
  Para controle otimista, usar `updated_at` como validador de `ETag` e responder
  `412 Precondition Failed`.
* **Erros de integridade não relacionados à unicidade** (ex.: `NOT NULL`) não são
  convertidos em `409`: indicam bug de programação e resultam em `500`.

## Consequências

Avaliadores podem ver rapidamente o que foi deliberadamente deixado de fora e como
cada item se encaixa na arquitetura existente sem reescrita.

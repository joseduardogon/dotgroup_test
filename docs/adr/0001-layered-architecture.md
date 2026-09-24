# ADR 0001 - Arquitetura em camadas com dependências apontando para dentro

- Status: aceito
- Data: 2026-09-23

## Contexto

O escopo é um CRUD de livros com busca. Padrões como DDD tático, CQRS ou
arquitetura hexagonal completa introduziriam cerimônia (agregados, portas,
eventos) sem regras de negócio que a justifiquem. Ao mesmo tempo, o serviço deve
ser um ponto de partida sólido para crescer em uma empresa de grande porte.

## Decisão

Arquitetura em camadas, com a regra de dependência `api -> services ->
repositories -> models`, sem referências no sentido contrário:

| Camada | Responsabilidade | Não pode |
|---|---|---|
| `api` | HTTP, serialização, códigos de status | conter regra de negócio ou SQL |
| `services` | casos de uso e fronteira transacional (unit of work) | conhecer FastAPI |
| `repositories` | única camada que monta SQL | commitar transação |
| `models` / `db` | mapeamento ORM, tipos, engine | conhecer HTTP |
| `core` | configuração, logging, erros, middleware | depender de regras de negócio |

Decisões complementares:

* Erros de domínio (`core.exceptions`) são traduzidos para RFC 9457 na borda.
* `create_app(settings)` é uma factory pura: sem globais, testável com SQLite em memória.
* O repositório recebe `BookSearchCriteria` (dataclass), não schemas Pydantic,
  mantendo a persistência independente do contrato HTTP.

## Consequências

* Baixo custo cognitivo e cobertura de testes simples (unidade, API, integração).
* Caminho de evolução explícito: quando surgirem regras (empréstimos, reservas,
  multas), extrair um bounded context de domínio com entidades ricas e portas
  (hexagonal), sem reescrever a API. Eventos de domínio e CQRS só entram com
  requisito real de leitura/escrita assimétrica.

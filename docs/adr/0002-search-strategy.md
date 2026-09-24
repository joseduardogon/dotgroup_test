# ADR 0002 - Busca por colunas normalizadas

- Status: aceito
- Data: 2026-09-23

## Contexto

Usuários pesquisam por título ou autor em português. O `LIKE` do SQLite só ignora
maiúsculas/minúsculas para ASCII e não conhece acentos: `joao` não encontraria `João`.

## Alternativas

1. `LIKE` direto - falha com acentos e caixa não ASCII.
2. Collation ICU / extensões - indisponíveis no SQLite padrão e frágeis em Docker.
3. FTS5 - excelente para relevância e palavras, excessivo aqui e sem substring.
4. **Colunas sombra normalizadas** (escolhida).

## Decisão

`title_search` e `author_search` guardam o texto após NFKD, remoção de marcas
combinantes, `casefold` e colapso de espaços. Os validators do modelo as mantêm
sincronizadas; a consulta do usuário passa pela mesma função. Caracteres `%` e `_`
são escapados (`autoescape`).

As mesmas colunas compõem a restrição de unicidade
(`title_search`, `author_search`, `published_date`), impedindo duplicatas que só
diferem por caixa, acentos ou espaços.

## Consequências

* Comportamento determinístico e testado, independente do build do SQLite.
* Busca por substring faz varredura (`%x%` não usa índice). Para catálogos grandes,
  migrar para FTS5 ou PostgreSQL com `pg_trgm`; a interface do repositório não muda.

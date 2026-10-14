# Geopolitical Watch — Beta de uso inicial

## Objetivo

Permitir uso real do monitor nesta semana sem esperar GCP, UCDP, ReliefWeb, FIRMS ou ACLED.

## Perfil público

O Beta usa somente fontes que podem operar sem segredo restrito no repositório:

- GDELT DOC 2.0 como sinal de publicação/notícia;
- GDACS como contexto institucional de desastres e interrupções.

Nenhuma dessas fontes, isoladamente, confirma atribuição militar. As mesmas regras de evidência do runtime principal continuam válidas.

## Execução automática

`.github/workflows/public-beta-monitor.yml` tem duas trilhas: o agendamento (`17 */2 * * *`, a cada duas horas) apenas acorda o runtime gratuito e verifica `/health`; a coleta completa abaixo roda somente por disparo manual (`workflow_dispatch`). Cada execução manual:

1. cria banco SQLite efêmero;
2. coleta as fontes públicas do perfil `config/sources.public-beta.json`;
3. normaliza eventos e cria episódios;
4. gera report situacional e report de episódios;
5. publica o report mais recente no GitHub Actions job summary;
6. salva JSON/Markdown como artifact por 1 dia.

## Execução local

```bash
python -m geowatch collect \
  --config config/sources.public-beta.json \
  --db data/beta.db \
  --raw data/raw \
  --reports reports
```

Depois:

- `reports/latest.md` — visão baseada em clusters/eventos;
- `reports/episodes/latest.md` — visão baseada em episódios persistentes;
- `python -m geowatch serve` — API/dashboard local usando o banco configurado.

## Limitações assumidas

- O banco do workflow é efêmero e não substitui PostgreSQL/PostGIS de produção.
- Histórico longo depende de backfill e fontes credenciadas.
- O Beta é utilizável para acompanhamento e validação editorial, não é ainda o gate de produção v1.0.
- Readiness, EvidenceStrength e alertas preservam as mesmas definições do projeto principal.

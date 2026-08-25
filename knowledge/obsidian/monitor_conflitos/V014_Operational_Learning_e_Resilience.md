---
title: v0.14 - Operational Learning e Resilience
project: Monitor de Conflitos
updated: 2026-08-25
knowledge_status: canonical
---

# v0.14 — Operational Learning & Resilience

## Problema
A v0.13 tornou o Beta operacional e criou snapshots, deltas, histórico UCDP e forecast benchmarks. A v0.14 fecha a lacuna entre “rodar” e “aprender com a operação”.

## Mudanças centrais
- Histórico de saúde por fonte com retenção de 365 dias.
- Disponibilidade, incidentes, MTTR e freshness por fonte.
- SLO operacional por provider.
- Circuit breaker com `closed / open / half_open`.
- Backoff exponencial com jitter determinístico e limites.
- Failover conservador: fallback do mesmo provider não conta como nova corroboração.
- Last-known-state pode ser servido somente com marcação explícita de staleness.
- Forecasting prospectivo append-only por episódio e horizonte 1/7/30/90 dias.
- Postmortem obrigatório para falhas materiais.
- Human-gold com review batch e validação explícita.
- Geoeconomia com fluxos datados e missing tratado como desconhecido.
- Promoção de infraestrutura exigindo identidade corroborada e evidência estratégica adicional.

## Relação causal
Provider instável → degradação de cobertura → maior risco de stale state → circuit breaker evita sobrecarga → last-known-state preserva continuidade → health permanece degradado → nenhuma falsa confirmação é criada.

## Lição operacional de 25/08/2026
No gate final da v0.13, uma execução encontrou GDELT HTTP 429 e GDACS HTTP 503 simultaneamente. O sistema classificou corretamente a execução como degradada e sem cobertura de conflito. A repetição posterior passou. Esse resultado negativo foi preservado porque demonstra que o fail-closed funciona e motivou SLO, MTTR, circuit breaker e backoff adaptativo.

## O que esta nota não afirma
- Não afirma disponibilidade mensal real antes de existir histórico suficiente.
- Não afirma MTTR representativo com poucas observações.
- Não afirma precisão de inteligência.
- Não fecha gates de produção GCP/Cloud SQL.

## Links
- [[MOC_Monitor_de_Conflitos]]
- [[Operacao_Beta_SLO_Incidentes_e_MTTR]]
- [[Human_Gold_Calibracao_e_Forecasting]]

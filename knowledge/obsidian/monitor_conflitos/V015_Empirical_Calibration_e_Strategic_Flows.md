---
title: v0.15 - Empirical Calibration e Strategic Flows
project: Monitor de Conflitos
updated: 2026-08-25
knowledge_status: canonical
---

# v0.15 — Empirical Calibration & Strategic Flows

## Objetivo
Mover o sistema de frameworks preparados para evidência empírica acumulável, sem fabricar resultados humanos, temporais ou de produção.

## Operação/SLO
- dashboard 7/30/90 dias;
- error budget e burn rate;
- reliability score estritamente operacional;
- stale coverage alerts;
- provider availability continua separada de qualidade analítica.

## Human-gold
- interface HTML e pacotes CSV para dois revisores;
- concordância pairwise + Cohen kappa;
- divergências vão para adjudicação;
- gold só nasce de consenso humano ou adjudicação humana;
- calibração usa apenas gold;
- holdout determinístico nunca entra no threshold search.

## Forecasting
- ledger prospectivo continua append-only;
- reliability diagram, Brier skill, skill por horizonte e largest misses;
- erro material de forecast pode gerar postmortem;
- track record só existe quando resultados são efetivamente resolvidos.

## Infraestrutura e fluxos
- WPI completo é normalizado, não apenas top-300;
- UN/LOCODE global é ingerido para identidade/localização;
- crosswalk WPI × UN/LOCODE global;
- identidade não prova criticidade;
- UN Comtrade escala com chave e bloqueia claims de matriz completa quando usa preview;
- FAOSTAT, USGS MCS e EIA International recebem adapters/gates públicos.

## Governança de fontes
- FAOSTAT Detailed Trade usa principalmente UNSD/Eurostat e pode imputar parceiro; não conta como corroboração independente de UN Comtrade para a mesma célula.
- FAOSTAT flags precisam ser preservadas para distinguir oficial, estimado/imputado e outras origens.
- EIA API v2 exige API key; bulk público não deve ser bloqueado por ausência da chave.
- USGS MCS data release é fonte estrutural de minerais, não sinal de conflito.

## Hard gates que continuam abertos
- revisão humana real dos lotes;
- ≥200 forecasts prospectivos resolvidos;
- ≥50 nós estratégicos com evidência adicional real;
- produção GCP/Cloud SQL/restore/security/cost.

[[Release_v0.14.0]]
[[Human_Gold_Calibracao_e_Forecasting]]
[[Fontes_Estrategicas_e_Geoeconomia]]

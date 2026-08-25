---
title: Human Gold, Calibracao e Forecasting
project: Monitor de Conflitos
updated: 2026-08-25
knowledge_status: canonical
---

# Human Gold, Calibração e Forecasting

## Human-gold
Research-coded, heurístico, pre-gold ou modelo não é human-gold. Uma observação só vira gold quando há:
1. tarefa de revisão definida;
2. rótulo humano válido;
3. identificador do revisor;
4. timestamp de revisão;
5. preservação do contexto apresentado ao revisor.

Tarefas iniciais:
- `episode_merge_split`: `separate` ou `merge`;
- `conflict_vs_context`: `conflict` ou `context`.

Metas de 100 e 500 decisões são gates de volume, não garantias de qualidade.

## Calibração
Thresholds por região e source mix só podem ser estudados após amostra mínima. A v0.14 usa 30 casos por segmento como piso técnico inicial e não promove thresholds automaticamente.

Métricas:
- precision;
- recall;
- false-positive rate;
- estabilidade temporal;
- desempenho por região;
- desempenho por combinação de fontes.

## Forecasting prospectivo
O ledger é append-only. Cada previsão registra:
- episode_id;
- criação;
- information cutoff;
- horizonte 1/7/30/90 dias;
- resultado alvo;
- probabilidade original;
- estado do episódio e EvidenceStrength na criação;
- prazo de resolução;
- resultado observado quando resolvido.

A probabilidade original não pode ser reescrita depois do resultado.

## Métrica
Brier Score para resultados binários: média de `(p - y)^2`; menor é melhor. Avaliar também por horizonte e calibração.

## Separações obrigatórias
- Forecast probability ≠ EvidenceStrength.
- Track record retrospectivo ≠ track record prospectivo.
- Base rate ≠ causal model.
- Boa calibração histórica ≠ garantia de desempenho futuro.

## Postmortem
Falso positivo/negativo material e erro relevante de forecast devem produzir postmortem. O postmortem pode gerar proposta de aprendizado, nunca mudança automática de modelo.

## Links
- [[MOC_Monitor_de_Conflitos]]
- [[Governanca_de_Evidencia_e_Aprendizado]]

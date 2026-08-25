---
title: Operacao Beta - SLO, Incidentes e MTTR
project: Monitor de Conflitos
updated: 2026-08-25
knowledge_status: canonical
---

# Operação Beta — SLO, Incidentes e MTTR

## Conceitos
**Disponibilidade da fonte** mede quantas observações operacionais terminaram com sucesso. Não mede qualidade editorial ou inteligência.

**Freshness** é a idade da última referência observada disponível para a fonte. Freshness precisa usar o timestamp do dado, não apenas o horário de coleta.

**Incidente** inicia quando uma fonte deixa de retornar sucesso e termina quando volta a retornar sucesso. Falhas transitórias e estruturais são separadas.

**MTTR** é a média do tempo entre o início de incidentes fechados e sua recuperação. Uma amostra pequena não deve ser generalizada.

## Estados do circuit breaker
- `closed`: requisições normais.
- `open`: falhas consecutivas excederam o limite; novas requisições são temporariamente bloqueadas.
- `half_open`: cooldown terminou e uma requisição de prova é permitida.

## SLO inicial
GDELT: freshness alvo 3h, disponibilidade alvo 95%.
GDACS: freshness alvo 12h, disponibilidade alvo 95%.
Bases estruturais anuais/menos frequentes usam janelas maiores.

Esses valores são objetivos operacionais iniciais e devem ser recalibrados depois de histórico suficiente.

## Falhas
- 429/5xx/timeout/conexão: normalmente `transient_failure`.
- parser/schema/configuração: `structural_failure` e fail-closed.

## Fallback
Reduzir janela ou volume de consulta ao mesmo provider é resiliência de coleta, não corroboração independente.

Servir estado anterior exige:
- timestamp original;
- marcação stale;
- health degradado;
- proibição de transformar ausência de dado novo em estabilidade confirmada.

## Evidência empírica inicial
25/08/2026: GDELT retornou 429 e GDACS 503 no mesmo smoke; a tentativa seguinte passou. Isso é evidência de indisponibilidade transitória, não prova de defeito interno.

## Links
- [[V014_Operational_Learning_e_Resilience]]
- [[Governanca_de_Evidencia_e_Aprendizado]]

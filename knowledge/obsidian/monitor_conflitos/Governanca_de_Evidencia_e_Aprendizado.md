---
title: Governanca de Evidencia e Aprendizado
project: Monitor de Conflitos
updated: 2026-08-25
knowledge_status: canonical
---

# Governança de Evidência e Aprendizado

## Cadeia canônica
`MOC → Síntese → Nota → Afirmação → Evidência → Fonte`

## Classes epistemológicas
- **OBSERVADO**: dado/evento diretamente publicado ou coletado de fonte identificada.
- **CALCULADO**: transformação determinística de observações.
- **ESTIMADO**: valor inferido por método explícito com incerteza.
- **PROJETADO**: valor futuro condicionado a modelo/cenário.
- **INFERIDO**: conclusão analítica suportada por evidências, mas não diretamente observada.
- **SINAL**: indicador sugestivo, insuficiente para confirmação.
- **SOURCE_LAG**: dado válido, porém defasado para o contexto atual.

## Separações obrigatórias
Fonte confiável não torna automaticamente uma afirmação verdadeira. Qualidade da fonte e confiança na afirmação são eixos distintos.

Contexto estrutural não é verificação de evento.

Uma fonte institucional pode publicar análise derivada de dados comerciais; a linhagem deve registrar ambos.

## Aprendizado
1. previsão/decisão é registrada antes do resultado;
2. resultado é observado;
3. erro é medido;
4. falha material gera postmortem;
5. postmortem pode gerar proposta de aprendizado;
6. proposta passa por validação;
7. somente então pode existir mudança de regra/modelo.

Nenhum erro autoriza alteração automática de threshold/modelo.

## Human-gold
Gold só existe após revisão humana registrada. Pesquisa codificada por terceiro (ex.: UCDP) é evidência histórica especializada, não human-gold interno.

## Infraestrutura
Identidade corroborada ≠ criticidade. Criticidade exige evidência estratégica adicional e datada.

## Operação
Provider outage ≠ system failure. Ambos devem aparecer separadamente no health.

## Resultados negativos
Indisponibilidade de fonte, hipótese rejeitada, forecast errado, falso positivo, falso negativo e falha de integração devem permanecer na memória.

## Links
- [[MOC_Monitor_de_Conflitos]]
- [[V014_Operational_Learning_e_Resilience]]
- [[Human_Gold_Calibracao_e_Forecasting]]

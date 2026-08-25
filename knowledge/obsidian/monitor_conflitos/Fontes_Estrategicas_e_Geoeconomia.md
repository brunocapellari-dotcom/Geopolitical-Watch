---
title: Fontes Estrategicas e Geoeconomia
project: Monitor de Conflitos
updated: 2026-08-25
knowledge_status: canonical
---

# Fontes Estratégicas e Geoeconomia

## UN/LOCODE — UNECE
Referência estrutural para localidades de comércio e transporte. A página oficial consultada em 25/08/2026 informa mais de 103.034 localidades em 249 países/territórios e release atual 2025-1. O código de função permite distinguir porto, terminal ferroviário, rodoviário, aeroporto etc.

Uso no Geopolitical Watch:
- corroborar identidade/localização de porto;
- padronizar código de localidade;
- não usar sozinho como prova de criticidade geopolítica.

## UN Comtrade — UNSD
Fonte de comércio bilateral reportado por autoridades estatísticas nacionais.

API:
- preview público sem chave, com limite reduzido;
- API completa/free tier mediante conta e subscription key;
- dimensões incluem reporter, partner, período, fluxo, classificação e commodity.

Uso:
- fluxos bilaterais datados;
- energia, alimentos, fertilizantes e minerais por HS;
- concentração de parceiros e dependência relativa.

Limitação central: países publicam em calendários diferentes. Data de referência e data de coleta devem ser preservadas. Ausência de registro não é zero.

## EIA — World Oil Transit Chokepoints
Fonte oficial analítica para fluxos energéticos em chokepoints. Atualização consultada: 03/03/2026, com dados até 1H25.

Uso:
- baseline energético de Hormuz, Malaca, Suez/SUMED, Bab el-Mandeb, Turkish Straits e Panamá;
- alternativas de rota/pipeline quando publicadas;
- exposição estrutural, não probabilidade de fechamento.

A publicação informa que parte da análise usa tanker tracking da Vortexa. Preservar essa linhagem metodológica: publicação oficial EIA + insumo comercial citado.

## Panama Canal Authority
Relatório anual FY2025: 13.404 trânsitos, +19,3% frente ao FY2024. Usar como dado operacional/estrutural do canal, mantendo segmento e período.

## UNCTAD
Referência de comércio marítimo e efeitos de disrupções. A análise consultada indica aproximadamente um décimo do comércio marítimo global passando pelo Suez em 2023 e forte queda dos trânsitos após a crise do Mar Vermelho. O dado de share usa insumos Clarksons, portanto a linhagem deve ser visível.

## Fontes planejadas
- FAOSTAT: produção e contexto agroalimentar.
- EIA International: energia.
- USGS Mineral Commodity Summaries/estatísticas: minerais críticos.

## Regra de modelagem
Observação geoeconômica = `{source_id, reference_period, collected_at, reporter/origin, partner/destination, commodity, value, unit}`.

Derivações como share, HHI e top-3 concentration são cálculos, nunca observações brutas.

## Links
- [[Chokepoints_Baselines_e_Cenarios]]
- [[Governanca_de_Evidencia_e_Aprendizado]]

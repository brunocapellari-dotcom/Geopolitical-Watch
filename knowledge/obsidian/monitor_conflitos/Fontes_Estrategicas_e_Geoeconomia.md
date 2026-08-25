---
title: Fontes Estrategicas e Geoeconomia
project: Monitor de Conflitos
updated: 2026-08-25
knowledge_status: canonical
---

# Fontes Estratégicas e Geoeconomia

## UN/LOCODE / UNECE
Referência estrutural para localidades de comércio e transporte. Release oficial consultada: 2025-1. A UNECE informa mais de 103 mil localidades em 249 países e territórios. Serve para identidade, localização e função de portos; não prova criticidade geopolítica.

O pipeline usa WPI × UN/LOCODE para corroborar identidade. Um espelho público pode ser usado apenas como transporte operacional dos bytes; UNECE permanece a fonte canônica e o espelho não conta como evidência independente.

## UN Comtrade / UNSD
Comércio bilateral oficial reportado por autoridades estatísticas nacionais.
- Preview público sem chave: limite reduzido.
- API `data/v1/get` com subscription key para volumes maiores.
- O piloto estratégico usa partner distributions, não apenas Partner=World.
- Se o preview atingir o cap, a matriz é marcada como possivelmente censurada e não pode ser tratada como completa.
- Ausência de registro não é zero.

## FAOSTAT
FAOSTAT fornece dados públicos de alimentação e agricultura, com datasets versionados e flags de qualidade/origem que devem permanecer no pipeline.

Datasets estratégicos da v0.15:
- Crop Production `d24a448b-3b62-4c09-8c1d-4a39bb599876`: 1961–2024; área, produção e rendimento; valores nacionais podem ser oficiais, não oficiais ou imputados, portanto a flag é obrigatória.
- Detailed Trade Matrix `955a7b61-ce56-4a04-adf5-61a3012eec84`: 1961–2024; quantidade/valor de importação e exportação; fonte principal UNSD/Eurostat e fontes nacionais; partner data e food-aid podem preencher lacunas.
- Detailed Fertilizers Trade Matrix `d5b0de53-e1d6-4060-b1d0-8443d4e13d5f`: 1990–2023; origem UN Comtrade. Por isso não é corroboração independente de uma célula Comtrade equivalente.
- Fertilizers by Nutrient `4e50bf79-ddf5-41b1-8608-468eca2697e2`: questionários FAO + UN Comtrade e fontes secundárias para gaps; preservar lineage/flags.
- Food Balances `2f264bb6-1238-459a-bf8b-0e2d0a16804a`: 2010–2023.

Status: adapters e catalog smokes entram na v0.15. Acesso ao catálogo não equivale a backfill numérico completo.

## EIA International
A EIA mantém API v2 e arquivos bulk da base International.
- API v2 exige `EIA_API_KEY`.
- bulk manifest público pode ser inspecionado sem chave.
- valores da API podem vir como strings e são normalizados com unidade e período preservados.
- ausência da chave EIA não bloqueia FAOSTAT, USGS, Comtrade preview ou outros providers.

## USGS Mineral Commodity Summaries 2026
Data release público DOI `10.5066/P1WKQ63T`, ScienceBase item `69837e43b66b01367d7ec7c7`, cobrindo dados 2021–2025. A MCS 2026 cobre mais de 90 minerais/materiais e é referência estrutural para produção, reservas, recursos e dependência de minerais.

Status: metadata/file inventory + parser estruturado entram na v0.15. Estrutura mineral é contexto geoeconômico, não sinal de conflito.

## EIA World Oil Transit Chokepoints
Publicação atualizada em 03/03/2026. O baseline 1H25 usado nos scenario packs inclui Malaca, Hormuz, Suez/SUMED, Bab el-Mandeb, Turkish Straits e Panamá. É exposição datada, não status operacional ao vivo.

## Regras de linhagem
- Toda observação mantém `source_id`, período de referência, data de coleta, unidade e entidade/commodity.
- OBSERVADO, CALCULADO, ESTIMADO e SOURCE_LAG permanecem separados.
- FAOSTAT trade derivado de UN Comtrade não conta como fonte independente contra a mesma célula UN Comtrade.
- Dados estruturais não confirmam eventos de conflito ao vivo.
- Missing data não vira zero sem regra explícita do provider.

[[MOC_Monitor_de_Conflitos]]
[[Chokepoints_Baselines_e_Cenarios]]
[[V015_Empirical_Calibration_e_Strategic_Flows]]

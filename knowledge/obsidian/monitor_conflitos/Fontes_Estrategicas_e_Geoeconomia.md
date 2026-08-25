---
title: Fontes Estrategicas e Geoeconomia
project: Monitor de Conflitos
updated: 2026-08-25
knowledge_status: canonical
---

# Fontes Estratégicas e Geoeconomia

## UN/LOCODE / UNECE
Referência estrutural para localidades de comércio e transporte. Release oficial consultada: 2025-1. A UNECE informa mais de 103 mil localidades em 249 países e territórios. Serve para identidade, localização e função de portos; não prova criticidade geopolítica.

O pipeline usa WPI × UN/LOCODE para corroborar identidade. Um espelho público em GitHub pode ser usado apenas como transporte operacional dos bytes; UNECE permanece a fonte canônica e o espelho não conta como evidência independente.

## UN Comtrade / UNSD
Comércio bilateral oficial reportado por autoridades estatísticas nacionais.
- Preview público sem chave: limite reduzido.
- API `data/v1/get` com subscription key para volumes maiores.
- O piloto estratégico usa partner distributions, não apenas Partner=World.
- Se o preview atingir o cap, a matriz é marcada como possivelmente censurada e não pode ser tratada como completa.
- Ausência de registro não é zero.

## FAOSTAT
FAOSTAT fornece acesso gratuito a dados de alimentação e agricultura para mais de 245 países e territórios, desde 1961 até o ano mais recente disponível. Existem API Developer Portal e bulk downloads.
Status no Monitor: `public_ready`, aguardando validação de identificadores de datasets/domínios antes de ingestão de produção.

## EIA International
A EIA mantém API v2 e arquivos bulk da base International. A API v2 exige API key gratuita.
Status no Monitor: `credential_blocked` para API; essa credencial não pode bloquear FAOSTAT, Comtrade, USGS ou demais fontes públicas.

## USGS Mineral Commodity Summaries 2026
Publicação de 06/02/2026, com data release público DOI `10.5066/P1WKQ63T`, cobrindo dados 2021–2025. A MCS 2026 contém mais de 90 minerais/materiais e é base para produção mundial, reservas, recursos e dependência de minerais críticos.
Status no Monitor: `public_ready`, aguardando resolução e validação do asset estruturado do data release.

## EIA World Oil Transit Chokepoints
Publicação atualizada em 03/03/2026. O baseline 1H25 usado nos scenario packs inclui Malaca, Hormuz, Suez/SUMED, Bab el-Mandeb, Turkish Straits e Panamá. É exposição datada, não status operacional ao vivo.

## Regras
Toda observação deve manter `source_id`, período de referência, data de coleta, unidade e entidade/commodity.
OBSERVADO, CALCULADO, ESTIMADO e SOURCE_LAG permanecem separados.
Dados estruturais não confirmam eventos de conflito ao vivo.

[[MOC_Monitor_de_Conflitos]]
[[Chokepoints_Baselines_e_Cenarios]]

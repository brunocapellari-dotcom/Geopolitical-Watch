# Source schema validation — 2026-08-24

This note records manual validation of the public-data bootstrap against current official documentation before the first scheduled artifact runs.

## UCDP/PRIO Armed Conflict Dataset 26.1

Official download center: https://ucdp.uu.se/downloads/
Codebook: https://ucdp.uu.se/downloads/ucdpprio/ucdp-prio-acd-261.pdf
CSV: https://ucdp.uu.se/downloads/ucdpprio/ucdp-prio-acd-261-csv.zip

Validated fields used by the parser include `conflict_id`, `location`, `side_a`, `side_b`, `year`, `intensity_level`, `type_of_conflict`, `start_date`, `start_date2`, `start_prec2`, `ep_end`, `ep_end_date`, `ep_end_prec`, `region`, and `version`.

Important semantic correction: UCDP retains the same conflict ID across separate periods of activity for the same incompatibility. A new episode is coded after one or more inactive years. Geopolitical Watch therefore splits conflict-year rows into continuous active-year episodes.

## UCDP Actor Dataset 26.1

Codebook: https://ucdp.uu.se/downloads/actor/ucdp-actor-codebook-261.pdf
CSV: https://ucdp.uu.se/downloads/actor/ucdp-actor-261-csv.zip

The current canonical-name field is `NameData`, not `Name`. Validated fields also include `ActorId`, `NameOrig`, `NameOrigFull`, `NameOrigFullEng`, `NewName`, `Org`, `ConflictId`, `DyadId`, `PrimaryParty`, `Splinter`, `ActorIdPrev`, `SplitTemp`, `ActorIdSplitTemp`, `Alliance`, `ActorIdAlliance`, `JoinGroup`, `ActorIdGroup`, `Location`, `Region`, and `Version`.

Actor lineage is preserved as source-coded context; it is not inferred from text aliases.

## UCDP Conflict Termination Dataset v4-2024

Codebook: https://ucdp.uu.se/downloads/monadterm/UCDPConflictTerminationDataset_v4_2024_Codebook.pdf
CSV: https://ucdp.uu.se/downloads/monadterm/UCDPConflictTerminationDataset_v4_2024_Conflict.csv

Conflict-level episode variables include `c_epno`, `c_outcome`, `c_ependdate`, and `c_ependprec`, together with the UCDP conflict identifier. The parser keys termination outcomes by `(conflict_id, episode_no)` so repeated episodes are not overwritten.

The termination dataset is an older compatible layer than ACD 26.1; absence of a termination record is not interpreted as an ongoing conflict or as evidence of no agreement.

## UCDP rights

The official UCDP Download Center states current datasets are free of charge and licensed under CC BY 4.0 with attribution. API access is separately token-protected for service stability. Bulk public files and live API credentials are therefore governed separately in `config/audit/source_rights.json`.

## NGA World Port Index

Official page: https://msi.nga.mil/Publications/WPI
Field explanations: https://msi.nga.mil/api/publications/download?key=16920959/SFH00000/WPI_Explanation_of_Data_Fields.pdf&type=view
Official CSV: https://msi.nga.mil/api/publications/download?type=view&key=16920959/SFH00000/UpdatedPub150.csv

The official CSV uses compact downloaded-field names. Validated examples include:

- `wpinumber` — WPI Number
- `main_port_` — Main Port Name
- `alternate_` — Alternate Port Name
- `unlocode` — UN/LOCODE
- `countryCode` — Country Code
- `dodwaterbo` — World Water Body
- `harbor_siz` / `harbor_typ` — harbor size/type
- `fac_contai`, `fac_oilter`, `fac_lngter`, `fac_solidb`, `fac_liquid`, `fac_roro`
- `com_rail`, `navarea`, `vts`, `tss`
- `channel_de`, `cargo_pier`, `oil_termin`, `lng_termin`
- `Latitude`, `Longitude`

The WPI is a structural reference/planning dataset. It does not establish current port operating status.

## World Bank Indicators API V2

Documentation: https://datahelpdesk.worldbank.org/knowledgebase/articles/889392

The V2 Indicators API requires no API key. Country metadata include ISO codes, region, income group, capital and coordinates. Indicator observations retain reference year and observation status. World Bank dataset licensing is normally CC BY 4.0 unless indicator/dataset metadata state otherwise, including possible third-party restrictions.

## Governance consequence

Schema alignment and public availability do not close the v1 production hard gates. Live production, restore/PITR, restricted-source credentials, large out-of-sample validation, and final security/source-rights audit still require direct evidence.

# Geopolitical Watch — GitHub Research Integration 2026-10-01

Status: APPROVED ARCHITECTURE ADDENDUM

## GeoIntel shared engine

Geopolitical Watch consumes the shared GeoIntel Service rather than building a second geospatial platform.

Approved candidates/patterns:

- TiTiler — POC for raster/COG/STAC/NetCDF/Zarr tiles.
- TiPG — POC for PostGIS OGC Features/Tiles APIs.
- Martin/PMTiles — retain for vector/static serving where appropriate.
- God’s Eye View-style interfaces — REFERENCE for dense multi-layer operational UX, not evidence authority.
- STAC/ODC-STAC — POC for satellite/earth-observation access and time-series processing.

Layers may include aircraft, vessels, satellite context, wildfire, weather, earthquakes, conflict events and public strategic infrastructure, subject to source rights and existing safety boundaries.

## OSINT and Research AI

Research AI is the shared discovery/verification layer.

Claude-OSINT and similar projects are REFERENCE/ADAPT only for authorized public-source workflows. They do not become a claim authority.

Required flow:

`discovery -> original source -> immutable evidence -> provenance -> independent corroboration -> deterministic verdict -> analyst synthesis`.

## Derived knowledge

QMD/Graphify/OpenWiki/CocoIndex are shared knowledge-context services only. None may supersede the existing evidence ledger, raw archive or deterministic Verdict Engine.

Graph relationships must preserve whether they are EXTRACTED/OBSERVED or INFERRED.

## Agent/runtime security

Inherit from Hermes:

- Agent Manifest;
- Action Firewall;
- OpenSandbox/OpenShell isolation;
- Skill/MCP/model security gates;
- MCP Inspector/MCPJam;
- OpenTelemetry traces.

Hostile web/OSINT content remains untrusted data and cannot alter system rules.

## Research/visualization

Archify-style interactive diagrams may be used to render event/source/actor/infrastructure relationships from validated structured data. Visualization is never evidence.

## Promotion rule

No new OSINT, mapping or satellite component becomes ACTIVE based on a demo. It requires source/rights review, hostile-input tests, provenance, freshness, operational health and regression tests.

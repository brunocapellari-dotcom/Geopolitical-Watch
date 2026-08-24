# Migration provenance

The first Geopolitical Watch MVP was implemented temporarily inside the AgroLogMT repository and later formally externalized.

The historical AgroLogMT commit containing the completed news-aware implementation before externalization is:

`9f8747a37dfe8ca9280623be3d408c0eabf2df21`

The AgroLogMT externalization was merged in PR #62. From that point onward, Geopolitical Watch is an independent provider and AgroLog MT is a downstream consumer only.

Version 0.3.0 established the clean standalone scaffold. Version 0.4.0 adds historical checkpoints, backfill, canonical geography, quality metadata and replay evaluation without changing the AgroLog separation boundary. It keeps the successful concepts from the earlier MVP while removing `AGROLOG_*` environment names and direct dependence on AgroLog storage, scheduling and database conventions.

from __future__ import annotations

import json, os, tempfile, threading, unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen
from unittest.mock import patch

from geowatch.api import Handler
from geowatch.convergence import converge_events
from geowatch.entities import EntityResolver
from geowatch.metrics import operational_snapshot, prometheus_text
from geowatch.models import Event
from geowatch.sources import acled, gdacs
from geowatch.storage import SQLiteStore
from geowatch.storage_factory import backend_name, open_store


class V06OperationalTests(unittest.TestCase):
    def test_gdacs_geojson_parser(self):
        payload=json.dumps({"features":[{"geometry":{"type":"Point","coordinates":[32.35,30.45]},"properties":{"eventid":"GDACS-1","eventtype":"FL","name":"Flood near transport corridor","country":"Egypt","fromdate":"2026-08-24T08:00:00Z"}}]}).encode()
        rows=gdacs.parse(payload,collected_at="2026-08-24T09:00:00+00:00")
        self.assertEqual(1,len(rows)); self.assertEqual("curated_report",rows[0].verification_level); self.assertAlmostEqual(30.45,rows[0].latitude or 0)

    def test_acled_parser_and_cursor_pagination(self):
        payload=json.dumps({"data":[{"event_id_cnty":"UKR1","event_date":"2026-08-24","event_type":"Battles","sub_event_type":"Armed clash","actor1":"Actor A","actor2":"Actor B","country":"Ukraine","admin1":"Odesa","location":"Odesa","latitude":"46.48","longitude":"30.73","fatalities":"2"}]}).encode()
        rows=acled.parse(payload,collected_at="2026-08-24T09:00:00+00:00"); self.assertEqual(2,rows[0].fatalities_best)
        first=json.dumps({"data":[],"next_cursor":"abc"}).encode(); second=json.dumps({"data":[],"next_cursor":None}).encode()
        with patch("geowatch.sources.acled.access_token",return_value="token"), patch("geowatch.sources.acled.collect",side_effect=[(first,"https://acled/1"),(second,"https://acled/2")]) as mocked:
            payloads,_=acled.collect_all(limit=100)
        self.assertEqual(2,len(payloads)); self.assertEqual(0,mocked.call_args_list[0].kwargs["cursor"]); self.assertEqual("abc",mocked.call_args_list[1].kwargs["cursor"])

    def test_postgis_schema_contract(self):
        sql=Path("sql/postgres_postgis.sql").read_text().casefold(); self.assertIn("create extension if not exists postgis",sql); self.assertIn("geography(point,4326)",sql); self.assertIn("using gist",sql)

    def test_storage_factory_defaults_to_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=open_store(Path(tmp)/"g.db"); self.assertIsInstance(store,SQLiteStore); store.close()
        self.assertEqual("postgresql-postgis",backend_name("postgresql://user:pass@host/db"))

    def test_metrics_snapshot_and_prometheus(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=SQLiteStore(Path(tmp)/"g.db"); store.record_run(run_id="run1",source_id="source",started_at="2026-08-24T10:00:00+00:00",finished_at="2026-08-24T10:01:00+00:00",status="ok",records=2)
            snap=operational_snapshot(store,now=datetime(2026,8,24,12,tzinfo=timezone.utc)); self.assertIn("geowatch_collector_runs_total 1",prometheus_text(snap)); store.close()

    def test_api_v2_episode_smoke(self):
        ev=Event(event_id="api1",source_id="test",source_kind="news",title="Port of Odesa attacked",event_type="media_report",reference_at="2026-08-24T10:00:00+00:00",collected_at="2026-08-24T10:00:00+00:00",published_at="2026-08-24T10:00:00+00:00",verification_level="osint_signal",country="Ukraine",publisher="example.com",source_url="https://example.com/api1")
        resolver=EntityResolver.from_json("config/entities.json"); episodes,claims,evidence,entities,changes=converge_events([ev],resolver=resolver,now=datetime(2026,8,24,12,tzinfo=timezone.utc))
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"api.db"; store=SQLiteStore(db); store.upsert_events([ev]); store.upsert_entities(entities); store.upsert_evidence(evidence); store.upsert_episodes(episodes); store.upsert_claims(claims); store.record_changes(changes); store.close()
            old=os.environ.get("GEOWATCH_DB"); os.environ["GEOWATCH_DB"]=str(db)
            try:
                with running_server() as base:
                    with urlopen(base+"/health") as r: health=json.load(r)
                    with urlopen(base+"/v2/episodes?country=Ukraine") as r: listing=json.load(r)
                    with urlopen(base+f"/v2/episodes/{episodes[0].episode_id}") as r: detail=json.load(r)
                    with urlopen(base+"/v2/review-queue") as r: review=json.load(r)
                    with urlopen(base+"/v2/coverage") as r: coverage=json.load(r)
                    with urlopen(base+"/v2/forecasts/summary") as r: forecasts=json.load(r)
                    with urlopen(base+"/v2/geopolitics/countries?country=JPN") as r: japan=json.load(r)
                    with urlopen(base+"/v2/geopolitics/graph") as r: graph=json.load(r)
                    with urlopen(base+"/v2/readiness") as r: readiness=json.load(r)
                    with urlopen(base+"/v2/geopolitics/infrastructure?node_id=STRAIT_HORMUZ") as r: infra=json.load(r)
                    with urlopen(base+"/v2/source-activation") as r: activation=json.load(r)
                    with urlopen(base+"/v2/acceleration") as r: acceleration=json.load(r)
                self.assertEqual("0.14.0",health["version"]); self.assertEqual(1,len(listing["episodes"])); self.assertEqual(episodes[0].episode_id,detail["episode"]["episode_id"])
                self.assertTrue(detail["strategic_context"]["context_not_evidence"]); self.assertTrue(detail["strategic_graph_context"]["context_not_evidence"]); self.assertTrue(detail["escalation_readout"]["indicator_score_not_probability"])
                self.assertEqual("geowatch-review-queue-v1",review["schema_version"]); self.assertEqual("geowatch-coverage-inventory-v1",coverage["schema_version"])
                self.assertEqual("geowatch-forecast-calibration-v1",forecasts["schema_version"]); self.assertEqual("JPN",japan["profile"]["country_id"]); self.assertTrue(graph["governance"]["edge_requires_source"])
                self.assertFalse(readiness["target_reached"]); self.assertEqual("STRAIT_HORMUZ",infra["node"]["node_id"])
                self.assertTrue(activation["single_source_block_does_not_block_pipeline"]); self.assertTrue(acceleration["external_gates_are_not_faked"])
            finally:
                os.environ.pop("GEOWATCH_DB",None) if old is None else os.environ.__setitem__("GEOWATCH_DB",old)


@contextmanager
def running_server():
    server=ThreadingHTTPServer(("127.0.0.1",0),Handler); thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    try:
        host,port=server.server_address; yield f"http://{host}:{port}"
    finally:
        server.shutdown(); thread.join(timeout=2); server.server_close()

if __name__=="__main__": unittest.main()

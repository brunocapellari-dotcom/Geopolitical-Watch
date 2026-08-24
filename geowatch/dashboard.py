from __future__ import annotations


def map_points(store, *, limit: int = 500) -> list[dict[str, object]]:
    entities = {entity.entity_id: entity for entity in store.load_entities()}
    rows: list[dict[str, object]] = []
    for episode in store.load_episodes(limit=limit):
        location = None
        for entity_id in (*episode.infrastructure_entity_ids, *episode.other_entity_ids):
            entity = entities.get(entity_id)
            if entity and entity.latitude is not None and entity.longitude is not None:
                location = (entity.latitude, entity.longitude, entity.canonical_name, entity.entity_type)
                break
        if location is None:
            for event in store.load_events_by_ids(episode.event_ids):
                if event.latitude is not None and event.longitude is not None:
                    location = (event.latitude, event.longitude, event.region or event.country or event.title, "event")
                    break
        if location is None:
            continue
        strength = episode.evidence_strength.overall_index if episode.evidence_strength else 0
        rows.append({
            "episode_id": episode.episode_id,
            "title": episode.title,
            "state": episode.state,
            "countries": list(episode.countries),
            "last_updated_at": episode.last_updated_at,
            "evidence_strength_index": strength,
            "latitude": location[0],
            "longitude": location[1],
            "location_name": location[2],
            "location_type": location[3],
        })
    return rows


def dashboard_html() -> str:
    return r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Geopolitical Watch</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
body{font-family:system-ui,sans-serif;margin:0;background:#101214;color:#e9ecef}header{padding:14px 18px;background:#171a1d;display:flex;gap:10px;align-items:center;flex-wrap:wrap}input,button,select{padding:8px;background:#24282c;color:#fff;border:1px solid #3a4046;border-radius:6px}button{cursor:pointer}.grid{display:grid;grid-template-columns:minmax(320px,42%) 1fr;height:calc(100vh - 70px)}#map{height:100%}.panel{overflow:auto;padding:12px}.card{background:#181c20;border:1px solid #2b3137;border-radius:8px;padding:10px;margin-bottom:9px}.meta{font-size:12px;color:#adb5bd}.high{font-weight:700}.error{color:#ff8787}@media(max-width:800px){.grid{grid-template-columns:1fr;grid-template-rows:48% 52%}}
</style>
</head>
<body>
<header><strong>Geopolitical Watch</strong><input id="token" type="password" placeholder="API bearer token"><select id="state"><option value="">all states</option><option>emerging</option><option>active</option><option>escalating</option><option>stable</option><option>deescalating</option><option>ceasefire</option></select><button onclick="loadAll()">Load</button><span id="status" class="meta"></span></header>
<div class="grid"><div id="map"></div><div class="panel"><div id="episodes"></div></div></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const map=L.map('map').setView([20,10],2);L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:18,attribution:'OpenStreetMap'}).addTo(map);let markers=[];
async function api(path){const token=document.getElementById('token').value;sessionStorage.setItem('geowatch_token',token);const r=await fetch(path,{headers:token?{'Authorization':'Bearer '+token}:{}});if(!r.ok)throw new Error('HTTP '+r.status);return r.json()}
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
async function loadAll(){const status=document.getElementById('status');status.textContent='loading';try{const state=document.getElementById('state').value;const [mp,ep]=await Promise.all([api('/v2/map'),api('/v2/episodes?limit=200'+(state?'&state='+encodeURIComponent(state):''))]);markers.forEach(m=>map.removeLayer(m));markers=[];for(const p of mp.points){const m=L.marker([p.latitude,p.longitude]).addTo(map).bindPopup('<b>'+esc(p.title)+'</b><br>'+esc(p.state)+' | strength '+esc(p.evidence_strength_index)+'<br>'+esc(p.location_name));markers.push(m)}const box=document.getElementById('episodes');box.innerHTML='';for(const e of ep.episodes){const s=e.evidence_strength?e.evidence_strength.overall_index:'n/a';const d=document.createElement('div');d.className='card';d.innerHTML='<div class="high">'+esc(e.title)+'</div><div class="meta">'+esc(e.state)+' | strength '+esc(s)+' | '+esc((e.countries||[]).join(', '))+' | '+esc(e.last_updated_at)+'</div><button onclick="showEpisode(\''+esc(e.episode_id)+'\')">Timeline</button><div id="d-'+esc(e.episode_id)+'"></div>';box.appendChild(d)}status.textContent=ep.episodes.length+' episodes'}catch(e){status.innerHTML='<span class="error">'+esc(e.message)+'</span>'}}
async function showEpisode(id){try{const d=await api('/v2/episodes/'+encodeURIComponent(id));const target=document.getElementById('d-'+id);target.innerHTML='<div class="meta">Claims: '+d.claims.length+' | Evidence: '+d.evidence.length+' | Events: '+d.events.length+'</div>'+d.events.slice(0,8).map(e=>'<div class="meta">'+esc(e.reference_at)+' — '+esc(e.title)+'</div>').join('')}catch(e){}}
document.getElementById('token').value=sessionStorage.getItem('geowatch_token')||'';
</script>
</body></html>'''

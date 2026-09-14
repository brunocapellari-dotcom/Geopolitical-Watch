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
<html lang="pt-BR">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Monitor de Conflitos</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
html,body{height:100%}body{font-family:system-ui,sans-serif;margin:0;background:#101214;color:#e9ecef}header{min-height:46px;padding:10px 14px;background:#171a1d;display:flex;gap:9px;align-items:center;flex-wrap:wrap}input,button,select{padding:8px;background:#24282c;color:#fff;border:1px solid #3a4046;border-radius:6px}button{cursor:pointer}.grid{display:grid;grid-template-columns:minmax(340px,38%) 1fr;height:calc(100vh - 66px)}#map{height:100%;min-height:360px}.panel{overflow:auto;padding:12px}.card{background:#181c20;border:1px solid #2b3137;border-radius:8px;padding:10px;margin-bottom:9px}.meta{font-size:12px;color:#adb5bd}.high{font-weight:700}.error{color:#ff8787}.badge{font-size:11px;padding:3px 6px;border:1px solid #3a4046;border-radius:10px}.leaflet-tooltip{white-space:nowrap} @media(max-width:800px){.grid{grid-template-columns:1fr;grid-template-rows:52% 48%;height:calc(100vh - 100px)}}
</style>
</head>
<body>
<header><strong>Monitor de Conflitos</strong><input id="token" type="password" placeholder="Token privado"><select id="state"><option value="">todos os estados</option><option>emerging</option><option>active</option><option>escalating</option><option>stable</option><option>deescalating</option><option>ceasefire</option></select><button onclick="loadAll()">Atualizar</button><span id="status" class="meta"></span></header>
<div class="grid"><div id="map"></div><div class="panel"><div id="episodes"></div></div></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const map=L.map('map',{worldCopyJump:true}).setView([20,10],2);
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:18,attribution:'OpenStreetMap'}).addTo(map);
const conflicts=L.layerGroup().addTo(map), infrastructure=L.layerGroup().addTo(map);
L.control.layers(null,{'Conflitos':conflicts,'Infraestrutura crítica':infrastructure},{collapsed:false}).addTo(map);

async function api(path){const token=document.getElementById('token').value;sessionStorage.setItem('geowatch_token',token);const r=await fetch(path,{headers:token?{'Authorization':'Bearer '+token}:{}});if(!r.ok)throw new Error('HTTP '+r.status);return r.json()}
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function validCoord(v,min,max){const n=Number(v);return Number.isFinite(n)&&n>=min&&n<=max}
function popupEpisode(p){return '<b>'+esc(p.title)+'</b><br>'+esc(p.state)+' | força '+esc(p.evidence_strength_index)+'<br>'+esc(p.location_name)+'<br><span class="meta">'+esc(p.last_updated_at)+'</span>'}
function popupInfrastructure(n){const themes=(n.themes||n.facilities||[]).join(', ');return '<b>'+esc(n.name)+'</b><br>'+esc(n.type||'infraestrutura')+'<br>'+esc(n.region||n.water_body||'')+(themes?'<br><span class="meta">'+esc(themes)+'</span>':'')+'<br><span class="meta">Contexto estrutural; não implica status operacional atual.</span>'}

async function loadAll(){
 const status=document.getElementById('status');status.textContent='carregando';
 try{
  const state=document.getElementById('state').value;
  const [mp,ep,infra]=await Promise.all([
   api('/v2/map?limit=1000'),
   api('/v2/episodes?limit=250'+(state?'&state='+encodeURIComponent(state):'')),
   api('/v2/geopolitics/infrastructure')
  ]);
  conflicts.clearLayers();infrastructure.clearLayers();
  let conflictPins=0,infraPins=0;
  for(const p of mp.points||[]){
   if(!validCoord(p.latitude,-90,90)||!validCoord(p.longitude,-180,180))continue;
   const m=L.marker([Number(p.latitude),Number(p.longitude)]).bindPopup(popupEpisode(p));
   m.bindTooltip(esc(p.location_name||p.title),{direction:'top',sticky:true});m.addTo(conflicts);conflictPins++;
  }
  for(const n of infra.nodes||[]){
   if(!validCoord(n.latitude,-90,90)||!validCoord(n.longitude,-180,180))continue;
   const m=L.circleMarker([Number(n.latitude),Number(n.longitude)],{radius:5,weight:1,fillOpacity:.65}).bindPopup(popupInfrastructure(n));
   m.bindTooltip(esc(n.name),{direction:'top',sticky:true});m.addTo(infrastructure);infraPins++;
  }
  const box=document.getElementById('episodes');box.innerHTML='';
  for(const e of ep.episodes||[]){
   const s=e.evidence_strength?e.evidence_strength.overall_index:'n/a';
   const d=document.createElement('div');d.className='card';
   d.innerHTML='<div class="high">'+esc(e.title)+'</div><div class="meta">'+esc(e.state)+' | força '+esc(s)+' | '+esc((e.countries||[]).join(', '))+' | '+esc(e.last_updated_at)+'</div><button onclick="showEpisode(\''+esc(e.episode_id)+'\')">Timeline</button><div id="d-'+esc(e.episode_id)+'"></div>';
   box.appendChild(d);
  }
  const totalInfra=infra.summary&&infra.summary.node_count!==undefined?infra.summary.node_count:(infra.nodes||[]).length;
  status.textContent=(ep.episodes||[]).length+' episódios | '+conflictPins+' no mapa | '+infraPins+'/'+totalInfra+' infraestruturas georreferenciadas';
 }catch(e){status.innerHTML='<span class="error">'+esc(e.message)+'</span>'}
}
async function showEpisode(id){try{const d=await api('/v2/episodes/'+encodeURIComponent(id));const target=document.getElementById('d-'+id);target.innerHTML='<div class="meta">Claims: '+d.claims.length+' | Evidências: '+d.evidence.length+' | Eventos: '+d.events.length+'</div>'+d.events.slice(0,12).map(e=>'<div class="meta">'+esc(e.reference_at)+' — '+esc(e.title)+'</div>').join('')}catch(e){}}
document.getElementById('token').value=sessionStorage.getItem('geowatch_token')||'';
</script>
</body></html>'''

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
html,body{height:100%}body{font-family:system-ui,sans-serif;margin:0;background:#101214;color:#e9ecef}header{min-height:46px;padding:10px 14px;background:#171a1d;display:flex;gap:9px;align-items:center;flex-wrap:wrap}input,button,select{padding:8px;background:#24282c;color:#fff;border:1px solid #3a4046;border-radius:6px}button{cursor:pointer}.grid{display:grid;grid-template-columns:minmax(340px,38%) 1fr;height:calc(100vh - 66px)}#map{height:100%;min-height:360px}.panel{overflow:auto;padding:12px}.card{background:#181c20;border:1px solid #2b3137;border-radius:8px;padding:10px;margin-bottom:9px}.meta{font-size:12px;color:#adb5bd}.high{font-weight:700}.error{color:#ff8787}.badge{font-size:11px;padding:3px 6px;border:1px solid #3a4046;border-radius:10px}.leaflet-tooltip{white-space:nowrap}.aircraft-icon{background:transparent;border:0}.aircraft-glyph{display:block;font-size:18px;line-height:18px;width:18px;height:18px;text-align:center;filter:drop-shadow(0 0 2px #000)} @media(max-width:800px){.grid{grid-template-columns:1fr;grid-template-rows:52% 48%;height:calc(100vh - 100px)}}
</style>
</head>
<body>
<header><strong>Monitor de Conflitos</strong><input id="token" type="password" placeholder="API bearer token"><select id="state"><option value="">todos os estados</option><option>emerging</option><option>active</option><option>escalating</option><option>stable</option><option>deescalating</option><option>ceasefire</option></select><button onclick="loadAll()">Atualizar</button><span id="status" class="meta"></span></header>
<div class="grid"><div id="map"></div><div class="panel"><div id="episodes"></div></div></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const map=L.map('map',{worldCopyJump:true}).setView([20,10],2);
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:18,attribution:'OpenStreetMap'}).addTo(map);
const conflicts=L.layerGroup().addTo(map), infrastructure=L.layerGroup().addTo(map), aircraft=L.layerGroup().addTo(map), aircraftRoute=L.layerGroup().addTo(map);
L.control.layers(null,{'Conflitos':conflicts,'Infraestrutura crítica':infrastructure,'Aeronaves ao vivo':aircraft,'Rota da aeronave selecionada':aircraftRoute},{collapsed:false}).addTo(map);
let lastCounts={episodes:0,conflicts:0,infra:0,infraTotal:0,aircraft:0};
let aircraftRequest=0;

async function api(path){const token=document.getElementById('token').value;sessionStorage.setItem('geowatch_token',token);const r=await fetch(path,{headers:token?{'Authorization':'Bearer '+token}:{}});if(!r.ok)throw new Error('HTTP '+r.status);return r.json()}
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function validCoord(v,min,max){const n=Number(v);return Number.isFinite(n)&&n>=min&&n<=max}
function fmt(v,suffix=''){return v===undefined||v===null||v===''?'—':esc(v)+suffix}
function updateStatus(){document.getElementById('status').textContent=lastCounts.episodes+' episódios | '+lastCounts.conflicts+' conflitos no mapa | '+lastCounts.infra+'/'+lastCounts.infraTotal+' infraestruturas | '+lastCounts.aircraft+' aeronaves'}
function popupEpisode(p){return '<b>'+esc(p.title)+'</b><br>'+esc(p.state)+' | força '+esc(p.evidence_strength_index)+'<br>'+esc(p.location_name)+'<br><span class="meta">'+esc(p.last_updated_at)+'</span>'}
function popupInfrastructure(n){const themes=(n.themes||n.facilities||[]).join(', ');return '<b>'+esc(n.name)+'</b><br>'+esc(n.type||'infraestrutura')+'<br>'+esc(n.region||n.water_body||'')+(themes?'<br><span class="meta">'+esc(themes)+'</span>':'')+'<br><span class="meta">Contexto estrutural; não implica status operacional atual.</span>'}
function aircraftLabel(a){return (a.flight||a.r||a.hex||'aeronave').trim()}
function popupAircraft(a,routeText='Clique para consultar origem/destino plausíveis'){return '<b>'+esc(aircraftLabel(a))+'</b><br>ICAO: '+fmt(a.hex)+' | Reg.: '+fmt(a.r)+' | Tipo: '+fmt(a.t)+'<br>Altitude: '+fmt(a.alt_baro,' ft')+' | Vel.: '+fmt(a.gs,' kt')+' | Rumo: '+fmt(a.track,'°')+'<br><span class="meta">Última posição: '+fmt(a.seen,' s')+' atrás</span><br><span class="meta">'+esc(routeText)+'</span>'}

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
  lastCounts={...lastCounts,episodes:(ep.episodes||[]).length,conflicts:conflictPins,infra:infraPins,infraTotal:totalInfra};updateStatus();
  loadAircraft();
 }catch(e){status.innerHTML='<span class="error">'+esc(e.message)+'</span>'}
}

async function loadAircraft(){
 if(!map.hasLayer(aircraft))return;
 const request=++aircraftRequest;
 try{
  const center=map.getCenter(),corner=map.getBounds().getNorthEast();
  const dist=Math.max(25,Math.min(250,Math.ceil(map.distance(center,corner)/1852)));
  const url='https://api.adsb.lol/v2/lat/'+center.lat.toFixed(4)+'/lon/'+center.lng.toFixed(4)+'/dist/'+dist;
  const r=await fetch(url,{headers:{'Accept':'application/json'}});if(!r.ok)throw new Error('ADSB '+r.status);
  const payload=await r.json();if(request!==aircraftRequest)return;
  aircraft.clearLayers();let count=0;
  for(const a of payload.ac||[]){
   if(!validCoord(a.lat,-90,90)||!validCoord(a.lon,-180,180))continue;
   const heading=Number.isFinite(Number(a.track))?Number(a.track):0;
   const icon=L.divIcon({className:'aircraft-icon',html:'<span class="aircraft-glyph" style="transform:rotate('+heading+'deg)">✈</span>',iconSize:[18,18],iconAnchor:[9,9]});
   const m=L.marker([Number(a.lat),Number(a.lon)],{icon}).bindPopup(popupAircraft(a));
   m.bindTooltip(esc(aircraftLabel(a)),{direction:'top',sticky:true});
   m.on('click',()=>loadAircraftRoute(a,m));m.addTo(aircraft);count++;
  }
  lastCounts.aircraft=count;updateStatus();
 }catch(e){lastCounts.aircraft=0;updateStatus()}
}

async function loadAircraftRoute(a,marker){
 aircraftRoute.clearLayers();
 const callsign=String(a.flight||'').trim();
 if(!callsign){marker.setPopupContent(popupAircraft(a,'Rota indisponível: aeronave sem callsign.')).openPopup();return}
 try{
  marker.setPopupContent(popupAircraft(a,'Consultando rota plausível…')).openPopup();
  const url='https://api.adsb.lol/api/0/route/'+encodeURIComponent(callsign)+'/'+Number(a.lat).toFixed(4)+'/'+Number(a.lon).toFixed(4);
  const r=await fetch(url,{headers:{'Accept':'application/json'}});if(!r.ok)throw new Error('HTTP '+r.status);
  const route=await r.json();const aps=(route._airports||[]).filter(p=>validCoord(p.lat,-90,90)&&validCoord(p.lon,-180,180));
  const codes=route.airport_codes&&route.airport_codes!=='unknown'?route.airport_codes:'rota não identificada';
  const plausibility=route.plausible===false?'não validada pela posição atual':'plausível pela posição atual';
  marker.setPopupContent(popupAircraft(a,'Rota: '+codes+' — '+plausibility+'. Fonte: ADSB.lol/VRS standing data.')).openPopup();
  if(aps.length>=2&&route.plausible!==false){
   L.polyline(aps.map(p=>[Number(p.lat),Number(p.lon)]),{weight:2,opacity:.7}).addTo(aircraftRoute);
   const origin=aps[0],destination=aps[aps.length-1],current=[Number(a.lat),Number(a.lon)];
   L.polyline([current,[Number(origin.lat),Number(origin.lon)]],{weight:1,opacity:.6,dashArray:'6,7'}).addTo(aircraftRoute);
   L.polyline([current,[Number(destination.lat),Number(destination.lon)]],{weight:1,opacity:.45,dashArray:'3,8'}).addTo(aircraftRoute);
   L.circleMarker([Number(origin.lat),Number(origin.lon)],{radius:6,weight:2,fillOpacity:.5}).bindTooltip('Origem: '+esc(origin.icao||origin.iata||origin.name||''),{sticky:true}).addTo(aircraftRoute);
   L.circleMarker([Number(destination.lat),Number(destination.lon)],{radius:6,weight:2,fillOpacity:.5}).bindTooltip('Destino: '+esc(destination.icao||destination.iata||destination.name||''),{sticky:true}).addTo(aircraftRoute);
  }
 }catch(e){marker.setPopupContent(popupAircraft(a,'Não foi possível consultar a rota agora.')).openPopup()}
}

async function showEpisode(id){try{const d=await api('/v2/episodes/'+encodeURIComponent(id));const target=document.getElementById('d-'+id);target.innerHTML='<div class="meta">Claims: '+d.claims.length+' | Evidências: '+d.evidence.length+' | Eventos: '+d.events.length+'</div>'+d.events.slice(0,12).map(e=>'<div class="meta">'+esc(e.reference_at)+' — '+esc(e.title)+'</div>').join('')}catch(e){}}
document.getElementById('token').value=sessionStorage.getItem('geowatch_token')||'';
let aircraftMoveTimer=null;map.on('moveend',()=>{clearTimeout(aircraftMoveTimer);aircraftMoveTimer=setTimeout(loadAircraft,800)});map.on('overlayadd',e=>{if(e.layer===aircraft)loadAircraft()});setInterval(loadAircraft,60000);
</script>
</body></html>'''

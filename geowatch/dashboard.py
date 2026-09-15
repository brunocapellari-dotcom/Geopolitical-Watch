from __future__ import annotations

import html
import json
import os

from .map_layers import load_map_layers

_MAPLIBRE_VERSION = "6.9.1"


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
                if event.latitude is not None and event.longitude is not None and event.verification_level != "sensor_signal":
                    location = (
                        event.latitude,
                        event.longitude,
                        event.region or event.country or event.title,
                        "event",
                    )
                    break
        if location is None:
            continue
        rows.append(
            {
                "episode_id": episode.episode_id,
                "title": episode.title,
                "state": episode.state,
                "countries": list(episode.countries),
                "last_updated_at": episode.last_updated_at,
                "evidence_strength_index": episode.evidence_strength.overall_index if episode.evidence_strength else 0,
                "latitude": location[0],
                "longitude": location[1],
                "location_name": location[2],
                "location_type": location[3],
            }
        )
    return rows


def _map_style_js() -> str:
    configured = os.environ.get("GEOWATCH_MAP_STYLE_URL", "").strip()
    if configured:
        return json.dumps(configured)
    return json.dumps(
        {
            "version": 8,
            "sources": {
                "osm": {
                    "type": "raster",
                    "tiles": ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
                    "tileSize": 256,
                    "attribution": "© OpenStreetMap contributors",
                }
            },
            "layers": [{"id": "osm", "type": "raster", "source": "osm"}],
        },
        ensure_ascii=False,
    )


def _layer_controls(catalog: dict[str, object]) -> str:
    controls: list[str] = []
    for layer in catalog["layers"]:  # type: ignore[index]
        row = layer  # type: ignore[assignment]
        checked = " checked" if row["default_visible"] else ""
        title = html.escape(f"{row['semantic_class']} · {row['source']} · {row['note']}", quote=True)
        controls.append(
            f'<label title="{title}"><input type="checkbox" data-layer="{html.escape(str(row["id"]), quote=True)}"{checked}>'
            f'{html.escape(str(row["label"]))} <span class="semantic">{html.escape(str(row["semantic_class"]))}</span></label>'
        )
    return "".join(controls)


def dashboard_html() -> str:
    catalog = load_map_layers()
    catalog_js = json.dumps(catalog, ensure_ascii=False).replace("</", "<\\/")
    controls = _layer_controls(catalog)
    template = r'''<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Monitor de Conflitos</title>
<link rel="stylesheet" href="https://unpkg.com/maplibre-gl@__MAPLIBRE_VERSION__/dist/maplibre-gl.css">
<style>
html,body{height:100%;margin:0}body{font-family:system-ui,sans-serif;background:#101214;color:#e9ecef;overflow:hidden}
header{min-height:48px;padding:9px 12px;background:#171a1d;display:flex;gap:8px;align-items:center;flex-wrap:wrap;border-bottom:1px solid #2b3137}
input,button,select{padding:7px 9px;background:#24282c;color:#fff;border:1px solid #3a4046;border-radius:6px}button{cursor:pointer}
.grid{display:grid;grid-template-columns:minmax(360px,34%) 1fr;height:calc(100vh - 68px)}#map{height:100%;min-height:360px}.panel{overflow:auto;padding:10px;background:#121518}
.card{background:#181c20;border:1px solid #2b3137;border-radius:8px;padding:9px;margin-bottom:8px}.meta{font-size:12px;color:#adb5bd}.high{font-weight:700}.error{color:#ff8787}
.badge{font-size:11px;padding:3px 6px;border:1px solid #3a4046;border-radius:10px;display:inline-block;margin:2px}.layers{display:flex;gap:7px;align-items:center;flex-wrap:wrap;font-size:12px}.layers label{white-space:nowrap}.semantic{font-size:9px;color:#868e96}
.maplibregl-popup-content{background:#181c20;color:#e9ecef;border:1px solid #3a4046;border-radius:8px;max-width:390px}.maplibregl-popup-tip{border-top-color:#181c20!important;border-bottom-color:#181c20!important}.maplibregl-ctrl-group{background:#181c20}.maplibregl-ctrl-group button{border:0}
@media(max-width:900px){body{overflow:auto}.grid{grid-template-columns:1fr;grid-template-rows:58vh auto;height:auto}#map{height:58vh}.panel{overflow:visible}}
</style>
</head>
<body>
<header>
<strong>Monitor de Conflitos</strong>
<input id="token" type="password" placeholder="API bearer token">
<select id="state"><option value="">todos os estados</option><option>emerging</option><option>active</option><option>escalating</option><option>stable</option><option>deescalating</option><option>ceasefire</option><option>closed</option></select>
<button id="refresh">Atualizar</button>
<div class="layers">__LAYER_CONTROLS__</div>
<span id="status" class="meta"></span>
</header>
<div class="grid"><div id="map"></div><div class="panel"><div id="episodes"></div></div></div>
<script type="module">
import * as maplibregl from 'https://unpkg.com/maplibre-gl@__MAPLIBRE_VERSION__/dist/maplibre-gl.mjs';
const MAP_STYLE=__MAP_STYLE__;
const MAP_LAYERS=__MAP_LAYERS__;
const layerMeta=Object.fromEntries(MAP_LAYERS.layers.map(x=>[x.id,x]));
window.__geowatchMapReady=false;
const map=new maplibregl.Map({container:'map',style:MAP_STYLE,center:[10,20],zoom:2,worldCopyJump:true,attributionControl:true});
map.addControl(new maplibregl.NavigationControl({showCompass:true}),'top-right');
const emptyFC=()=>({type:'FeatureCollection',features:[]});
let stateData={episodes:[],conflicts:emptyFC(),infrastructure:emptyFC(),physical:emptyFC(),network:emptyFC(),aircraft:emptyFC(),vessels:emptyFC(),route:emptyFC(),routeEndpoints:emptyFC()};
let lastCounts={episodes:0,conflicts:0,infra:0,infraTotal:0,physical:0,network:0,aircraft:0,vessels:0,aisConfigured:false};
let aircraftRequest=0;

async function api(path){
 const token=document.getElementById('token')?.value||'';
 const headers=token?{'Authorization':'Bearer '+token}:{};
 const r=await fetch(path,{headers,credentials:'same-origin'});
 if(!r.ok){let detail='HTTP '+r.status;try{const b=await r.json();if(b.error)detail=b.error}catch(_e){}throw new Error(detail)}
 return r.json();
}
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function validCoord(v,min,max){const n=Number(v);return Number.isFinite(n)&&n>=min&&n<=max}
function fmt(v,suffix=''){return v===undefined||v===null||v===''?'—':esc(v)+suffix}
function feature(lon,lat,props){return {type:'Feature',geometry:{type:'Point',coordinates:[Number(lon),Number(lat)]},properties:props}}
function setSource(name,data){stateData[name]=data;const src=map.getSource(name);if(src)src.setData(data)}
function visible(name){const box=document.querySelector('input[data-layer="'+name+'"]');return box?box.checked:Boolean(layerMeta[name]?.default_visible)}
const idsByLayer={conflicts:['conflicts-clusters','conflicts-count','conflicts-points'],infrastructure:['infrastructure-points'],physical:['physical-points'],network:['network-points'],aircraft:['aircraft-points'],vessels:['vessels-points']};
function applyVisibility(name){for(const id of idsByLayer[name]||[]){if(map.getLayer(id))map.setLayoutProperty(id,'visibility',visible(name)?'visible':'none')}}
function updateStatus(){const ais=lastCounts.aisConfigured?'':' (AIS aguardando chave/ativação)';document.getElementById('status').textContent=lastCounts.episodes+' episódios | '+lastCounts.conflicts+' conflitos | '+lastCounts.infra+'/'+lastCounts.infraTotal+' infra | '+lastCounts.physical+' físico | '+lastCounts.network+' rede | '+lastCounts.aircraft+' aeronaves | '+lastCounts.vessels+' navios'+ais}
function popupAt(coords,body){new maplibregl.Popup({closeButton:true,maxWidth:'390px'}).setLngLat(coords).setHTML(body).addTo(map)}
function semanticLine(id){const m=layerMeta[id];return m?'<br><span class="meta">'+esc(m.semantic_class)+' · '+esc(m.source)+' · '+esc(m.note)+'</span>':''}
function popupEpisode(p){return '<b>'+esc(p.title)+'</b><br>'+esc(p.state)+' | força '+esc(p.evidence_strength_index)+'<br>'+esc(p.location_name)+semanticLine('conflicts')}
function popupInfrastructure(n){const themes=(n.themes||n.facilities||[]).join(', ');return '<b>'+esc(n.name)+'</b><br>'+esc(n.type||'infraestrutura')+'<br>'+esc(n.region||n.water_body||'')+(themes?'<br><span class="meta">'+esc(themes)+'</span>':'')+semanticLine('infrastructure')}
function popupContext(e,id){return '<b>'+esc(e.title)+'</b><br>'+esc(e.source_id)+'<br><span class="meta">'+esc(e.reference_at)+'</span>'+semanticLine(id)}
function aircraftLabel(a){return String(a.flight||a.r||a.hex||'aeronave').trim()}
function popupAircraft(a,routeText='Clique para consultar origem/destino plausíveis'){return '<b>'+esc(aircraftLabel(a))+'</b><br>ICAO: '+fmt(a.hex)+' | Reg.: '+fmt(a.r)+' | Tipo: '+fmt(a.t)+'<br>Altitude: '+fmt(a.alt_baro,' ft')+' | Vel.: '+fmt(a.gs,' kt')+' | Rumo: '+fmt(a.track,'°')+'<br><span class="meta">Última posição: '+fmt(a.seen,' s')+' atrás</span><br><span class="meta">'+esc(routeText)+'</span>'+semanticLine('aircraft')}
function vesselLabel(v){return String(v.ship_name||v.mmsi||'navio').trim()}
function popupVessel(v){const voyage=(v.reported_destination||v.reported_eta)?'<br>Destino AIS: '+fmt(v.reported_destination)+(v.reported_eta?' | ETA: '+fmt(v.reported_eta):''):'';const ids=(v.imo_number||v.call_sign)?'<br>IMO: '+fmt(v.imo_number)+' | Callsign: '+fmt(v.call_sign):'';return '<b>'+esc(vesselLabel(v))+'</b><br>MMSI: '+fmt(v.mmsi)+ids+'<br>Vel.: '+fmt(v.speed_over_ground_kt,' kt')+' | Curso: '+fmt(v.course_over_ground_deg,'°')+' | Rumo: '+fmt(v.true_heading_deg,'°')+voyage+'<br><span class="meta">'+fmt(v.received_at)+'</span>'+semanticLine('vessels')}
function haversineNm(a,b){const R=3440.065,toRad=x=>x*Math.PI/180;const dLat=toRad(b.lat-a.lat),dLon=toRad(b.lng-a.lng),la1=toRad(a.lat),la2=toRad(b.lat);const h=Math.sin(dLat/2)**2+Math.cos(la1)*Math.cos(la2)*Math.sin(dLon/2)**2;return 2*R*Math.asin(Math.min(1,Math.sqrt(h)))}

function addGeoJsonLayers(){
 map.addSource('conflicts',{type:'geojson',data:stateData.conflicts,cluster:true,clusterMaxZoom:8,clusterRadius:42});
 map.addLayer({id:'conflicts-clusters',type:'circle',source:'conflicts',filter:['has','point_count'],paint:{'circle-radius':['step',['get','point_count'],16,20,20,100,27],'circle-color':'#b02a37','circle-opacity':0.78,'circle-stroke-width':1,'circle-stroke-color':'#f8f9fa'}});
 map.addLayer({id:'conflicts-count',type:'symbol',source:'conflicts',filter:['has','point_count'],layout:{'text-field':['get','point_count_abbreviated'],'text-size':11},paint:{'text-color':'#fff'}});
 map.addLayer({id:'conflicts-points',type:'circle',source:'conflicts',filter:['!',['has','point_count']],paint:{'circle-radius':7,'circle-color':['match',['get','state'],'escalating','#dc3545','active','#fd7e14','ceasefire','#20c997','deescalating','#0dcaf0','#adb5bd'],'circle-stroke-width':1.5,'circle-stroke-color':'#fff'}});
 map.addSource('infrastructure',{type:'geojson',data:stateData.infrastructure});map.addLayer({id:'infrastructure-points',type:'circle',source:'infrastructure',paint:{'circle-radius':5,'circle-color':'#6f42c1','circle-opacity':0.72,'circle-stroke-width':1,'circle-stroke-color':'#fff'}});
 map.addSource('physical',{type:'geojson',data:stateData.physical});map.addLayer({id:'physical-points',type:'circle',source:'physical',paint:{'circle-radius':['case',['==',['get','source_id'],'usgs_earthquakes'],7,4],'circle-color':'#ffc107','circle-opacity':0.65,'circle-stroke-width':1,'circle-stroke-color':'#111'}});
 map.addSource('network',{type:'geojson',data:stateData.network});map.addLayer({id:'network-points',type:'circle',source:'network',paint:{'circle-radius':5,'circle-color':'#0dcaf0','circle-opacity':0.65,'circle-stroke-width':1,'circle-stroke-color':'#111'}});
 map.addSource('aircraft',{type:'geojson',data:stateData.aircraft});map.addLayer({id:'aircraft-points',type:'circle',source:'aircraft',paint:{'circle-radius':5,'circle-color':'#e9ecef','circle-stroke-width':1.5,'circle-stroke-color':'#0d6efd'}});
 map.addSource('vessels',{type:'geojson',data:stateData.vessels});map.addLayer({id:'vessels-points',type:'circle',source:'vessels',paint:{'circle-radius':5,'circle-color':'#20c997','circle-stroke-width':1.5,'circle-stroke-color':'#111'}});
 map.addSource('route',{type:'geojson',data:stateData.route});map.addLayer({id:'selected-route',type:'line',source:'route',paint:{'line-color':'#0dcaf0','line-width':2.5,'line-opacity':0.85,'line-dasharray':[2,1]}});
 map.addSource('routeEndpoints',{type:'geojson',data:stateData.routeEndpoints});map.addLayer({id:'route-endpoints',type:'circle',source:'routeEndpoints',paint:{'circle-radius':7,'circle-color':'#fff','circle-stroke-width':2,'circle-stroke-color':'#0dcaf0'}});
 for(const row of MAP_LAYERS.layers)applyVisibility(row.id);
}

function attachMapEvents(){
 map.on('click','conflicts-clusters',e=>{const f=e.features?.[0];if(!f)return;map.getSource('conflicts').getClusterExpansionZoom(f.properties.cluster_id).then(z=>map.easeTo({center:f.geometry.coordinates,zoom:z}))});
 map.on('click','conflicts-points',e=>{const f=e.features?.[0];if(f)popupAt(f.geometry.coordinates,popupEpisode(f.properties))});
 map.on('click','infrastructure-points',e=>{const f=e.features?.[0];if(f)popupAt(f.geometry.coordinates,popupInfrastructure(JSON.parse(f.properties.raw)))});
 map.on('click','physical-points',e=>{const f=e.features?.[0];if(f)popupAt(f.geometry.coordinates,popupContext(JSON.parse(f.properties.raw),'physical'))});
 map.on('click','network-points',e=>{const f=e.features?.[0];if(f)popupAt(f.geometry.coordinates,popupContext(JSON.parse(f.properties.raw),'network'))});
 map.on('click','vessels-points',e=>{const f=e.features?.[0];if(f)popupAt(f.geometry.coordinates,popupVessel(JSON.parse(f.properties.raw)))});
 map.on('click','aircraft-points',e=>{const f=e.features?.[0];if(!f)return;const a=JSON.parse(f.properties.raw);popupAt(f.geometry.coordinates,popupAircraft(a,'Consultando rota plausível…'));loadAircraftRoute(a,f.geometry.coordinates)});
 for(const id of ['conflicts-clusters','conflicts-points','infrastructure-points','physical-points','network-points','aircraft-points','vessels-points']){map.on('mouseenter',id,()=>map.getCanvas().style.cursor='pointer');map.on('mouseleave',id,()=>map.getCanvas().style.cursor='')}
}

async function loadAll(){
 const status=document.getElementById('status');status.textContent='carregando';
 try{
  const selected=document.getElementById('state').value;
  const [mp,ep,infra,phys,net]=await Promise.all([api('/v2/map?limit=1000'),api('/v2/episodes?limit=250'+(selected?'&state='+encodeURIComponent(selected):'')),api('/v2/geopolitics/infrastructure'),api('/v2/context/physical?hours=24&limit=1000'),api('/v2/context/network?hours=24&limit=1000')]);
  const conflicts=emptyFC(),infrastructure=emptyFC(),physical=emptyFC(),network=emptyFC();
  for(const p of mp.points||[])if(validCoord(p.latitude,-90,90)&&validCoord(p.longitude,-180,180))conflicts.features.push(feature(p.longitude,p.latitude,{...p}));
  for(const n of infra.nodes||[])if(validCoord(n.latitude,-90,90)&&validCoord(n.longitude,-180,180))infrastructure.features.push(feature(n.longitude,n.latitude,{name:n.name,type:n.type,raw:JSON.stringify(n)}));
  for(const e of phys.events||[])if(validCoord(e.latitude,-90,90)&&validCoord(e.longitude,-180,180))physical.features.push(feature(e.longitude,e.latitude,{source_id:e.source_id,title:e.title,raw:JSON.stringify(e)}));
  for(const e of net.events||[])if(validCoord(e.latitude,-90,90)&&validCoord(e.longitude,-180,180))network.features.push(feature(e.longitude,e.latitude,{source_id:e.source_id,title:e.title,raw:JSON.stringify(e)}));
  setSource('conflicts',conflicts);setSource('infrastructure',infrastructure);setSource('physical',physical);setSource('network',network);
  stateData.episodes=ep.episodes||[];renderEpisodes();
  const totalInfra=infra.summary?.node_count??(infra.nodes||[]).length;
  lastCounts={...lastCounts,episodes:stateData.episodes.length,conflicts:conflicts.features.length,infra:infrastructure.features.length,infraTotal:totalInfra,physical:(phys.events||[]).length,network:(net.events||[]).length};updateStatus();
  Promise.allSettled([loadAircraft(),loadVessels()]);
 }catch(e){status.innerHTML='<span class="error">'+esc(e.message)+'</span>'}
}
function renderEpisodes(){const box=document.getElementById('episodes');box.innerHTML='';for(const e of stateData.episodes){const s=e.evidence_strength?.overall_index??'n/a';const d=document.createElement('div');d.className='card';d.innerHTML='<div class="high">'+esc(e.title)+'</div><div class="meta">'+esc(e.state)+' | força '+esc(s)+' | '+esc((e.countries||[]).join(', '))+' | '+esc(e.last_updated_at)+'</div><button data-episode="'+esc(e.episode_id)+'">Detalhes</button><div id="d-'+esc(e.episode_id)+'"></div>';d.querySelector('button').addEventListener('click',()=>showEpisode(e.episode_id));box.appendChild(d)}}
async function showEpisode(id){const target=document.getElementById('d-'+id);if(!target)return;target.innerHTML='<div class="meta">carregando…</div>';try{const [d,v]=await Promise.all([api('/v2/episodes/'+encodeURIComponent(id)),api('/v2/verification/episode?episode_id='+encodeURIComponent(id))]);const verdicts=(v.verdicts||[]).map(x=>'<span class="badge">'+esc(x.verdict)+' '+esc(x.confidence)+'%</span>').join('');target.innerHTML='<div>'+verdicts+'</div><div class="meta">Claims: '+d.claims.length+' | Evidências: '+d.evidence.length+' | Eventos: '+d.events.length+'</div>'+d.events.slice(0,16).map(e=>'<div class="meta">'+esc(e.reference_at)+' — '+esc(e.title)+'</div>').join('')}catch(e){target.innerHTML='<span class="error">'+esc(e.message)+'</span>'}}
async function loadAircraft(){if(!visible('aircraft'))return;const request=++aircraftRequest;try{const c=map.getCenter(),ne=map.getBounds().getNorthEast();const dist=Math.max(25,Math.min(250,Math.ceil(haversineNm({lat:c.lat,lng:c.lng},{lat:ne.lat,lng:ne.lng}))));const payload=await api('/v2/live/aircraft?lat='+c.lat.toFixed(4)+'&lon='+c.lng.toFixed(4)+'&dist_nm='+dist);if(request!==aircraftRequest)return;const fc=emptyFC();for(const a of payload.ac||[])if(validCoord(a.lat,-90,90)&&validCoord(a.lon,-180,180))fc.features.push(feature(a.lon,a.lat,{label:aircraftLabel(a),raw:JSON.stringify(a)}));setSource('aircraft',fc);lastCounts.aircraft=fc.features.length;updateStatus()}catch(_e){setSource('aircraft',emptyFC());lastCounts.aircraft=0;updateStatus()}}
async function loadVessels(){if(!visible('vessels'))return;try{const b=map.getBounds();const payload=await api('/v2/live/vessels?south='+b.getSouth().toFixed(4)+'&west='+b.getWest().toFixed(4)+'&north='+b.getNorth().toFixed(4)+'&east='+b.getEast().toFixed(4)+'&limit=1500');const fc=emptyFC();lastCounts.aisConfigured=Boolean(payload.configured);for(const v of payload.vessels||[])if(validCoord(v.lat,-90,90)&&validCoord(v.lon,-180,180))fc.features.push(feature(v.lon,v.lat,{label:vesselLabel(v),raw:JSON.stringify(v)}));setSource('vessels',fc);lastCounts.vessels=fc.features.length;updateStatus()}catch(_e){setSource('vessels',emptyFC());lastCounts.vessels=0;updateStatus()}}
async function loadAircraftRoute(a,currentCoords){const callsign=String(a.flight||'').trim();if(!callsign){popupAt(currentCoords,popupAircraft(a,'Rota indisponível: aeronave sem callsign.'));return}try{const route=await api('/v2/live/aircraft/route?callsign='+encodeURIComponent(callsign)+'&lat='+Number(a.lat).toFixed(4)+'&lon='+Number(a.lon).toFixed(4));const aps=(route._airports||[]).filter(p=>validCoord(p.lat,-90,90)&&validCoord(p.lon,-180,180));const codes=route.airport_codes&&route.airport_codes!=='unknown'?route.airport_codes:'rota não identificada';const plausibility=route.plausible===false?'não validada pela posição atual':'plausível pela posição atual';popupAt(currentCoords,popupAircraft(a,'Rota: '+codes+' — '+plausibility+'. Contexto de rota não equivale a plano de voo confirmado.'));if(aps.length>=2&&route.plausible!==false){const origin=[Number(aps[0].lon),Number(aps[0].lat)],destination=[Number(aps[aps.length-1].lon),Number(aps[aps.length-1].lat)];setSource('route',{type:'FeatureCollection',features:[{type:'Feature',geometry:{type:'LineString',coordinates:[origin,currentCoords,destination]},properties:{}}]});setSource('routeEndpoints',{type:'FeatureCollection',features:[feature(origin[0],origin[1],{role:'origem'}),feature(destination[0],destination[1],{role:'destino'})]})}else{setSource('route',emptyFC());setSource('routeEndpoints',emptyFC())}}catch(_e){popupAt(currentCoords,popupAircraft(a,'Não foi possível consultar a rota agora.'))}}

map.on('load',()=>{addGeoJsonLayers();attachMapEvents();window.__geowatchMapReady=true;loadAll()});
map.on('error',e=>{if(e?.error?.message)console.warn('MapLibre:',e.error.message)});
document.getElementById('refresh').addEventListener('click',loadAll);document.getElementById('state').addEventListener('change',loadAll);
for(const box of document.querySelectorAll('input[data-layer]'))box.addEventListener('change',()=>{applyVisibility(box.dataset.layer);if(box.checked&&box.dataset.layer==='aircraft')loadAircraft();if(box.checked&&box.dataset.layer==='vessels')loadVessels()});
let moveTimer=null;map.on('moveend',()=>{clearTimeout(moveTimer);moveTimer=setTimeout(()=>{if(visible('aircraft'))loadAircraft();if(visible('vessels'))loadVessels()},700)});
setInterval(()=>{if(visible('aircraft'))loadAircraft();if(visible('vessels'))loadVessels()},60000);
</script>
</body></html>'''
    return (
        template.replace("__MAPLIBRE_VERSION__", _MAPLIBRE_VERSION)
        .replace("__LAYER_CONTROLS__", controls)
        .replace("__MAP_STYLE__", _map_style_js())
        .replace("__MAP_LAYERS__", catalog_js)
    )


__all__ = ["dashboard_html", "map_points"]

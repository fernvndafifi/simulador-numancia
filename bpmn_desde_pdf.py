"""Visor vectorial de los BPMN de Numancia. Fuente EXCLUSIVA: PDF aprobado.
No extrae semántica BPMN ni inventa conexiones. Los rectángulos interactivos
se vinculan a etiquetas textuales originales, no a identificadores XML.
"""
from pathlib import Path
import json
import re
import fitz
import streamlit.components.v1 as components

PDF_PATH = Path(__file__).with_name('modelos_to_be_fuente.pdf')


def _s(v):
    return json.dumps(v, ensure_ascii=False).replace('</', '<\\/')




def page_search_rects(pdf_path, pagina, label):
    """Find text in PDF vector text layer, returning original PDF coordinates.

    Returns [] instead of guessing when the text is absent or ambiguous.
    """
    with fitz.open(pdf_path) as doc:
        page=doc[pagina-1]
        matches=page.search_for(label, quads=False)
        # Short labels often match several words and are unsafe to auto-focus.
        if not matches and len(label.split()) > 2:
            # Partial phrase fallback, still derived directly from PDF text.
            words=label.split()
            matches=page.search_for(' '.join(words[:min(3,len(words))]))
        # Keep text fragments belonging to one occurrence, never fuse distant labels.
        if matches:
            clusters=[]
            for r in matches:
                if not clusters or abs(r.y0-clusters[-1][-1].y0)>32 or abs(r.x0-clusters[-1][-1].x0)>220:
                    clusters.append([r])
                else:
                    clusters[-1].append(r)
            matches=clusters[0]
        return [[round(r.x0,2),round(r.y0,2),round(r.x1,2),round(r.y1,2)] for r in matches[:12]]

def mostrar_bpmn_pdf(pagina: int, height: int = 720, active_labels=None, visited_labels=None, focus_label=None, initial_mode="auto", key=None):
    """Página 1-7 del PDF. Diagrama vectorial fiel; selección de textos por superposición."""
    if not PDF_PATH.exists():
        raise FileNotFoundError(f'Falta el PDF original: {PDF_PATH}')
    with fitz.open(PDF_PATH) as doc:
        if not 1 <= pagina <= len(doc):
            raise ValueError('Página fuera del PDF')
        page = doc[pagina - 1]
        svg = page.get_svg_image(text_as_path=False)
        width, ph = page.rect.width, page.rect.height
        # Spans textuales del PDF: coordenadas conservadas, no inferidas del XML.
        spans=[]
        for block in page.get_text('dict')['blocks']:
            if block.get('type') != 0:
                continue
            for line in block.get('lines', []):
                for span in line.get('spans', []):
                    txt=' '.join(span.get('text', '').split())
                    if len(txt) < 3:
                        continue
                    x0,y0,x1,y1 = span['bbox']
                    if x1-x0 < 7 or y1-y0 < 3:
                        continue
                    spans.append({'text':txt,'x':round(x0,2),'y':round(y0,2),'w':round(x1-x0,2),'h':round(y1-y0,2)})
    # Coordenadas de las etiquetas reales en el PDF; no se infiere el flujo del XML.
    # search_for encuentra frases aunque estén divididas en varios renglones.
    targets = list(dict.fromkeys([x for x in [focus_label] + list(active_labels or []) if x]))
    focus_regions = []
    for label in targets:
        hits = page_search_rects(PDF_PATH, pagina, label)
        if hits:
            focus_regions.append({"label": label, "rects": hits})
    # Eventos del SVG: superponer rectángulos transparentes sobre etiquetas.
    # El dibujo original (líneas, carriles, objetos de datos) permanece intacto.
    hotspots=''.join(
        f'<rect class="hotspot" data-i="{i}" x="{v["x"]}" y="{v["y"]}" width="{v["w"]}" height="{v["h"]}" rx="2" />'
        for i,v in enumerate(spans)
    )
    svg = svg.replace('</svg>', f'<g id="selection-hotspots">{hotspots}</g></svg>')
    svg = re.sub(r'^<svg ', '<svg id="pdf-diagram" ', svg, count=1)
    html = '''<!doctype html><html lang="es"><head><meta charset="utf-8"/>
<style>
*{box-sizing:border-box}body{margin:0;background:#f3f6fa;color:#18324c;font:12px Inter,Arial,sans-serif}
.bar{display:flex;align-items:center;gap:6px;padding:7px 9px;background:#fff;border:1px solid #dce5ef;border-bottom:0;flex-wrap:wrap}
button{border:1px solid #cbd8e4;border-radius:8px;background:#fff;color:#17324d;padding:5px 8px;cursor:pointer;font-weight:600}
button:hover{background:#eaf1f8}input{border:1px solid #cbd8e4;border-radius:8px;padding:7px 10px;min-width:115px;flex:1}
.main{display:flex;gap:0;border:1px solid #dce5ef;background:#fff;position:relative}
.viewport{height:HEIGHTpx;overflow:hidden;position:relative;cursor:grab;flex:1;min-width:0;background:#fff}
.viewport.moving{cursor:grabbing}
#stage{position:absolute;left:0;top:0;transform-origin:0 0;will-change:transform}
#pdf-diagram{display:block;max-width:none}
.hotspot{fill:transparent;stroke:transparent;stroke-width:1;cursor:pointer;pointer-events:all}
.hotspot:hover{fill:rgba(41,123,203,.16);stroke:#4789c4;stroke-width:2}
.hotspot.selected{fill:rgba(22,106,197,.16);stroke:#1d6fba;stroke-width:3}
.hotspot.searched{fill:rgba(239,181,48,.3);stroke:#c49125;stroke-width:2}
.hotspot.active{fill:rgba(42,138,215,.3);stroke:#237bcc;stroke-width:3}
.hotspot.visited{fill:rgba(50,150,92,.16);stroke:#2e925c;stroke-width:2}
.focus-mark{fill:rgba(41,123,203,.18);stroke:#237bcc;stroke-width:2;pointer-events:none}
.info{position:absolute;bottom:10px;left:10px;width:min(460px,calc(100% - 20px));padding:7px 10px;border:1px solid #dce5ef;border-radius:7px;background:rgba(255,255,255,.94);line-height:1.3;box-shadow:0 2px 10px rgba(0,0,0,.06);pointer-events:none}
.info h4{display:none}.meta{color:#5f7489;font-size:12px}.value{font-weight:650;overflow-wrap:anywhere;margin-top:8px}
.note{display:none}.counter{font-size:12px;color:#61768c;white-space:nowrap}
@media(max-width:740px){.viewport{height:520px}.info{max-width:90%}}
</style></head><body>
<div class="bar"><label for="mode" style="font-weight:650">Vista:</label><select id="mode" style="padding:7px;border-radius:8px;border:1px solid #cbd8e4"><option value="auto">Seguimiento automático</option><option value="manual">Exploración libre</option><option value="context">Vista contextual</option></select><button id="whole">Proceso completo</button><button id="focus">Centrar actividad</button><button id="plus" title="Acercar">＋</button><button id="minus" title="Alejar">－</button><button id="fit">Ajustar</button><button id="reset">100 %</button><select id="speed" title="Duración de transición" style="padding:6px;border:1px solid #cbd8e4;border-radius:8px"><option value="850">Suave</option><option value="550">Normal</option><option value="300">Rápida</option></select>
<input id="search" placeholder="Buscar texto en el diagrama"/><button id="find">Buscar</button><span id="count" class="counter"></span></div>
<div class="main"><div id="view" class="viewport"><div id="stage">SVG_CONTENT</div></div>
<aside class="info"><h4>Elemento seleccionado</h4><div id="selected" class="meta">Haz clic en cualquier texto del BPMN para consultar su denominación original.</div>
<div class="note"><strong>Fuente:</strong> página PAGE del PDF To-Be.<br/>Se preservan líneas, pools, carriles, documentos y asociaciones exactamente como están dibujados en el PDF.<br/><br/>La selección reconoce texto, pero no determina automáticamente responsables ni flujos ejecutables.</div></aside></div>
<script>
const items=ITEMS,active=ACTIVE,visited=VISITED,focusRegions=FOCUS_REGIONS;
const modeSelect=document.getElementById("mode");modeSelect.value=INITIAL_MODE;
const view=document.getElementById('view'),stage=document.getElementById('stage');
const diag=document.getElementById('pdf-diagram');
const W=WIDTH,H=HEIGHT0;
let scale=1,tx=0,ty=0,drag=false,dragged=false,lastX=0,lastY=0,animation=null;
const storageKey='numancia-pdf-camera-v16-page-'+PAGE;
const motionAllowed=!(window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches);
function ease(t){return t<.5?4*t*t*t:1-Math.pow(-2*t+2,3)/2}
function store(){try{sessionStorage.setItem(storageKey,JSON.stringify({scale,tx,ty,at:Date.now()}))}catch(e){}}
function restore(){try{let saved=JSON.parse(sessionStorage.getItem(storageKey)||'null');if(saved&&Date.now()-saved.at<1800000&&Number.isFinite(saved.tx)&&Number.isFinite(saved.ty)&&Number.isFinite(saved.scale)){scale=saved.scale;tx=saved.tx;ty=saved.ty;draw();return true}}catch(e){}return false}
function cancelMotion(){if(animation!==null){cancelAnimationFrame(animation);animation=null}}
function glide(x,y,z,animated=true){
  cancelMotion();
  z=Math.max(.03,Math.min(12,z));
  const from={x:tx,y:ty,z:scale},to={x,y,z};
  if(!animated||!motionAllowed){tx=x;ty=y;scale=z;draw();store();return}
  const duration=Number(document.getElementById('speed').value)||850;
  const distance=Math.hypot(to.x-from.x,to.y-from.y);
  const longTrip=distance>Math.max(view.clientWidth,view.clientHeight)*1.4;
  const t0=performance.now();
  function tick(now){
    const t=Math.min(1,(now-t0)/duration),e=ease(t);
    tx=from.x+(to.x-from.x)*e;ty=from.y+(to.y-from.y)*e;
    // On long moves, pull the camera back briefly to preserve orientation.
    const base=from.z+(to.z-from.z)*e;
    scale=longTrip?base*(1-.18*Math.sin(Math.PI*t)):base;
    draw();
    if(t<1)animation=requestAnimationFrame(tick);else{animation=null;scale=to.z;tx=to.x;ty=to.y;draw();store()}
  }
  animation=requestAnimationFrame(tick)
}
function draw(){stage.style.transform=`translate(${tx}px,${ty}px) scale(${scale})`;document.getElementById('count').textContent=Math.round(scale*100)+' %';}
function fit(animated=true){const z=Math.min((Math.max(view.clientWidth,420)-24)/W,(Math.max(view.clientHeight,500)-24)/H);glide((view.clientWidth-W*z)/2,(view.clientHeight-H*z)/2,z,animated)}
function zoom(f,cx=view.clientWidth/2,cy=view.clientHeight/2){let next=Math.max(.03,Math.min(12,scale*f));glide(cx-(cx-tx)*(next/scale),cy-(cy-ty)*(next/scale),next,true)}

// Locate a label based on PDF search rectangles, retaining nearby context.
// A missing/ambiguous match never triggers a guessed location.
const overlay=document.createElementNS('http://www.w3.org/2000/svg','g');
overlay.id='focus-overlays';diag.appendChild(overlay);
function clearMarks(){while(overlay.firstChild)overlay.removeChild(overlay.firstChild)}
function focusCurrent(mode=modeSelect.value){
  clearMarks();const matches=focusRegions[0]?.rects||[];
  if(!matches.length){document.getElementById('selected').textContent='No se pudo localizar con seguridad la actividad actual en el texto del PDF. Puedes buscarla o explorar manualmente.';return false}
  const x0=Math.min(...matches.map(r=>r[0])),y0=Math.min(...matches.map(r=>r[1]));
  const x1=Math.max(...matches.map(r=>r[2])),y1=Math.max(...matches.map(r=>r[3]));
  const padding=Math.max(18,(x1-x0)*.13);
  const rect=document.createElementNS('http://www.w3.org/2000/svg','rect');
  rect.setAttribute('x',x0-padding);rect.setAttribute('y',y0-padding);
  rect.setAttribute('width',x1-x0+2*padding);rect.setAttribute('height',y1-y0+2*padding);
  rect.setAttribute('rx',5);rect.setAttribute('class','focus-mark');overlay.appendChild(rect);
  if(mode==='manual')return true;
  const cx=(x0+x1)/2,cy=(y0+y1)/2;
  // Auto shows several neighboring activities; contextual is a closer view.
  const nearbyWidth=mode==='context'?Math.max(250,(x1-x0)*3):Math.max(480,(x1-x0)*5);
  const nearbyHeight=mode==='context'?Math.max(180,(y1-y0)*7):Math.max(340,(y1-y0)*12);
  const z=Math.max(.38,Math.min(mode==='context'?2.8:1.7,(Math.max(view.clientWidth,420)-35)/nearbyWidth,(Math.max(view.clientHeight,500)-35)/nearbyHeight));
  glide(view.clientWidth/2-cx*z,view.clientHeight/2-cy*z,z,true);
  document.getElementById('selected').textContent='Actividad enfocada: '+focusRegions[0].label;
  return true
}
modeSelect.onchange=()=>{if(modeSelect.value!=='manual')focusCurrent();else clearMarks()};
document.getElementById('focus').onclick=()=>{if(modeSelect.value==='manual')modeSelect.value='auto';focusCurrent()};
document.getElementById('whole').onclick=()=>{modeSelect.value='manual';clearMarks();fit()};

document.getElementById('plus').onclick=()=>zoom(1.3);document.getElementById('minus').onclick=()=>zoom(1/1.3);
document.getElementById('fit').onclick=fit;document.getElementById('reset').onclick=()=>glide(0,0,1,true);
view.addEventListener('wheel',e=>{e.preventDefault();let r=view.getBoundingClientRect();zoom(e.deltaY<0?1.15:1/1.15,e.clientX-r.left,e.clientY-r.top)},{passive:false});
view.addEventListener('pointerdown',e=>{cancelMotion();drag=true;dragged=false;lastX=e.clientX;lastY=e.clientY;view.setPointerCapture(e.pointerId);view.classList.add('moving')});
view.addEventListener('pointermove',e=>{if(!drag)return;let dx=e.clientX-lastX,dy=e.clientY-lastY;if(Math.abs(dx)+Math.abs(dy)>2)dragged=true;tx+=dx;ty+=dy;lastX=e.clientX;lastY=e.clientY;draw()});
view.addEventListener('pointerup',e=>{drag=false;store();view.classList.remove('moving')});
function normal(t){return (t||'').normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase().replace(/\\s+/g,' ').trim()}
const rects=[...document.querySelectorAll('.hotspot')];
for(const r of rects){let i=+r.dataset.i,t=normal(items[i].text);
 if(active.some(x=>normal(x).includes(t)||t.includes(normal(x))))r.classList.add('active');
 else if(visited.some(x=>normal(x).includes(t)||t.includes(normal(x))))r.classList.add('visited');
 r.addEventListener('click',e=>{if(dragged)return;rects.forEach(z=>z.classList.remove('selected'));r.classList.add('selected');let a=items[i];document.getElementById('selected').innerHTML='<div class="meta">Texto original del PDF</div><div class="value"></div><div class="meta" style="margin-top:8px">Posición: '+Math.round(a.x)+', '+Math.round(a.y)+'</div>';document.querySelector('.value').textContent=a.text;e.stopPropagation()})
}
function search(){const val=normal(document.getElementById('search').value);let found=[];rects.forEach(r=>{r.classList.remove('searched');let i=+r.dataset.i;if(val&&normal(items[i].text).includes(val)){r.classList.add('searched');found.push(items[i])}});if(found.length){let a=found[0];let z=Math.max(scale,.9);glide(view.clientWidth/2-(a.x+a.w/2)*z,view.clientHeight/2-(a.y+a.h/2)*z,z,true)}document.getElementById('selected').textContent=found.length?`${found.length} coincidencia(s) con «${val}»`:'No se encontraron coincidencias'}
document.getElementById('find').onclick=search;document.getElementById('search').onkeydown=e=>{if(e.key==='Enter')search()};
window.addEventListener('resize',()=>{if(modeSelect.value==='manual')fit();else focusCurrent()});requestAnimationFrame(()=>requestAnimationFrame(()=>{if(!restore())fit(false);if(modeSelect.value!=='manual')focusCurrent()}));
</script></body></html>'''
    html=(html.replace('SVG_CONTENT',svg).replace('ITEMS',_s(spans))
          .replace('ACTIVE',_s(active_labels or [])).replace('VISITED',_s(visited_labels or []))
          .replace('FOCUS_REGIONS',_s(focus_regions)).replace('INITIAL_MODE',_s(initial_mode))
          .replace('WIDTH',str(width)).replace('HEIGHT0',str(ph))
          .replace('HEIGHT',str(height)).replace('PAGE',str(pagina)))
    components.html(html, height=height+125, scrolling=False)

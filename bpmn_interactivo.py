"""Representación SVG vectorial a partir de las coordenadas BPMN-DI de Lucidchart.
No es una imagen. Conserva ubicaciones y segmentos XML exportados.
"""
from pathlib import Path
from html import escape
import json
import textwrap
import xml.etree.ElementTree as ET
import streamlit.components.v1 as components

NS={"bpmndi":"http://www.omg.org/spec/BPMN/20100524/DI","dc":"http://www.omg.org/spec/DD/20100524/DC","di":"http://www.omg.org/spec/DD/20100524/DI"}

def _num(val): return float(val)
def _attr(s):return escape(str(s),quote=True)
def _lines(name,maxchars=26,maxlines=4):
    name=' '.join((name or '').split())
    if not name:return []
    lines=textwrap.wrap(name,width=maxchars,break_long_words=False,break_on_hyphens=False)
    if len(lines)>maxlines:lines=lines[:maxlines-1]+[' '.join(lines[maxlines-1:])[:maxchars-1]+'…']
    return lines

# Carriles tomados de los laneSet de cada proceso del BPMN original. La exportación
# Lucidchart omite con frecuencia su geometría (BPMNShape) y algunas referencias.
PAGE_PROCESS = {1:'Macroproceso Comercial',2:'captación y seguimiento',3:'Reserva',4:'Resciliación',5:'Escrituración',6:'Promesa',7:'Cesión'}
SYSTEMS = {1:['PlanOK','UnySoft (UnyVen / UnyFin)','Linux'],2:['PlanOK','Linux'],3:['PlanOK','UnySoft (UnyVen / UnyFin)','Linux'],4:['PlanOK','UnySoft (UnyVen / UnyFin)'],5:['PlanOK','UnySoft (UnyVen / UnyFin)'],6:['PlanOK','UnySoft (UnyVen / UnyFin)'],7:['PlanOK','UnySoft (UnyVen)']}

def metadata_carriles(root, page, nodes):
    from collections import Counter
    proces=[]
    for elem in root:
        if elem.tag.rsplit('}',1)[-1]=='process' and PAGE_PROCESS[page].casefold() in elem.get('name','').casefold():
            proces.append(elem)
    lane_elements=[]
    if proces:
        for e in proces[0].iter():
            if e.tag.rsplit('}',1)[-1]=='lane':lane_elements.append(e)
    byid={n['id']:n for n in nodes}
    result=[]
    for lane in lane_elements:
        owned=[byid[r.text] for r in lane if r.tag.rsplit('}',1)[-1]=='flowNodeRef' and r.text in byid]
        result.append({'name':lane.get('name','Actor no identificado'),'owned':owned,'count':len(owned)})
    return result

# Reconstrucción de bandas de carriles desde el PDF: coordenadas aproximadas
# dentro del mismo espacio SVG que las tareas exportadas, no asignaciones BPMN verificadas.
PDF_BANDS = {
  2: [-260, 930, 1530],
  3: [85, 780, 1300, 1700],
  4: [-60, 280, 700, 1180, 1400],
  5: [-1330, -310, 650, 1580, 2310],
  6: [-750, -40, 520, 1230, 1950, 2590],
}
# Pools externos reproducidos según las etiquetas y bandas inferiores del PDF
# original. Las coordenadas son aproximaciones visuales cuando Lucidchart no
# exporta BPMNShape de estos pools; no se alteran tareas ni flujos del XML.
# Cada entrada indica: nombre visible, y inicial y y final en coordenadas XML.
EXTERNAL_POOLS = {
  1: [('PlanOK',-700,-360),('UnySoft',-360,-80),('Linux',-80,260)],
  2: [('PlanOK',1530,1900),('Cliente',1900,2250),('Linux',2250,2580)],
  3: [('Cliente',1700,2080),('PlanOK',2080,2380),('UnySoft',2380,2710),('Linux',2710,3070)],
  4: [('Cliente',1400,1750),('PlanOK',1750,2010),('UnySoft',2010,2300),('Linux',2300,2650)],
  5: [('Cliente',2310,2670),('PlanOK',2670,3010),('UnySoft',3010,3340),('Notaría',3340,3650),('Linux',3650,4000)],
  6: [('Cliente',2590,3150),('PlanOK',3150,3440),('UnySoft',3440,3730),('Notaría',3730,4040),('Linux',4040,4550)],
  7: [('Cliente cedente',975,1380),('Cliente cesionario',1380,1860),('UnySoft',1860,2230),('PlanOK',2230,2600),('Linux',2600,2990)],
}

# PDF: procesos que muestran sistemas/participantes auxiliares debajo de los carriles de trabajo.
# Nombres reales de carriles se extraen del laneSet del XML.

def _local(tag): return tag.rsplit('}',1)[-1]
def norm_list(labels, f):
    return {f(label) for label in (labels or []) if label}

def crear_html(path, active_labels=None, visited_labels=None):
    root=ET.parse(path).getroot()
    refs={e.attrib['id']:e for e in root.iter() if 'id' in e.attrib}
    nodes=[];edges=[]
    for s in root.findall('.//bpmndi:BPMNShape',NS):
        b=s.find('dc:Bounds',NS)
        if b is None:continue
        el=refs.get(s.get('bpmnElement',''))
        if el is None:continue
        tag=el.tag.rsplit('}',1)[-1]
        if tag in ('lane','participant','group'): continue
        x,y,w,h=(_num(b.get(k,'0')) for k in ('x','y','width','height'))
        nodes.append(dict(id=el.get('id'),name=el.get('name',''),kind=tag,x=x,y=y,w=w,h=h))
    for e in root.findall('.//bpmndi:BPMNEdge',NS):
        el=refs.get(e.get('bpmnElement',''))
        kind=el.tag.rsplit('}',1)[-1] if el is not None else ''
        pts=[(_num(p.get('x','0')),_num(p.get('y','0'))) for p in e.findall('di:waypoint',NS)]
        if len(pts)>=2: edges.append(dict(id=e.get('bpmnElement',''),kind=kind,points=pts,name=el.get('name','') if el is not None else ''))
    if not nodes: raise ValueError('El archivo BPMN no contiene coordenadas BPMN-DI.')
    # Determinar referencias semánticas de cada conexión, incluso las asociaciones
    # de datos cuyos extremos se expresan como elementos XML hijos.
    def endpoints(element, kind):
        if element is None: return [], []
        if kind in ('sequenceFlow','messageFlow','association'):
            return ([element.get('sourceRef')] if element.get('sourceRef') else [],
                    [element.get('targetRef')] if element.get('targetRef') else [])
        if kind in ('dataInputAssociation','dataOutputAssociation'):
            ss=[c.text for c in element if _local(c.tag)=='sourceRef' and c.text]
            tt=[c.text or c.get('id') for c in element if _local(c.tag)=='targetRef' and (c.text or c.get('id'))]
            return ss,tt
        return [],[]
    visible={n['id'] for n in nodes}
    for e in edges:
        element=refs.get(e['id'])
        e['source_ids'],e['target_ids']=endpoints(element,e['kind'])
        e['source_names']=[refs[k].get('name',_local(refs[k].tag)) for k in e['source_ids'] if k in refs]
        e['target_names']=[refs[k].get('name',_local(refs[k].tag)) for k in e['target_ids'] if k in refs]
        e['source_visible']=any(k in visible for k in e['source_ids'])
        e['target_visible']=any(k in visible for k in e['target_ids'])
    
    def norm(t):
        import unicodedata,re
        t=''.join(c for c in unicodedata.normalize('NFD',str(t).lower()) if unicodedata.category(c)!='Mn')
        return re.sub(r'[^a-z0-9]+',' ',t).strip()
    active_norm=norm_list(active_labels, norm)
    visited_norm=norm_list(visited_labels, norm)
    for node in nodes:
        label=norm(node.get('name',''))
        node['simulation_state'] = ('current' if label and label in active_norm else 'done' if label and label in visited_norm else '')
    page=int(Path(path).stem.split('_')[-1])
    lanes=metadata_carriles(root,page,nodes)
    systems=SYSTEMS.get(page,[])
    actor_by_id={n['id']:lane['name'] for lane in lanes for n in lane['owned']}
    for n in nodes:n['actor']=actor_by_id.get(n['id'],'Sin asignación explícita en XML')
    # Geometría ORIGINAL disponible en Macroproceso y Cesión.
    lane_shapes=[]
    for shape in root.findall('.//bpmndi:BPMNShape',NS):
        b=shape.find('dc:Bounds',NS)
        el=refs.get(shape.get('bpmnElement',''))
        if b is not None and el is not None and _local(el.tag)=='lane':
            lane_shapes.append(dict(name=el.get('name','Carril'),x=_num(b.get('x')),y=_num(b.get('y')),w=_num(b.get('width')),h=_num(b.get('height'))))
    # En archivos sin geometría del carril, las bandas se reconstruyen según
    # las líneas horizontales del PDF y el orden de actores del laneSet.
    if lane_shapes:
        bands=sorted(lane_shapes,key=lambda a:a['y'])
        band_source='Coordenadas originales del BPMN XML'
    else:
        cut=PDF_BANDS.get(page,[])
        regular=[n for n in nodes if n['kind'] not in ('dataStoreReference','dataInput','dataOutput')]
        ymax=max((n['y']+n['h'] for n in regular),default=2200)
        if len(cut) < len(lanes)+1:
            lo=min((n['y'] for n in regular),default=0)-70
            cut=[lo+(ymax-lo+100)*j/max(len(lanes),1) for j in range(len(lanes)+1)]
        bands=[dict(name=l['name'],x=0,y=cut[i],w=0,h=max(80,cut[i+1]-cut[i])) for i,l in enumerate(lanes)]
        band_source='Bandas reconstruidas con referencia visual al PDF (revisar límites)'
    external=[dict(name=name,y=start,h=end-start,category='externo' if name.lower().startswith('cliente') else 'sistema') for name,start,end in EXTERNAL_POOLS.get(page,[])]
    # Completamos los participantes que la exportación XML no guarda como
    # lane/participant, sin mover sus tareas ni sus conectores.
    for n in nodes:
        cy=n['y']+n['h']/2
        ext=next((b for b in external if b['y'] <= cy < b['y']+b['h']),None)
        if ext is not None and n['actor']=='Sin asignación explícita en XML':
            n['actor']=ext['name']+' (ubicación reconstruida del PDF)'
    if bands:
        # Alineación espacial de las tareas con los carriles; no se afirma que
        # sea una asignación lógica XML cuando flowNodeRef no está presente.
        for n in nodes:
            if n['actor']=='Sin asignación explícita en XML':
                cy=n['y']+n['h']/2
                hit=next((b for b in bands if b['y']<=cy<b['y']+b['h']),None)
                if hit and n['kind'] not in ('dataStoreReference','dataInput','dataOutput'):
                    n['actor']=hit['name']+' (ubicación visual del PDF)' 
    # Agrupamos los nodos por su pertenencia BPMN verificable. Algunos exports de
    # Lucidchart dejan flowNodeRef vacíos; los demás no reciben un actor inventado.

    x0=min(n['x'] for n in nodes)-250;y0=min(n['y'] for n in nodes)-130
    x1=max(n['x']+n['w'] for n in nodes)+140;y1=max(n['y']+n['h'] for n in nodes)+110
    if external:
        y0=min(y0,min(b['y'] for b in external)-50)
        y1=max(y1,max(b['y']+b['h'] for b in external)+40)
    if bands:
        y0=min(y0,min(b['y'] for b in bands)-65)
        y1=max(y1,max(b['y']+b['h'] for b in bands)+45)
    # Include edge extents to avoid clipped loops
    for e in edges:
        for px,py in e['points']:x0=min(x0,px-25);x1=max(x1,px+25);y0=min(y0,py-25);y1=max(y1,py+25)
    svg=[]
    svg.append(f'<svg id="diagram" xmlns="http://www.w3.org/2000/svg" viewBox="{x0:.1f} {y0:.1f} {x1-x0:.1f} {y1-y0:.1f}" role="img" aria-label="Modelo BPMN vectorial interactivo">')
    svg.append('''<defs>
      <marker id="arrow" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto"><path d="M0 0 L9 4.5 L0 9 z" fill="#647d93"/></marker>
      <marker id="openArrow" markerWidth="12" markerHeight="12" refX="11" refY="6" orient="auto"><path d="M1 1 L11 6 L1 11" fill="none" stroke="#546f88" stroke-width="1.5"/></marker>
      <marker id="messageStart" markerWidth="10" markerHeight="10" refX="5" refY="5"><circle cx="5" cy="5" r="3.2" fill="white" stroke="#546f88" stroke-width="1.3"/></marker>
      </defs>''')
    svg.append('<g id="drawing">')
    # Carriles: bandas dentro del MISMO espacio vectorial de las tareas y flechas.
    for i,b in enumerate(bands):
        bx=x0+8;by=b['y'];bw=max(100,x1-x0-16);bh=b['h']
        fill='#f0f5fb' if i%2==0 else '#fafcff'
        svg.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="{fill}" stroke="#b9cad9" stroke-width="3"/>')
        svg.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="195" height="{bh:.1f}" fill="#dce8f4" stroke="#b9cad9" stroke-width="2"/>')
        # Horizontal label, much more legible than the original vertical labels.
        label=_lines(b['name'],21,5)
        for j,t in enumerate(label):
            svg.append(f'<text x="{bx+13:.1f}" y="{by+29+j*24:.1f}" font-family="Segoe UI,Arial" font-weight="700" font-size="19" fill="#1d3c59">{escape(t)}</text>')
    if bands:
        svg.append(f'<text x="{x0+17:.1f}" y="{min(b["y"] for b in bands)-20:.1f}" font-family="Segoe UI,Arial" font-size="22" fill="#406480">PARTICIPANTES INTERNOS · {escape(band_source)}</text>')
    # La ubicación de carriles originales no está en el XML; por eso NO asignamos
    # arbitrariamente bandas a coordenadas de actividades. Mostramos actores en
    # un panel verificable y el vínculo al seleccionar cada elemento.

    # Participantes externos: pools rosados independientes, bajo las bandas
    # internas. Se incluyen dentro del mismo lienzo vectorial interactivo.
    for i,b in enumerate(external):
        bx=x0+8;by=b['y'];bw=max(100,x1-x0-16);bh=b['h']
        fill='#fff8fc' if i%2==0 else '#fffbfd'
        svg.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="{fill}" stroke="#c8a8bb" stroke-width="3"/>')
        svg.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="195" height="{bh:.1f}" fill="#f6dfed" stroke="#c8a8bb" stroke-width="2"/>')
        label=_lines(b['name'],21,4)
        for j,t in enumerate(label):
            svg.append(f'<text x="{bx+13:.1f}" y="{by+29+j*24:.1f}" font-family="Segoe UI,Arial" font-weight="700" font-size="19" fill="#733953">{escape(t)}</text>')
    if external:
        svg.append(f'<text x="{x0+17:.1f}" y="{min(b["y"] for b in external)-19:.1f}" font-family="Segoe UI,Arial" font-weight="700" font-size="22" fill="#925774">PARTICIPANTES EXTERNOS Y SISTEMAS · bandas reconstruidas del PDF</text>')
    # BPMN 2.0: sequence flow (continuo), message flow (guiones),
    # asociaciones de datos (punteado) y asociaciones no dirigidas (punteado).
    edge_styles={
        'sequenceFlow':('stroke="#647d93" stroke-width="2.8"','marker-end="url(#arrow)"'),
        'messageFlow':('stroke="#6a849a" stroke-width="2.6" stroke-dasharray="11 7"','marker-start="url(#messageStart)" marker-end="url(#openArrow)"'),
        'dataInputAssociation':('stroke="#61778a" stroke-width="2.3" stroke-dasharray="3 7"','marker-end="url(#openArrow)"'),
        'dataOutputAssociation':('stroke="#61778a" stroke-width="2.3" stroke-dasharray="3 7"','marker-end="url(#openArrow)"'),
        'association':('stroke="#7e8e9e" stroke-width="2.2" stroke-dasharray="3 7"',''),
    }
    for e in edges:
        points=e['points'];d='M '+' L '.join(f'{x:.1f} {y:.1f}' for x,y in points)
        sty,markers=edge_styles.get(e['kind'],('stroke="#7c8d9e" stroke-width="2" stroke-dasharray="5 6"',''))
        eidx=edges.index(e)
        svg.append(f'<g class="edge-group" data-e="{eidx}" tabindex="0" role="button" aria-label="{_attr(e["kind"])}">')
        svg.append(f'<path class="edge-hit" d="{d}" fill="none" stroke="transparent" stroke-width="18"/>')
        svg.append(f'<path class="edge-line" d="{d}" fill="none" {sty} {markers}><title>{_attr(e["kind"]+": "+e["name"])}</title></path></g>')
    for i,n in enumerate(nodes):
        x,y,w,h=n['x'],n['y'],n['w'],n['h'];kind=n['kind'];name=n['name']
        if 'Gateway' in kind or 'gateway' in kind.lower(): klass='gateway'
        elif 'Event' in kind or 'event' in kind.lower(): klass='event'
        elif kind in ('dataInput','dataOutput','dataObject','dataObjectReference'): klass='document'
        elif kind=='dataStoreReference': klass='datastore'
        elif kind=='textAnnotation': klass='annotation'
        else: klass='task'
        svg.append(f'<g class="node {klass}" data-i="{i}" tabindex="0" role="button" aria-label="{_attr(name or kind)}">')
        # Data Input/Output & Data Object: proper folded-corner BPMN sheet,
        # not an activity box. State/usage is shown below the sheet.
        if klass=='document':
            fold=max(7,min(15,w*.27,h*.3))
            path=f'M{x:.1f},{y:.1f} H{x+w-fold:.1f} L{x+w:.1f},{y+fold:.1f} V{y+h:.1f} H{x:.1f} Z'
            svg.append(f'<path class="doc-sheet" d="{path}"/>')
            svg.append(f'<path class="doc-fold" d="M{x+w-fold:.1f},{y:.1f} V{y+fold:.1f} H{x+w:.1f}"/>')
            # Input/Output indication is metadata, rather than mislabeling
            # a data object as an activity. Keep the document itself uncluttered.
            label={'dataInput':'Entrada','dataOutput':'Salida','dataObject':'Dato','dataObjectReference':'Dato'}.get(kind,'Dato')
            svg.append(f'<text class="doc-tag" x="{x+w/2:.1f}" y="{y+h+14:.1f}" text-anchor="middle">{label}</text>')
            if name:
                ll=_lines(name,26,4)
                for j,line in enumerate(ll):
                    svg.append(f'<text class="doc-label" x="{x+w/2:.1f}" y="{y+h+30+j*15:.1f}" text-anchor="middle">{escape(line)}</text>')
        elif klass=='datastore':
            ry=min(11,max(4,h*.18))
            svg.append(f'<path class="store-body" d="M{x:.1f},{y+ry:.1f} V{y+h-ry:.1f} C{x:.1f},{y+h+ry:.1f} {x+w:.1f},{y+h+ry:.1f} {x+w:.1f},{y+h-ry:.1f} V{y+ry:.1f} Z"/>')
            svg.append(f'<ellipse class="store-top" cx="{x+w/2:.1f}" cy="{y+ry:.1f}" rx="{w/2:.1f}" ry="{ry:.1f}"/>')
            ll=_lines(name,18,2)
            for j,line in enumerate(ll):
                svg.append(f'<text class="store-label" x="{x+w/2:.1f}" y="{y+h/2+j*14:.1f}" text-anchor="middle">{escape(line)}</text>')
        elif klass=='annotation':
            svg.append(f'<path class="annotation-bracket" d="M{x+12},{y} H{x} V{y+h} H{x+12}"/>')
            for j,line in enumerate(_lines(name,25,5)):
                svg.append(f'<text x="{x+17}" y="{y+17+j*17}">{escape(line)}</text>')
        elif klass=='gateway':
            svg.append(f'<polygon points="{x+w/2},{y} {x+w},{y+h/2} {x+w/2},{y+h} {x},{y+h/2}"/>')
        elif klass=='event':
            r=min(w,h)/2;svg.append(f'<circle cx="{x+w/2}" cy="{y+h/2}" r="{r}"/>')
        else:
            svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8"/>')
        if klass in ('task','gateway','event'):
            maxc=max(12,int(w/8.5)) if klass!='gateway' else max(9,int(w/11))
            lines=_lines(name,maxc,4 if klass!='gateway' else 3)
            spacing=min(19,max(12,h/(len(lines)+1))) if lines else 14
            ystart=y+h/2-(len(lines)-1)*spacing/2
            for j,line in enumerate(lines):
                svg.append(f'<text x="{x+w/2}" y="{ystart+j*spacing:.1f}" dominant-baseline="middle" text-anchor="middle">{escape(line)}</text>')
        type_label={'dataInput':'Documento de entrada','dataOutput':'Documento de salida','dataObject':'Objeto de datos','dataObjectReference':'Referencia a objeto de datos','dataStoreReference':'Almacén de datos','textAnnotation':'Anotación BPMN'}.get(kind,kind)
        n['type_label']=type_label
        svg.append(f'<title>{_attr(name or kind)} — {_attr(type_label)}</title></g>')
    svg.append('</g></svg>')
    jsnodes=json.dumps(nodes,ensure_ascii=False).replace('</','<\\/')
    jsedges=json.dumps(edges,ensure_ascii=False).replace('</','<\\/')
    lane_html=''.join('<div class="actor"><span>👤 '+escape(l['name'])+'</span><small>'+str(l['count'])+' elementos con asignación XML en este diagrama</small></div>' for l in lanes)
    system_html=''.join('<div class="actor system">🗄️ '+escape(x)+'</div>' for x in systems)
    from collections import Counter
    tally=Counter(e['kind'] for e in edges)
    summary=('Conexiones presentes en este archivo: '
             + f"{tally['sequenceFlow']} flujos de secuencia; "
             + f"{tally['dataInputAssociation']+tally['dataOutputAssociation']} asociaciones de datos; "
             + f"{tally['association']} asociaciones generales.")
    missing=sum(1 for e in edges if e['kind'] in ('dataInputAssociation','dataOutputAssociation') and not (e['source_visible'] and e['target_visible']))
    summary+= f" {missing} asociaciones de datos tienen al menos un extremo sin objeto gráfico en este archivo exportado; se conserva su línea XML, sin inventar el elemento faltante."
    disclaimer='<p class="note">Los carriles internos se recuperan del XML cuando es posible; los pools externos se reconstruyen según la distribución visual del PDF. La asignación reconstruida se identifica al seleccionar cada elemento. Los flujos y las actividades del XML no se modifican.</p>'
    ext_html=''.join('<div class="actor system">'+('👤 ' if b['category']=='externo' else '🗄️ ')+escape(b['name'])+'</div>' for b in external)
    people_panel='<aside class="actors"><h3>Actores internos</h3>'+lane_html+'<h3>Participantes externos y sistemas</h3>'+ext_html+'<h3>Auditoría de conexiones</h3><p class="note">'+escape(summary)+'</p>'+disclaimer+'</aside>'
    html="""<!doctype html><html lang="es"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<style>
*{box-sizing:border-box}body{margin:0;background:#f5f8fc;color:#18304a;font-family:Inter,Segoe UI,Arial,sans-serif}.toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:10px 14px;background:#fff;border-bottom:1px solid #dce5ee}.toolbar button{border:1px solid #cbd8e4;border-radius:8px;padding:7px 12px;background:#fff;color:#17324d;font-weight:600;cursor:pointer}.toolbar button:hover{background:#edf5ff}.toolbar small{color:#60748b}.workspace{display:grid;grid-template-columns:235px minmax(0,1fr)}.actors{padding:12px;background:#fff;border-right:1px solid #dce5ee;max-height:590px;overflow:auto}.actors h3{font-size:13px;margin:6px 0 12px;color:#17324d}.actor{padding:9px;background:#eef4fa;border-radius:8px;margin-bottom:7px;font-size:12px;color:#183650}.actor small{display:block;margin-top:4px;color:#60748b}.actor.system{background:#f5edf9}.note{font-size:11px;color:#7b5a21;line-height:1.4}#canvas{height:570px;overflow:hidden;position:relative;touch-action:none;cursor:grab}#canvas.drag{cursor:grabbing}#diagram{width:100%;height:100%;display:block}#drawing{transform-origin:0 0}.node{cursor:pointer}.edge-group{cursor:pointer}.edge-group:hover .edge-line{stroke:#116bb8;stroke-width:5}.edge-group.selected .edge-line,.edge-group.related .edge-line{stroke:#d36c25;stroke-width:5;filter:drop-shadow(0 0 3px #e6aa6f)}.node.sim-current>*:first-child{stroke:#1979df!important;stroke-width:8!important;filter:drop-shadow(0 0 9px #58a7ff)}
.node.sim-done>*:first-child{stroke:#239563!important;stroke-width:6!important}
.node.dimmed{opacity:.38}.edge-group.dimmed{opacity:.23}#canvas{height:680px}.node rect{fill:#fff;stroke:#567895;stroke-width:3}.node.gateway polygon{fill:#fff0cc;stroke:#b58d38;stroke-width:3}.node.event circle{fill:#e4f1ef;stroke:#55958b;stroke-width:4}.node.document .doc-sheet{fill:#fff;stroke:#3c647f;stroke-width:2.7;stroke-linejoin:round}
.node.document .doc-fold{fill:none;stroke:#3c647f;stroke-width:2.4}
.node.document .doc-tag{font-size:11px;fill:#637990;font-weight:700}
.node.document .doc-label{font-size:12px;fill:#27435d;font-weight:600}
.node.datastore .store-body{fill:#e7eff8;stroke:#4e6d88;stroke-width:2.8}
.node.datastore .store-top{fill:#f7fbff;stroke:#4e6d88;stroke-width:2.8}
.node.datastore .store-label{font-size:12px;fill:#23435f;font-weight:700}
.node.annotation .annotation-bracket{fill:none;stroke:#788d9e;stroke-width:2.6}
.node.document:hover .doc-sheet,.node.datastore:hover .store-body{stroke:#1973c7;stroke-width:4}
.node.selected .doc-sheet,.node.selected .store-body{stroke:#1377d1;stroke-width:5;filter:drop-shadow(0 0 4px #8bbbe6)}.node text{font-family:Inter,Segoe UI,Arial,sans-serif;font-size:16px;font-weight:600;fill:#1b3650;pointer-events:none}.node:hover>*:first-child{stroke:#1973c7;stroke-width:5}.node.selected>*:first-child{stroke:#1377d1;stroke-width:6;filter:drop-shadow(0 0 4px #8bbbe6)}.info{background:#fff;border-top:1px solid #dce5ee;padding:13px 18px;min-height:86px}.info h3{margin:0 0 7px;font-size:15px}.info p{margin:2px 0;font-size:13px;color:#60748b}.legend{font-size:12px;color:#69798b;padding:7px 14px;background:#fff;border-top:1px solid #e1eaf2}@media(max-width:650px){.workspace{grid-template-columns:1fr}.actors{max-height:190px}#canvas{height:430px}.toolbar small{width:100%}}
</style></head><body><div class="toolbar"><button id="plus">＋ Acercar</button><button id="minus">－ Alejar</button><button id="fit">⊡ Ajustar</button><button id="reset">↺ Restablecer</button><button id="clear">✕ Quitar selección</button><label style="font-size:12px"><input id="toggleData" type="checkbox" checked> Asociaciones de datos</label><label style="font-size:12px"><input id="toggleSeq" type="checkbox" checked> Flujos de secuencia</label><label style="font-size:12px"><input id="toggleOther" type="checkbox" checked> Otras conexiones</label><small>Rueda: zoom · Arrastra: desplazar · Selecciona una actividad para consultar su nombre</small></div><div class="workspace">PEOPLE_PANEL<div id="canvas">"""+''.join(svg)+"""</div></div><div class="info"><h3 id="selected">Selecciona un elemento del diagrama</h3><p id="selectedKind">El diagrama se ha reconstruido a partir del BPMN XML original de Lucidchart.</p></div><div class="legend">Notación BPMN: documento = hoja con esquina doblada · almacén = cilindro · flujo de secuencia = línea continua · asociación de datos = línea punteada · mensaje = línea discontinua · Sin ejecución automática de reglas</div>
<script>
const nodes=NODE_DATA,edges=EDGE_DATA;const canvas=document.querySelector('#canvas'),svg=document.querySelector('#diagram'),drawing=document.querySelector('#drawing');let scale=1,dx=0,dy=0,drag=false,last=null,active=null;
function update(){drawing.setAttribute('transform',`translate(${dx} ${dy}) scale(${scale})`)}
function zoom(f){scale=Math.max(.12,Math.min(20,scale*f));update()}
function fit(){scale=1;dx=0;dy=0;update();}
function clearSelection(){document.querySelectorAll('.selected,.related,.dimmed').forEach(x=>x.classList.remove('selected','related','dimmed'));document.querySelector('#selected').textContent='Selecciona una actividad, almacén o conexión';document.querySelector('#selectedKind').textContent='Las conexiones proceden de cada XML BPMN exportado.'}
document.querySelector('#clear').onclick=clearSelection;
function filterEdges(){document.querySelectorAll('.edge-group').forEach(g=>{const kind=edges[Number(g.dataset.e)].kind;const group=kind==='sequenceFlow'?'toggleSeq':(kind.startsWith('data')?'toggleData':'toggleOther');g.style.display=document.getElementById(group).checked?'':'none'})}
['toggleData','toggleSeq','toggleOther'].forEach(id=>document.getElementById(id).onchange=filterEdges);

document.querySelector('#plus').onclick=()=>zoom(1.5);document.querySelector('#minus').onclick=()=>zoom(1/1.5);document.querySelector('#fit').onclick=fit;document.querySelector('#reset').onclick=fit;
canvas.addEventListener('wheel',e=>{e.preventDefault();const rect=svg.getBoundingClientRect(),v=svg.viewBox.baseVal;const px=v.x+(e.clientX-rect.left)*v.width/rect.width,py=v.y+(e.clientY-rect.top)*v.height/rect.height;const old=scale;scale=Math.max(.12,Math.min(20,scale*(e.deltaY<0?1.25:.8)));dx+=(px-dx)*(1-old/scale);dy+=(py-dy)*(1-old/scale);update()},{passive:false});
canvas.addEventListener('pointerdown',e=>{if(e.target.closest('.node'))return;drag=true;last=[e.clientX,e.clientY];canvas.classList.add('drag');canvas.setPointerCapture(e.pointerId)});
canvas.addEventListener('pointermove',e=>{if(!drag)return;const r=svg.getBoundingClientRect(),v=svg.viewBox.baseVal;dx+=(e.clientX-last[0])*v.width/r.width;dy+=(e.clientY-last[1])*v.height/r.height;last=[e.clientX,e.clientY];update()});
canvas.addEventListener('pointerup',()=>{drag=false;canvas.classList.remove('drag')});
canvas.addEventListener('pointercancel',()=>{drag=false;canvas.classList.remove('drag')});
function showEdge(e,group){clearSelection();group.classList.add('selected');document.querySelector('#selected').textContent=e.kind==='sequenceFlow'?'Flujo de secuencia':(e.kind.startsWith('data')?'Asociación de datos':'Conexión BPMN');const from=e.source_names.join(', ')||'Referencia no identificada';const to=e.target_names.join(', ')||'Referencia no identificada';document.querySelector('#selectedKind').textContent='Origen: '+from+' · Destino: '+to+(e.source_visible&&e.target_visible?'':' · Atención: un extremo no está representado gráficamente en esta exportación.');}
for(const el of document.querySelectorAll('.edge-group')){const run=()=>showEdge(edges[Number(el.dataset.e)],el);el.onclick=run;el.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();run()}}}
for(const el of document.querySelectorAll('.node')){const select=()=>{clearSelection();el.classList.add('selected');const n=nodes[Number(el.dataset.i)];const adjacent=[];document.querySelectorAll('.edge-group').forEach(g=>{const e=edges[Number(g.dataset.e)];if([...e.source_ids,...e.target_ids].includes(n.id)){g.classList.add('related');adjacent.push(e)}else g.classList.add('dimmed')});document.querySelector('#selected').textContent=n.name||'Elemento BPMN';document.querySelector('#selectedKind').textContent='Tipo: '+(n.type_label||n.kind)+' · Actor: '+n.actor+' · Conexiones vinculadas en el XML: '+adjacent.length;};el.onclick=select;el.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();select()}}}
for (const el of document.querySelectorAll('.node')) {
  const nd=nodes[Number(el.dataset.i)];
  if(nd && nd.simulation_state) el.classList.add('sim-'+nd.simulation_state);
}
filterEdges();
fit();
</script></body></html>""".replace('NODE_DATA',jsnodes).replace('EDGE_DATA',jsedges)
    return html.replace('PEOPLE_PANEL', people_panel)

def mostrar_bpmn(path,height=790,active_labels=None,visited_labels=None):
    components.html(crear_html(path,active_labels,visited_labels),height=height,scrolling=False)

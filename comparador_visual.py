"""Comparación visual de documentos originales. As-Is: Draw.io (PNG); To-Be: PDF.
No estima equivalencias semánticas ni modifica los diagramas fuente.
"""
from pathlib import Path
import base64
import csv
import io
import json
import re
import html as htmlstdlib
import xml.etree.ElementTree as ET
import fitz
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

ROOT=Path(__file__).parent
FOLDER=ROOT/'as_is'
PDF=ROOT/'modelos_to_be_fuente.pdf'
# Las relaciones son para comparación visual, no equivalencias uno a uno validadas.
PAIRS={
 'Macroproceso comercial': ('Macro Proceso Comercial.drawio.png','Macro Proceso Comercial.drawio.drawio',1,'Macroproceso frente a macroproceso'),
 'Captación y seguimiento': ('Subproceso de captación y seguimiento de cliente.drawio.png','Subproceso de captación y seguimiento de cliente.drawio',2,'Captación frente a captación'),
 'Reserva': ('Subproceso de reserva.drawio.png','Subproceso de reserva.drawio',3,'Reserva frente a reserva'),
 'Resciliación y desistimiento': ('Subproceso de Resciliación y Desestimiento.drawio.png','Subproceso de Resciliación y Desestimiento.drawio',4,'Resciliación frente a resciliación'),
 'Escrituración': ('ProcesoPrincipalEscrituracion.drawio.png',None,5,'Escrituración: imagen As-Is; confirmar correspondencia del alcance'),
 'Proceso principal As-Is / Escrituración To-Be': ('ProcesoPrincipal.drawio.png','ProcesoPrincipal.drawio',5,'Alcances no equivalentes; solo comparación exploratoria'),
}
EMPTY=[{'Modelo':'','Elemento As-Is':'','Elemento To-Be':'','Tipo de cambio':'Pendiente de revisar','Brecha abordada':'','Regla asociada':'','Observación / evidencia':'','Estado de revisión':'Pendiente'}]

def _drawio_inventory(path):
    if not path or not path.exists(): return []
    try: root=ET.parse(path).getroot()
    except ET.ParseError:return []
    entries=[]
    for cell in root.iter('mxCell'):
        raw=cell.attrib.get('value','')
        val=htmlstdlib.unescape(re.sub('<[^>]+>',' ',raw)).strip()
        val=' '.join(val.split())
        if not val: continue
        style=cell.attrib.get('style','')
        kind='Conector' if cell.attrib.get('edge')=='1' else ('Carril' if 'swimlane' in style else 'Elemento')
        entries.append({'ID':cell.attrib.get('id',''),'Texto':val,'Tipo aproximado':kind})
    return entries

def _viewer(left_bytes,pdfsvg,label):
    uri='data:image/png;base64,'+base64.b64encode(left_bytes).decode()
    svg64=base64.b64encode(pdfsvg.encode('utf-8')).decode()
    name=json.dumps(label,ensure_ascii=False)
    # Two separate, persisted zoomable panes. The exact PDF shapes are not modified.
    document=r"""<!doctype html><html lang="es"><head><meta charset="utf-8"><style>
    *{box-sizing:border-box}body{margin:0;font:13px system-ui,Arial,sans-serif;color:#25354a;background:#f5f7fa}
    .wrap{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:2px}
    .panel{border:1px solid #cdd7e5;border-radius:10px;overflow:hidden;min-width:0;background:white}
    .head{padding:10px 12px;border-bottom:1px solid #dde4ed;display:flex;justify-content:space-between;align-items:center;gap:7px;flex-wrap:wrap;background:#f8fafc}
    .controls{display:flex;gap:5px;align-items:center}.controls button{border:1px solid #b8c8d9;background:white;border-radius:6px;padding:5px 9px;cursor:pointer}
    .viewport{height:610px;overflow:hidden;position:relative;background:#fff;touch-action:none;cursor:grab}
    .viewport:active{cursor:grabbing}.surface{position:absolute;left:0;top:0;transform-origin:0 0;will-change:transform}
    .surface img,.surface svg{display:block;max-width:none}
    .hint{background:#f8fafc;color:#617085;font-size:11px;padding:7px 12px}
    @media(max-width:740px){.wrap{grid-template-columns:1fr}.viewport{height:420px}}
    </style></head><body><div class="wrap">
      <div class="panel"><div class="head"><strong>AS-IS · Draw.io</strong><div class="controls"><button data-act="minus" data-panel="a">−</button><button data-act="plus" data-panel="a">+</button><button data-act="fit" data-panel="a">Ajustar</button><span id="pct-a"></span></div></div>
      <div class="viewport" id="view-a"><div class="surface" id="surface-a"><img src="__PNG__" id="graphic-a" draggable="false"></div></div><div class="hint">Imagen original del As-Is · zoom y arrastre independientes</div></div>
      <div class="panel"><div class="head"><strong>TO-BE · PDF original</strong><div class="controls"><button data-act="minus" data-panel="b">−</button><button data-act="plus" data-panel="b">+</button><button data-act="fit" data-panel="b">Ajustar</button><span id="pct-b"></span></div></div>
      <div class="viewport" id="view-b"><div class="surface" id="surface-b"></div></div><div class="hint">Página correspondiente del PDF To-Be · dibujo vectorial intacto</div></div>
    </div><script>
    const svgText=new TextDecoder('utf-8').decode(Uint8Array.from(atob('__SVG64__'),c=>c.charCodeAt(0)));document.getElementById('surface-b').innerHTML=svgText;
    const panes={};
    function setup(id){const v=document.getElementById('view-'+id), s=document.getElementById('surface-'+id), el=s.firstElementChild;
      if(id==='b'){el.style.width='auto';el.style.height='auto';}
      const w=(el.viewBox&&el.viewBox.baseVal&&el.viewBox.baseVal.width)||el.naturalWidth||el.width.baseVal.value;
      const h=(el.viewBox&&el.viewBox.baseVal&&el.viewBox.baseVal.height)||el.naturalHeight||el.height.baseVal.value;
      const p={v,s,w,h,z:1,x:0,y:0,drag:null};panes[id]=p;
      const render=()=>{p.s.style.transform=`translate(${p.x}px,${p.y}px) scale(${p.z})`;document.getElementById('pct-'+id).textContent=Math.round(p.z*100)+' %';};
      const fit=()=>{p.z=Math.min((v.clientWidth-24)/w,(v.clientHeight-24)/h);p.x=(v.clientWidth-w*p.z)/2;p.y=(v.clientHeight-h*p.z)/2;render()};p.fit=fit;
      p.zoom=(ratio,cx=v.clientWidth/2,cy=v.clientHeight/2)=>{const nz=Math.min(5,Math.max(.02,p.z*ratio));p.x=cx-(cx-p.x)*nz/p.z;p.y=cy-(cy-p.y)*nz/p.z;p.z=nz;render()};
      v.addEventListener('wheel',e=>{e.preventDefault();const r=v.getBoundingClientRect();p.zoom(e.deltaY<0?1.12:1/1.12,e.clientX-r.left,e.clientY-r.top)},{passive:false});
      v.addEventListener('pointerdown',e=>{p.drag={x:e.clientX,y:e.clientY,ox:p.x,oy:p.y};v.setPointerCapture(e.pointerId)});
      v.addEventListener('pointermove',e=>{if(!p.drag)return;p.x=p.drag.ox+e.clientX-p.drag.x;p.y=p.drag.oy+e.clientY-p.drag.y;render()});
      v.addEventListener('pointerup',()=>{p.drag=null});v.addEventListener('pointercancel',()=>{p.drag=null});
      window.addEventListener('resize',fit);fit();
    }
    const img=document.getElementById('graphic-a');if(img.complete)setup('a');else img.onload=()=>setup('a');
    setup('b');document.querySelectorAll('button[data-act]').forEach(btn=>btn.addEventListener('click',()=>{let p=panes[btn.dataset.panel];if(!p)return;if(btn.dataset.act==='fit')p.fit();else p.zoom(btn.dataset.act==='plus'?1.25:.8)}));
    </script></body></html>"""
    return document.replace('__PNG__',uri).replace('__SVG64__',svg64)

def comparador_visual_view():
    st.title('Comparador visual As-Is / To-Be')
    st.caption('Fuentes originales: imágenes y archivos Draw.io del As-Is, y PDF aprobado del To-Be. Ninguna conexión se reconstruye a partir de XML defectuosos.')
    model=st.selectbox('Selecciona el proceso para comparar',list(PAIRS),key='vis_pair')
    image_name,drawio_name,page,scope=PAIRS[model]
    st.info('Alcance: '+scope+'. Las ubicaciones y flujos se muestran tal como aparecen en los originales; su equivalencia requiere revisión.')
    img=FOLDER/image_name
    if not img.exists() or not PDF.exists():
        st.error('Falta un archivo de origen. Comprueba que se copió la carpeta as_is y el PDF del To-Be.')
        return
    with fitz.open(PDF) as doc:svg=doc[page-1].get_svg_image(text_as_path=False)
    components.html(_viewer(img.read_bytes(),svg,model),height=705,scrolling=False)
    with st.expander('Inventario textual del As-Is (extraído del archivo editable)',expanded=False):
        inventory=_drawio_inventory(FOLDER/drawio_name) if drawio_name else []
        if inventory:
            df=pd.DataFrame(inventory)
            st.dataframe(df,use_container_width=True,hide_index=True,height=240)
            st.download_button('Descargar inventario CSV',df.to_csv(index=False).encode('utf-8-sig'),'numancia_inventario_as_is.csv',mime='text/csv')
            st.caption('El inventario extrae etiquetas; no clasifica de forma concluyente eventos, tareas o compuertas.')
        else:st.info('No hay archivo draw.io editable para esta imagen; el As-Is se compara visualmente.')
    st.subheader('Matriz de correspondencias y diferencias')
    st.caption('Completa únicamente lo verificable en los diagramas. Las filas son editables y se conservan durante esta sesión de Streamlit.')
    k='matrix_'+re.sub(r'\W+','_',model)
    if k not in st.session_state:
        st.session_state[k]=pd.DataFrame([{**EMPTY[0], 'Modelo':model}])
    edited=st.data_editor(st.session_state[k],num_rows='dynamic',use_container_width=True,hide_index=True,key='editor_'+k,column_config={
        'Tipo de cambio':st.column_config.SelectboxColumn(options=['Pendiente de revisar','Se mantiene','Se modifica','Se incorpora al To-Be','Se elimina del To-Be','Sin correspondencia directa']),
        'Estado de revisión':st.column_config.SelectboxColumn(options=['Pendiente','En revisión','Validado con equipo','Validado con Numancia'])})
    st.session_state[k]=edited
    st.download_button('⬇ Descargar matriz de este proceso',edited.to_csv(index=False).encode('utf-8-sig'),file_name='numancia_comparacion_'+re.sub(r'\W+','_',model.lower())+'.csv',mime='text/csv')
    st.caption('La matriz registra diferencias descriptivas: no atribuye automáticamente mejoras de tiempo, calidad o retrabajo.')
    with st.expander('Otros archivos As-Is recibidos'):
        st.write('También se conservaron Macro proceso Contabilidad.drawio y Subproceso de Compraventa.drawio. No se les asignó automáticamente un To-Be equivalente porque tienen otro alcance y no incluyen PNG suministrado.')

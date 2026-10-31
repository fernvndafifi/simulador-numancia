"""Extensiones de análisis del prototipo NUMANCIA: datos exclusivamente ficticios.
No ejecuta XML BPMN ni consulta PlanOK/UnySoft.
"""
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
import pandas as pd
import streamlit as st
from bpmn_interactivo import mostrar_bpmn

ROOT=Path(__file__).parent
NS={'b':'http://www.omg.org/spec/BPMN/20100524/MODEL','di':'http://www.omg.org/spec/BPMN/20100524/DI','bpmndi':'http://www.omg.org/spec/BPMN/20100524/DI','dc':'http://www.omg.org/spec/DD/20100524/DC'}
PROCESS_XML={"Captación y seguimiento":2,"Reserva":3,"Promesa de compraventa":6,"Escrituración":5,"Resciliación y desistimiento":4,"Cesión":7,"Entrega":1}
RULES={
'1.3':('Unicidad del registro del cliente','CLIENTE_UNICO'),
'2.3':('Cambiar estado de la unidad','ESTADO_UNIDAD'),
'2.6':('Comprobación del estado de la unidad','ESTADO_UNIDAD'),
'2.7':('Correspondencia unidad–roles','ROLES'),
'4.2':('Validación de datos antes de escrituración','ANTECEDENTES'),
'5.1':('Validación del pago del pie','PIE'),
'6.1':('Consistencia del documento de cesión','CESION'),
'7.1':('Validación previa al traspaso entre etapas','ANTECEDENTES'),
'7.2':('Consistencia de datos económicos','ECONOMIA'),
'7.4':('Notificación de modificaciones y/o avances','NOTIFICACION'),
}
DATA={
'operacion':'OP-002','cliente_id':'CL-019','cliente_duplicado':False,
'unidad':'A-405','estado_planok':'Reservada','estado_unysoft':'Disponible',
'bodega_planok':'B-12','bodega_unysoft':'B-21',
'antecedentes_completos':False,'precio_planok':78000000,'precio_unysoft':78000000,
'pie_pactado':7800000,'pie_pagado':7700000,
'cesion_validada':False,'notificacion_enviada':False,
}
DATA_LABELS={'cliente_duplicado':'Cliente ya registrado','estado_planok':'Estado PlanOK (simulado)',
'estado_unysoft':'Estado UnySoft (simulado)','bodega_planok':'Bodega PlanOK (simulada)',
'bodega_unysoft':'Bodega UnySoft (simulada)','antecedentes_completos':'Antecedentes completos',
'precio_planok':'Precio comercial','precio_unysoft':'Precio financiero',
'pie_pactado':'Pago del pie pactado','pie_pagado':'Pago del pie registrado',
'cesion_validada':'Documento de cesión conforme','notificacion_enviada':'Notificación comunicada'}

def normal(t):
    t=''.join(c for c in unicodedata.normalize('NFD',str(t).lower()) if unicodedata.category(c)!='Mn')
    return re.sub(r'[^a-z0-9]+',' ',t).strip()

def bpmn_graph(page):
    path=ROOT/'bpmn_xml'/f'modelo_{page}.bpmn'
    root=ET.parse(path).getroot()
    items={e.get('id'):e for e in root.iter() if e.get('id')}
    nodes={};edges=[];lane_members=defaultdict(list)
    for e in root.iter():
        kind=e.tag.rsplit('}',1)[-1]
        if kind in {'task','userTask','manualTask','serviceTask','sendTask','receiveTask','scriptTask','businessRuleTask','subProcess','callActivity','startEvent','endEvent','intermediateCatchEvent','intermediateThrowEvent','exclusiveGateway','parallelGateway','inclusiveGateway','eventBasedGateway','dataObjectReference','dataStoreReference','dataInput','dataOutput'} and e.get('id'):
            nodes[e.get('id')]={'name':e.get('name',''),'kind':kind}
        if kind=='lane':
            for child in e:
                if child.tag.rsplit('}',1)[-1]=='flowNodeRef' and child.text:
                    lane_members[child.text].append(e.get('name') or 'Carril sin nombre')
        if kind in {'sequenceFlow','messageFlow','association','dataInputAssociation','dataOutputAssociation'}:
            src=e.get('sourceRef');dst=e.get('targetRef')
            if kind.startswith('data'):
                sources=[x.text for x in e if x.tag.rsplit('}',1)[-1]=='sourceRef']
                targets=[x.text for x in e if x.tag.rsplit('}',1)[-1]=='targetRef']
                src=sources[0] if sources else src; dst=targets[0] if targets else dst
            edges.append({'tipo':kind,'origen':src,'destino':dst,'etiqueta':e.get('name','')})
    shapes={e.get('bpmnElement') for e in root.findall('.//bpmndi:BPMNShape',NS)}
    di_edges={e.get('bpmnElement') for e in root.findall('.//bpmndi:BPMNEdge',NS)}
    return {'nodes':nodes,'edges':edges,'lanes':lane_members,'shapes':shapes,'edge_count_di':len(di_edges),'path':path}

def results_rules(record):
    check={
     'CLIENTE_UNICO':(not record['cliente_duplicado'],'El identificador del cliente ya se encuentra registrado.'),
     'ESTADO_UNIDAD':(record['estado_planok']==record['estado_unysoft'],'Los estados simulados de la unidad no coinciden.'),
     'ROLES':(record['bodega_planok']==record['bodega_unysoft'],'La bodega asociada no corresponde al registro relacionado.'),
     'ANTECEDENTES':(record['antecedentes_completos'],'Faltan antecedentes necesarios para el hito.'),
     'PIE':(record['pie_pactado']==record['pie_pagado'],'El monto del pie registrado difiere del pactado.'),
     'CESION':(record['cesion_validada'],'El documento de cesión no se encuentra conforme.'),
     'ECONOMIA':(record['precio_planok']==record['precio_unysoft'],'Los precios comerciales y financieros difieren.'),
     'NOTIFICACION':(record['notificacion_enviada'],'La modificación no fue notificada.'),
    }
    return [(rid,name,code,check[code][0], 'Conforme' if check[code][0] else check[code][1]) for rid,(name,code) in RULES.items()]

def record_rule_events():
    if 'rule_runs' not in st.session_state:st.session_state.rule_runs=[]
    if 'rule_data' not in st.session_state:st.session_state.rule_data=dict(DATA)

def rules_view():
    record_rule_events()
    st.title('Validaciones de consistencia · laboratorio de datos')
    st.info('Estos controles están programados sobre datos **ficticios**. Son ejemplos verificables de reglas seleccionadas, no una implementación operativa de Numancia ni una validación automática de toda su matriz.')
    c1,c2=st.columns([1.25,1])
    with c1:
        with st.form('datos_simulados'):
            d=dict(st.session_state.rule_data)
            d['cliente_duplicado']=st.checkbox(DATA_LABELS['cliente_duplicado'],value=d['cliente_duplicado'])
            d['estado_planok']=st.selectbox(DATA_LABELS['estado_planok'],['Disponible','Reservada','Promesada'],index=['Disponible','Reservada','Promesada'].index(d['estado_planok']))
            d['estado_unysoft']=st.selectbox(DATA_LABELS['estado_unysoft'],['Disponible','Reservada','Promesada'],index=['Disponible','Reservada','Promesada'].index(d['estado_unysoft']))
            d['bodega_planok']=st.text_input(DATA_LABELS['bodega_planok'],value=d['bodega_planok'])
            d['bodega_unysoft']=st.text_input(DATA_LABELS['bodega_unysoft'],value=d['bodega_unysoft'])
            d['antecedentes_completos']=st.checkbox(DATA_LABELS['antecedentes_completos'],value=d['antecedentes_completos'])
            d['precio_planok']=st.number_input(DATA_LABELS['precio_planok'],min_value=0,value=d['precio_planok'],step=100000)
            d['precio_unysoft']=st.number_input(DATA_LABELS['precio_unysoft'],min_value=0,value=d['precio_unysoft'],step=100000)
            d['pie_pactado']=st.number_input(DATA_LABELS['pie_pactado'],min_value=0,value=d['pie_pactado'],step=10000)
            d['pie_pagado']=st.number_input(DATA_LABELS['pie_pagado'],min_value=0,value=d['pie_pagado'],step=10000)
            d['cesion_validada']=st.checkbox(DATA_LABELS['cesion_validada'],value=d['cesion_validada'])
            d['notificacion_enviada']=st.checkbox(DATA_LABELS['notificacion_enviada'],value=d['notificacion_enviada'])
            apply=st.form_submit_button('▶ Aplicar y comprobar reglas',type='primary')
        if apply:
            st.session_state.rule_data=d
            rr=results_rules(d)
            st.session_state.rule_runs.append({'fecha':datetime.now().isoformat(timespec='seconds'),'operacion':d['operacion'],'resultado':sum(x[3] for x in rr),'total':len(rr),'reglas':[{'id':a,'cumple':ok,'detalle':detail} for a,_,_,ok,detail in rr]})
    with c2:
        rr=results_rules(st.session_state.rule_data)
        st.metric('Controles conformes',f'{sum(x[3] for x in rr)}/{len(rr)}')
        for rid,name,code,passed,desc in rr:
            with st.container(border=True):
                st.markdown(('✅' if passed else '⚠️')+f' **{rid} · {name}**')
                st.caption(desc)
        st.caption('Los controles se evalúan de forma independiente y no modifican registros reales.')
    if st.button('Restablecer datos ficticios'):
        st.session_state.rule_data=dict(DATA);st.rerun()
    st.download_button('⬇ Descargar verificaciones JSON',json.dumps(st.session_state.rule_runs,ensure_ascii=False,indent=2),file_name='numancia_validaciones.json',mime='application/json')

def trace_view():
    st.title('Trazabilidad de información y conexiones')
    st.caption('Relaciones identificadas en los archivos XML BPMN. La pertenencia funcional de un dato a PlanOK/UnySoft solo debe darse por confirmada cuando figure en el diseño o la matriz.')
    label=st.selectbox('Proceso',list(PROCESS_XML),key='trace_process')
    graph=bpmn_graph(PROCESS_XML[label]); nodes=graph['nodes'];edges=graph['edges']
    datanodes={k:v for k,v in nodes.items() if v['kind'] in ('dataObjectReference','dataStoreReference','dataInput','dataOutput')}
    if not datanodes:
        st.warning('El XML seleccionado no expone objetos de datos como nodos semánticos independientes. Consulta el visor BPMN y registra esta limitación.')
    else:
        opts=list(datanodes)
        selected=st.selectbox('Documento o almacén',opts,format_func=lambda x:(datanodes[x]['name'] or datanodes[x]['kind'])+' · '+x)
        rel=[e for e in edges if selected in (e['origen'],e['destino'])]
        st.metric('Relaciones directas encontradas',len(rel))
        if rel:
            st.dataframe(pd.DataFrame([{'Tipo':e['tipo'],'Origen':nodes.get(e['origen'],{}).get('name') or e['origen'],'Destino':nodes.get(e['destino'],{}).get('name') or e['destino']} for e in rel]),hide_index=True,use_container_width=True)
        else:st.info('No hay enlaces semánticos directos recuperables para este objeto.')
    st.subheader('BPMN interactivo')
    mostrar_bpmn(graph['path'],height=760)

def coverage_view(scenarios):
    st.title('Auditoría de cobertura y fidelidad')
    st.caption('Compara los recorridos de prueba con las etiquetas del XML. La coincidencia por nombre es una ayuda, no demuestra correspondencia exacta de flechas, carriles o condiciones.')
    rows=[];detail=[]
    for title,pg in PROCESS_XML.items():
        g=bpmn_graph(pg);labels={normal(x['name']) for x in g['nodes'].values() if x['name']}
        specs=[(key,spec) for key,spec in scenarios.items() if spec['module']==title]
        total=sum(len(s['nodes']) for _,s in specs)
        matched=sum(normal(n['label']) in labels for _,s in specs for n in s['nodes'].values())
        rows.append({'Proceso':title,'Nodos semánticos en XML':len(g['nodes']),'Conexiones XML':len(g['edges']),'Líneas con geometría':g['edge_count_di'],'Pasos de guiones':total,'Coincidencias exactas de etiqueta':matched,'Pasos sin correspondencia':total-matched})
        for sid,spec in specs:
            for key,n in spec['nodes'].items():
                detail.append({'Escenario':sid,'Actividad del guion':n['label'],'Coincide con nombre XML':normal(n['label']) in labels})
    st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
    st.download_button('⬇ Exportar cobertura CSV',pd.DataFrame(rows).to_csv(index=False).encode('utf-8-sig'),file_name='numancia_cobertura.csv')
    if detail:
        with st.expander('Detalle de correspondencias',expanded=True):
            st.dataframe(pd.DataFrame(detail),hide_index=True,use_container_width=True)
    allids=set(x for s in scenarios.values() for x in s['rules'])
    st.subheader('Cobertura documental de reglas')
    st.write(f'**{len(allids)} identificadores** asociados a los guiones piloto. Esto significa que están referenciados; NO que todos se hayan validado mediante código.')
    st.write(', '.join(sorted(allids)))
    st.info('La verificación definitiva exige cotejar las actividades, las rutas completas, los responsables y las asociaciones documentales contra el BPMN original y con Numancia.')

def compare_view(process_info):
    st.title('Comparación de diseño As-Is / To-Be')
    st.warning('No se ha incorporado un BPMN As-Is estructurado a este proyecto. Esta matriz es cualitativa y sus casillas As-Is deben confirmarse con el diagnóstico; no calcula mejoras reales.')
    data=[
    ('Validación previa al traspaso','Brecha de validaciones no formalizadas','Control previo al avance, según regla 7.1'),
    ('Correspondencia de registros','Falta de homologación entre registros','Control de unidad–roles, regla 2.7'),
    ('Cambios y comunicaciones','Falta de notificación estandarizada','Notificación de cambios, regla 7.4'),
    ('Escrituración','Antecedentes inconsistentes o incompletos','Validación comercial, financiera y documental, regla 4.2'),
    ('Cesión','Revisar evidencia específica As-Is','Validación documental y actualización, reglas 6.1–6.3')]
    df=pd.DataFrame(data,columns=['Aspecto','Situación As-Is / brecha a verificar','Respuesta propuesta To-Be'])
    st.dataframe(df,hide_index=True,use_container_width=True)
    st.download_button('⬇ Descargar matriz CSV',df.to_csv(index=False).encode('utf-8-sig'),file_name='numancia_comparacion.csv')
    st.subheader('Próximo paso para comparación cuantitativa')
    st.write('Agregar el BPMN As-Is, definir supuestos equivalentes y medir las mismas rutas en ambos diseños. Sin esos datos no es válido afirmar reducciones de tiempo o retrabajo.')

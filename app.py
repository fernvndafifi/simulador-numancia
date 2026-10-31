"""NUMANCIA | Simulador visual del modelo To-Be (prototipo académico).
Ejecutar: py -3.13 -m streamlit run app.py
No se conecta a PlanOK ni UnySoft. Los recorridos son pilotos que requieren cotejo con BPMN.
"""
from datetime import datetime
from pathlib import Path
from html import escape
import io
import json
import pandas as pd
import streamlit as st
from bpmn_desde_pdf import mostrar_bpmn_pdf
from numancia_extra import rules_view, trace_view, coverage_view, PROCESS_XML
from comparador_visual import comparador_visual_view

st.set_page_config(page_title="NUMANCIA · Simulador visual To-Be", page_icon="🏢", layout="wide", initial_sidebar_state="expanded")
# Estilos de la interfaz: archivo independiente para facilitar el mantenimiento.
def cargar_estilos():
    ruta_css = Path(__file__).with_name("styles.css")
    if ruta_css.exists():
        st.markdown(f"<style>{ruta_css.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
    else:
        st.warning("No se encontró styles.css; la simulación funciona sin personalización visual.")

cargar_estilos()

MODULES = [
("Captación y seguimiento",2,"Captación, contacto, visitas y datos de reserva"),
("Reserva",3,"Pagos, validación, correcciones y cambio de unidad"),
("Promesa de compraventa",6,"Pie, documentos, validación y firmas"),
("Escrituración",5,"Documentación, financiamiento, borradores y firmas"),
("Resciliación y desistimiento",4,"Documentos, pagos y liberación"),
("Cesión",7,"Nuevo comprador, documento de cesión y registros"),
("Entrega",1,"Etapa representada en el macroproceso general"),
]
# Nodos de las pruebas piloto: actividad, ayuda, regla(s), opciones (etiqueta, destino, efectos).
# No son una transcripción exhaustiva del BPMN, sino rutas de ensayo contrastables.
def n(label, help_text, rules, *choices):
    return {"label":label,"help":help_text,"rules":rules,"choices":list(choices)}
def c(text, target, **effects):
    return {"text":text,"target":target,"effects":effects}

SCENARIOS = {
"R01": {"module":"Reserva","name":"Reserva sin inconvenientes","goal":"Recorrer una operación de reserva con pago y antecedentes conformes.","start":"comprobante","rules":["2.3","2.6","7.1"],"nodes":{
 "comprobante":n("Recepcionar comprobante de pago","Comprobante ficticio recibido para evaluación.",[],c("Recepcionar comprobante","movimiento")),
 "movimiento":n("Validar movimiento","Comprobar el resultado preconfigurado del pago ficticio.",[],c("Pago sin inconvenientes","contabilizar",payment="Válido")),
 "contabilizar":n("Contabilizar ingreso","Representación del registro del ingreso, no registro contable real.",["2.5"],c("Registrar ingreso simulado","crear")),
 "crear":n("Crear reserva","Se genera una reserva ficticia.",["2.1","2.2"],c("Crear reserva","validar",reservation="Creada")),
 "validar":n("¿Reserva validada?","El escenario contiene antecedentes completos.",["2.4","7.1"],c("Sí: antecedentes conformes","estado")),
 "estado":n("Cambiar estado de unidad a reservada","Se representa la actualización del estado, no una escritura en sistemas.",["2.3"],c("Actualizar estado simulado","documento",unit_status="Reservada")),
 "documento":n("Generar documento de reserva","Generación representada de respaldo documental.",[],c("Generar documento","firma",document="Generado")),
 "firma":n("Firmar documento de reserva y cierre de negocios","Firma ficticia para finalizar el recorrido.",[],c("Firmar y finalizar","FIN",document="Firmado"))}},
"R02": {"module":"Reserva","name":"Reserva con errores","goal":"Observar el rechazo de una validación, corregir antecedentes y revalidar.","start":"crear","rules":["2.4","7.1"],"nodes":{
 "crear":n("Crear reserva","La operación se creó con un antecedente incompleto.",[],c("Crear reserva","validar",reservation="En validación")),
 "validar":n("¿Reserva validada?","El escenario preconfigurado exige corregir un antecedente.",["2.4","7.1"],c("No: solicitar corrección","corregir",reservation="Observada")),
 "corregir":n("Corregir errores en reserva","El usuario puede representar la subsanación del antecedente faltante.",["2.4"],c("Corregir antecedente","revalidar",reservation="Corregida",document="Corregido")),
 "revalidar":n("¿Reserva validada? · nueva revisión","Se verifica el dato ficticio corregido.",["2.4","7.1"],c("Sí: aprobar revalidación","estado",reservation="Validada"),c("No: volver a corregir","corregir",reservation="Observada")),
 "estado":n("Cambiar estado de unidad a reservada","Cambio de estado representado.",["2.3"],c("Actualizar y finalizar","FIN",unit_status="Reservada"))}},
"R03": {"module":"Reserva","name":"Pago de reserva inválido","goal":"Probar las alternativas ante un pago rechazado: reintento o cancelación.","start":"comprobante","rules":["2.5","7.1"],"nodes":{
 "comprobante":n("Recepcionar comprobante de pago","Comprobante de prueba recibido.",[],c("Continuar","validar")),
 "validar":n("Validar movimiento","La configuración del caso establece un inconveniente inicial.",[],c("No: pago con inconvenientes","avisar",payment="Inválido")),
 "avisar":n("Avisar sobre pago inválido","Se representa la comunicación al cliente.",[],c("Notificar","acepta")),
 "acepta":n("¿Cliente acepta realizar nuevamente el pago?","Selecciona la alternativa que quieres recorrer.",[],c("Sí: rehacer el pago","rehacer"),c("No: cancelar reserva","CANCEL",reservation="Cancelada")),
 "rehacer":n("Rehacer pago","Nuevo pago simulado, sin transacción real.",[],c("Realizar nuevo pago","revalidar",payment="Reintento realizado")),
 "revalidar":n("Validar movimiento · nuevo intento","Esta vez el pago ficticio puede considerarse conforme.",[],c("Sí: pago válido","contabilizar",payment="Válido"),c("No: nuevo inconveniente","avisar",payment="Inválido")),
 "contabilizar":n("Contabilizar ingreso","Registro ficticio del ingreso.",["2.5"],c("Registrar y finalizar","FIN"))}},
"R04": {"module":"Reserva","name":"Cambio de unidad","goal":"Representar la autorización del cambio y las actualizaciones de unidades.","start":"solicitar","rules":["2.3","2.6","7.4"],"nodes":{
 "solicitar":n("Solicitar cambio de unidad","El comprador solicita cambiar la unidad reservada.",[],c("Enviar solicitud","autorizar")),
 "autorizar":n("Autorizar cambio de unidad","El escenario contempla autorización favorable.",["2.3"],c("Autorizar cambio","liberar")),
 "liberar":n("Cambiar estado de unidad a disponible","Se representa la modificación de la unidad original.",["2.3","2.6"],c("Liberar unidad anterior","seleccionar",unit_status="Anterior: disponible")),
 "seleccionar":n("Seleccionar nueva unidad","Nueva unidad ficticia A-406.",[],c("Seleccionar unidad A-406","reservar",unit="A-406")),
 "reservar":n("Reservar nueva unidad","Registrar actualización simulada.",["2.3","7.4"],c("Reservar y finalizar","FIN",unit_status="Nueva unidad: reservada"))}},
"C01": {"module":"Cesión","name":"Cesión con documento conforme","goal":"Recorrer el registro ficticio de cesión y las rutas del comprador nuevo o existente.","start":"recepcion","rules":["6.1","6.2","6.3"],"nodes":{
 "recepcion":n("Recepcionar información de la cesión","Recepción de la decisión de cesión.",[],c("Recepcionar caso","antecedentes")),
 "antecedentes":n("Solicitar antecedentes del nuevo comprador","Solicitar datos ficticios del cesionario.",[],c("Solicitar y recibir datos","acuerdos")),
 "acuerdos":n("Establecer acuerdos de la cesión","Se registran los acuerdos comerciales ficticios.",["6.1"],c("Registrar acuerdos","redactar")),
 "redactar":n("Redactar documento de cesión","Documento de prueba preparado.",["6.1"],c("Redactar documento","validar",document="Redactado")),
 "validar":n("¿Documento correcto?","El documento ficticio cumple la revisión.",["6.1"],c("Sí: continuar","firma")),
 "firma":n("Firmar documento","Se representa la firma documental.",["6.3"],c("Firmar","registrar",document="Firmado")),
 "registrar":n("Registrar documento","Registro simulado del documento.",["6.3"],c("Registrar","cliente")),
 "cliente":n("¿Cliente nuevo con registro previo?","Selecciona la situación del cesionario.",["6.2"],c("Sí: actualizar registros","actualizar"),c("No: crear registros","crear")),
 "actualizar":n("Actualizar cuenta corriente y acuerdo comercial","Actualización simulada para cliente existente.",["6.2"],c("Actualizar y finalizar","FIN",buyer="Registro existente actualizado")),
 "crear":n("Crear cuenta corriente y acuerdo comercial","Alta simulada para cliente nuevo.",["6.2"],c("Crear y finalizar","FIN",buyer="Registro nuevo creado"))}},
"C02": {"module":"Cesión","name":"Cesión con documento incorrecto","goal":"Representar devolución, corrección y revalidación del documento de cesión.","start":"redactar","rules":["6.1","6.3"],"nodes":{
 "redactar":n("Redactar documento de cesión","Se prepara un documento con inconsistencia ficticia.",["6.1"],c("Redactar","validar",document="Con error")),
 "validar":n("¿Documento correcto?","La primera revisión no es conforme.",["6.1"],c("No: corregir","corregir")),
 "corregir":n("Corregir documento","Se modifica el dato ficticio incorrecto.",["6.1"],c("Corregir documento","revalidar",document="Corregido")),
 "revalidar":n("¿Documento correcto? · nueva revisión","Revisar el documento corregido.",["6.1"],c("Sí: continuar","firma"),c("No: devolver para corrección","corregir")),
 "firma":n("Firmar documento","Firma simulada.",["6.3"],c("Firmar","registrar",document="Firmado")),
 "registrar":n("Registrar documento","Registro ficticio.",["6.3"],c("Registrar y finalizar","FIN"))}}
}

# Fichas documentadas a partir del PDF «NUMANCIA - Modelos To-Be (BPMN)».
# Los textos descriptivos son síntesis interpretativas; los nombres de tareas/decisiones
# se basan en las etiquetas de los diagramas. No sustituyen la validación del mandante.
PROCESS_INFO = {
"Captación y seguimiento": {
 "objective":"Captar, registrar y dar seguimiento al interés del cliente hasta disponer de antecedentes para una eventual reserva.",
 "inputs":["Interés o contacto del cliente", "Antecedentes del cliente", "Preferencias y unidades de interés"],
 "outputs":["Datos de reserva enviados", "Reporte del cliente", "Visita realizada o seguimiento continuado"],
 "activities":["Tomar datos del cliente", "Registrar cliente en PlanOK", "Filtrar perfil del cliente", "Realizar cotización", "Mostrar unidades disponibles / pilotos", "Programar visita a Centro de Ventas", "Recordar visita al cliente", "Realizar visita", "Seleccionar unidades", "Generar reporte con datos de cliente y unidad de interés", "Enviar datos de la reserva"],
 "decisions":["¿Cliente llega vía presencial?", "¿Cliente califica?", "¿Cliente sigue interesado?", "¿Cliente asiste?", "¿Cliente desea visitar unidad?", "¿Cliente quiere cambiar unidad?"],
 "rules":["1.1", "1.2", "1.3", "7.1", "7.4"],
 "critical":["Identificación del cliente sin registros duplicados", "Actualización del interés y de las unidades seleccionadas", "Entrega de antecedentes completos a Reserva"],
 "links":"Recorrido habitual hacia Reserva cuando se obtienen y envían sus antecedentes; incluye rutas de seguimiento o término del interés.",
 "page":2},
"Reserva": {
 "objective":"Gestionar y formalizar una reserva, controlando pago, registro, estado de la unidad, documentación y cambios cuando corresponda.",
 "inputs":["Datos de reserva", "Antecedentes del cliente y unidad", "Comprobante de pago"],
 "outputs":["Reserva formalizada y firmada", "Documento de reserva y cierre de negocios", "Reserva cancelada o nuevos datos de reserva según la ruta"],
 "activities":["Recepcionar comprobante de pago", "Validar movimiento", "Avisar sobre pago inválido", "Rehacer pago", "Contabilizar ingreso", "Crear cuenta corriente", "Crear acuerdo comercial", "Crear reserva", "Corregir errores en reserva", "Cambiar estado de unidad a reservada", "Solicitar cambio de unidad", "Autorizar cambio de unidad", "Reservar nueva unidad", "Generar documento de reserva", "Firmar documento de reserva y cierre de negocios"],
 "decisions":["¿Pago sin inconvenientes?", "¿Cliente acepta realizar nuevamente el pago?", "¿Primera compra del cliente?", "¿Reserva validada?", "¿Cliente desea cambiar unidad?"],
 "rules":["2.1", "2.2", "2.3", "2.4", "2.5", "2.6", "2.7", "7.1", "7.4"],
 "critical":["Correspondencia de la unidad y sus roles en los registros", "Validación de pago y corrección de errores", "Estado actualizado de la unidad y firma del documento"],
 "links":"Recibe antecedentes desde Captación; la operación puede continuar hacia Promesa o terminar/cambiar según condiciones del modelo general.",
 "page":3},
"Promesa de compraventa": {
 "objective":"Formalizar la promesa de compraventa mediante verificación del pie, revisión de antecedentes, validación documental y firmas.",
 "inputs":["Antecedentes de reserva", "Pago del pie", "Documentos de promesa de compraventa"],
 "outputs":["Promesa firmada y documentada", "Copia de PCV entregada", "Estado de unidad actualizado a promesado"],
 "activities":["Recepcionar documentos de PCV", "Cambiar estado de la unidad a Acordado", "Verificar monto pago del pie", "Notificar monto incorrecto", "Generar documento de promesa compra y venta", "Validar documento de promesa compra y venta", "Corregir documento de promesa compra-venta", "Consultar financiamiento del cliente", "Revisar antecedentes de reserva", "Firmar PCV", "Enviar documentos a Notaría", "Recibir PCV firmada", "Enviar copia de PCV al cliente", "Cambiar estado de unidad a Promesado"],
 "decisions":["¿Monto del pie correcto?", "¿Documento de promesa correcto?", "¿Cliente firma?", "¿Cliente cede?"],
 "rules":["5.1", "5.2", "5.3", "7.1", "7.2", "7.4"],
 "critical":["Monto del pie coherente con el acuerdo", "Documento de promesa validado antes de firmar", "Cambios de estado y antecedentes transmitidos a la siguiente etapa"],
 "links":"Continúa después de Reserva y antecede a Escrituración; el modelo contempla alternativas hacia Cesión o Resciliación/Desistimiento.",
 "page":6},
"Escrituración": {
 "objective":"Gestionar la escrituración, coordinando antecedentes jurídicos y financieros, borradores, reparos, firmas y cierre de la operación.",
 "inputs":["PCV firmada", "Antecedentes de financiamiento", "Títulos, documentos y pagos asociados"],
 "outputs":["Escritura firmada", "Facturación y documentación asociada", "Cierre de escrituración o cancelación según la ruta"],
 "activities":["Recepcionar PCV", "Preparar títulos de proyecto", "Enviar títulos al banco del cliente", "Informar inicio de proceso de Escrituración", "Confirmar condiciones de compra", "Redactar borrador de escritura", "Revisar borrador de escritura", "Solicitar corrección del borrador", "Subsanar reparos", "Gestionar firmas de bancos", "Firmar escritura", "Solicitar emisión de factura de venta", "Emitir factura de venta", "Enviar escritura al cliente", "Ingresar fecha de firma de escritura"],
 "decisions":["¿Cliente desea continuar operación?", "¿Cliente desiste?", "¿Cliente desea ceder?", "¿Borrador correcto?", "¿Saldo pendiente?", "¿Posibles reparos?", "¿Cliente con crédito?"],
 "rules":["4.1", "4.2", "4.3", "7.1", "7.2", "7.3", "7.4"],
 "critical":["Antecedentes validados antes de elaborar escritura", "Correcciones documentales trazables", "Coordinación de pagos, firmas y estados"],
 "links":"Sigue a Promesa y puede conectar con Entrega; contempla rutas de Cesión y Resciliación/Desistimiento.",
 "page":5},
"Resciliación y desistimiento": {
 "objective":"Gestionar el término de una operación, su formalización documental, efectos económicos y eventual liberación de la unidad.",
 "inputs":["Decisión de desistimiento", "Antecedentes de la operación", "Información económica y contractual"],
 "outputs":["Documento de resciliación", "Egreso contabilizado cuando corresponde", "Unidad liberada y áreas notificadas"],
 "activities":["Informar desistimiento oficial", "Recepcionar información del caso", "Traspasar información a Escrituración", "Establecer multas", "Redactar documento de resciliación", "Revisar documento de resciliación", "Firmar documento de resciliación", "Verificar documento de resciliación", "Enviar documento para contabilizar egreso", "Contabilizar movimiento", "Liberar unidad", "Notificar unidad liberada"],
 "decisions":["¿Cliente firma?", "¿Implica movimiento de dinero?"],
 "rules":["2.3", "3.1", "3.2", "7.1", "7.3", "7.4"],
 "critical":["Respaldo de la resciliación", "Determinar si corresponde movimiento de dinero", "No liberar unidades antes de cumplir las condiciones pertinentes"],
 "links":"Se activa desde distintas decisiones del macroproceso y conduce al cierre o liberación según los antecedentes del caso.",
 "page":4},
"Cesión": {
 "objective":"Formalizar la transferencia de una operación hacia un nuevo comprador, validando antecedentes, acuerdos, documento de cesión y actualización de registros.",
 "inputs":["Decisión de cesión", "Antecedentes del comprador nuevo", "Antecedentes y acuerdos de la operación original"],
 "outputs":["Documento de cesión firmado y registrado", "Antecedentes del nuevo comprador registrados o actualizados", "Cesión finalizada"],
 "activities":["Informar cesión", "Recepcionar información de la cesión", "Solicitar antecedentes del nuevo comprador", "Recepcionar datos de nuevo comprador", "Recepcionar caso", "Documentar caso", "Establecer acuerdos de la cesión", "Redactar documento de cesión", "Enviar documento de cesión", "Validar documento de cesión", "Corregir documento", "Firmar documento", "Registrar documento", "Crear cliente en sistema", "Crear cuenta corriente de cliente nuevo", "Actualizar cuenta corriente", "Crear acuerdo comercial con cliente nuevo"],
 "decisions":["¿Documento correcto?", "¿Cliente confirma datos de documento?", "¿Cliente nuevo con registro previo?"],
 "rules":["6.1", "6.2", "6.3", "7.1", "7.4"],
 "critical":["Identidad y antecedentes del cesionario", "Consistencia del documento de cesión y firmas", "Correspondencia de registros comerciales del nuevo comprador"],
 "links":"Proceso confirmado con el mandante; aparece como ruta alternativa desde decisiones del macroproceso general, Promesa y Escrituración.",
 "page":7},
"Entrega": {
 "objective":"Representar la etapa de entrega de la unidad identificada en el macroproceso general.",
 "inputs":["Operación que ha avanzado desde Escrituración", "Documentación que corresponda según procedimientos de Numancia (por validar)"],
 "outputs":["Unidad entregada (salida del macroproceso general)"],
 "activities":[], "decisions":[], "rules":[],
 "critical":["Confirmar antecedentes de entrada y cierre con el mandante"],
 "links":"En la página 1 figura como Proceso de Entrega conectado con Escrituración. No se adjunta un BPMN detallado independiente de esta etapa.",
 "page":1},
}

def process_sheet(name):
    meta=PROCESS_INFO[name]
    st.markdown(f'<div class="hero"><h2>{html(name)}</h2><p>Ficha del modelo To-Be · Referencia BPMN: página {meta["page"]}</p></div>',unsafe_allow_html=True)
    st.info("Descripción de apoyo basada en los diagramas. Los puntos críticos y la relación con reglas son propuestas de trazabilidad sujetas a cotejo; no constituyen validación operativa.")
    tabs=st.tabs(["Descripción", "Actividades", "Controles y reglas", "BPMN original", "Pruebas disponibles"])
    with tabs[0]:
        st.subheader("Objetivo")
        st.write(meta["objective"])
        c1,c2=st.columns(2,gap="medium")
        with c1:
            with st.container(border=True):
                st.markdown("#### 📥 Entradas")
                for x in meta["inputs"]:st.markdown("• "+x)
        with c2:
            with st.container(border=True):
                st.markdown("#### 📤 Salidas")
                for x in meta["outputs"]:st.markdown("• "+x)
        with st.container(border=True):
            st.markdown("#### 🔗 Relación con otros procesos")
            st.write(meta["links"])
    with tabs[1]:
        st.subheader("Actividades identificadas en el BPMN")
        if meta["activities"]:
            st.caption("Relación de actividades visibles en el diagrama, no necesariamente un único orden lineal: existen caminos paralelos y decisiones.")
            for i,a in enumerate(meta["activities"],1):
                st.markdown(f'<div class="activity-tile"><span class="activity-number">{i:02}</span><span>{html(a)}</span></div>',unsafe_allow_html=True)
        else:st.warning("El documento solo representa Entrega en el macroproceso general; falta el diagrama de detalle.")
    with tabs[2]:
        st.subheader("Decisiones y controles del proceso")
        if meta["decisions"]:
            for d in meta["decisions"]:st.markdown(f'<div class="decision-tile">◇ {html(d)}</div>',unsafe_allow_html=True)
        else:st.caption("Sin decisiones detalladas en el diagrama disponible.")
        st.markdown("#### Puntos críticos de información · propuesta de análisis")
        for x in meta["critical"]:st.markdown("• "+x)
        st.markdown("#### Reglas relacionadas · trazabilidad preliminar")
        if meta["rules"]:st.markdown(" ".join(f'<span class="rule-pill">{html(r)}</span>' for r in meta["rules"]),unsafe_allow_html=True)
        else:st.caption("Requiere definición con datos adicionales.")
        st.caption("Las asociaciones de reglas no equivalen a controles implementados automáticamente.")
    with tabs[3]:
        st.subheader("BPMN vectorial interactivo — fuente: PDF original")
        st.caption("Acerca, desplaza y selecciona actividades, eventos o compuertas. No es una imagen estática.")
        st.caption("Reproducción vectorial directa del PDF. Carriles, participantes externos, datos y flechas permanecen exactamente como están en la fuente. Haz zoom, arrastra o selecciona textos.")
        try:
            mostrar_bpmn_pdf(meta["page"], height=740)
        except Exception as exc:
            st.error(f"No se pudo mostrar el diagrama del PDF: {exc}")
    with tabs[4]:
        matches=[(sid,s) for sid,s in SCENARIOS.items() if s["module"]==name]
        if matches:
            for sid,s in matches:
                with st.container(border=True):
                    st.markdown(f"**{sid} · {s['name']}**")
                    st.write(s["goal"])
                    st.caption("Reglas vinculadas: "+", ".join(s["rules"]))
                    if st.button("Preparar escenario",key="prepare_"+sid):
                        st.session_state.prefill_sid=sid
                        st.success("Escenario seleccionado. Abre ‘Simulación’ en el menú lateral.")
        else:st.warning("Aún no hay escenarios interactivos configurados para este módulo.")

CRITERIA = ["Secuencia lógica", "Manejo de excepciones", "Puntos de control", "Responsabilidades", "Reglas de consistencia", "Coordinación entre áreas", "Comprensión del procedimiento", "Factibilidad operativa"]


def initialize():
    defaults={"sid":None,"current":None,"trail":[],"history":[],"runs":[],"evaluations":[],"status":{},"session_completed":False,"last_id":None}
    for k,v in defaults.items():
        if k not in st.session_state: st.session_state[k]=v
    # Compatibilidad con registros guardados en st.session_state por versiones anteriores.
    # No se eliminan las ejecuciones históricas al actualizar la aplicación.
    normalized = []
    for i, old in enumerate(st.session_state.runs, start=1):
        if not isinstance(old, dict):
            continue
        run = old.copy()
        run.setdefault("ID de ejecución", i)
        run.setdefault("Escenario", run.get("scenario", run.get("sid", "Sin identificar")))
        run.setdefault("Subproceso", SCENARIOS.get(run["Escenario"], {}).get("module", "No especificado"))
        run.setdefault("Resultado", run.get("resultado", "Registro anterior"))
        normalized.append(run)
    st.session_state.runs = normalized

def start(sid):
    st.session_state.sid=sid
    st.session_state.current=SCENARIOS[sid]["start"]
    st.session_state.trail=[st.session_state.current]
    st.session_state.history=[]
    st.session_state.status={"operation":"OP-002" if sid.startswith("R") else "CS-001", "client":"Cliente ficticio A", "unit":"A-405", "unit_status":"Disponible" if sid!="R04" else "Reservada", "payment":"Pendiente", "reservation":"Pendiente", "document":"Pendiente", "buyer":"Sin definir"}
    st.session_state.session_completed=False
    st.session_state.last_id=None

def advance(choice):
    sid=st.session_state.sid
    current=st.session_state.current
    node=SCENARIOS[sid]["nodes"][current]
    for field,value in choice["effects"].items():st.session_state.status[field]=value
    st.session_state.history.append({"Fecha y hora":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),"Escenario":sid,"Actividad":node["label"],"Decisión / acción":choice["text"],"Reglas":", ".join(node["rules"]),"Destino":choice["target"]})
    nxt=choice["target"]
    if nxt in ("FIN","CANCEL"):
        st.session_state.current=None
        st.session_state.session_completed=True
        record={"ID de ejecución":len(st.session_state.runs)+1,"Fecha y hora":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),"Escenario":sid,"Subproceso":SCENARIOS[sid]["module"],"Resultado":"Completado" if nxt=="FIN" else "Cancelado", "Acciones":len(st.session_state.history),"Ruta":" → ".join(e["Actividad"] for e in st.session_state.history),"Historial":list(st.session_state.history)}
        st.session_state.runs.append(record)
        st.session_state.last_id=record["ID de ejecución"]
    else:
        st.session_state.current=nxt
        st.session_state.trail.append(nxt)
    st.rerun()

def html(s): return escape(str(s))

def badge(value):return f'<span class="chip">{html(value)}</span>'

def panel_track(spec):
    nodes=spec["nodes"]
    trail=st.session_state.trail
    current=st.session_state.current
    used=set(trail)
    elements=[]
    for i,key in enumerate(trail):
        node=nodes[key]; cls="active" if key==current else "done"
        prefix="▶" if key==current else "✓"
        elements.append(f'<div class="tracknode {cls}">{prefix} {html(node["label"])}</div>')
        if i<len(trail)-1:elements.append('<span class="arrow">→</span>')
    if current and nodes[current]["choices"]:
        elements.append('<span class="arrow">→</span>')
        targets=[x["target"] for x in nodes[current]["choices"]]
        for t in targets[:3]:
            label=nodes[t]["label"] if t in nodes else ("Fin" if t=="FIN" else "Cancelación")
            elements.append(f'<div class="tracknode">{html(label)}</div>')
    st.markdown('<div class="sectionbox"><div class="kicker">Mapa del recorrido ejecutado y próximos destinos</div><div class="track">'+''.join(elements)+'</div></div>',unsafe_allow_html=True)

def csv_button(rows,filename):
    if not rows:return
    df=pd.DataFrame(rows)
    st.download_button("⬇️ Exportar CSV",df.to_csv(index=False).encode("utf-8-sig"),file_name=filename,mime="text/csv")

initialize()
with st.sidebar:
    st.markdown("## 🏢 NUMANCIA")
    st.caption("Validación funcional · Modelo To-Be")
    section=st.radio("Navegación",["Inicio","Macroproceso","Simulación","Modo Evaluador","Resultados","Reglas de consistencia","Auditoría BPMN","Comparador As-Is/To-Be","Alcance y referencias"],label_visibility="collapsed")
    st.divider()
    st.info("🧪 Prototipo académico · Datos ficticios")
    st.caption("Sin conexión a PlanOK ni UnySoft. No ejecuta BPMN automáticamente.")

if section=="Inicio":
    st.markdown('<div class="hero"><h2>Simulador visual del modelo To-Be</h2><p>Inmobiliaria Numancia · Recorridos, decisiones, validaciones y evidencia de prueba</p></div>',unsafe_allow_html=True)
    a,b,c,d=st.columns(4)
    a.metric("Procesos identificados",len(MODULES))
    b.metric("Escenarios interactivos",len(SCENARIOS))
    c.metric("Ejecuciones registradas",len(st.session_state.runs))
    d.metric("Evaluaciones registradas",len(st.session_state.evaluations))
    st.subheader("¿Qué se puede probar?")
    q1,q2,q3=st.columns(3)
    with q1:
        with st.container(border=True):st.markdown("### 🧭 Recorrer el proceso");st.write("Ver actividades, caminos alternativos y el punto actual de una operación ficticia.")
    with q2:
        with st.container(border=True):st.markdown("### 🔎 Ver validaciones");st.write("Representar errores, decisiones, corrección y revalidación según guiones de prueba.")
    with q3:
        with st.container(border=True):st.markdown("### 📋 Evaluar el diseño");st.write("Documentar resultados y observaciones separando recorrido de validación funcional.")
    st.warning("Piloto: recorridos simplificados de Reserva y Cesión. Deben cotejarse las transiciones con los BPMN originales antes de usarlos como evidencia formal.")

elif section=="Macroproceso":
    st.title("Explorador de procesos To-Be")
    st.caption("Siete fichas basadas en los diagramas proporcionados. Cesión forma parte del alcance acordado con el mandante.")
    names=[x[0] for x in MODULES]
    default=names.index(st.session_state.get("process_name","Reserva")) if st.session_state.get("process_name","Reserva") in names else 1
    picked=st.selectbox("Selecciona un proceso o subproceso",names,index=default)
    st.session_state.process_name=picked
    process_sheet(picked)

elif section=="Simulación":
    st.markdown('<div class="hero"><h2>Simulación interactiva</h2><p>Observa el proceso, selecciona decisiones y revisa los antecedentes de cada operación</p></div>',unsafe_allow_html=True)
    sid=st.selectbox("Seleccionar escenario",list(SCENARIOS),index=list(SCENARIOS).index(st.session_state.get("prefill_sid","R01")) if st.session_state.get("prefill_sid","R01") in SCENARIOS else 0,format_func=lambda x:f"{x} · {SCENARIOS[x]['module']} · {SCENARIOS[x]['name']}")
    spec=SCENARIOS[sid]
    st.write(f"**Objetivo:** {spec['goal']}")
    st.caption("Reglas relacionadas: "+", ".join(spec["rules"]))
    if st.button("▶️ Iniciar / reiniciar escenario",type="primary",key="start_test"):
        start(sid); st.rerun()
    if st.session_state.sid!=sid:
        st.info("Presiona «Iniciar / reiniciar escenario» para visualizar el recorrido.")
    else:
        finished=st.session_state.session_completed
        current=st.session_state.current
        count=len(st.session_state.history)
        m1,m2,m3,m4=st.columns(4)
        m1.metric("Operación",st.session_state.status["operation"])
        m2.metric("Pasos ejecutados",count)
        m3.metric("Estado", "Finalizado" if finished else "En ejecución")
        m4.metric("Módulo",spec["module"])
        st.progress(1.0 if finished else min(0.92,count/max(1,len(spec["nodes"]))))
        # Vista de trabajo en paralelo: el visor nunca queda debajo de los controles.
        st.markdown("### 🖥️ Mesa de simulación · BPMN y controles simultáneos")
        diagram_col, controls_col = st.columns([2.35, 1], gap="medium")
        with diagram_col:
            with st.container(border=True):
                st.markdown("**🗺️ BPMN original · referencia PDF**")
                st.caption("El enfoque utiliza coincidencias textuales del PDF; no modifica el modelo ni supone conexiones no verificadas.")
                page=PROCESS_XML.get(spec['module'])
                labels_visit=[spec['nodes'][k]['label'] for k in st.session_state.trail if k in spec['nodes']]
                active=[spec['nodes'][current]['label']] if current in spec['nodes'] else []
                view_mode=st.radio("Vista del diagrama",["Seguimiento automático","Exploración libre","Vista contextual"],horizontal=True,key="sim_bpmn_mode",label_visibility="collapsed")
                mode_map={"Seguimiento automático":"auto","Exploración libre":"manual","Vista contextual":"context"}
                if page:
                    try:
                        mostrar_bpmn_pdf(page,height=740,active_labels=active,
                            visited_labels=labels_visit[:-1] if not finished else labels_visit,
                            focus_label=(active[0] if active else labels_visit[-1] if labels_visit else None),
                            initial_mode=mode_map[view_mode])
                    except Exception as exc:
                        st.error("No pudo mostrarse el BPMN PDF: "+str(exc))
                else:
                    st.warning("No hay una página de PDF asociada a este escenario.")
                st.caption("Dentro del visor puedes acercar, arrastrar y volver al proceso completo.")
        with controls_col:
            with st.container(border=True):
                st.markdown("#### ⚙️ Actividad actual")
                if finished:
                    outcome=st.session_state.runs[-1].get("Resultado","Registro anterior") if st.session_state.runs else "Registro anterior"
                    st.success("Recorrido completado" if outcome=="Completado" else "Reserva cancelada")
                    st.caption(f"Ejecución N.º {st.session_state.last_id} disponible en Modo Evaluador.")
                else:
                    node=spec['nodes'][current]
                    st.markdown(f"<span class='kicker'>Actividad / decisión</span><h3>{html(node['label'])}</h3>",unsafe_allow_html=True)
                    st.write(node['help'])
                    if node['rules']:
                        st.info("Reglas vinculadas: "+", ".join(node['rules']))
                    if len(node['choices'])>1:
                        st.warning("Selecciona la ruta que deseas probar.")
                    for i,choice in enumerate(node['choices']):
                        if st.button("➡️ "+choice['text'],key=f"choice_{sid}_{current}_{i}",type="primary" if i==0 else "secondary",use_container_width=True):
                            advance(choice)
                st.caption("Prueba con datos ficticios; no se consultan sistemas reales.")
            tab_route,tab_data,tab_events=st.tabs(["🧭 Ruta","🗂️ Datos","🕘 Eventos"])
            with tab_route:
                labels_map={k:v['label'] for k,v in spec['nodes'].items()}
                for i,key in enumerate(st.session_state.trail):
                    cls="current" if key==current else "done"
                    sign="🔵" if key==current else "✅"
                    st.markdown(f'<div class="node {cls}"><b>{sign} {i+1}. {html(labels_map[key])}</b></div>',unsafe_allow_html=True)
                if finished:st.success("🏁 Recorrido terminado")
            with tab_data:
                for title,key in [("Operación","operation"),("Cliente","client"),("Unidad","unit"),("Estado de unidad","unit_status"),("Pago","payment"),("Reserva","reservation"),("Documento","document"),("Cesionario","buyer")]:
                    st.markdown(f'<div class="small">{html(title)}</div><div class="darktext"><b>{html(st.session_state.status[key])}</b></div>',unsafe_allow_html=True)
            with tab_events:
                if st.session_state.history:
                    for e in st.session_state.history[-5:][::-1]:
                        st.markdown(f'<div class="timeline"><b>{html(e["Actividad"])}</b><div class="small">{html(e["Decisión / acción"])}</div></div>',unsafe_allow_html=True)
                else:
                    st.caption("Todavía no hay eventos ejecutados.")
        with st.expander("🧭 Ver mapa del recorrido completo",expanded=False):
            panel_track(spec)
        with st.expander("📜 Historial completo de la prueba",expanded=finished):
            if st.session_state.history:
                st.dataframe(pd.DataFrame(st.session_state.history),hide_index=True,use_container_width=True)
                csv_button(st.session_state.history,f"numancia_eventos_{sid}.csv")
            else:st.write("Aún no hay actividades ejecutadas.")

elif section=="Reglas de consistencia":
    rules_view()

elif section=="Auditoría BPMN":
    coverage_view(SCENARIOS)

elif section=="Comparador As-Is/To-Be":
    comparador_visual_view()

elif section=="Modo Evaluador":
    st.title("📋 Modo Evaluador")
    st.write("El evaluador registra manualmente el cumplimiento. Completar el recorrido no equivale a validar el diseño.")
    st.info("Antes de aprobar un escenario, comprueba su cobertura en Auditoría BPMN y su coherencia documental con el modelo original.")
    if not st.session_state.runs:
        st.info("Primero ejecuta un escenario desde Simulación para generar una ficha de evaluación.")
    else:
        options=list(range(len(st.session_state.runs)))
        run_i=st.selectbox("Ejecución a evaluar",options,index=len(options)-1,format_func=lambda i:f"#{st.session_state.runs[i].get('ID de ejecución', i+1)} · {st.session_state.runs[i].get('Escenario', 'Sin identificar')} · {st.session_state.runs[i].get('Resultado', 'Registro anterior')}")
        record=st.session_state.runs[run_i]
        st.markdown(f"**Escenario:** {record['Escenario']}  |  **Subproceso:** {record['Subproceso']}  |  **Resultado del recorrido:** {record['Resultado']}")
        st.caption("Referencia: "+", ".join(SCENARIOS.get(record["Escenario"], {}).get("rules", [])) if record["Escenario"] in SCENARIOS else "Referencia del escenario anterior no disponible en esta versión.")
        # Enfoque desde el historial de ejecución, sin atribuir semántica BPMN inexistente.
        with st.expander("🔎 Revisar actividad en el BPMN original", expanded=False):
            hist=record.get("Historial", [])
            if isinstance(hist,str):
                try: hist=json.loads(hist)
                except (ValueError,TypeError): hist=[]
            if isinstance(hist,list) and hist:
                options_hist=[(i,e) for i,e in enumerate(hist) if isinstance(e,dict)]
                if options_hist:
                    selected_i=st.selectbox("Evento del recorrido",range(len(options_hist)),format_func=lambda i: str(options_hist[i][1].get("Actividad","Actividad sin etiqueta")),key="eval_hist_focus")
                    activity=options_hist[selected_i][1].get("Actividad","")
                    pg=PROCESS_XML.get(record.get("Subproceso"))
                    if pg:
                        mostrar_bpmn_pdf(pg,height=570,focus_label=activity,active_labels=[activity],initial_mode="context")
                    else:st.info("No hay una página de referencia asignada a este subproceso.")
            else:
                st.info("Esta ejecución no tiene un historial de actividades guardado. El visor necesita esas etiquetas para enfocar un paso.")
        with st.form("evaluation_form"):
            evaluator=st.text_input("Identificación del evaluador (opcional)")
            ratings={}
            for item in CRITERIA:
                ratings[item]=st.selectbox(item,["No evaluado","Cumple","Cumple parcialmente","No cumple","No evaluable"],key="rating_"+item)
            obs=st.text_area("Observaciones y ajustes propuestos",height=120)
            submitted=st.form_submit_button("💾 Guardar evaluación",type="primary")
        if submitted:
            entry={"Fecha y hora":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),"ID de ejecución":record["ID de ejecución"],"Escenario":record["Escenario"],"Evaluador":evaluator,"Observaciones":obs,**ratings}
            st.session_state.evaluations.append(entry)
            st.success("Evaluación registrada en la sesión actual.")
        if st.session_state.evaluations:csv_button(st.session_state.evaluations,"numancia_evaluaciones.csv")

elif section=="Resultados":
    st.title("📊 Resultados de pruebas")
    a,b,c=st.columns(3)
    a.metric("Ejecuciones",len(st.session_state.runs))
    b.metric("Evaluaciones",len(st.session_state.evaluations))
    c.metric("Escenarios disponibles",len(SCENARIOS))
    if st.session_state.runs:
        st.subheader("Ejecuciones")
        st.dataframe(pd.DataFrame(st.session_state.runs),hide_index=True,use_container_width=True)
        csv_button(st.session_state.runs,"numancia_ejecuciones.csv")
        counts=pd.DataFrame(st.session_state.runs).groupby("Escenario").size()
        st.bar_chart(counts)
    else:st.info("No se han ejecutado escenarios en esta sesión.")
    if st.session_state.evaluations:
        st.subheader("Evaluaciones registradas")
        st.dataframe(pd.DataFrame(st.session_state.evaluations),hide_index=True,use_container_width=True)
        csv_button(st.session_state.evaluations,"numancia_evaluaciones.csv")
    st.caption("Los datos se almacenan en la sesión de Streamlit. Descárgalos en CSV antes de cerrarla; no son registros persistentes.")

else:
    st.title("📚 Alcance y referencias")
    st.markdown("**Fuente conceptual:** NUMANCIA — Modelos To-Be (BPMN), páginas 1 a 7; matriz de reglas de consistencia del proyecto.")
    st.markdown("**Alcance:** representación visual e interactiva de seis escenarios piloto de Reserva y Cesión. Los otros módulos se encuentran identificados y deben desarrollarse después de contrastar los flujos exactos.")
    st.warning("El prototipo **no importa ni ejecuta archivos BPMN**, no tiene conexión a PlanOK ni UnySoft y no demuestra mejoras reales en tiempos, errores o productividad. Los recorridos son guiones interpretativos para pruebas de escritorio.")
    st.write("**Mapeo de páginas:** Captación (2), Reserva (3), Resciliación y desistimiento (4), Escrituración (5), Promesa (6), Cesión (7), Macroproceso y Entrega (1).")

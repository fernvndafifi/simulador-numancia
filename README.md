# 🏢 NUMANCIA | Simulador del Macroproceso Comercial

### Prototipo interactivo para el análisis y evaluación del modelo To-Be

Herramienta desarrollada en **Python y Streamlit** como parte de un proyecto académico de Ingeniería Civil Industrial, orientado al análisis y evaluación del rediseño del macroproceso comercial de **Inmobiliaria Numancia S.A.**

El simulador permite visualizar los procesos comerciales, recorrer escenarios ficticios, representar decisiones y validaciones, y contrastar los modelos de la situación actual (*As-Is*) con los modelos propuestos (*To-Be*).

> **Importante:** Esta herramienta corresponde a un prototipo académico de evaluación funcional. No constituye una implementación operacional ni se conecta con los sistemas reales de la inmobiliaria.

---

## 🎯 Objetivo del proyecto

Apoyar la evaluación del modelo To-Be del macroproceso comercial mediante una herramienta interactiva que facilite la comprensión de los procesos, la identificación de puntos de control y el análisis de las mejoras propuestas respecto de la situación actual.

El desarrollo se enmarca en una propuesta de mejora de la consistencia y trazabilidad de la información utilizada por las áreas participantes del macroproceso.

## ⚙️ Funcionalidades

| Módulo | Descripción |
|---|---|
| **Macroproceso** | Visualización de los siete modelos To-Be provenientes del PDF original. |
| **Simulación** | Ejecución de escenarios ficticios con actividades, decisiones, rutas alternativas y correcciones. |
| **Visor BPMN** | Exploración de diagramas mediante zoom, desplazamiento y enfoque de actividades. |
| **Reglas de consistencia** | Pruebas de validación mediante antecedentes ficticios. |
| **Modo Evaluador** | Registro de observaciones y evaluación de los recorridos simulados. |
| **Resultados** | Consulta de los registros generados durante las pruebas. |
| **Comparador As-Is / To-Be** | Visualización paralela de los modelos actuales y propuestos, con registro editable de diferencias. |
| **Auditoría BPMN** | Revisión preliminar de correspondencia entre los escenarios de prueba y los elementos identificados en los modelos exportados. |

### 🔎 Comparador As-Is / To-Be

El comparador permite observar ambos modelos simultáneamente, con controles independientes de zoom y desplazamiento.

También incorpora una matriz editable para documentar diferencias entre la situación actual y la propuesta, incluyendo actividades modificadas, controles incorporados, brechas abordadas y observaciones de evaluación.

La información registrada puede descargarse en formato CSV para su posterior análisis.

---

## 🧩 Modelos considerados

El proyecto contempla los siguientes modelos To-Be:

1. Macroproceso comercial.
2. Captación y seguimiento del cliente.
3. Reserva.
4. Resciliación y desistimiento.
5. Escrituración.
6. Promesa de compraventa.
7. Cesión.

Los escenarios interactivos disponibles corresponden a recorridos simplificados de procesos seleccionados, principalmente Reserva y Cesión. Por tanto, la disponibilidad de un diagrama no implica que todas sus rutas estén implementadas como simulaciones ejecutables.

## 🛠️ Tecnologías utilizadas

- **Python:** lógica de la aplicación y escenarios de simulación.
- **Streamlit:** interfaz web interactiva.
- **PyMuPDF:** procesamiento y visualización de los diagramas contenidos en PDF.
- **HTML, CSS y JavaScript:** elementos visuales, navegación y controles de interacción.
- **Pandas:** organización y presentación de información.

## 🚀 Instalación y ejecución local

**Requisitos:** Python 3.13 y conexión a internet para instalar las dependencias.

**1. Descargar el proyecto**

Clonar el repositorio desde GitHub o descargarlo en formato ZIP.

**2. Instalar dependencias**

Abrir una terminal en la carpeta principal del proyecto y ejecutar:

```bash
py -3.13 -m pip install -r requirements.txt
```

**3. Iniciar la aplicación**

```bash
py -3.13 -m streamlit run app.py
```

Streamlit abrirá la aplicación en el navegador.

En sistemas donde Python esté disponible mediante el comando `python`, se puede ejecutar alternativamente:

```bash
python -m streamlit run app.py
```

## 📁 Estructura general del proyecto

```text
simulador-numancia/
├── app.py
├── bpmn_desde_pdf.py
├── bpmn_interactivo.py
├── comparador_visual.py
├── numancia_extra.py
├── styles.css
├── requirements.txt
├── modelos_to_be_fuente.pdf
├── as_is/
├── assets/
├── bpmn_xml/
└── README.md
```

Las carpetas de recursos deben incorporarse al repositorio cuando sean requeridas por los módulos activos de la aplicación.

## 📚 Fuentes de los modelos

**Situación actual (As-Is):** modelos elaborados en draw.io y sus respectivas representaciones gráficas.

**Situación propuesta (To-Be):** modelos BPMN contenidos en `modelos_to_be_fuente.pdf`.

El PDF constituye la **fuente principal para la representación visual del To-Be**, debido a las inconsistencias detectadas en la exportación original desde Lucidchart.

Los archivos BPMN XML pueden permanecer como recursos auxiliares de funciones heredadas, pero no deben considerarse la referencia definitiva para determinar actividades, carriles, responsables o conexiones del To-Be.

## 📌 Alcance y limitaciones

El simulador está diseñado para apoyar la comprensión y evaluación de la propuesta, por lo que deben considerarse las siguientes restricciones:

- Los datos utilizados en las simulaciones son ficticios.
- No existe integración directa con PlanOK, UnySoft ni otros sistemas operacionales de Numancia.
- Los recorridos ejecutables representan escenarios seleccionados y no la totalidad de las rutas de los modelos BPMN.
- La identificación visual de actividades en el PDF no equivale a una interpretación automática completa de BPMN 2.0.
- Las comparaciones As-Is/To-Be son preliminares y requieren revisión de equivalencia y validación por parte del equipo y de Numancia.
- La herramienta no acredita reducciones de tiempos, errores o retrabajos sin una evaluación empírica posterior.
- Los registros de evaluación y las tablas editables no cuentan con persistencia en una base de datos. Su conservación depende de la sesión y de las exportaciones realizadas.

## 📊 Utilidad del prototipo

La herramienta permite complementar el diseño del modelo To-Be con una instancia de exploración y prueba, facilitando la identificación de decisiones, controles y posibles situaciones que requieren revisión.

Asimismo, el comparador contribuye a relacionar las brechas identificadas durante el diagnóstico As-Is con las modificaciones propuestas para el macroproceso comercial.

Los resultados obtenidos deben interpretarse como **evidencia de pruebas del prototipo**, y no como resultados operacionales reales de Inmobiliaria Numancia.

---

**Proyecto académico — Ingeniería Civil Industrial**
*Prototipo de apoyo a la evaluación del rediseño del macroproceso comercial de Inmobiliaria Numancia S.A.*
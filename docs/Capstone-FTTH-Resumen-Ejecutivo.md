# FTTH QoE Risk Analysis - Resumen Ejecutivo del Proyecto
### Capstone: Google Data Analytics + FCC MBA Data | 2022-09-12 a 2022-10-31 | Metodología v3.0

> Contexto de negocio para lector no técnico. Fuente de verdad de cada regla y valor: `docs/metrics_spec.md` (v1.2.0) y `config.yaml`.

---

### 1. ¿De qué se trata este proyecto? (Para todos)

Imagina que eres un ISP de fibra óptica (FTTH). Algunas de tus casas tienen un aparatito blanco (Whitebox) que mide la calidad del internet cada hora.

La pregunta: en el horario pico nocturno local (19:00-22:59), cuando muchos ven streaming, juegan y hacen videollamadas, ¿qué casas muestran calidad degradada? Y ¿cuánto de esa degradación es real, y cuánto es un artefacto del equipo de medición o del propio análisis?

**Resultado clave:** pendiente. El alcance es de 258 unidades FTTH. El número de unidades analizadas y el de unidades en riesgo se publicarán solo cuando termine la reconciliación Python ↔ Power BI (el pipeline y sus pruebas automáticas ya están terminados; ver el roadmap del README). Las cifras de versiones anteriores (v1, v2.x) son inválidas y no se reutilizan.

### 2. ¿Qué mide cada registro? (Explicado sin tecnicismos)

Cada fila en los datos crudos NO es un cliente y NO es un paquete suelto. Es **una prueba horaria** de un Whitebox.

*   **Prueba de latencia (`curr_udplatency`):** una fila resume la prueba: tiempo de ida y vuelta promedio (`rtt_avg`) y cuántos paquetes recibieron respuesta (`successes`) o no (`failures`). El número de paquetes varía por fila (131 a 2,365 en las primeras filas inspeccionadas).
*   **Prueba de jitter (`curr_udpjitter`):** una fila es un flujo UDP; reporta cuánto varió el retraso (`jitter_up`, `jitter_down`).
*   **Recorrido:** Whitebox -> red de la casa -> ISP -> Internet -> servidor de prueba (todos alojados por SamKnows).

**Valores de referencia observados en los datos:** mediana de RTT por unidad entre 2.5 y 17.2 ms; pérdida global de paquetes de aproximadamente 0.022%.

**Cuando marcamos `risk_flag = 1`:**
En horario pico, contra el servidor primario de la unidad y sobre los 50 días observados, se cumple al menos una de estas condiciones:
- latencia P95 > 20 ms, o
- jitter P95 > 5 ms, o
- pérdida de paquetes > 1%.

Estos umbrales son **umbrales operativos definidos por el proyecto**, no valores de un estándar. P95 significa que el 95% de las pruebas pico de la unidad están en ese valor o por debajo; la unidad se marca cuando su peor 5% de pruebas pico ya supera el límite. Se calcula sobre promedios horarios, así que los picos breves dentro de una sola prueba no se ven en él.

### 3. Datasets Usados

| Archivo | Rol | 1 fila = | Columnas Clave |
| :--- | :--- | :--- | :--- |
| `unit-profile-sept2022.xlsx` | DIM - Quién | 1 Whitebox / casa | `Unit ID, ISP, Technology, State, Whitebox Model, Download, Upload, timezone_offset_dst` |
| `fiber_units.csv` | DIM Limpia (258) | 1 casa en alcance | Filtro: `Whitebox Model IN (skwb8 227, ac1750v2 28, skwb8p 3)` |
| `curr_udplatency.csv` | FACT - Latencia + pérdida | 1 prueba horaria | `unit_id, dtime, target, rtt_avg (µs), successes, failures` |
| `curr_udpjitter.csv` | FACT - Jitter | 1 prueba de flujo UDP | `unit_id, dtime, target, jitter_up, jitter_down` |
| `curr_udpcloss.csv` | Eventos de caída (solo referencia) | 1 evento de caída | `unit_id, dtime, duration, packets` - NO es un porcentaje de pérdida |
| `ftth_qoe_unit_metrics.csv` | FACT de salida (planeado) | 1 unidad analizada | `unit_id, p95_latency_ms, p95_jitter_ms, loss_pct, risk_flag, risk_severe` |

**Reglas de oro:**
- microsegundos crudos / 1000 = ms.
- P95 con interpolación lineal (`quantile(0.95)` en pandas = `PERCENTILE.INC` en Excel y Power BI), nunca `AVERAGE`.
- Pérdida = `sum(failures) / sum(successes + failures) * 100` (ratio of sums, desde `curr_udplatency`).
- Sin capping y sin `fillna(0)`: los registros inválidos se excluyen y se cuentan.

### 4. Proceso Completo (6 pasos para repaso rápido)

**Paso 1 - Población (corrección del sesgo de instrumento):**
El Whitebox es el instrumento de medición; un modelo legacy que no reenvía a velocidad de línea crea la degradación que reporta. De 285 unidades FTTH se conservan los modelos `skwb8`, `skwb8p`, `ac1750v2` -> **258 unidades**. Las 27 unidades legacy están en `data/excluded_legacy_ftth_units.csv`. El filtro usa la capacidad nominal de cada modelo, no una prueba de throughput por unidad.

**Paso 2 - Ventana pico (D-03):**
`dtime` se trata como hora **local** de la unidad (los datos no se comportan como UTC, como dice la documentación de la FCC). `local_hour = hour(dtime)`, sin sumar offset. Ventana pico: hora local >= 19 y < 23. La lectura UTC se reporta como sensibilidad en cada resultado.

**Paso 3 - Regla de servidor (D-04):**
Una unidad usa de 1 a 4 servidores de prueba a distintas distancias. Las métricas usan el **servidor primario** de la unidad (el `target` con más registros en la ventana pico; desempate por orden alfabético). Todos los servidores juntos se reporta como sensibilidad.

**Paso 4 - Métricas por unidad (solo ventana pico):**
`p95_latency = P95(rtt_avg / 1000)`, `p95_jitter = P95((jitter_up + jitter_down) / 2 / 1000)`, `loss_pct` como arriba. Las unidades con menos de 50 registros pico (`N_MIN`, D-02) se reportan aparte y no se califican.

**Paso 5 - Flag de riesgo:**
`risk_flag = 1` si latencia > 20 ms O jitter > 5 ms O pérdida > 1% (estrictamente mayor). `risk_severe` usa 50 ms / 15 ms / 10%. Con cada resultado se reporta una rejilla de sensibilidad de umbrales.

**Paso 6 - Power BI:**
Power BI consume solo `data/processed/ftth_qoe_unit_metrics.csv`; no recalcula métricas. Python y Power BI se reconcilian por `Unit ID` con tolerancias explícitas (`docs/reconciliation.md`, planeado).

### 5. Glosario Rápido (Para stakeholder no técnico)
 (Glosario COMPLETO en `docs/glossary_of_terms.md`)
*   **FTTH:** Fiber To The Home. Internet por fibra hasta la casa.
*   **Whitebox:** Dispositivo de medición de la FCC, no el router del cliente.
*   **P95:** El 95% de las pruebas está en este valor o por debajo. Si el P95 es alto, las peores pruebas en horario pico son malas.
*   **Bufferbloat:** Cola de paquetes en el router de casa cuando se satura el upload.
*   **OLT/ONT:** OLT es el equipo en la central del ISP, ONT es la cajita en casa. Entre ellos va la luz.
*   **Churn:** Cliente que se va.

### 6. Stakeholders y Preguntas de Negocio

**Stakeholders:** NOC Manager (quiere lista accionable), CXO (quiere dimensionar el problema).

**3 Preguntas que responde:**
1. ¿Qué proporción de las unidades de fibra analizadas tiene mala QoE en pico?
2. ¿Cuáles son las unidades específicas a revisar?
3. ¿Qué tan robusto es ese resultado ante la convención horaria, la regla de servidor y los umbrales (análisis de sensibilidad)?

**3 Acciones propuestas (por confirmar cuando existan resultados):**
1. Auto-alerta cuando el P95 pico de una unidad se mantiene sobre el umbral varios días seguidos (número de días por definir).
2. Triage remoto (OLT, bufferbloat) antes de enviar un técnico.
3. Contacto proactivo con los clientes marcados.

No se estima impacto financiero (churn, truck rolls): no hay fuente para los costos unitarios. Si se agrega una estimación, será un escenario claramente etiquetado, con supuestos explícitos.

### 7. Limitaciones

- Dos meses de datos de una muestra no aleatoria de unidades voluntarias; los resultados no representan a todos los suscriptores FTTH.
- 220 de las 258 unidades (85%) están en la zona horaria Eastern de EE.UU.
- La lectura de `dtime` como hora local se basa en evidencia indirecta y contradice la nota general de la FCC.
- La unidad del jitter (µs) tiene respaldo indirecto (jitter por unidad frente a `rtt_std`) pero la FCC no la documenta, y el jitter está dominado por el valor de subida. Solo se evalúa en unidades con al menos 50 registros pico de jitter (decisión D-07); las demás se califican por latencia y pérdida.
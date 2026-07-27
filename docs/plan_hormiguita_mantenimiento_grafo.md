# Plan Hormiguita: Arquitectura de Mantenimiento Autónomo del Grafo BioRAG

El **Plan Hormiguita** es el sistema de mantenimiento de precisión quirúrgica diseñado para la curación y optimización continua del grafo de conocimiento BioRAG. Su objetivo es actuar como el "subconsciente" del sistema, reparando sinapsis, clasificando nodos y eliminando ruido semántico de forma incremental y autónoma, sin intervención manual del usuario.

## 1. El Concepto: La Hormiguita como Agente de Curación

A diferencia de los procesos mecánicos de consolidación (LTP/LTD), la **Hormiguita** es una entidad inteligente (potenciada por modelos externos como Gemini) que recorre el grafo decidiendo la validez semántica de cada conexión y la calidad de cada nodo.

> **Definición**: Un proceso en segundo plano (daemon) que utiliza algoritmos de exploración de grafos para seleccionar subgrafos de conflicto y enviarlos a una IA externa para su evaluación y corrección.

## 2. El Algoritmo: Hormiga con Frontera (Frontier-Based Exploration)

Para manejar la escalabilidad y no saturar los límites de tokens de las APIs externas, la hormiguita no intenta procesar todo el grafo a la vez. Utiliza una estrategia de **Exploración Basada en Frontera**:

1.  **Semilla**: El ciclo comienza en un nodo "semilla" (usualmente el nodo más reciente o uno que haya causado fallos de búsqueda).
2.  **Frontera**: Se identifican los vecinos inmediatos (radio de 1 o 2 saltos) que no han sido visitados recientemente.
3.  **Evaluación Local**: El sistema local (SQL) prepara un *payload* con el contenido completo del nodo actual y sus vecinos.
4.  **Consulta a la IA**: Se envía este contexto a la IA externa para que tome decisiones (mantener, eliminar, reponderar).
5.  **Persistencia**: Los nodos procesados se marcan como "visitados" y los nuevos vecinos se añaden a la "frontera" para el siguiente ciclo.

## 3. Procesos del Subconsciente (Mapeo Biológico)

| Proceso Biológico | Acción en el Grafo BioRAG | Descripción Técnica |
| :--- | :--- | :--- |
| **Poda (Pruning)** | Eliminación de Sinapsis | La IA detecta conexiones `PMI_HEBBIANO` que son solo coincidencias temporales y no semánticas. |
| **Fortalecimiento (LTP)** | Recálculo de Pesos | Nodos con alta conectividad pero bajo peso sináptico son "rescatados" y fortalecidos. |
| **Replay / Corrección** | Creación de Sinapsis | Durante el "sueño", la IA compara nodos nuevos con viejos y crea conexiones semánticas que el sistema local omitió. |
| **Neurogénesis** | Clasificación y Enriquecimiento | Nodos sin dimensiones o en categoría "General" son clasificados correctamente por la IA. |

## 4. Estrategia de Recorrido y Priorización

La hormiguita divide su presupuesto de tokens diario en tres fases para asegurar que el mantenimiento sea efectivo:

*   **Fase Urgente (20%)**: Atiende nodos que dispararon errores en el log de búsquedas o tienen anomalías detectadas (como `peso_cero`).
*   **Fase Reciente (30%)**: Procesa nodos creados o modificados en las últimas 24 horas para limpiar la "contaminación" de la sesión actual.
*   **Fase de Barredo (50%)**: Realiza un recorrido sistemático de los nodos más antiguos que no han recibido mantenimiento, avanzando de a poco hasta cubrir el grafo completo.

## 5. Integración con la API Externa (JSON Estricto)

Para garantizar el determinismo y la seguridad, la IA externa nunca escribe directamente en la base de datos. El flujo es:
1.  **Backend** envía un JSON con el contenido de los nodos y la tarea.
2.  **IA** responde con un JSON estricto de veredictos (ej: `{"nodo_id": "X", "accion": "eliminar_sinapsis", "razon": "..."}`).
3.  **Backend** valida el JSON y aplica los cambios mediante comandos SQL controlados.

## 6. Persistencia y Continuidad (`estado_hormiga.json`)

El estado de la hormiguita se guarda en un archivo de configuración persistente que permite retomar el trabajo exactamente donde se dejó:
*   **Frontera pendiente**: Lista de nodos que faltan por visitar de la semilla actual.
*   **Nodos visitados**: Registro para evitar ciclos infinitos y duplicidad de trabajo.
*   **Gestión de Quota**: Si la API devuelve un error de límite (429), la hormiguita guarda su posición, calcula el tiempo de espera y se "duerme" hasta que la cuota se renueve.

---
*Este documento sintetiza el plan original extraído de la sesión v24.0 para la realineación del modelo de memoria BioRAG.*

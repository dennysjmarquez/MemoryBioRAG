═══════════════════════════════════════════════════════════════════════════════
 GUÍA PARA CREAR Y ENTRENAR UNA NEURONA EN BIORAG
 (lo que se hizo con las dos primeras neuronas, en qué se basó y por qué)
═══════════════════════════════════════════════════════════════════════════════

───────────────────────────────────────────────────────────────────────────────
NOTA DE USO: ESTA GUÍA ES UNA SUGERENCIA, NO UN REQUISITO OBLIGATORIO
───────────────────────────────────────────────────────────────────────────────

Este documento es una referencia técnica recopilada a partir de las dos primeras
neuronas implementadas en BioRAG. Puedes usarla como base, adaptarla, ignorar
partes o no usarla en absoluto. No es un estándar impuesto ni un requisito
bloqueante para crear neuronas. Cada quien decide qué aplicar y qué adaptar
según su propio criterio y las necesidades de su sistema.

Las secciones que mencionan "obligatorio", "invariable" o "rechazada" se
refieren al contexto interno de los experimentos previos y a las decisiones
tomadas en esos casos específicos, no a una imposición sobre el uso de este
documento.

───────────────────────────────────────────────────────────────────────────────

Lee primero, en este orden:
  docs/Mi neurona en el sistema/experimento_10_neuronas_del_motor/README.md  (normas, molde, mapa)
  docs/Mi neurona en el sistema/experimento_01_pesos_aprendidos/LA_NEURONA_EXPLICADA.md
  docs/Mi neurona en el sistema/experimento_11_neurona_asociativa/README.md  (PARTE 2 manda)
  core/memory/neurona.py (cabecera), core/memory/neurona_examen.py, core/neurona_asociativa.py

───────────────────────────────────────────────────────────────────────────────
0. QUÉ ES UNA NEURONA BIORAG, EN UNA FRASE
───────────────────────────────────────────────────────────────────────────────
Una pieza CHICA, con UNA sola tarea, puesta en un punto clave del motor. Recibe
unos pocos números ya calculados (las "agujas") y decide algo: ordenar, conectar o
dejar pasar. Siempre arranca desde una fórmula a mano (el piso) y nunca puede
quedar por debajo de ella. No lee texto ni "entiende": pondera evidencia.

Hoy existen dos, y son de DOS TIPOS distintos. Elegir el tipo es la primera
decisión de cualquier neurona nueva:

 A) NEURONA VIVA (la del ranking, core/memory/neurona.py, v34/v34.1)
    - Aprende dentro de CADA base de datos, sola, con un autoexamen.
    - Pesos propios de cada DB, guardados en la tabla `neurona_estado`.
    - Red 29 → 6 → 1 que SUMA una corrección a la fórmula a mano.
    - Solo reordena el top-k que ya eligió el motor.

 B) NEURONA CERRADA DE FÁBRICA (la asociativa, core/neurona_asociativa.py, v35)
    - Se calibró UNA vez en el laboratorio con memorias públicas de verdad conocida.
    - Llega "nacida" y NO aprende de la memoria del usuario (decisión de Dennys).
    - Solo se auto-regula: mide en cada DB si el tiempo y las etiquetas son fiables.
    - Dados dos recuerdos devuelve una fuerza de 0 a 1.
    - Estado: construida, examinada y cerrada; el motor todavía NO la llama.

 Cuándo elegir cada tipo (criterio que usé):
    - Si lo que decide depende mucho de cada memoria (cómo pregunta cada persona,
      qué agujas hablan en esa DB) → VIVA, con piso, guardia y techo.
    - Si lo que decide es universal (¿estos dos textos tienen que ver?) y aprender
      del usuario sería memorizar → CERRADA, calibrada en varias memorias públicas.
    - Medido en el exp 11: lo universal cabe en el piso. Lo que queda por aprender
      es PROPIO de cada memoria: lo que ayuda a una empeora a otra.

───────────────────────────────────────────────────────────────────────────────
1. NORMAS DE DENNYS (OBLIGATORIAS: si una propuesta rompe una, se descarta)
───────────────────────────────────────────────────────────────────────────────
Sobre el sistema
 1. El recall NUNCA baja. La tabla de QA de Dennys es el piso; ningún valor
    puede quedar por debajo, en ninguna categoría.
 2. El ranking no se toca (la fórmula a mano y la neurona del ranking quedan igual).
 3. Tiempo constante por operación. Nada que recorra toda la DB en cada consulta.
    Nada de redes pesadas ni "modelos embellecidos". Solo SQLite + Python + numpy.
 4. Sin feedback del agente, sin registrar qué usó y sin trabajo extra para el
    agente. Agente y MCP quedan iguales, salvo un parámetro que la neurona
    necesite de verdad.
 5. Funciona desde una DB VACÍA, para terceros que nunca van a correr la QA.
 6. Nunca se borran recuerdos. Para conexiones: cuarentena reversible, nunca borrar.
    Los enlaces `manual` (los que crea el agente o el usuario) no los toca nada automático.
 7. Ninguna DB real se toca en experimentos: siempre en COPIAS. El snapshot
    snapshots/qa_escape_qcr_20260811.db es intocable (sha256 104dd2902aaf…);
    verificarlo antes y después.
Sobre cada neurona
 8. Piso a mano primero: fórmula o tabla calibrada a mano. La que aprende va ENCIMA
    y nunca queda por debajo del piso.
 9. Techo: aprende hasta un límite y para (aprender, no memorizar). Si el
    rendimiento baja, vuelve a aprender o se retira.
10. Campeón / guardia / techo: una versión nueva solo reemplaza a la vieja si
    gana el examen de control.
11. Tiene que ser perfecta: probar todos los modos de falla; si falta una capa de
    protección, se inventa y se prueba.
Sobre cómo se trabaja
12. Primero se conversa con Dennys y después se mide. Ningún experimento de una
    idea nueva sin hablarlo.
13. Primero se mide la línea base, después UN cambio aislado, después se mide de nuevo.
14. Rama propia y PR. Solo Dennys hace merge.
15. Resultados presentables a un auditor: números exactos, salida literal, scripts
    incluidos, sin exagerar y sin "primero en el mundo".
16. Soluciones generales para cualquier corpus y tamaño. Sin parches por caso.

───────────────────────────────────────────────────────────────────────────────
2. EL MOLDE: LAS 7 PIEZAS DE TODA NEURONA
───────────────────────────────────────────────────────────────────────────────
 1. AGUJAS      Entradas, cada una de 0 a 1, con regla fija y calibrada en el banco.
 2. PISO        Fórmula a mano. Si la neurona no está lista, MANDA EL PISO.
 3. NEURONA     Pocos pesos que corrigen al piso según el contexto.
 4. AUTOEXAMEN  Preguntas con respuesta conocida (estudio + control/guardia).
 5. CAMPEÓN     La nueva solo asciende si gana al campeón en el control.
 6. TECHO       Deja de aprender al estancarse (meseta, paciencia).
 7. COSTO FIJO  Presupuesto de tiempo y de memoria constante, siempre.

REGLA DE ORO: si cualquier pieza falla (no hay examen suficiente, baja el control,
se acaba el tiempo, los pesos están rotos), la neurona se aparta sola y queda el
piso. El sistema nunca queda peor que la fórmula a mano.

───────────────────────────────────────────────────────────────────────────────
3. PASO A PASO PARA CREAR UNA NEURONA NUEVA
───────────────────────────────────────────────────────────────────────────────
PASO 1 · Elegir el LUGAR y la DECISIÓN (una sola)
  Escribe en una línea qué decide. Ejemplos: "reordenar el top-5", "con qué
  fuerza nace esta sinapsis", "qué vecinos del grafo traer", "cuántos resultados
  devolver".
  Ubícala en el motor:
  - Dónde se juntan candidatos: capas de core/memory/search.py.
  - Dónde se ordenan: scoring.py y neurona.py. El ranking NO se toca.
  - Dónde nacen las sinapsis (la neurona reemplaza SOLO la regla fija):
      core/sinapsis.py auto_vincular            → co_ocurrencia, co_nombre, co_semantica, pmi_hebbiano
      core/sinapsis.py vincular_por_sinonimos   → sinonimo_explicito
      core/memory/consolidation.py L102/L159    → co_ocurrencia (misma sesión)
      core/memory/rafaga.py L349                → rafaga_rememb
      core/lexical_learning.py L317             → léxica
      core/sueno_vacios.py L280/L307            → directas y latentes
      core/dmn_engine.py L128/L331/L339         → dmn_synthesized, latentes
      core/inferencia_transitiva.py L238        → latentes
      core/memory/synapses.py vincular          → manual (NO SE TOCA)
  Principio: EL MOTOR BUSCA (rápido, igual que hoy) y LA NEURONA DECIDE.

PASO 2 · Decidir CUÁNDO actúa y CUÁNDO aprende
  - Actúa en la búsqueda solo si cuesta tiempo constante (ej. reordenar el top-k).
  - Aprende o decide cambios del grafo en la CONSOLIDACIÓN o el SUEÑO, nunca en
    vivo. Ahí sí se conoce la respuesta, y una consulta suelta no deforma la memoria.
  - La neurona del ranking practica 1 vez por consolidación (consolidar, sueño,
    contexto_fin), no por cada `aprender`.

PASO 3 · Inventario de agujas (qué le das de "agua")
  "Una neurona solo puede aprender sobre las agujas que recibe; si las agujas son
  pobres, aprenderá ruido con apariencia de inteligencia."
  Busca en el código y en una COPIA qué características existen y cuántos
  recuerdos las tienen.
  - Ejemplo real (exp 10 §15.3), parecido: contenido, PPMI, sinónimos (96 %),
    dims (90 %), vecinos, categoría, grado, peso/tipo de sinapsis.
  - Lo estructural casi vacío: sustantivos_clave 0.7 %, predicados 12 %, valencia
    11 %, sin id de episodio, sin contradicción.
  Si falta algo esencial que solo el agente sabe, se discute con Dennys cambiar
  un parámetro del MCP que no aporta por uno que sí (trabajo neto cero). Nunca se
  agregan cargas al agente sin su permiso.

PASO 4 · Reglas de una buena aguja
  - Número de 0 a 1, con una regla FIJA y simple (no aprende nada).
  - UNIVERSAL: no mira QUÉ palabras hay sino CÓMO se relacionan dentro de su propia
    memoria. Sin listas de palabras de ningún idioma.
  - Barata: tiempo constante por consulta o por par.
  - Determinista: el mismo dato siempre da el mismo número. Nada de list(set)[:N]
    ni orden de hash; correr todo con PYTHONHASHSEED=1.
  - Si una aguja puede no ser fiable en una DB (tiempo, etiquetas), que se
    AUTO-REGULE: medir sin verdad si en ESTA memoria coincide con el texto y
    multiplicarla por esa fiabilidad (0 si no la hay). Nunca confiar a ciegas.
  - Signo fijo "por biología": las que suman solo suman (peso 0 a 4); las de
    sobreconexión (hub, "se tocan por una sola palabra") solo restan.
  - Giro dentado: incluir siempre agujas de RAREZA. Una palabra común compartida
    no debe pegar recuerdos (caso real: "recall" unía 49 recuerdos).

PASO 5 · Banco de calibración (solo lectura, sobre copia)
  Para cada aguja candidata:
   1. su distribución (mín, máx, cuartiles);
   2. normalizarla a 0–1 con regla fija;
   3. cuánto SEPARA lo bueno de lo malo: AUC (.5 = azar), con el autoexamen o con
      la verdad de las memorias de fábrica;
   4. su costo en ms;
   5. Dennys decide: entra, no entra o cambia la regla.
  El banco no cambia el motor: lee una copia y escribe un informe.

PASO 6 · El piso a mano
  - Ranking: los pesos que Dennys fue poniendo a mano (scoring.py).
  - Asociativa: pesos ENTEROS elegidos por el banco, subiendo peso por peso desde
    cero, con el AUC medio como objetivo y los signos fijos. Resultado:
       z = −1 + 2·parecido + 1·semantica + 1·rareza_max + 4·episodio + 1·etiquetas
       fuerza = 1 / (1 + e^−z)
  - Cómo se eligió el procedimiento: "dejar una memoria fuera". Se calibra con 6
    memorias y se examina en la 7ª, las 7 veces.
      "desde cero"            .9394 medio / .882 peor   ← el mejor
      "recalibrar desde v1"   .9233 / .827
      "v1 sin recalibrar"     .9125 / .74
  - El sesgo (cuándo "conectar") no se elige a ojo: con −1, lo que pasa de .80
    acierta ≥ 80 % en fábrica.
  - Las agujas que quedan con peso 0 en el piso no aportaban nada ENCIMA de las
    otras. La parte que aprende sí las ve todas.

PASO 7 · La parte que aprende (si es VIVA) o la corrección de fábrica (si es CERRADA)
  Ver secciones 5 y 6.

PASO 8 · Capas de protección, cada una con su prueba automática (sección 7).

PASO 9 · Validación de punta a punta (sección 8). Solo si nada baja, se cablea
  detrás de un interruptor (BIORAG_<NOMBRE>=0 la apaga) y va a PR.

───────────────────────────────────────────────────────────────────────────────
4. DE DÓNDE SALEN LOS DATOS DE ENTRENAMIENTO (LO MÁS IMPORTANTE)
───────────────────────────────────────────────────────────────────────────────
Condición sin la que nada funciona: para aprender hay que saber CUÁL ERA LA
RESPUESTA CORRECTA (exp 03). En una búsqueda en vivo nadie lo dice.
  - Re-ranquear en vivo con una "nota" que el motor se pone a sí mismo SIEMPRE
    empeoró (88.9 → 83.1 con más vueltas). Es circular: mide cuánto se cree a sí mismo.
  - El mismo ajuste con un oráculo que sabe la respuesta llegaba a 99.5 %.
  - O sea: el algoritmo de ajuste nunca fue el problema; el problema es la verdad.
  - Por norma, la verdad NO puede venir del feedback del agente.
Las fuentes de verdad que se usaron:

4.1 Neurona VIVA (ranking): el AUTOEXAMEN "tapar y adivinar"
  - Cada recuerdo genera sus propias preguntas; como salen de él, la respuesta se
    conoce. Si no sale #1 en su propia pregunta, eso es "lo que falló".
  - Generador: core/memory/neurona_examen.py, copia del de
    scripts/generar_casos_qa.py para que el motor no dependa de scripts/.
  - Determinista: el azar se siembra con el nombre del concepto.
  - Categorías:
      variante gramatical (reglas de sufijo)
      typo (una letra cambiada, borrada o insertada)
      sinónimo (del recuerdo o de un mapa fijo)
      pregunta natural (6 plantillas: "¿Qué tenemos registrado para…?")
      por tema (3 palabras del contenido que no están en el nombre)
      cruce de idioma (diccionario ES↔EN de ~40 palabras)
      CONTENIDO (palabras de una oración, como pregunta quien no sabe el nombre)
    No genera literal ni dormido: eso ya lo resuelve el motor solo.
  - Cuánto practica (core/memory/neurona.py::_cfg, variables BIORAG_NEURONA_*):
      8 recuerdos × 7 preguntas por consolidación, preguntadas A LO ANCHO (ronda 1
        de todos, ronda 2 de todos…), dentro de un presupuesto de 3 s;
      memoria de examen fija: 1200 de estudio + 300 de guardia;
      mínimo para entrenar: 150 + 40;
      tope de 4 casos por recuerdo; relleno al azar por rowid (O(log N)), primero
        el grupo al que más le falta.
    En profundidad (2 recuerdos × muchas preguntas) se descartó: conocía menos
    recuerdos y la QA bajó.
  - Practica los dos caminos, alternando: "agente" (como llega por el MCP
    `recordar`: pool 3x, convergencia, sustantivos sacados de la consulta) y
    "crudo" (como la QA).
  - DESFASE 0: una sola función `vista` arma lo que ve la red desde la página TAL
    COMO SE SIRVE. El examen guarda esa vista y `reordenar` corrige esa misma.
    Se estudia exactamente lo que se usa (en v4 el desfase era 46.7 %).
  - Silencio: las búsquedas de práctica no escriben log, accesos ACT-R ni DMN
    (silencio por hilo).
  - Para una DB que ya existe y recibe poco: scripts/despertar_neurona.py hace
    seguido lo mismo que el uso. Misma práctica, mismas capas. Solo escribe
    `neurona_estado`. --olvidar deshace. Rechaza el snapshot oficial.
  - Historia: el exp 01 entrenó con las 921 preguntas de la QA (875 evaluables,
    228 432 candidatos exportados). El exp 04 pasó al autoexamen (866 recuerdos →
    4149 preguntas) y llegó MÁS alto (95.3 vs 94.5 antes del post-proceso),
    porque el examen era 5 veces más grande.

4.2 Neurona CERRADA (asociativa): MEMORIAS DE FÁBRICA con verdad conocida
  Público, sin datos del usuario. Corpus de NLTK más la librería estándar de Python
  (experimento_11/corpus.py):
   memoria      lengua  qué es                                    "sí tienen que ver" si…
   noticias     en      Reuters                                   mismo tema
   diccionario  en      WordNet (textos de ~14 palabras)          relación directa
   relatos      en      Brown, trozos de 150 palabras             mismo texto
   codigo       Python  métodos de la stdlib sin nombre de clase  misma clase
   charla       en      chat real NPS, ventanas de 10, sin users  misma sala y día
   noticias_es  es      agencia EFE (CESS-ESP), con fecha         misma noticia
   machado      pt      obra de Machado de Assis                  misma obra
  - Pares de entrenamiento = los que un motor PROPONDRÍA: comparten raíz o son
    vecinos semánticos, hasta 30 por recuerdo, más los 2 guardados justo antes y
    justo después si la memoria tiene tiempo.
  - Reglas de los datos:
     · solo TIEMPO REAL, nunca inventado;
     · las etiquetas siempre MÁS GRUESAS que la verdad (como las dims);
     · la verdad debe ser FINA. Se probó y se SACÓ "reportes" (fallas de 5
       programas, "sí" si eran del mismo programa): AUC ~.55–.65. Dos fallas de
       Firefox no tienen por qué tener que ver; habría enseñado algo falso;
     · variedad: lenguas distintas, textos largos y muy cortos, código y chat.
  - Examen real, NUNCA usado para entrenar ni elegir: la memoria de Dennys (copia
    del snapshot, 851 recuerdos, 13 342 conexiones). Jueces:
      381 enlaces manuales (humano = sí): AUC .868 (peso de hoy: .271);
      lo que Gemini mandó a cuarentena (3 971) y lo que confirmó (120): AUC .930;
      hoja de 100 pares marcados a mano por Dennys sin saber qué opinaba la
        neurona (etiquetado/preparar_hoja.py; NO va a git porque muestra recuerdos
        privados). Es un EXAMEN, no una clase: la neurona no aprende de ella.
        AUC .73. Con fuerza ≥ .6 en sinapsis existentes, 13 de 14 eran buenas.

4.3 Reglas sobre los datos que salieron de los experimentos
  - La neurona solo aprende a buscar por SIGNIFICADO si se le enseña con preguntas
    de significado. Sin ejemplos de "por tema", esa categoría se hundió de 63 a 28 %.
  - Con muy pocos datos es peligrosa: con 36 preguntas ganó 40 casos y rompió 34.
    Con ~70 llega la mayor parte de la mejora; con 342 a 700 se estabiliza.
  - Trampa de "enseñar para el examen": el autoexamen y la QA son de la misma
    familia. En una DB que nunca vio, con preguntas HUMANAS (FAQ de python-docs-es,
    164 preguntas), la mejora fue casi nula. Siempre medir también con preguntas
    humanas o reales.
  - Revisar las etiquetas débiles antes de exigir 0 pérdidas: "por tema" son 3
    palabras al azar y "sinónimo" a veces pertenece a muchos recuerdos ("regla"
    es sinónimo de 18).
  - Nunca trasplantar un campeón entrenado en otra DB: dañó (−4.9 R@1). Lo de
    fábrica viaja solo como piso o como retadora que debe ganar el examen local.

───────────────────────────────────────────────────────────────────────────────
5. CÓMO SE ENTRENA LA NEURONA VIVA (RECETA TÉCNICA)
───────────────────────────────────────────────────────────────────────────────
Forma: corrección SOBRE el piso, en el espacio logit (arranca EXACTAMENTE en el piso).
   M0 = fórmula a mano (el score de hoy)
   R1 = logit(M0) + w·x                     (lineal: casi nunca cumple el piso)
   R2 = logit(M0) + v·tanh(W·x + b)         ← LA ELEGIDA: capa oculta de 6
   La capa oculta hace falta por el "XOR" de BioRAG: el hub ayuda cuando no hay
   coincidencia literal y estorba cuando sí la hay. Ningún peso fijo separa eso.
   Una red por tipo de consulta NO mejoró: la capa oculta ya lo hace por dentro.
Entradas: 29 señales = las 17 agujas de la fórmula
   (bm25, dims, concepto, sinónimos, latcad, grupo, temático, asoc, predicados,
   ppmi, hub, ncd, episodio, campo, jsd, nombre exacto, sinónimo ≥ .95)
   + 12 de lo que pasa después de la fórmula y de lo que aporta el agente
   (bono de convergencia, evidencia por campo, sustantivos_clave, peso,
   ¿score con peso?, ¿con agente?, origen léxico/hub/no literal, sin rasgos).
Pérdida: entropía cruzada softmax sobre TODO el pool de cada pregunta (listwise).
   El correcto se empuja arriba y cada impostor abajo, según lo que le "robó".
Optimizador: Adam, lr .03, L2 1e-3. Offline 400 pasos; en el motor 30 por ciclo.
   Hiperparámetros fijados ANTES de mirar resultados.
Partición: por RECUERDO (nunca el mismo nodo en estudio y en prueba).
   Guardia = 20 % de recuerdos por hash: sha256(nombre)[:8] % 5 == 0, nunca se estudia.
   Repetir con 3 semillas (7, 11, 23); solo vale lo que se repite en las tres.
Cuándo asciende un retador a campeón (_calibrar / _evaluar_y_decidir):
   - no pierde NINGÚN caso de guardia que la fórmula acertaba;
   - en total pierde < 5 % de lo que gana;
   - PISO por categoría Y por camino en R@1, MRR y R@5: nunca debajo de la fórmula;
   - ningún caso de guardia que la fórmula tenía en el top-5 sale de él;
   - PISO CONTRA EL CAMPEÓN: en ninguna categoría queda debajo del campeón
     saliente por más de τ = 1 caso (τ = 0 frena el aprendizaje por ruido);
   - gana ESTRICTAMENTE a la fórmula;
   - anti-memorización: si estudia mejor pero la guardia no, se reinicia y no
     asciende ese ciclo.
Margen "primero no dañar": solo cambia el orden si su ventaja supera ε; a cada
   puesto se le suma ε·(k − puesto). ε = el MENOR de (0, .25, .5, 1, 1.5, 2, 3, 5, 8)
   que cumple todo lo anterior, recalibrado en cada ciclo. Si ninguno lo cumple,
   el campeón se retira.
Techo: paciencia de 12 ciclos sin mejora → "tranquila" (solo vigila, a mitad de
   costo). Se despierta con 150 preguntas nuevas o si baja.
Cómo sirve: solo REORDENA los k primeros (5, o 10 por el MCP; topk_max = 10).
   Mismos nodos y mismos números reasignados por posición. Así R@k no puede
   bajar y GABA, abstención y FP no ven nada distinto. También se permutan los
   mapas de score del MCP (_permutar_mapas).
   Regla de identidad: si la consulta es el nombre del recuerdo ("_" = espacio)
   y la fórmula lo tenía #1, sigue #1.
Probado y DESCARTADO:
   - sumar la corrección al score (modo escala): infla los scores, 3 sinónimos
     salían del top-5;
   - reordenar todo el pool antes del post-proceso: mismo daño.

───────────────────────────────────────────────────────────────────────────────
6. CÓMO SE CALIBRÓ LA NEURONA CERRADA (RECETA TÉCNICA)
───────────────────────────────────────────────────────────────────────────────
12 agujas del par (A, B), todas de 0 a 1, en cualquier idioma (experimento_11/agujas.py):
   parecido (coseno tf-idf), semantica (LSA de 100 dimensiones), rareza_max,
   rareza_media, pistas_raras, cobertura, mutuo, vecinos, hub (resta),
   una_sola (resta), episodio (auto-regulada), etiquetas (auto-regulada)
   + 3 de contexto solo para la parte que aprende (largo, fiab_episodio, fiab_etiquetas).
   En el motor quedan 5: raíces de 7 letras, DF_MAX .15, ventana de episodio 10,
   hueco máximo 7 días reales.
Mapa del hipocampo (réplica FUNCIONAL, no física):
   corteza entorrinal = agujas · giro dentado = rareza (separar lo parecido)
   · CA3 = vecinos/grafo (completar) · CA1 + inhibición lateral = juez y competencia
   · células de tiempo = episodio · prefrontal = etiquetas · homeostasis = hub
Parte que aprende (red 15 → 6 → 1 SOBRE el piso, techo ±1), entrenada solo en fábrica:
   - por COMPETENCIA: dentro de un mismo recuerdo, el socio que sí tiene que ver
     debe ganarle al que no (lo mismo que decide después);
   - guardia del 20 % por memoria;
   - homeostasis: la memoria que va peor recibe más atención;
   - NUNCA BAJO EL PISO en la guardia de CADA memoria; si ninguna versión lo
     logra, queda APAGADA.
   Resultado: apagada (escala 0 en pesos_fabrica.json). Cada memoria sola tenía
   algo que aprender (hasta +4.5), pero juntas se perjudicaban. Y donde pasó la
   regla en 6 memorias, empeoró la 7ª que no conocía.
Construcción en cada DB (sin aprender): tablas neurona_asociativa_estado y
   neurona_asociativa_raices. Se rehace cuando la memoria crece 10 %, sobre una
   muestra máxima de 2000 (costo con techo). Cada decisión por par es tiempo constante.
   BIORAG_NEURONA_ASOCIATIVA=0 la apaga.

───────────────────────────────────────────────────────────────────────────────
7. CAPAS DE PROTECCIÓN (CADA FALLA POSIBLE → UNA CAPA → UNA PRUEBA)
───────────────────────────────────────────────────────────────────────────────
Viven en tests/test_neurona.py. Toda neurona nueva debe tener su equivalente:
 - baja el recall → solo permuta lo que el motor ya eligió;
 - cambian los números que ven los umbrales → mismos números por posición,
   también en los mapas del MCP;
 - empeoran las búsquedas literales → regla de identidad;
 - memoriza → guardia que nunca se estudia + reinicio anti-memorización;
 - daña una categoría → piso por categoría y camino (R@1, MRR, R@5);
 - le gana al campeón cediendo una categoría → piso contra el campeón (τ = 1);
 - daña preguntas que el examen no ve → margen "primero no dañar";
 - campeón que solo empata o solo daña → debe ganar estrictamente o se retira;
 - la DB cambió → recalibra en cada consolidación; si no cumple, se retira;
 - pesos NaN/Inf o que explotan → _sano al servir, guardar y cargar;
 - el entrenamiento diverge → vuelve a los pesos anteriores;
 - estado guardado corrupto → arranca limpio desde el piso; nunca un margen negativo;
 - cambió la fórmula del motor (otra versión) → huella del motor: se reaprende;
 - el autoexamen ensucia log, ACT-R o DMN → silencio por hilo;
 - dos prácticas a la vez → candado no bloqueante: se salta el ciclo;
 - varios procesos sobre la misma DB → refresco por marca de tiempo, guardado atómico;
 - falla repetida → disyuntor: tras 3 errores seguidos, pausa;
 - el costo crece con los datos → número fijo de búsquedas y presupuesto de tiempo;
 - un recuerdo acapara el examen → sin duplicados y tope por recuerdo;
 - recuerdos olvidados → purga del examen;
 - DB vacía, de solo lectura o sin datos suficientes → sin campeón: motor idéntico;
 - apagado → interruptor de entorno (BIORAG_NEURONA=0).

───────────────────────────────────────────────────────────────────────────────
8. CÓMO SE VALIDA (EN ESTE ORDEN, SIEMPRE EN COPIAS)
───────────────────────────────────────────────────────────────────────────────
 1. Determinismo primero: PYTHONHASHSEED=1. Si el motor no repite el mismo
    resultado, "nunca baja" no se puede verificar.
 2. Pruebas unitarias de la neurona: forma, rango, sin NaN, simetría, memoria
    vacía/mínima, techo, guardar/cargar, velocidad (la asociativa tiene 31).
 3. Banco y "dejar una memoria fuera" (cerrada) o examen sellado de 3 grupos
    (viva): estudio 3/5 · validación 1/5 (decide cuándo parar) · sellado 1/5 (se
    mira UNA vez).
 4. Neurona cableada SIN nada aprendido → QA IDÉNTICA a master, byte a byte
    (tabla, JSON de métricas, lista de fallidos).
 5. QA oficial de punta a punta, con post-proceso incluido:
      PYTHONHASHSEED=1 BIORAG_PATH=<copia> python scripts/evaluar_qa.py
    (921 casos: 875 de recuperación + 40 negativos). Ninguna categoría baja.
    FP 0/40. GATE OK. Comparar caso a caso: gana / pierde.
 6. Camino del agente: herramienta MCP `recordar`, con y sin neurona. Mismos
    recuerdos, mismos números por posición, 0 violaciones.
 7. Una DB que nunca vio, con preguntas HUMANAS (python-docs-es, 164 del FAQ).
 8. Uso simulado: DB vacía que crece (5 recuerdos por sesión, 80 sesiones).
    ¿Cuándo junta su examen? ¿Cuándo asciende? ¿Retiros?
 9. Costo p50/p95 por consolidación y tiempo de la QA con y sin neurona.
10. sha256 del snapshot antes y después.
11. QA en la DB viva la corre Dennys (un comando: run_qa_suite.sh, que ya muestra
    la neurona; --con-neurona pregunta y estima el tiempo si no hay una entrenada).
Comparación justa entre dos versiones: el presupuesto de 3 s hace que dos corridas
del MISMO código difieran algunos casos. Para un A/B limpio, subir el presupuesto
(ej. 1000 s) o igualar el número de prácticas. Cada caso de una categoría de 65
vale 1.54 puntos: no confundir variación entre entrenamientos con daño.

───────────────────────────────────────────────────────────────────────────────
9. LO QUE YA SE PROBÓ Y FALLÓ (NO REPETIR)
───────────────────────────────────────────────────────────────────────────────
 - Entrenar hasta 100 % en lo estudiado: llega memorizando y empeora en lo nuevo
   (98–100 % estudiado → 88 % en nodos nuevos). El 100 % es el horizonte, no el
   criterio de parada.
 - Autoevaluarse en vivo sin la respuesta, o guardar "pesos campeones" sin juez:
   inestable o desastroso.
 - Una neurona por perfil de consulta: no mejora.
 - Trasplantar un campeón de otra DB: daña.
 - Sumar la corrección al score, o reordenar todo el pool antes del post-proceso.
 - Umbrales absolutos de score (R@5 96 → 73.4), PageRank personalizado (0 %, +100–190 ms),
   expansión de 1 salto sin juez, recorte fijo de la lista en el MCP.
 - Juzgar conexiones por "significado": la hormiguita/Gemini mandó 6 870 a
   cuarentena y 2 681 (39 %) tuvieron que volver. Se juzga por UTILIDAD medida.
 - Cortar sinapsis al nacer: baja el recall con cualquier umbral (exp 13). El
   "ruido" del grafo sirve para buscar; donde estorba es en lo que ve el agente.
 - "La neurona solo pone el peso": la QA salió idéntica; Dennys lo rechazó y se
   revirtió (76fe11c).
 - Elegir un ε o una regla mirando el examen de prueba: después falla en lo nuevo.
 - LSTM, Transformers, BD vectorial, Redis: no aplican. La neurona ordena unos
   pocos números por candidato y SQLite basta.

───────────────────────────────────────────────────────────────────────────────
10. LECCIONES DE FONDO (EN LO QUE ME BASÉ)
───────────────────────────────────────────────────────────────────────────────
 - Historia de la neurona: McCulloch-Pitts 1943 (pesos a mano = la fórmula de
   Dennys) → perceptrón 1958 → XOR 1969 (hace falta capa oculta) →
   retropropagación 1986 → atención 2017. Combinar señales con pesos aprendidos se
   llama learning-to-rank (RankNet 2005, LambdaMART). Eso NO es nuevo. Lo propio
   de BioRAG: agujas bioinspiradas, sin embeddings ni GPU, arranque exacto desde
   el piso del inventor, explicable aguja por aguja, examen propio en cualquier corpus.
 - Retropropagación en una cuenta: culpa de una aguja = Σ (objetivo − probabilidad)
   × valor de la aguja; peso nuevo = peso + tasa × culpa (exp 03).
 - La neurona NO crea significado: lo pondera. Si ninguna aguja capta que dos
   cosas son lo mismo, ningún peso lo va a encontrar. Primero mejores agujas.
 - La neurona solo reordena lo que llegó. Si la respuesta no entra al pool,
   encontrarla es trabajo de otra pieza (candidatos), no de la que ordena.
 - Lo universal va al piso; lo particular de cada memoria se aprende dentro de
   ella con piso y techo, o no se aprende.
 - "No tiene relación de significado" no es lo mismo que "no sirve": como en el
   cerebro, una asociación rara puede llevar al recuerdo. Se mide utilidad.
 - Cerebro de referencia: aprender en el sueño (replay), Hebb + tercer factor (la
   utilidad medida en el autoexamen hace de "dopamina"), homeostasis, inhibición lateral.

───────────────────────────────────────────────────────────────────────────────
11. FICHA PARA UNA NEURONA NUEVA (LLENARLA Y CONVERSARLA CON DENNYS ANTES DE MEDIR)
───────────────────────────────────────────────────────────────────────────────
 Nombre:
 Lugar exacto en el motor (archivo y función):
 Decisión única que toma:
 Tipo: VIVA (aprende en cada DB) / CERRADA (de fábrica). ¿Por qué?
 Cuándo actúa (búsqueda / consolidación / sueño) y su costo constante:
 Agujas candidatas (regla 0–1, costo, AUC en el banco, auto-regulación):
 Piso a mano (fórmula exacta y cómo se eligió):
 Fuente de verdad para entrenar o calibrar (autoexamen / memorias de fábrica):
 Examen que NUNCA ve (guardia, memoria fuera, preguntas humanas):
 Techo y parada:
 Regla de ascenso (piso, guardia, campeón, margen):
 Capas de protección y sus pruebas:
 Interruptor de apagado:
 Línea base de QA (antes) → QA después, caso a caso; FP; GATE; sha del snapshot:
 Qué NO toca (ranking, enlaces manuales, recuerdos):

───────────────────────────────────────────────────────────────────────────────
12. LUGARES CANDIDATOS PARA LAS PRÓXIMAS NEURONAS (exp 10 §7 y exp 13)
───────────────────────────────────────────────────────────────────────────────
 1. Asociativa en el canal 2: elegir qué asociaciones ve el agente. No toca el
    ranking. Medido: los visibles buenos/malos pasan de 5/8 a 9/1 con fuerza ≥ .50.
 2. Reemplazar a la hormiguita: modo aprendiz → relevo → retiro, por etapas.
 3. Revisar sinónimos y proponer enlaces que faltan: 12 de 15 propuestas fueron
    buenas en la hoja.
 4. Saltos del grafo: qué vecinos traer. Va DESPUÉS de limpiar el grafo (un salto
    ciego trae ~215 candidatos por 1 bueno).
 5. Largo de la lista, y qué capas del motor correr por consulta.
 Ideas para después: una práctica alimenta a todas las neuronas; retadora de
 fábrica; mielina; neurogénesis controlada (una "hija" nace como retadora y muere
 si no gana su examen); costo fijo de K cosas por ciclo para millones de recuerdos.

───────────────────────────────────────────────────────────────────────────────
13. TAXONOMÍA COMPLETA DE TIPOS DE NEURONAS (ARQUITECTURA Y PROPÓSITO)
───────────────────────────────────────────────────────────────────────────────

Esta sección extiende la distinción básica VIVA vs CERRADA (sección 0) con una taxonomía
completa basada en arquitectura, objetivo, y modo de aprendizaje. Cada neurona nueva
DEBE clasificarse aquí antes de escribir código.

┌────────────────────────────────────────────────────────────────────────────────────┐
│ TIPO                        │ ARQUITECTURA          │ APRENDE    │ CASO DE USO BIORAG         │
├─────────────────────────────┼───────────────────────┼────────────┼──────────────────────────┤
│ 1. RANKING / RE-RANKER      │ MLP 29→6→1 logit-add  │ Online     │ Neurona 1: reordenar top-k │
│    (VIVA, listwise)         │ + capas protección    │ por DB     │ en búsqueda              │
├─────────────────────────────┼───────────────────────┼────────────┼──────────────────────────┤
│ 2. SCORING / REGRESIÓN      │ MLP 15→6→1 logit-add  │ Factory    │ Neurona asociativa:        │
│    (CERRADA, pairwise)      │ + homeostasia         │ only       │ fuerza sinapsis 0-1        │
├─────────────────────────────┼───────────────────────┼────────────┼──────────────────────────┤
│ 3. GATING / CLASIFICACIÓN   │ MLP pequeña + sigmoid │ Online/    │ Decidir: ¿nace sinapsis?   │
│    BINARIA                  │ (umbral calibrado)    │ Factory    │ ¿pasa a canal 2? ¿consolida?│
├─────────────────────────────┼───────────────────────┼────────────┼──────────────────────────┤
│ 4. SELECTION / TOP-K        │ Scoring + argmax/     │ Online     │ Elegir K vecinos,          │
│    (policy network)         │ beam search           │ por DB     │ qué saltos del grafo traer │
├─────────────────────────────┼───────────────────────┼────────────┼──────────────────────────┤
│ 5. GENERATIVE / AUTOENCODER │ Encoder-decoder       │ Factory/   │ Examen de rescate,         │
│    (masked prediction)      │ (reconstruir ranking) │ Online     │ completar patrones         │
├─────────────────────────────┼───────────────────────┼────────────┼──────────────────────────┤
│ 6. CONTRASTIVE / EMBEDDING  │ Siamese / triplet     │ Factory    │ Aprender similitud         │
│    LEARNING                 │ loss (InfoNCE)        │ + fine-tune│ invariante entre pares     │
├─────────────────────────────┼───────────────────────┼────────────┼──────────────────────────┤
│ 7. POLICY / ACTOR-CRITIC    │ Actor (acción) +      │ Online RL  │ Controlar presupuesto      │
│    (neuroevolución híbrida) │ Critic (valor)        │ / ES       │ consolidación, poda        │
├─────────────────────────────┼───────────────────────┼────────────┼──────────────────────────┤
│ 8. HEBBIAN / LOCAL          │ Regla local           │ Online     │ Plasticidad sináptica      │
│    (STDP, Oja, BCM)         │ (Δw = f(pre, post))   │ continua   │ biológicamente fiel        │
└─────────────────────────────┴───────────────────────┴────────────┴──────────────────────────┘

NOTA CRÍTICA: En BioRAG hoy SOLO existen tipos 1 y 2 implementados. Los tipos 3-8 son
candidatos para neuronas futuras (sección 12). Cada tipo requiere su propio molde de
protección (sección 7) y examen (sección 4).

⚠️ **ACLARACIÓN IMPORTANTE — ESTA TAXONOMÍA NO ES EXHAUSTIVA DEL CAMPO:**
Los 8 tipos arriba son una **clasificación operativa para BioRAG** (lo que cabe en nuestro
motor: SQLite + numpy, sin GPU, costo fijo, determinista). En el mundo de la IA/ML
existen **decenas de paradigmas más**: Transformers, Diffusion, RNNs/LSTMs/GRUs,
Graph Neural Networks (GNNs), Spiking Neural Networks, Liquid Time-Constant Networks,
Neuromodulated plasticity, Meta-learning (MAML, Reptile), Hypernetworks, Neural ODEs,
Reservoir Computing, Echo State Networks, y muchos más. **No están aquí porque:**
(a) requieren GPU/entorno pesado, (b) no son deterministas en CPU, (c) no encajan en
el molde "piso + corrección + guardia" de BioRAG, (d) el costo no es fijo.
**Si tu problema encaja en otro paradigma → CONSULTA INTERNET (sección 19) y evalúa
si vale la pena adaptar el motor o crear infraestructura nueva.** La Regla 0-Q de
Dennys aplica: "Si faltaba una herramienta, se construye. La limitación no existe."

───────────────────────────────────────────────────────────────────────────────
13.1. NEUROEVOLUCIÓN / EVOLUTION STRATEGIES (GUÍA PRÁCTICA DETALLADA)
───────────────────────────────────────────────────────────────────────────────

**Esto ES tu "circuito de 200 carros".** Lo que describes es **Neuroevolución pura**:
una población de redes neuronales (cada carro = una red con pesos distintos) que
compiten en un entorno (el circuito), los que llegan más lejos se seleccionan, se
mutan/cruzan para crear la siguiente generación, y así hasta que emergen redes que
completan el circuito **aprendiendo la política, no memorizándolo**.

En BioRAG esto se usa en **Caso 4 (Selection/TOP-K)** y **Caso 7 (Policy/RL híbrido)**.
Aquí la guía práctica completa para cuando la elijas.

═══════════════════════════════════════════════════════════════════════════════
¿QUÉ VARIANTE USAR? (Árbol de decisión dentro de Neuroevolución)
═══════════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────────────┐
│ 1. ¿El espacio de búsqueda es ALTA DIMENSIÓN (>100 params) y                    │
│    la función de fitness es RUIDOSA / NO diferenciable?                         │
│    → SÍ: **Sep-CMA-ES** (Covariance Matrix Adaptation Evolution Strategy,       │
│       separable/diagonal). Es el ESTÁNDAR ORO actual.                           │
│       Papers: Ros & Hansen 2008; NeuroEvoBench 2023 (top para LED);            │
│       Sep-CMA-ES-LED 2022 (adapta hyperparámetros por signal-to-noise).         │
│    → NO (dimensión baja <50, fitness suave): **CMA-ES completo** o **OpenAI-ES**│
├─────────────────────────────────────────────────────────────────────────────────┤
│ 2. ¿Necesitas OPTIMIZAR ARQUITECTURA (topología, capas, conexiones) no solo     │
│    pesos?                                                                        │
│    → SÍ: **NEAT** (NeuroEvolution of Augmenting Topologies, Stanley 2002)       │
│       o **HyperNEAT** (para patrones geométricos/regulares).                    │
│       En BioRAG: solo si la neurona debe CRECER su estructura (neurogénesis).   │
│    → SOLO PESOS: Sep-CMA-ES / PGPE / SNES / ARS.                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 3. ¿El fitness es DISCRETO / NO diferenciable (R@1, NDCG, exact match,         │
│    tarea completada sí/no)?                                                     │
│    → SÍ: **Evolution Strategies (ES)** — optimizan fitness DIRECTO,             │
│       sin gradiente. **Sep-CMA-ES con fitness shaping rank-based**              │
│       (z-score → ranks → normalizado) es lo más robusto.                       │
│    → NO (fitness diferenciable): **Gradiente (AdamW) + ES híbrido**             │
│       (Plan Paso 4 §9.1: "dos retadores, mismo juez").                          │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 4. ¿Presupuesto de evaluaciones MUY LIMITADO (<1000 evals totales)?             │
│    → SÍ: **Bayesian Optimization** (GP/Random Forest surrogate) + ES            │
│       o **ARS** (Augmented Random Search) — muy sample-efficient.              │
│    → Presupuesto amplio (>5000): **Sep-CMA-ES población 20-40, 100+ gens**.    │
└─────────────────────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════
ARQUITECTURA DE LA RED QUE EVOLUCIONA (Hidden layers, neuronas, entradas)
═══════════════════════════════════════════════════════════════════════════════

Para BioRAG (CPU, numpy, determinista, costo fijo), la red que evoluciona es **pequeña**.
Regla de oro: **Menos parámetros = más sample-efficient = converge más rápido.**

┌─────────────────────────────────────────────────────────────────────────────────┐
│ ESCENARIO                          │ ENTRADAS (agujas) │ CAPAS OCULTAS          │
│                                    │ (tamaño input)    │ NEURONAS / CAPA        │
├────────────────────────────────────┼───────────────────┼────────────────────────┤
│ Scoring sinapsis (par A,B)         │ 12-15             │ 1 capa: 6-8            │
│    (Caso 2, Neurona asociativa)    │                   │ (15→6→1 actual)        │
├────────────────────────────────────┼───────────────────┼────────────────────────┤
│ Re-ranking top-k (query, cand)     │ 29                │ 1 capa: 6              │
│    (Caso 1, Neurona ranking)       │                   │ (29→6→1 actual)        │
├────────────────────────────────────┼───────────────────┼────────────────────────┤
│ Gating binario (¿nace sinapsis?)   │ 8-12              │ 1 capa: 4-6            │
│    (Caso 3)                        │                   │ MLP pequeña + sigmoid  │
├────────────────────────────────────┼───────────────────┼────────────────────────┤
│ Policy: elegir K vecinos (A, cands)│ 15-20 por candi-  │ 1-2 capas: 8-16 → 4-8  │
│    dato (Caso 4)                   │                   │ (scoring network)      │
├────────────────────────────────────┼───────────────────┼────────────────────────┤
│ Actor-Critic (Caso 7)              │ Estado: 10-20     │ Actor: 1 capa 16-32    │
│                                    │                   │ Critic: 1 capa 16-32   │
├────────────────────────────────────┼───────────────────┼────────────────────────┤
│ Hebbian local (Caso 8)             │ N/A (regla local) │ N/A (sin red)          │
└────────────────────────────────────┴───────────────────┴────────────────────────┘

**PRINCIPIOS DE DISEÑO (validados en experimentos BioRAG):**

1. **UNA SOLA CAPA OCULTA basta para XOR-like problems** (BioRAG: hub ayuda si no
   hay literal, estorba si hay literal). Dos capas solo si hay evidencia empírica.
2. **Tamaño oculto estrecho (heurística inicial, no regla rígida):** con 12–29 agujas,
   en BioRAG se empieza por **6–8 neuronas ocultas** (cuello de botella más estrecho
   que el input, como `29→6→1` y `15→6→1`) para frenar el overfitting en la guardia.
   Más grande solo si la validación muestra subajuste; siempre medir antes de fijar.
3. **Activación: tanh** (centrada en 0 y acotada en `[-1, 1]`).
   Esto estabiliza la corrección acotada en espacio logit y evita salidas explosivas
   (ReLU no está acotada; sigmoid no está centrada en 0). Nota: en ES puro no hay
   gradientes, así que la ventaja de `tanh` ahí es el rango acotado y centrado, no
   «evitar gradientes cero». **tanh es el default BioRAG.**
4. **Salida: corrección en espacio LOGIT** (logit(p) = logit(piso) + v·tanh(W·x+b)).
   Esto garantiza que con pesos=0 → salida = piso exacto (cold-start perfecto).
5. **Inicialización: Xavier/Glorot para tanh** (var = 2/(fan_in + fan_out)).
   En ES: población inicial = piso + ruido gaussiano pequeño (σ=0.1).

═══════════════════════════════════════════════════════════════════════════════
HIPERPARÁMETROS NEUROEVOLUCIÓN (Sep-CMA-ES) — VALORES DE PARTIDA BIO-RAG
═══════════════════════════════════════════════════════════════════════════════

Estos son **valores de partida probados**. Ajustar SOLO tras medir en guardia.

┌─────────────────────────────────────────────────────────────────────────────────┐
│ PARÁMETRO                    │ VALOR INICIAL     │ RANGO EXPLORAR      │ NOTA  │
├──────────────────────────────┼───────────────────┼─────────────────────┼───────┤
│ Población (λ)                │ 20-30             │ 10-50               │ LED:  │
│                              │                   │                     │ usa   │
│                              │                   │                     │ menos │
├──────────────────────────────┼───────────────────┼─────────────────────┼───────┤
│ Padres (μ)                   │ λ // 2            │ λ/3 a λ/2           │ élite │
├──────────────────────────────┼───────────────────┼─────────────────────┼───────┤
│ Sigma inicial (σ₀)           │ 0.5               │ 0.2-1.0             │ paso  │
│                              │                   │                     │ mutac │
├──────────────────────────────┼───────────────────┼─────────────────────┼───────┤
│ Fitness shaping              │ Rank-based        │ z-score / rank /    │ Rank  │
│                              │ (normalizado)     │ raw                 │ =robus│
├──────────────────────────────┼───────────────────┼─────────────────────┼───────┤
│ Elitismo                     │ SÍ (mejor 1-2)    │ 1-5                 │ nunca │
│                              │                   │                     │ pierda│
├──────────────────────────────┼───────────────────┼─────────────────────┼───────┤
│ Generaciones por ciclo       │ 50-100            │ 30-200              │ costo │
│                              │                   │                     │ fijo  │
├──────────────────────────────┼───────────────────┼─────────────────────┼───────┤
│ Evaluaciones por gen         │ λ (paralelizable) │ λ                   │ en RAM│
├──────────────────────────────┼───────────────────┼─────────────────────┼───────┤
│ Early stopping               │ 20 gens sin mejora│ 10-30               │ gap   │
│                              │ en guardia        │                     │ train │
├──────────────────────────────┼───────────────────┼─────────────────────┼───────┤
│ Semillas ensemble            │ 3 (7, 11, 23)     │ 3-5                 │ misma │
│                              │                   │                     │ guardia│
├──────────────────────────────┼───────────────────┼─────────────────────┼───────┤
│ Temperature scaling          │ SÍ (post-hoc)     │ T ∈ [0.5, 2.0]      │ calib │
│                              │                   │                     │ración │
└──────────────────────────────┴───────────────────┴─────────────────────┴───────┘

**LED (Low Effective Dimensionality):** Si tus agujas están correlacionadas
(S, X, B suelen correlacionarse), **Sep-CMA-ES-LED** (IEEE 2022) adapta
hyperparámetros por dimensión usando signal-to-noise ratio. **Úsalo si input > 15.**

═══════════════════════════════════════════════════════════════════════════════
MINI-GUÍA: ¿QUÉ AGUJAS USAR SEGÚN EL ESCENARIO? (Feature Engineering)
═══════════════════════════════════════════════════════════════════════════════

La neuroevolución **solo es tan buena como las features (agujas) que le das**.
Si las agujas no separan lo bueno de lo malo, ES no lo arregla — aprende ruido.

┌─────────────────────────────────────────────────────────────────────────────────┐
│ PROBLEMA A RESOLVER                    │ AGUJAS RECOMENDADAS (prioridad)        │
├────────────────────────────────────────┼────────────────────────────────────────┤
│ "¿Nace esta sinapsis A→B?"             │ 1. S (dimensiones/sustantivos shared)  │
│ (Gating binario, Caso 3)               │ 2. X (cobertura cruzada reciproca)     │
│                                        │ 3. rareza_max (giro dentado)           │
│                                        │ 4. tipo_sinapsis (one-hot + prioridad) │
│                                        │ 5. episodio_auto (auto-regulado)       │
├────────────────────────────────────────┼────────────────────────────────────────┤
│ "Fuerza 0-1 de relación A↔B"           │ 1. S_idf (dimensiones pesadas IDF)     │
│ (Scoring regresión, Caso 2)            │ 2. X_refinada (concepto/sustantivos/   │
│                                        │    contenido separados, reciproca min) │
│                                        │ 3. B (bridges agente cruzados)         │
│                                        │ 4. K (competencia intra-nodo)          │
│                                        │ 5. hub_resta / una_sola_resta          │
├────────────────────────────────────────┼────────────────────────────────────────┤
│ "Reordenar top-k para query Q"         │ 1. BM25 + convergencia + evidencia     │
│ (Listwise LTR, Caso 1)                 │ 2. sustantivos_clave agente            │
│                                        │ 3. PPMI + SVD coseno                   │
│                                        │ 4. Jaccard dimensional 13 ejes         │
│                                        │ 5. peso_sinaptico + hub_match          │
├────────────────────────────────────────┼────────────────────────────────────────┤
│ "Elegir K mejores vecinos de A"        │ 1. Scoring network (par A,cand → score)│
│ (Policy Selection, Caso 4)             │ 2. MMR (diversidad: penaliza vecinos   │
│                                        │    redundantes entre sí)               │
│                                        │ 3. G_ciego (engrama: vecinos compartidos│
│                                        │    en búsqueda ciega)                  │
│                                        │ 4. latente_local_2_saltos (solo agente)│
├────────────────────────────────────────┼────────────────────────────────────────┤
│ "Controlar sueño/consolidación/poda"   │ 1. Estado actual grafo (densidad,      │
│ (Actor-Critic, Caso 7)                 │    clusters, hubs)                     │
│                                        │ 2. Presupuesto restante (ms, KB)       │
│                                        │ 3. Historial reciente (qué funcionó)   │
│                                        │ 4. Violaciones Pilar 12 detectadas     │
│                                        │ 5. Valencia somática nodos críticos    │
├────────────────────────────────────────┼────────────────────────────────────────┤
│ "Plasticidad local continua"           │ 1. pre_activity, post_activity         │
│ (Hebbian/STDP, Caso 8)                 │ 2. eligibility_trace (τ decaimiento)   │
│                                        │ 3. third_factor = RPE (autoexamen)     │
│                                        │ 4. homeostatic_target (suma pesos)     │
└────────────────────────────────────────┴────────────────────────────────────────┘

**REGLA DE ORO AGUJAS:** Cada aguja debe superar el umbral **fijado antes de medir**
en su protocolo (por ejemplo, AUC ≥ 0.60–0.65 con IC95 > 0.50 en el banco de
calibración, sección 5 PASO 5). Si no separa ni aporta sobre el piso → NO ENTRA.
Mide ANTES de dar a la neurona y nunca muevas el umbral después de ver los datos.

═══════════════════════════════════════════════════════════════════════════════
CUÁNDO NEUROEVOLUCIÓN FALLA (Anti-patrones) Y QUÉ HACER
═══════════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────────────┐
│ SÍNTOMA                          │ CAUSA RAÍZ                    │ ACCIÓN        │
├──────────────────────────────────┼───────────────────────────────┼───────────────┤
│ Fitness mejora en train,         │ Overfitting / memorización    │ 1. Aumenta    │
│ guardia NO mejora (gap > 5%)     │                               │    guardia a  │
│                                  │                               │    30%        │
│                                  │                               │ 2. Reduce σ₀  │
│                                  │                               │ 3. Early stop │
│                                  │                               │    más agresivo│
├──────────────────────────────────┼───────────────────────────────┼───────────────┤
│ Población converge prematuramente│ Diversidad insuficiente       │ 1. Aumenta σ₀ │
│ (todos iguales, fitness plano)   │ (σ colapsa)                   │ 2. Añade noise│
│                                  │                               │    a fitness  │
│                                  │                               │ 3. Reinicia   │
│                                  │                               │    población  │
├──────────────────────────────────┼───────────────────────────────┼───────────────┤
│ Mejora en guardia pero           │ Distribution shift            │ 1. Valida en  │
│ FALLA en DB nueva / humanos      │ (train ≠ real)                │    DB distinta│
│                                  │                               │ 2. Añade ruido│
│                                  │                               │    a inputs   │
│                                  │                               │ 3. Domain rand│
├──────────────────────────────────┼───────────────────────────────┼───────────────┤
│ Costo explota (gens × λ × eval)  │ Fitness evaluation lento      │ 1. Cache eval │
│                                  │                               │ 2. Reduce λ   │
│                                  │                               │ 3. Surrogate  │
│                                  │                               │    model (BO) │
├──────────────────────────────────┼───────────────────────────────┼───────────────┤
│ Pesos NaN / Inf / explotan       │ Gradientes numéricos inestables│ 1. Clip grad  │
│                                  │                               │    (solo grad)│
│                                  │                               │ 2. Bounded act│
│                                  │                               │    (tanh OK)  │
│                                  │                               │ 3. Weight     │
│                                  │                               │    decay L2   │
└──────────────────────────────────┴───────────────────────────────┴───────────────┘

═══════════════════════════════════════════════════════════════════════════════
ESQUELETO ILUSTRATIVO EN NUMPY (NO ES IMPLEMENTACIÓN COMPLETA DE PRODUCCIÓN)
═══════════════════════════════════════════════════════════════════════════════

> **Nota:** Este bloque muestra únicamente la estructura `ask/tell` y el fitness
> shaping por rango; **omite** las ecuaciones de actualización de `pc`, `ps`, `C`
> y `sigma`. No lo copies tal cual esperando que funcione completo: usa una
> implementación completa y probada (por ejemplo `cma` / `pycma`, o escribe y
> testea todas las actualizaciones con RNG explícito por semilla).

```python
# Esqueleto ilustrativo Sep-CMA-ES (con RNG explícito por semilla)
import numpy as np

class SepCMAES:
    def __init__(self, dim, sigma0=0.5, popsize=None, seed=7):
        self.dim = dim
        self.sigma = sigma0
        self.rng = np.random.default_rng(seed)
        self.popsize = popsize or (4 + int(3 * np.log(dim)))  # λ
        self.mu = self.popsize // 2
        self.weights = np.log(self.mu + 0.5) - np.log(np.arange(1, self.mu + 1))
        self.weights /= self.weights.sum()
        self.mueff = 1 / (self.weights**2).sum()
        # Estrategia separable: solo diagonales de C
        self.pc = np.zeros(dim)
        self.ps = np.zeros(dim)
        self.C = np.ones(dim)  # diagonal de covarianza
        self.chi_n = np.sqrt(dim) * (1 - 1/(4*dim) + 1/(21*dim**2))
        
    def ask(self, mean):
        """Genera λ candidatos: mean + σ * N(0, C)"""
        z = self.rng.standard_normal((self.popsize, self.dim))
        return mean + self.sigma * z * np.sqrt(self.C)
    
    def tell(self, solutions, fitness):
        """Actualiza media, sigma, C con ranking (esqueleto incompleto)"""
        idx = np.argsort(fitness)  # menor fitness = mejor (minimizar)
        # Fitness shaping rank-based:
        ranks = np.argsort(idx) + 1
        utilities = np.maximum(0, np.log(self.mu + 0.5) - np.log(ranks))
        utilities /= utilities.sum()
        utilities -= 1/self.popsize
        # Faltan: actualización completa de mean, pc, ps, C y sigma (ver pycma)
        raise NotImplementedError("Completar actualizaciones CMA-ES antes de usar")
```

**Para producción:** usa `cma` (pip install cma) — es la implementación de referencia
de Nikolaus Hansen. En BioRAG: `BIORAG_NEUROEVOLUTION=1` habilita; `=0` apaga.

───────────────────────────────────────────────────────────────────────────────
19. PROTOCOLO OBLIGATORIO: CONSULTA A INTERNET (MCP) PARA INVESTIGACIÓN DE VANGUARDIA
═══════════════════════════════════════════════════════════════════════════════

**REGLA INQUEBRANTABLE:** La guía documenta LO PROBADO EN BIORAG. El campo avanza
semanalmente. **Antes de diseñar una neurona nueva, SIEMPRE consulta internet.**

┌─────────────────────────────────────────────────────────────────────────────────┐
│ CUÁNDO CONSULTAR (siempre que ocurra UNO de estos):                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│ ✓ Nueva arquitectura / paradigma no cubierto en secciones 13-14                │
│ ✓ Paper reciente (últimos 12 meses) que promete mejora relevante               │
│ ✓ Benchmark nuevo (NeuroEvoBench, DomainBed, LTR benchmarks)                   │
│ ✓ Problema atascado > 2 ciclos sin mejora en guardia                           │
│ ✓ Decisión de "construir vs comprar vs adaptar" (Regla 0-Q Dennys)             │
│ ✓ Validar que tu enfoque no fue refutado recientemente                         │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│ CÓMO CONSULTAR (herramientas MCP disponibles):                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 1. **parallel-search** (recomendado para investigación multi-fuente):          │
│    tools["parallel-search"].web_search({                                       │
│      objective: "pregunta específica técnica",                                 │
│      search_queries: ["query1", "query2", "query3"]  # 3-5 variaciones        │
│    })                                                                          │
│                                                                                │
│ 2. **firecrawl** (para papers, docs técnicos, GitHub):                         │
│    tools["firecrawl"].firecrawl_search({                                       │
│      query: "términos exactos",                                                │
│      categories: ["research", "developer"]  # papers + code                   │
│    })                                                                          │
│                                                                                │
│ 3. **websearch** (búsqueda general):                                           │
│    tools.websearch({ query: "..." })                                           │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│ PLANTILLA DE CONSULTA EFECTIVA (copia y adapta):                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│ objective: "Estado del arte 2024-2025 para [TU PROBLEMA ESPECÍFICO]            │
│   en [CONTEXTO: CPU-only, numpy, determinista, costo fijo, BioRAG]"            │
│ search_queries: [                                                               │
│   "[término técnico principal] 2024 2025",                                     │
│   "[paradigma] benchmark comparison",                                          │
│   "[problema específico] solution numpy CPU",                                  │
│   "[método] vs [método alternativo] sample efficiency",                        │
│   "recent advances [dominio] synaptic plasticity memory"                       │
│ ]                                                                              │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│ QUÉ BUSCAR EN RESULTADOS (filtro rápido):                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│ ✓ Paper con código abierto (GitHub link) → reproducible                        │
│ ✓ Benchmark en entorno similar (CPU, sample-efficient, determinista)           │
│ ✓ Comparación honesta (reporta fracasos, no solo éxitos)                       │
│ ✓ Código en numpy/PyTorch/JAX ligero (no requiere cluster GPU)                 │
│ ✓ Licencia compatible (MIT, Apache, BSD) si vas a integrar                     │
│ ✗ Solo teórico sin experimentos → descartar                                     │
│ ✗ Requiere GPU masiva / TPU / cluster → no encaja en BioRAG                    │
│ ✗ Licencia restrictiva (GPL, comercial) → evaluar coste legal                  │
└─────────────────────────────────────────────────────────────────────────────────┘

**FLUJO OBLIGATORIO TRAS CONSULTA:**
1. Ejecuta búsqueda MCP (parallel-search preferido)
2. Lee 3-5 fuentes top (papers, benchmarks, código)
3. Extrae: método, hiperparámetros, métricas, limitaciones, código disponible
4. **Documenta en BioRAG** con `biorag_aprender` (concepto, contenido, dimensiones,
   syn, cat=Lesson, predicados=[{sujeto: "Athena-OEC", accion: "investiga", ...}])
5. Decide: (a) adaptar a BioRAG, (b) prototipar en rama aislada, (c) descartar
6. Si (a) o (b) → actualiza GUIA_CREAR_UNA_NEURONA.md con hallazgos
7. Conversa con Dennys ANTES de medir (sección 11 ficha)

═══════════════════════════════════════════════════════════════════════════════
EJEMPLO REAL: TU CASO "200 CARROS EN CIRCUITO" → NEUROEVOLUCIÓN APLICADA
═══════════════════════════════════════════════════════════════════════════════

**Mapeo exacto a BioRAG:**

| Concepto "Carros"           | Equivalente BioRAG                    |
|----------------------------|---------------------------------------|
| Carro = red neuronal       | Candidato de pesos (vector θ)         |
| Circuito = entorno         | Examen de rescate / función fitness   |
| Chocar = fallar            | Violación guardia / bajo R@1          |
| Llegar lejos = fitness     | R@1/R@5 en guardia sellada            |
| Selección + mutación       | Sep-CMA-ES (mean + σ·N(0,C))          |
| 200 carros = población λ   | λ = 20-40 (sample-efficient)          |
| Generaciones = ciclos      | 50-100 gens por ciclo de sueño        |
| Aprender curva, no memorizar| Generaliza a DB nueva (guardia + externa)|

**Para tu caso (sinapsis, recuerdo, recuperación):**
- Fitness = **examen de rescate** (B pregunta, A responde: puesto de B en vecinos de A)
- Red que evoluciona = **scoring network** (par A,B → score 0-1) o **policy** (estado → acción)
- Agujas = **S, X, B, K, tipo, rareza** (sección 13.1 tabla "Qué agujas usar")
- Guardia = **20% hash determinista + DB externa nunca vista**
- Anti-memorización = **gap train/guardia ≤ 5% + early stopping + ensemble 3 seeds**

**Esto YA está implementado en el plan:** Paso 4 §9.1 "Dos retadores, mismo juez:
(a) Gradiente (AdamW) + (b) Neuroevolución (Sep-CMA-ES) optimizando R@1/R@5 directo".

═══════════════════════════════════════════════════════════════════════════════
FIN DE EXPANSIÓN — LA GUÍA CRECE CON CADA NEURONA NUEVA
═══════════════════════════════════════════════════════════════════════════════

───────────────────────────────────────────────────────────────────────────────
14. MÉTODOS DE ENTRENAMIENTO POR CASO DE USO (GUÍA DE SELECCIÓN)
───────────────────────────────────────────────────────────────────────────────

Esta es la sección MÁS IMPORTANTE para elegir el algoritmo correcto. Lee la tabla
entera antes de decidir.

════════════════════════════════════════════════════════════════════════════════
CASO 1: TIENES VERDAD GRATIS POR CONSTRUCCIÓN (AUTO-SUPERVISADO)
═══════════════════════════════════════════════════════════════════════════════
Situación: Cada muestra genera su propia etiqueta correcta. No hay anotación humana.
Ejemplos BioRAG: Examen de rescate (B pregunta, A responde), Masked autoencoding en grafo.

┌─────────────────────────────────────────────────────────────────────────────────┐
│ MÉTODO RECOMENDADO: LISTWISE LEARNING-TO-RANK CON AUTOEXAMEN                   │
│ (Lo que usa Neurona 1 - core/memory/neurona.py)                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│ Algoritmo base:  Softmax cross-entropy sobre pool completo por pregunta        │
│                  (ListNet / ListMLE / LambdaLoss framework)                    │
│ Arquitectura:    Piso (fórmula a mano) + MLP corrección en espacio logit       │
│                  logit(p) = logit(piso) + v·tanh(W·x + b)                      │
│ Optimizador:     AdamW, lr=0.03, L2=1e-3, cosine decay, input noise/dropout   │
│ Partición:       POR RECUERDO (nunca mismo nodo en train/test)                 │
│ Guardia:         20% por hash determinista (sha256(nombre)[:8] % 5 == 0)       │
│ Calibración:     Platt scaling / isotonic regression en validación             │
│ Early stopping:  Paciencia 12 ciclos; anti-memorización (gap train/guard > 5%)│
│ Ensemble:        3-5 semillas (7, 11, 23) + temperature scaling                │
├─────────────────────────────────────────────────────────────────────────────────┤
│ CUÁNDO USAR:                                                                  │
│ ✓ Cada muestra (recuerdo/consulta) genera su examen con respuesta conocida    │
│ ✓ La verdad es "¿qué posición debería tener X en la lista de Y?"             │
│ ✓ Necesitas explicabilidad aguja por aguja (pesos = importancia)              │
│ ✓ Debe arrancar EXACTAMENTE desde piso humano (cero cold-start)               │
│ ✓ Online learning en cada DB individual (distribución propia)                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│ PAPERS CLAVE (2020-2025):                                                     │
│ • "LambdaLoss: A Probabilistic Framework for Ranking Metric Optimization"     │
│   (Wang et al., CIKM 2018) — base teórica optimización NDCG                   │
│ • "ListNet: A Listwise Approach to Learning to Rank" (Cao et al., ICML 2007)  │
│ • "Self-Supervised Learning to Rank via Masked Autoencoding" (Zhuang et al.,  │
│   SIGIR 2023) — masked prediction para ranking                                │
│ • "Behavioral Timescale Synaptic Plasticity" (Milstein et al., Nature 2025)   │
│   — base biológica: "tercer factor" = utilidad medida = dopamina              │
│ • "Continual Learning to Rank" (Zhang et al., WSDM 2024) — online LTR         │
└─────────────────────────────────────────────────────────────────────────────────┘

════════════════════════════════════════════════════════════════════════════════
CASO 2: TIENES DATOS DE FÁBRICA CON VERDAD CONOCIDA (SUPERVISADO CERRADO)
════════════════════════════════════════════════════════════════════════════════
Situación: Corpus públicos con etiquetas de verdad fundamentada (ground truth).
No aprendes del usuario; calibras una vez y deployas congelado.
Ejemplos BioRAG: Neurona asociativa (core/neurona_asociativa.py) - "¿A y B tienen que ver?"

┌─────────────────────────────────────────────────────────────────────────────────┐
│ MÉTODO RECOMENDADO: PAIRWISE LEARNING-TO-RANK CON COMPETENCIA INTRA-NODO       │
│ (Lo que usa Neurona Asociativa - experimento_11)                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│ Algoritmo base:  Pairwise logistic loss / RankNet / LambdaRank gradients       │
│                  optimizando AUC / NDCG dentro de cada nodo origen              │
│ Arquitectura:    Piso (pesos enteros calibrados) + MLP 15→6→1 corrección       │
│                  logit(p) = logit(piso) + v·tanh(W·x + b), techo ±1 logit      │
│ Datos fábrica:   Múltiples corpus (Reuters, WordNet, Brown, código, chat,      │
│                  noticias ES, literatura PT) — split por documento/tema        │
│ Partición:       3 vías POR DOCUMENTO: Estudio / Validación-Calib / Guardia 20%│
│                  + grupo externo nunca visto (dominio distinto)                │
│ Auto-regulación: Features con fiabilidad incierta (episodio, etiquetas)        │
│                  se multiplican por fiabilidad medida en ESTA memoria (0-1)    │
│ Homeostasia:     Memoria que va peor recibe más muestras de entrenamiento      │
│ Guardia:         20% POR MEMORIA (no global); NUNCA BAJO PISO en CADA memoria  │
│                  Si ninguna versión pasa en todas → neurona APAGADA (escala 0) │
├─────────────────────────────────────────────────────────────────────────────────┤
│ CUÁNDO USAR:                                                                  │
│ ✓ Tarea es universal ("similitud semántica", "fuerza de relación")            │
│ ✓ Aprender del usuario = memorizar ruido (decisión Dennys)                    │
│ ✓ Tienes acceso a corpus públicos diversos con verdad conocida                │
│ ✓ Necesitas garantías de generalización cross-domain                          │
│ ✓ Deploy "nacido listo" — cero latencia de cold-start en DB nueva             │
├─────────────────────────────────────────────────────────────────────────────────┤
│ PAPERS CLAVE (2020-2025):                                                     │
│ • "Domain Generalization for Learning to Rank" (Zhu et al., SIGIR 2021)       │
│ • "Out-of-Distribution Generalization in Neural Ranking" (MacAvaney et al.,   │
│   SIGIR 2022)                                                                  │
│ • "Continual Learning for Neural Ranking Models" (Xiong et al., CIKM 2023)    │
│ • "Neural Ranking Models with Frozen Features" (Lin et al., WWW 2024)         │
│ • "Robust Ranking with Label Noise" (Wang et al., ICML 2024) — etiquetas      │
│   gruesas vs finas (regla: "etiquetas más gruesas que la verdad")             │
└─────────────────────────────────────────────────────────────────────────────────┘

════════════════════════════════════════════════════════════════════════════════
CASO 3: DECISIÓN BINARIA CON UMBRAL (GATING / CLASIFICACIÓN)
════════════════════════════════════════════════════════════════════════════════
Situación: Sí/No — ¿nace esta sinapsis? ¿pasa al canal 2? ¿consolida esta memoria?
Ejemplos BioRAG futuros: Neurona tipo 3 (sección 13) - reemplazar reglas fijas de nacimiento.

┌─────────────────────────────────────────────────────────────────────────────────┐
│ MÉTODO RECOMENDADO: CALIBRATED BINARY CLASSIFICATION CON UMBRAL ÓPTIMO         │
├─────────────────────────────────────────────────────────────────────────────────┤
│ Algoritmo base:  Logistic regression / MLP pequeña + sigmoid                   │
│                  Pérdida: Focal loss (clase desbalanceada) o BCE ponderada     │
│                  Calibración OBLIGATORIA: Platt scaling / Isotonic regression  │
│                  Umbral: Optimizado en validación (Youden's J / F1 máx /       │
│                  coste asimétrico FP vs FN)                                    │
│ Arquitectura:    Piso = regla heurística actual (ej. "co_ocurrencia ≥ 3")      │
│                  Neurona = corrección calibrada que SOLO decide umbral         │
│ Partición:       Estratificada por clase + guardia 20% hash                    │
│ Métricas:        AUC-ROC, AUC-PR, Precision@Recall=0.9, F1, Brier score       │
│                  CALIBRACIÓN: ECE (Expected Calibration Error) < 0.02         │
├─────────────────────────────────────────────────────────────────────────────────┤
│ CUÁNDO USAR:                                                                  │
│ ✓ Decisión es binaria con consecuencias asimétricas (FP ≠ FN)                │
│ ✓ Necesitas probabilidad CALIBRADA (no solo score) para combinar con otras    │
│   neuronas / reglas                                                            │
│ ✓ El umbral DEBE ser interpretable y ajustable por Dennys                     │
│ ✓ Online (por DB) o Factory según si criterio depende de distribución local   │
├─────────────────────────────────────────────────────────────────────────────────┤
│ PAPERS CLAVE:                                                                 │
│ • "On Calibration of Modern Neural Networks" (Guo et al., ICML 2017)          │
│   — Temperature scaling, ECE                                                  │
│ • "Focal Loss for Dense Object Detection" (Lin et al., ICCV 2017)             │
│ • "Threshold Optimization for Binary Classification" (Kull et al., 2017)      │
│ • "Conformal Prediction for Calibrated Classification" (Vovk et al., 2005)    │
│   — Ya usado en BioRAG (calibracion.py UmbralConforme)                        │
└─────────────────────────────────────────────────────────────────────────────────┘

════════════════════════════════════════════════════════════════════════════════
CASO 4: SELECCIÓN TOP-K / POLICY (QUÉ VECINOS TRAER, QUÉ SALTOS HACER)
════════════════════════════════════════════════════════════════════════════════
Situación: De N candidatos, elegir K óptimos. Acción discreta, espacio combinatorio.
Ejemplos BioRAG futuros: Neurona tipo 4 - "qué vecinos del grafo traer al canal 2".

┌─────────────────────────────────────────────────────────────────────────────────┐
│ MÉTODO RECOMENDADO: SCORING + BEAM SEARCH / NEUROEVOLUCIÓN (μ,λ)-ES            │
├─────────────────────────────────────────────────────────────────────────────────┤
│ Enfoque híbrido (como plan Paso 4 §9.1):                                       │
│  1. SCORING NETWORK: MLP que puntúa cada candidato individualmente             │
│     (features del par (A, candidato) → score 0-1)                             │
│  2. SELECTION: Top-K por score + beam search para diversidad                  │
│     (evitar K vecinos redundantes: MMR - Maximal Marginal Relevance)          │
│  3. POLICY OPTIMIZATION: Neuroevolución (Sep-CMA-ES) optimiza MÉTRICA REAL    │
│     (R@1/R@5 del examen de rescate) SIN gradiente — black-box optimization    │
│     Población 20-40, mutación gaussiana, elitismo, fitness shaping rank-based │
│  4. ENSEMBLE: 3-5 retadores, mismo juez (guardia sellada), elige campeón      │
├─────────────────────────────────────────────────────────────────────────────────┤
│ CUÁNDO USAR:                                                                  │
│ ✓ Acción = elegir subconjunto discreto (K de N)                               │
│ ✓ Métrica final es NO diferenciable (R@K, NDCG@K, diversidad)                │
│ ✓ Espacio de búsqueda grande pero evaluación barata (simulación en RAM)       │
│ ✓ Puedes definir "piso heurístico" (ej. top-K por score actual)               │
├─────────────────────────────────────────────────────────────────────────────────┤
│ PAPERS CLAVE:                                                                 │
│ • "NeuroEvoBench: Benchmarking Evolutionary Optimizers for Deep Learning"     │
│   (NeurIPS 2023) — Sep-CMA-ES top para LED (low effective dimensionality)    │
│ • "Sep-CMA-ES for High-Dimensional Optimization" (Ros & Hansen, 2008;         │
│   IEEE SSCI 2022 LED variant)                                                  │
│ • "Learning to Rank with Selection Bias" (Joachims et al., SIGIR 2017)        │
│ • "Maximal Marginal Relevance" (Carbonell & Goldstein, SIGIR 1998)            │
│ • "Evolution Strategies as a Scalable Alternative to Reinforcement Learning"  │
│   (Salimans et al., 2017)                                                     │
└─────────────────────────────────────────────────────────────────────────────────┘

════════════════════════════════════════════════════════════════════════════════
CASO 5: COMPLETAR PATRONES / RECONSTRUIR (GENERATIVO / MASKED AUTOENCODING)
════════════════════════════════════════════════════════════════════════════════
Situación: Dado contexto parcial, predecir lo faltante. "Examen de rescate" = caso.
Ejemplos BioRAG: Examen de rescate (B genera pregunta, A debe recuperar B).

┌─────────────────────────────────────────────────────────────────────────────────┐
│ MÉTODO RECOMENDADO: MASKED GRAPH AUTOENCODER + CONTRASTIVE (GCMAE)             │
│ O en versión simbólica BioRAG: EXAMEN DE RESCATE = PRETEXT TASK GRATIS         │
├─────────────────────────────────────────────────────────────────────────────────┤
│ Paradigma:       Generativo (reconstruir) + Contrastive (alinear vistas)       │
│ Arquitectura:    Encoder compartido → Decoder (reconstrucción) + Projector     │
│                  (contraste)                                                   │
│ Pérdida:         L = λ₁·L_recon + λ₂·L_contrast + λ₃·L_curriculum              │
│ Currículo:       Structure-aware: mask easy edges first → hard edges          │
│                  (Li et al., ICML 2025 "Self-supervised Masked Graph          │
│                  Autoencoder via Structure-aware Curriculum")                  │
│ Versión BioRAG:  NO red neuronal. Examen = "B pregunta, búsqueda ciega        │
│                  cae en A, ¿en qué puesto queda B entre vecinos de A?"         │
│                  Entrena ranker (Caso 1) con estas preguntas auto-generadas.  │
├─────────────────────────────────────────────────────────────────────────────────┤
│ CUÁNDO USAR:                                                                  │
│ ✓ Tienes "verdad gratis" por construcción (masked prediction)                 │
│ ✓ Quieres aprender representaciones / ranking SIN etiquetas humanas           │
│ ✓ El patrón a completar es la MISMA estructura que usas en inferencia         │
│ ✓ Complementario a contrastive: generativo = local, contrastive = global      │
├─────────────────────────────────────────────────────────────────────────────────┤
│ PAPERS CLAVE (2024-2025):                                                     │
│ • "Generative and Contrastive Paradigms Are Complementary for Graph SSL"      │
│   (ICDE 2024) — GCMAE framework                                               │
│ • "Self-supervised Masked Graph Autoencoder via Structure-aware Curriculum"   │
│   (ICML 2025) — curriculum por dificultad estructural                          │
│ • "Topology and Semantic Contrastive Learning for Link Prediction"            │
│   (Neurocomputing 2025) — TSCLA                                               │
│ • "Behavioral Timescale Synaptic Plasticity" (Nature Comm 2026) — BTSP       │
│   = masked prediction biológico con "tercer factor" (eligibility trace)       │
└─────────────────────────────────────────────────────────────────────────────────┘

════════════════════════════════════════════════════════════════════════════════
CASO 6: APRENDER SIMILITUD INVARIANTE (CONTRASTIVE / SIAMESE)
════════════════════════════════════════════════════════════════════════════════
Situación: "Estos dos son similares / disimilares" — aprender métrica de distancia.
Ejemplos BioRAG futuros: Pre-entrenar features S, X, B (sección 13 tipo 6).

┌─────────────────────────────────────────────────────────────────────────────────┐
│ MÉTODO RECOMENDADO: CONTRASTIVE LEARNING CON INFO NCE / TRIPLET LOSS           │
├─────────────────────────────────────────────────────────────────────────────────┤
│ Arquitectura:    Siamese network (comparten pesos) → embedding d-dim            │
│                  Projection head (2 capas) para contraste                        │
│ Pérdida:         InfoNCE (normalizado temperatura τ)                            │
│                  L = -log(exp(sim(z_i,z_j)/τ) / Σ_k exp(sim(z_i,z_k)/τ))        │
│                  O Triplet: max(0, d(anchor,pos) - d(anchor,neg) + margin)    │
│ Augmentations:   CRÍTICO: vistas que preservan semántica, cambian superficie    │
│                  (GraphCL: node dropping, edge masking, subgraph sampling)     │
│ Hard negatives:  Mining en batch / memory bank (MoCo style)                    │
│ Evaluación:      Linear probe / k-NN en downstream / transfer a dominios nuevos │
├─────────────────────────────────────────────────────────────────────────────────┤
│ CUÁNDO USAR:                                                                  │
│ ✓ Objetivo = feature extractor REUTILIZABLE para múltiples tareas             │
│ ✓ Tienes pares positivo/negativo (o puedes generarlos: mismo doc = pos)       │
│ ✓ Quieres invariancia a ruido superficial (idioma, longitud, estilo)          │
│ ✓ Pre-entrenamiento ANTES de fine-tuning supervisado (Caso 1/2)               │
├─────────────────────────────────────────────────────────────────────────────────┤
│ PAPERS CLAVE:                                                                 │
│ • "Graph Contrastive Learning with Adaptive Augmentation" (WWW 2022)          │
│ • "InfoGraph: Unsupervised and Semi-supervised Graph-Level Representation     │
│   Learning" (ICLR 2020)                                                       │
│ • "GraphCL: Contrastive Learning for Graphs" (NeurIPS 2020)                   │
│ • "SimCLR / MoCo / BYOL" — visión, principios transfieren a grafos            │
│ • "Domain Adaptation for Graph Neural Networks" (KDD 2021)                    │
└─────────────────────────────────────────────────────────────────────────────────┘

════════════════════════════════════════════════════════════════════════════════
CASO 7: CONTROL SECUENCIAL / PRESUPUESTO (RL / ACTOR-CRITIC / NEUROEVOLUCIÓN)
════════════════════════════════════════════════════════════════════════════════
Situación: Secuencia de decisiones con presupuesto fijo (tiempo, memoria, ciclos).
Ejemplos BioRAG futuros: Neurona tipo 7 - controlar consolidación, poda, sueño.

┌─────────────────────────────────────────────────────────────────────────────────┐
│ MÉTODO RECOMENDADO: ACTOR-CRITIC (PPO / SAC) + NEUROEVOLUCIÓN HÍBRIDA         │
├─────────────────────────────────────────────────────────────────────────────────┤
│ Actor:           Policy network π(a|s) — elige acción (qué consolidar, podar)  │
│ Critic:          Value network V(s) — estima retorno esperado                  │
│ Reward:          R = ΔQA (mejora recall) - λ·costo - μ·violaciones_pilar12    │
│ Entrenamiento:   PPO (clip) en simulador (copias DB) / Neuroevolución en RAM  │
│                  Neuroevolución (Sep-CMA-ES) para política + gradiente critic │
│ Seguridad:       Hard constraints via Lagrangian / CPO (Constrained Policy    │
│                  Optimization) — NUNCA viola Pilar 12                          │
│ Simulador:       Entorno determinista (PYTHONHASHSEED=1), copia DB,           │
│                  reward model entrenado offline                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│ CUÁNDO USAR:                                                                  │
│ ✓ Decisiones secuenciales con estado (qué consolidar AHORA afecta DESPUÉS)    │
│ ✓ Presupuesto duro (tiempo, memoria, ciclos de sueño)                         │
│ ✓ Trade-offs complejos (recall vs costo vs estabilidad)                       │
│ ✓ Puedes simular miles de episodios en copias (offline RL)                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│ PAPERS CLAVE:                                                                 │
│ • "Proximal Policy Optimization" (Schulman et al., 2017)                      │
│ • "Constrained Policy Optimization" (Achiam et al., ICML 2017)                │
│ • "Offline RL for Neural Architecture Search" (Wang et al., 2021)             │
│ • "Neuroevolution for RL" (Conti et al., 2018) — ES como policy gradient     │
│ • "Decision Transformer" (Chen et al., 2021) — RL as sequence modeling        │
└─────────────────────────────────────────────────────────────────────────────────┘

════════════════════════════════════════════════════════════════════════════════
CASO 8: PLASTICIDAD LOCAL CONTINUA (HEBBIAN / STDP / OJA / BCM)
════════════════════════════════════════════════════════════════════════════════
Situación: Actualización online por muestra, sin batch, sin backprop, biológica.
Ejemplos BioRAG futuros: Neurona tipo 8 - plasticidad sináptica pura (sección 13).

┌─────────────────────────────────────────────────────────────────────────────────┐
│ MÉTODO RECOMENDADO: REGLAS LOCALES CON TERCER FACTOR (DOPAMINA / UTILIDAD)    │
├─────────────────────────────────────────────────────────────────────────────────┤
│ Regla base:      Δw_ij = η · f(pre_i, post_j) · third_factor                  │
│ STDP:            Ventana causal pre→post (LTP) / post→pre (LTD)               │
│ Oja:             Δw = η · (y·x - y²·w) — normalización automática (PCA online)│
│ BCM:             Δw = η · y · (y - θ_M) · x — umbral deslizante θ_M = ⟨y²⟩    │
│ Tercer factor:   Eligibility trace e_ij(t) = ∫ pre_i(τ) post_j(τ) e^-(t-τ)/τ_d │
│                  Dopamina δ(t) = R(t) - V(t) — modula consolidación           │
│                  Δw_ij = η · e_ij · δ  (Frémaaux & Gerstner 2015)             │
│ Homeostasia:     Synaptic scaling: w_i ← w_i · (target / Σ w_i)               │
│                  Intrinsic plasticity: ajusta ganancia neuronal               │
├─────────────────────────────────────────────────────────────────────────────────┤
│ CUÁNDO USAR:                                                                  │
│ ✓ Quieres plasticidad CONTINUA, online, sin batches, biológicamente fiel     │
│ ✓ No hay "verdad" externa — solo señal de recompensa/uso interno              │
│ ✓ Necesitas estabilidad automática (Oja/BCM/homeostasia)                      │
│ ✓ El "tercer factor" = utilidad medida en autoexamen (ya existe en BioRAG)   │
├─────────────────────────────────────────────────────────────────────────────────┤
│ PAPERS CLAVE (FUNDAMENTALES):                                                 │
• "Neural Networks and Physical Systems with Emergent Collective Computational  │
  Abilities" (Hopfield, 1982) — energía, attractores                            │
• "A Theory of Cerebral Cortex" (Friston, 2005) — predictive coding           │
• "Neuromodulated Spike-Timing-Dependent Plasticity" (Frémaaux & Gerstner,    │
  2015) — tercer factor, eligibility traces                                     │
• "Behavioral Timescale Synaptic Plasticity" (Milstein et al., Nature 2025)   │
  — BTSP = eligibility trace + plateau gate (gating = entorhinal input)        │
• "Synaptic Tagging and Capture" (Frey & Morris, 1997) — captura, histéresis   │
• "C1q tags synapses for elimination" (Stevens et al., 2007) — poda inmunológica│
└─────────────────────────────────────────────────────────────────────────────────┘

───────────────────────────────────────────────────────────────────────────────
15. ÁRBOL DE DECISIÓN: ¿QUÉ MÉTODO ELIJO PARA MI NEURONA NUEVA?
───────────────────────────────────────────────────────────────────────────────

Responde EN ORDEN. La primera que SÍ sea tu caso, usa ese método.

┌─────────────────────────────────────────────────────────────────────────────────┐
│ 1. ¿Cada muestra genera su PROPIA respuesta correcta SIN anotación humana?     │
│    (ej. examen de rescate, masked prediction, auto-pregunta)                   │
│    → SÍ: CASO 1 (Listwise LTR + Autoexamen) — Neurona VIVA tipo ranking        │
│    → NO: continúa                                                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 2. ¿La tarea es UNIVERSAL (vale para cualquier usuario) y aprender del         │
│    usuario sería MEMORIZAR RUIDO?                                              │
│    (ej. "fuerza de relación semántica A↔B", "similitud textual")              │
│    → SÍ: CASO 2 (Pairwise LTR Factory + Multi-corpus) — Neurona CERRADA        │
│    → NO: continúa                                                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 3. ¿La decisión es BINARIA (Sí/No) con consecuencias asimétricas FP≠FN?       │
│    (ej. "¿nace esta sinapsis?", "¿pasa al canal 2?", "¿consolida?")           │
│    → SÍ: CASO 3 (Clasificación binaria CALIBRADA + umbral óptimo)             │
│    → NO: continúa                                                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 4. ¿La acción es ELEGIR K de N candidatos (subconjunto discreto)?              │
│    (ej. "qué K vecinos traer", "qué saltos del grafo hacer")                  │
│    → SÍ: CASO 4 (Scoring + Beam Search + Neuroevolución Sep-CMA-ES)           │
│    → NO: continúa                                                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 5. ¿El objetivo es COMPLETAR / RECONSTRUIR patrón faltante (generativo)?      │
│    (ej. examen de rescate, masked autoencoding, completion)                   │
│    → SÍ: CASO 5 (Masked Graph Autoencoder + Contrastive / Examen rescate)     │
│    → NO: continúa                                                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 6. ¿Quieres aprender un EXTRACTOR DE FEATURES REUTILIZABLE (embedding)        │
│    para MÚLTIPLES tareas downstream?                                          │
│    (ej. pre-entrenar agujas S, X, B antes de fine-tuning)                     │
│    → SÍ: CASO 6 (Contrastive / Siamese / Triplet / InfoNCE)                   │
│    → NO: continúa                                                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 7. ¿Son DECISIONES SECUENCIALES con PRESUPUESTO DURO y estado que evoluciona? │
│    (ej. controlar consolidación/poda/sueño ciclo a ciclo)                     │
│    → SÍ: CASO 7 (Actor-Critic PPO + Neuroevolución + Constrained RL)          │
│    → NO: continúa                                                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│ 8. ¿Quieres PLASTICIDAD LOCAL CONTINUA, biológica, sin batches, online?       │
│    (ej. actualización sináptica por muestra con eligibility trace + dopamina) │
│    → SÍ: CASO 8 (STDP / Oja / BCM + Tercer factor = utilidad autoexamen)      │
│    → NO: REVISA TU DISEÑO — todo caso encaja en 1-8                           │
└─────────────────────────────────────────────────────────────────────────────────┘

───────────────────────────────────────────────────────────────────────────────
16. BUENAS PRÁCTICAS UNIVERSALES (APLICAN A TODOS LOS CASOS 1-8)
───────────────────────────────────────────────────────────────────────────────

Estas son INVARIANTES. Violar cualquiera = neurona rechazada en revisión.

1. PISO PRIMERO, SIEMPRE
   - Toda neurona ARRANCA desde una fórmula/heurística a mano (el piso).
   - La parte que aprende SOLO SUMA CORRECCIÓN (en espacio logit para scores,
     en espacio lineal para probabilidades).
   - Si la neurona falla/apaga/retira → QUEDA EL PISO. Sistema nunca peor.

2. TECHO DE CORRECCIÓN (APRENDER, NO MEMORIZAR)
   - Límite duro en |logit(p) - logit(piso)| ≤ MAX_CORRECTION (ej. 20% = ±0.22 logit).
   - Paciencia: N ciclos sin mejora en guardia → "tranquila" (solo vigila).
   - Anti-memorización: si train mejora pero guardia NO → REINICIO, no asciende.

3. GUARDIA SELLADA (HOLDOUT DETERMINISTA)
   - 20% de datos NUNCA vistos durante entrenamiento/validación.
   - Split por hash: sha256(id)[:8] % 5 == 0 (reproducible, sin leakage).
   - Neurona nueva SOLO asciende si GANA en guardia (no solo en train/valid).

4. CAMPEÓN / RETADOR CON TOLERANCIA
   - Retador desafía campeón actual.
   - Gana SI: (a) no pierde ningún caso de guardia que campeón acertaba
     (b) gana estrictamente en total (net gain > 0)
     (c) no cede más de τ=1 caso en ninguna categoría vs campeón
     (d) gap train/guardia ≤ 5% (anti-memorización)

5. MARGEN "PRIMERO NO DAÑAR"
   - Solo cambia orden/predicción si ventaja > ε.
   - ε = MÍNIMO que cumple todas las protecciones (recalibrado cada ciclo).
   - Si ningún ε cumple → campeón se retira, queda piso.

6. PARTICIÓN POR ENTIDAD, NO POR MUESTRA
   - NUNCA mismo recuerdo/nodo/documento en train y test.
   - Regla de prioridad para evitar fuga de datos (data leakage): si existen
     documentos o temas con múltiples recuerdos relacionados, **manda la partición
     por documento/tema** (ningún par relacionado a ambos lados). El split por hash
     de ID (`sha256(id)[:8] % 5 == 0`) aplica cuando las unidades son independientes
     o sobre el identificador del documento/tema.

7. DETERMINISMO ABSOLUTO
   - Exportar `PYTHONHASHSEED=1` **antes de iniciar el proceso Python** (fijarlo en
     `os.environ` con el intérprete ya arrancado no surte efecto) en entrenamiento,
     evaluación e inferencia.
   - Mismo input → SIEMPRE mismo output. Sin `list(set(...))[:N]` ni orden dependiente
     de hash interno; usar `np.random.default_rng(seed)` con semilla explícita.

8. AUTO-REGULACIÓN DE FEATURES INFIABLES
   - Si feature puede ser ruidosa en ALGUNAS DBs (ej. episodio, etiquetas):
     medir fiabilidad EN ESTA DB (correlación con texto) y multiplicar feature × fiabilidad.
   - Fiabilidad 0 = feature apagada automáticamente. Nunca confiar a ciegas.

9. COSTO FIJO Y ACOTADO
   - Presupuesto de tiempo (ms) y memoria (KB) POR OPERACIÓN, declarado ANTES.
   - Número fijo de candidatos, pasos, iteraciones. Nada que escale con N.
   - Tests de velocidad obligatorios (p50, p95).

10. INTERRUPTOR DE APAGADO
    - Variable de entorno BIORAG_<NOMBRE_NEURONA>=0 desactiva COMPLETAMENTE.
    - Sistema idéntico a master sin neurona. Cero overhead si apagada.

11. EXPLICABILIDAD AGUJA POR AGUJA
    - Pesos de la red = importancia de cada feature (SHAP / Integrated Gradients).
    - Dennys debe poder leer: "la neurona subió peso de 'rareza_max' porque...".
    - Sin cajas negras. Si no se explica, no entra.

12. VALIDACIÓN HUMANA / REAL (NO SOLO AUTOEXAMEN)
    - Autoexamen y QA son de la misma familia → siempre medir TAMBIÉN con:
      (a) Preguntas HUMANAS reales (FAQ, logs de usuario)
      (b) DB que NUNCA vio la neurona (distribución distinta)
      (c) Casos límite documentados (CJK, typos, sinónimos ambiguos)

───────────────────────────────────────────────────────────────────────────────
17. CHECKLIST DE REVISIÓN PARA NEURONA NUEVA (ANTES DE PR)
───────────────────────────────────────────────────────────────────────────────

Copia esta lista, márcala, y adjúntala al PR. Dennys la revisa.

[ ] 1. TIPO identificado (sección 13) y justificado en ficha (sección 11)
[ ] 2. CASO de entrenamiento elegido (sección 14) y árbol de decisión (sección 15) seguido
[ ] 3. PISO a mano documentado con fórmula exacta y procedimiento de calibración
[ ] 4. AGUJAS inventariadas (regla 0-1, costo ms, AUC banco, auto-regulación)
[ ] 5. FUENTE DE VERDAD documentada (autoexamen / fábrica / humano) con ejemplos
[ ] 6. EXAMEN DE GUARDIA definido (20% hash, sellado, NUNCA usado para train)
[ ] 7. ARQUITECTURA: piso + corrección (logit/lineal), techo, hidden size justificado
[ ] 8. OPTIMIZADOR: AdamW lr, L2, scheduler, noise/dropout, pasos, semillas (3+)
[ ] 9. PARTICIÓN: por entidad (recuerdo/documento), guardia 20%, grupo externo
[ ] 10. CAPAS DE PROTECCIÓN (sección 7): todas implementadas + tests unitarios
[ ] 11. DETERMINISMO: PYTHONHASHSEED=1 verificado en train/eval/inferencia
[ ] 12. AUTO-REGULACIÓN: features inestables multiplicadas por fiabilidad local
[ ] 13. COSTO FIJO: ms p50/p95 medidos, presupuesto declarado, interruptor ENV
[ ] 14. VALIDACIÓN ORDEN (sección 8): 1→11 TODAS en COPIAS, QA IDÉNTICA master
[ ] 15. PREGUNTAS HUMANAS: evaluado en DB nueva + FAQ real + casos límite
[ ] 16. EXPLICABILIDAD: pesos ↔ agujas mapeados, Dennys puede leer decisión
[ ] 17. NO ROMPE NADA: ranking intacto, manuales intocados, recuerdos no borrados
[ ] 18. SHA256 snapshot antes/después adjunto al PR
[ ] 19. FICHA (sección 11) COMPLETA y conversada con Dennys ANTES de medir
[ ] 20. DOCUMENTACIÓN: README actualizado, comentarios en código, diagramas

───────────────────────────────────────────────────────────────────────────────
18. REFERENCIAS BIBLIOGRÁFICAS COMPLETAS (PAPERS CITADOS)
───────────────────────────────────────────────────────────────────────────────

[1]  Wang et al., "LambdaLoss: A Probabilistic Framework for Ranking Metric Optimization", CIKM 2018
[2]  Cao et al., "ListNet: A Listwise Approach to Learning to Rank", ICML 2007
[3]  Zhuang et al., "Self-Supervised Learning to Rank via Masked Autoencoding", SIGIR 2023
[4]  Milstein et al., "Behavioral Timescale Synaptic Plasticity", Nature Communications 2025
[5]  Zhang et al., "Continual Learning to Rank", WSDM 2024
[6]  Zhu et al., "Domain Generalization for Learning to Rank", SIGIR 2021
[7]  MacAvaney et al., "Out-of-Distribution Generalization in Neural Ranking", SIGIR 2022
[8]  Xiong et al., "Continual Learning for Neural Ranking Models", CIKM 2023
[9]  Lin et al., "Neural Ranking Models with Frozen Features", WWW 2024
[10] Wang et al., "Robust Ranking with Label Noise", ICML 2024
[11] Guo et al., "On Calibration of Modern Neural Networks", ICML 2017
[12] Lin et al., "Focal Loss for Dense Object Detection", ICCV 2017
[13] Kull et al., "Threshold Optimization for Binary Classification", 2017
[14] Vovk et al., "Algorithmic Learning in a Random World", 2005 (Conformal Prediction)
[15] NeuroEvoBench, NeurIPS 2023 (Datasets and Benchmarks track)
[16] Ros & Hansen, "Sep-CMA-ES for High-Dimensional Optimization", IEEE SSCI 2022
[17] Joachims et al., "Learning to Rank with Selection Bias", SIGIR 2017
[18] Carbonell & Goldstein, "Maximal Marginal Relevance", SIGIR 1998
[19] Salimans et al., "Evolution Strategies as a Scalable Alternative to RL", 2017
[20] Li et al., "Self-supervised Masked Graph Autoencoder via Structure-aware Curriculum", ICML 2025
[21] GCMAE: "Generative and Contrastive Paradigms Are Complementary for Graph SSL", ICDE 2024
[22] TSCLA: "Topology and Semantic Contrastive Learning for Link Prediction", Neurocomputing 2025
[23] Milstein et al., "Behavioral Timescale Synaptic Plasticity", Nature Communications 2026 (v2)
[24] Frémaux & Gerstner, "Neuromodulated Spike-Timing-Dependent Plasticity", 2015
[25] Frey & Morris, "Synaptic Tagging and Capture", 1997
[26] Stevens et al., "C1q tags synapses for elimination", 2007
[27] Hopfield, "Neural Networks and Physical Systems", 1982
[28] Friston, "A Theory of Cerebral Cortex", 2005
[29] Achiam et al., "Constrained Policy Optimization", ICML 2017
[30] Schulman et al., "Proximal Policy Optimization", 2017
[31] Wang et al., "Offline RL for Neural Architecture Search", 2021
[32] Conti et al., "Neuroevolution for RL", 2018
[33] Chen et al., "Decision Transformer", 2021

════════════════════════════════════════════════════════════════════════════════
───────────────────────────────────────────────────────────────────────────────
20. EJEMPLOS CONCRETOS DE NEURONAS (TEMPLATE + CASOS REALES)
───────────────────────────────────────────────────────────────────────────────

Esta sección contiene **plantillas ilustrativas de partida** para copiar y adaptar.
No representan código integrado ni agujas ya validadas; cada diseño real debe
pasar antes por su protocolo (agujas medidas, piso, guardia y ficha de sección 11).

═══════════════════════════════════════════════════════════════════════════════
EJEMPLO A: NEURONA DE GATING BINARIA — ¿NACE ESTA SINAPSIS? (CASO 3)
═══════════════════════════════════════════════════════════════════════════════

Propósito: reemplazar la regla fija de auto_vincular en core/sinapsis.py
que decide si nace una sinapsis automática entre A y B.

Ficha (sección 11):
  Nombre: neurona_gating_binaria
  Lugar: core/sinapsis.py → función decidir_nacimiento (punto único de nacimiento)
  Decisión única: ¿nace esta sinapsis A→B? (Sí/No)
  Tipo: 3 — Gating / Clasificación binaria
  Caso de entrenamiento: 3 — Clasificación binaria calibrada con umbral óptimo
  Fuente de verdad: examen de rescate (B pregunta, ¿aparece A en vecinos?)
  Piso: regla fija actual (co_ocurrencia ≥ 3 umbral)
  Guardia: 20% hash sha256(nombre_B)[:8] % 5 == 0
  Techo: |logit(p) - logit(piso)| ≤ 0.22 (20%)
  Interruptor: BIORAG_NEURONA_GATING=0

Arquitectura:
  MLP 12→6→1 + sigmoid
  logit(p) = logit(piso) + v·tanh(W·x + b)
  Activación salida: sigmoid → probabilidad calibrada

Agujas (12):
  1. S (dimensiones compartidas, sin auto_generada)
  2. X_refinada (concepto/sustantivos/contenido, recíproca min)
  3. rareza_max (giro dentado)
  4. tipo_sinapsis (one-hot + prioridad ordinal)
  5. episodio_auto (auto-regulada por fiabilidad local)
  6. hub_resta (penaliza hubs)
  7. una_sola_resta (penaliza palabras ≤3 letras)
  8. vecinos_comunes (Adamic-Adar local)
  9. mismo_grado_log (|log(deg_A) - log(deg_B)|)
  10. distancia_temporal_7d (guardia experimento 12)
  11. peso_tipo_onehot (tipo de sinapsis padre)
  12. contexto_fiab_episodio (0-1 auto-regulado)

Criterio de ascenso (sección 16, punto 4):
  - no pierde ningún caso de guardia que el piso acertaba
  - net gain > 0 en total
  - τ = 1 caso máximo cedido por categoría
  - gap train/guardia ≤ 5%

Capas de protección (sección 7):
  - identidad: si consulta es el nombre exacto y piso tenía #1, sigue #1
  - manuales: nunca toca enlaces manual ni manual_v7
  - disyuntor: 3 errores seguidos → pausa
  - costo fijo: < 2 ms por par, presupuesto 200 pares/ciclo

═══════════════════════════════════════════════════════════════════════════════
EJEMPLO B: NEURONA DE SELECCIÓN TOP-K — QUÉ VECINOS TRAER AL CANAL 2 (CASO 4)
═══════════════════════════════════════════════════════════════════════════════

Propósito: elegir K vecinos del grafo para mostrar al agente en el canal 2,
evitando vecinos redundantes y hubs falsos.

Ficha (sección 11):
  Nombre: neurona_topk_canal2
  Lugar: core/memory/search.py → capa de expansión por grafo (L337-406)
  Decisión única: ¿cuáles K vecinos de A mostrar al agente?
  Tipo: 4 — Selection / TOP-K (policy network)
  Caso de entrenamiento: 4 — Scoring + Beam Search + Neuroevolución Sep-CMA-ES
  Fuente de verdad: examen de rescate (puesto de B en top-K de A)
  Piso: top-K por peso a mano actual (top 6, ventana 512)
  Guardia: 20% hash sha256(nombre_A)[:8] % 5 == 0
  Techo: margen ε por puesto (ε·(k - puesto))
  Interruptor: BIORAG_NEURONA_TOPK=0

Arquitectura:
  1. Scoring network: MLP 20→8→1 por candidato (par A,candidato → score 0-1)
  2. Beam search: ancho 3, diversidad MMR (evitar vecinos redundantes)
  3. Neuroevolución: Sep-CMA-ES, población 30, 60 generaciones por ciclo
  4. Ensemble: 3 retadores, misma guardia sellada

Agujas (20 por candidato):
  1-5. S, S_idf, X_refinada, B, K (del par A→candidato)
  6. rareza_max del candidato
  7. grado_candidato_log (penaliza hubs)
  8. vecinos_comunes_con_A
  9. mismo_tipo_sinapsis
  10. distancia_temporal
  11-15. tipo one-hot + prioridad ordinal
  16. fiabilidad_episodio (auto-regulado)
  17. fiabilidad_etiquetas (auto-regulado)
  18. contexto_convergencia (otra regla propuso el par)
  19. MMR_diversidad (penaliza si vecino ya seleccionado)
  20. puntuación_piso (score actual del motor)

Criterio de ascenso:
  - R@1/R@5 del examen de rescate mejora en guardia
  - no pierde ningún caso de guardia que el piso tenía en top-5
  - diversidad medida: vecinos únicos por tema ≥ 80%

═══════════════════════════════════════════════════════════════════════════════
EJEMPLO C: NEURONA DE PLASTICIDAD LOCAL — EXAMEN DE RESCATE EN SUEÑO (CASO 8)
═══════════════════════════════════════════════════════════════════════════════

Propósito: actualizar pesos sinápticos en el sueño usando regla local con tercer
factor (eligibility trace + dopamina = utilidad del autoexamen).

Ficha (sección 11):
  Nombre: neurona_plasticidad_sueno
  Lugar: core/dmn_engine.py → ciclo de consolidación
  Decisión única: ¿consolidar, atenuar o cuarentenar esta sinapsis transitoria?
  Tipo: 8 — Hebbian / Local (STDP / Oja / BCM + tercer factor)
  Caso de entrenamiento: 8 — Plasticidad local continua, sin batches
  Fuente de verdad: utilidad medida en autoexamen (dopamina interna)
  Piso: regla actual (hipotesis_sueno 0.08, olvido por desuso)
  Guardia: 20% hash de par (A,B)
  Techo: sináptico, sin backprop global
  Interruptor: BIORAG_NEURONA_PLASTICIDAD=0

Regla de actualización (por par, en sueño):
  Δw_ij = η · e_ij(t) · δ(t)
  donde:
    e_ij(t) = eligibility trace (activación conjunta pre/post en ventana τ_d)
    δ(t) = R(t) - V(t) = utilidad_autoexamen - expectativa
    η = tasa de aprendizaje (0.01 inicial, decae)

Agujas (reglas locales, no red):
  1. pre_activity (activación de A en consolidación)
  2. post_activity (activación de B en consolidación)
  3. ventana_temporal (∆t entre activaciones, STDP causal)
  4. fuerza_actual (peso sináptico existente)
  5. utilidad_autoexamen (R: ¿B apareció en top-K de A en examen?)
  6. expectativa_V (media móvil de utilidad histórica)
  7. homeostatic_target (suma pesos por nodo, escalado sináptico)

Criterio de consolidación:
  - transitoria → madura si e_ij·δ > umbral en N sueños consecutivos
  - madura → cuarentena si e_ij·δ < -umbral en M sueños
  - cuarentena → reversible (histéresis: requiere evidencia nueva + margen)

═══════════════════════════════════════════════════════════════════════════════
TEMPLATE EN BLANCO PARA NEURONA NUEVA (COPIAR Y LLENAR)
═══════════════════════════════════════════════════════════════════════════════

[ ] NOMBRE: ________________________________________
[ ] LUGAR exacto (archivo + función): ________________________________
[ ] DECISIÓN ÚNICA (una línea): ______________________________________
[ ] TIPO (sección 13): 1-Ranking 2-Scoring 3-Gating 4-Selection 5-Generative 6-Contrastive 7-Policy 8-Hebbian
[ ] CASO de entrenamiento (sección 14): 1-8
[ ] ÁRBOL de decisión (sección 15): pregunta ____ → SÍ → Caso ____
[ ] FUENTE DE VERDAD: autoexamen / fábrica / humano / otro: ________
[ ] PISO A MANO (fórmula exacta): ____________________________________
[ ] AGUJAS (lista, regla 0-1, costo ms, AUC banco): ____________________
[ ] GUARDIA (20% hash, qué ID se tiene): _____________________________
[ ] TECHO (|corrección| ≤ ?): ________________________________________
[ ] CRITERIO DE ASCENSO (campeón/retador, τ, gap): ____________________
[ ] MARGEN ε (primero no dañar): ____________________________________
[ ] CAPAS DE PROTECCIÓN (cuáles, con pruebas): ________________________
[ ] COSTO FIJO (ms p50/p95, presupuesto): ___________________________
[ ] INTERRUPTOR (BIORAG_<NOMBRE>=0): _________________________________
[ ] EXPLICABILIDAD (pesos ↔ agujas): _________________________________
[ ] VALIDACIÓN HUMANA (DB nueva, FAQ, casos límite): __________________
[ ] SHA256 snapshot antes/después: ____________________________________
[ ] FICHA conversada con Dennys ANTES de medir: [ ] SÍ [ ] NO

FIN DE LA GUÍA — ESTE DOCUMENTO ES VIVO: SE ACTUALIZA CON CADA NEURONA NUEVA
════════════════════════════════════════════════════════════════════════════════
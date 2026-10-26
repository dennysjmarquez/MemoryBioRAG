═══════════════════════════════════════════════════════════════════════════════
 GUÍA PARA CREAR Y ENTRENAR UNA NEURONA EN BIORAG
 (lo que se hizo con las dos primeras neuronas, en qué se basó y por qué)
═══════════════════════════════════════════════════════════════════════════════

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
═══════════════════════════════════════════════════════════════════════════════
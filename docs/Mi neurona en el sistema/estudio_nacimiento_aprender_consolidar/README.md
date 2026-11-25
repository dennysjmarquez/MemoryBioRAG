# Cómo nacen las sinapsis al aprender y al consolidar (estudio, 25-11)

Este estudio solo lee el código y corre el motor real sobre una base nueva en `/tmp` con 8 recuerdos inventados.
No abre ninguna base real ni cambia el motor.

- **Script:** `trazar.py`.
- **Salida:** `salida_traza.txt` (sale igual con `PYTHONHASHSEED` = 1 y = 7).
- **Complementa:** `../mapa_nacimiento_sinapsis/README.md`.

## Recorrido (verificado en el código)

**1. `aprender`** (`core/mcp_server/write.py:_aprender_impl`)
- `percibir_corto_plazo`: escribe en `corto_plazo` y no crea sinapsis.
- `auto_vincular(clave, contenido)` (L316): compara **solo contra `largo_plazo`**. Los recuerdos de la misma sesión todavía no se ven entre sí.
- `vincular_por_sinonimos(clave, syn)` (L320).
- `vincular_con` → `establecer_asociacion`: crea un enlace `manual` de 0.5 en los dos sentidos.
- El hub y los bridges van a otras tablas, no a `sinapsis`.

**2. `consolidar` / `sueno`** (`ciclo_sueno_consolidacion`)
1. Pasa a `largo_plazo` todo lo que está en corto plazo.
2. `auto_vincular` de nuevo para cada recuerdo.
3. WordNet.
4. `_auto_generar_co_ocurrencia`.
5. DMN: hasta 8 enlaces `dmn_synthesized` de 0.30.
6. Latentes, que van a otra tabla.
7. LTD.
8. Poda.

**3. Fin de sesión**
- Si queda algo en corto plazo, corre el ciclo de sueño.
- Si no, `consolidar_concepto` → `auto_vincular`.

**Fuera de aprender y consolidar:**
- `buscar` → ráfaga crea `rafaga_rememb` de 0.6.
- `ensenar_expresion` crea un `sinonimo_explicito` en los dos sentidos.
- `sleep_cycle.py` crea `hipotesis_sueno` de 0.08.
- Abrir el cerebro corre el DMN.

## Hallazgos nuevos (vistos en la traza)

**H1. `vincular_por_sinonimos` relabela enlaces temáticos como «sinónimo declarado».**
- Busca cada término de `sinonimos` con `LIKE '%término%'` en el nombre y en los sinónimos de los demás.
- Si encuentra, sube el enlace a 0.9 y cambia el tipo a `sinonimo_explicito`, que es un tipo protegido.
- En la traza, «tomate» y «receta» convirtieron `co_nombre 0.75` y `co_ocurrencia 0.40` en `sinonimo_explicito 0.90`.
- Esto explica por qué hay tantos `sinonimo_explicito` y por qué su precisión es baja (exp. 16: 9–13 %).

**H2. Los puentes («rojo») hoy nacen por esa misma vía.**
- `sangre_donacion` con el sinónimo «rojo» se enlazó a 0.9 con `receta_salsa_tomate` y con `semaforo_rojo_transito`.
- Nace al peso máximo y con tipo protegido, igual que un sinónimo real.
- No lleva `ultimo_uso`, así que es inmune al LTD.
- El motor no distingue entre puente, sinónimo y tema.

**H3. Un enlace que se vuelve a tocar pierde la inmunidad.**
- Cualquier `ON CONFLICT` llena `ultimo_uso`, ya sea la segunda pasada de `auto_vincular` en el sueño, los sinónimos o la co-ocurrencia.
- Desde ese momento el LTD sí puede bajarlo (matiza el §3.4 del mapa).

**H4. Los procesos automáticos tocan el `manual` (confirma el §3.3 del mapa).**
- La co-ocurrencia de sesión subió `manual` de 0.50 a 0.60, pero solo en el sentido c1→c2.
- El sentido inverso quedó en 0.50. El par manual queda asimétrico.

**H5. Los enlaces dentro de una sesión solo nacen al consolidar.**
- Al aprender, `auto_vincular` no ve el corto plazo.

**H6. DMN.**
- Une pares de los 40 recuerdos más pesados que comparten **cualquier** dimensión o ≥ 2 palabras de 4 letras o más.
- Les da 0.30 sin mirar el tema.
- En la traza todos comparten las mismas dimensiones, así que el DMN unió recetas con servidores. Esto exagera el efecto, porque en uso real las dimensiones varían.

## No verificado en este estudio

- `lexical_learning` más allá del `upsert`.
- La lógica interna de `sueno_vacios`.
- Las ramas `TERMODINAMICA_DMN`.

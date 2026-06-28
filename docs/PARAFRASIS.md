# Parafrasis en BioRAG — Resumen Ejecutivo

## ¿Qué es?
Mecanismo de búsqueda que permite encontrar nodos cuyo contenido usa vocabulario diferente al del query.

## ¿Para qué sirve?
Para cerrar el gap entre cómo piensa el usuario (query) y cómo está escrito el nodo en la BD.
- Ejemplo: "el gato se sentó" ↔ nodo dice "el felino reposó en el tapete"
- Sin parafrasis: FTS5 trigram no hace match (ningún token comparte 3+ caracteres)
- Con parafrasis: buscando "el felino reposó" encuentra el nodo

## ¿Por qué se hace?
Porque FTS5 trigram busca por similaridad textual, no por significado. Si el vocabulario diverge, no hay match aunque el tema sea el mismo.

Es la segunda vía del principio "Múltiples Vías, Mismo Destino":
- Vía 1: el agente reformula el query (parafrasis)
- Vía 2: el sistema rescata con sinapsis (rafaga)

## ¿Cómo se hace?

**Paso del agente:**
1. Recibe query original
2. Genera 3-5 reformulaciones con vocabulario diferente
3. Llama a `recordar(query, parafrasis="variante1,variante2,variante3")`

**Paso del sistema:**
1. Busca query original → evalúa score
2. Si score < 0.5 → busca cada variante con penalización ×0.95
3. Fusiona resultados por concepto, mejor score gana
4. Si alguna variante encuentra algo que el original no encontró → gap semántico обнаружен

## ¿Qué debe hacer el agente?
- SIEMPRE generar reformulaciones antes de llamar a `recordar`
- Cada reformulación debe usar vocabulario diferente al original
- Formato: strings separados por coma

## ¿Cuál es el resultado esperado?
- Si parafrasis encuentra resultados que el original no encontró → gap обнаружен
- Si parafrasis no encuentra nada nuevo → el vocabulario original ya era suficiente
- El resultado siempre es mejor que sin parafrasis (más cobertura sin perder precisión)

## Parámetros relacionados
| Parámetro | Qué hace |
|-----------|----------|
| `query` | Query original del usuario |
| `parafrasis` | Reformulaciones separated por coma |
| `PARAFRASIS_THRESHOLD = 0.5` | Score mínimo para activar variantes |
| `PARAFRASIS_PENALTY = 0.95` | Penalización por variante no original |

## Ejemplo de uso
```
recordar(
    query="el gato se sentó",
    parafrasis="el felino descansó,el minino reposó,cat repose"
)
```
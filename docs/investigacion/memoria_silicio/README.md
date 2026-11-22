# Memoria de silicio — investigación para BioRAG

**Estado: biblioteca de investigación, no integración ni demostración de superioridad.** Conservada en la rama experimental `arena/6459e2d0-memorybiorag`. No modifica core/master, modelos, fuentes privadas ni la configuración de la QA en curso.

Objetivo: investigar memoria persistente auditable, contextual, resistente a fallos y capaz de incorporar correcciones sin destruir el pasado. La inspiración biológica genera hipótesis; no demuestra vida/consciencia ni sustituye mediciones.

## Contenido

- [Fichas de diez fuentes](FICHAS.md): mecanismo, representación, actualización, conflictos, resultados reportados, límites y decisión para BioRAG.
- [Arquitectura propuesta](ARQUITECTURA_PROPUESTA.md): eventos, afirmaciones bitemporales, confirmación, proyecciones y consultas de aceptación. Es diseño, no esquema ya migrado.
- [Experimentos preregistrados](EXPERIMENTOS.md): comparación de orden/etiquetas, casos tardíos, conflictos, fallos y crecimiento.
- [fuentes.json](fuentes.json): URLs versionadas cuando fue posible, versiones vistas, fragmentos HTML consultados, estado de descarga y reproducción.
- [referencias.bib](referencias.bib): bibliografía importable. No se inventan autores o fechas no verificados.
- `descargar_fuentes.py`: descarga opcional de PDFs a un directorio externo explícito, con hashes y control de tamaño. No se ejecuta al importar ni altera el motor.

## Qué se consultó realmente

Se consultaron fuentes primarias HTML, no solo mensajes de otros agentes. La lectura es **parcial y dirigida**, no diez revisiones exhaustivas: el manifest enumera exactamente los chunks leídos. Para TEM se revisaron método, resultados y discusión; para los demás, secciones indicadas en las fichas. Ninguno de sus benchmarks fue reproducido aquí. Las cifras son declaraciones de los autores, no medidas de BioRAG.

**No se descargaron los diez PDFs completos.** La recuperación directa inicial del PDF de TEM falló y el entorno de comandos limita el acceso a arXiv/Nature. Sí fue posible consultar HTML por la herramienta de lectura. No se simula una descarga ni se etiqueta como archivado lo que no lo está. La biblioteca publicada contiene notas originales, enlaces y metadatos, no copias íntegras de los artículos.

Para descargar en un entorno con acceso a esas editoriales:

```bash
python docs/investigacion/memoria_silicio/descargar_fuentes.py --output /ruta/externa/biorag-papers
```

Los PDFs y datos grandes quedan fuera de Git; revisar licencias antes de redistribuir. El manifiesto de descarga indica tamaño y SHA256 de lo que realmente se obtuvo. Un fallo de descarga no cuenta como éxito. Las versiones arXiv están fijadas a las observadas; la fuente Nature se fija por DOI pero puede recibir correcciones editoriales.

## Correcciones a las conclusiones recibidas

1. Un paper parecido no valida al 100% nuestra implementación. Es antecedente y referencia para diseñar controles.
2. Memoria temporal no es exclusiva de BioRAG: Zep/Graphiti ya representa validez y tiempo de ingesta.
3. TEM no es solo para servidores gigantes por definición. Su experimento usa A100 y varios modelos; eso no demuestra que sea imposible adaptar sus ideas a CPU.
4. El +10.58 pp de TEM en LoCoMo es una diferencia conservadora entre cotas de puntuación semántica con una configuración concreta, no una mejora universal de precisión de entidades. Sus ahorros de tokens del ensayo de estados no son el costo completo del sistema.
5. Mem0 del paper y Mem0 actual no se deben mezclar. MemOS y MemoryOS son referencias distintas.
6. “Append-only” no equivale a inmutable frente a un administrador ni a autenticidad criptográfica. Guardar una frase original preserva lo dicho, no garantiza que sea verdad.
7. No copiar filtros que eliminen pistas históricas ni consolidaciones destructivas por analogía biológica.
8. Un porcentaje de éxito no prueba imposibilidad universal de otras arquitecturas. “RAG” abarca sistemas con grafos, filtros temporales y metadatos, no solo cosine top-k.

## Prioridad

Primero terminar la QA emparejada existente y el flujo seguro de confirmación. Esta investigación no cambia semillas, gates, casos ni parámetros a mitad del benchmark. Los experimentos nuevos se ejecutarán aparte y con contratos fijados antes de medir. Ninguna propuesta de este directorio autoriza integración productiva.

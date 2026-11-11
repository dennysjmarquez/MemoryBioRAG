# Cómo avanzar sin degradar (para el auditor y para cualquiera)

> **Para quién es esto:** quien audite o revise este proyecto, humano o IA.
> **Qué problema resuelve:** una revisión que solo busca fallos no deja avanzar.
> Encontrar errores es necesario; **cerrarlos y seguir**, también.
> **Última revisión:** 2026-11-07.

## 1. El patrón que hay que evitar

```
auditar → encontrar 3 fallos → arreglarlos → auditar → encontrar 4 → arreglarlos → ...
```

Esto no converge. Cada auditoría abre superficie nueva igual de rápido que la
cierra, y el proyecto nunca llega a la versión siguiente. **No es que auditar
esté mal: es que una auditoría sin criterio de salida no termina nunca.**

## 2. El criterio de salida: qué es bloqueante y qué no

Un hallazgo es **bloqueante** solo si cumple alguna de estas tres:

1. **Puede corromper o perder datos del usuario.**
2. **Puede filtrar datos o permitir ejecución no autorizada** (OWASP A01/A03).
3. **Deja el sistema sin arrancar o sin poder cerrarse de forma segura.**

Todo lo demás —estilo, nombres, un docstring que falta, una función larga,
una mejora de rendimiento— es **deuda declarada**: se anota, se congela y se
paga cuando toque ese archivo. **No bloquea un merge.**

Sin esta distinción, todo es urgente y por lo tanto nada avanza.

## 3. El flujo, en orden

| Paso | Qué se hace | Qué lo cierra |
|---|---|---|
| 1. Definir el objetivo | Qué se quiere lograr, en una frase, con su métrica | La frase escrita |
| 2. Medir antes | Se corre la batería y se anota el número de partida | Tabla de "antes" |
| 3. Implementar | Un cambio medido a la vez (Invariante 2) | El cambio con su docstring |
| 4. Comprobar regresión | La métrica no empeora **más allá del ruido declarado** | Tabla de "después" |
| 5. Seguridad | Lista OWASP del cambio (Pilar 12) | PR con la lista respondida |
| 6. Auditar | Solo lo bloqueante de §2 | Los bloqueantes cerrados |
| 7. **Seguir** | Se mergea y se abre el siguiente objetivo | **Merge hecho** |

**El paso 7 no es opcional.** Un proyecto que nunca llega a él no tiene
auditoría: tiene una parálisis con actas.

## 4. La regla del ruido, para no bloquear por una décima

Una métrica de búsqueda no es determinista al decimal. Para decidir si un
cambio degrada:

- **Se declara antes** cuánto es ruido aceptable (p. ej. ±0,5 puntos de R@5).
- Si el resultado cae dentro del ruido, **no es regresión** y no bloquea.
- Si cae fuera, se revierte (Pilar 1) y se anota por qué.
- La comparación es **sobre el mismo snapshot congelado**, nunca sobre bases
  distintas.

Sin esta regla, cualquier diferencia de una décima se convierte en un debate de
semanas y no se distingue una regresión real de una casualidad.

## 5. Cómo se escribe un hallazgo para que se pueda cerrar

Un hallazgo útil tiene cuatro partes. Si le falta alguna, no es un hallazgo,
es una opinión:

```markdown
**Qué**: la decisión se toma después de abrir SQLite.
**Por qué importa**: abrir con un diario ajeno lo aplica y cambia los datos.
**Cómo se comprueba**: matar el proceso con un commit pendiente y reabrir.
**Cómo se cierra**: comprobar antes de `connect`, sin abrir. Prueba: test_x.
```

Con esto, quien lo recibe sabe **exactamente** cuándo está cerrado, y no hay
idas y vueltas.

## 6. Qué se hace con la deuda que no es bloqueante

No se ignora: **se congela a la vista.**

- `tests/test_arquitectura.py` falla si la cifra **crece**.
- `docs/CODIGO_LIMPIO.md` §5 lista la deuda con su remedio.
- Cada archivo que se toque, se deja algo mejor (una docstring, un nombre).
  No hace falta campaña; hace falta que nadie empeore.

Esto convierte la deuda en algo **visible y estable**, en lugar de una razón
permanente para no mergear.

## 7. Aplicado al caso de ahora

Los tres escenarios de la auditoría de SQLite están cerrados y con prueba.
La capa está dividida y documentada. La CI está en verde en cinco plataformas.

Con el criterio de §2: **no queda ningún bloqueante conocido.** Lo que queda
es deuda declarada y congelada (docstrings en archivos viejos, archivos
grandes que se parten de uno en uno), que no impide avanzar a la v36.

**La siguiente acción no es otra auditoría: es el merge**, y después el
siguiente objetivo del roadmap.

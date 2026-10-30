"""Identidad Unicode común para entradas de memoria.

Por qué: una consulta y un recuerdo nuevo no deberían separarse solo porque
se escribieron con ancho completo, medio ancho o marcas combinantes equivalentes.
Dónde: en las fronteras de consulta, escritura nueva y validación, antes de
contar o comparar, para que todas usen la misma identidad.
Conecta con: búsqueda, ingreso de memoria, sustantivos y puentes del Concept Hub.
En contenido y sinónimos nuevos el plegado de ancho se limita a letras/números;
la puntuación, los símbolos y U+3000 se conservan.

Esta función no quita marcas ni usa NFKC general. No migra, reindexa ni fusiona
registros anteriores; las comparaciones aproximadas existentes son otra capa.
Evidencia de la elección: docs/e3_unicode_identidad_investigacion_20261028.md.
"""

import unicodedata


def _recortar_sin_perder_espacio_ideografico(texto: str) -> str:
    """Recorta espacios como antes, pero conserva U+3000 al fusionar sinónimos."""
    inicio, fin = 0, len(texto)
    prefijo, sufijo = [], []
    while inicio < fin and texto[inicio].isspace():
        if texto[inicio] == "\u3000":
            prefijo.append(texto[inicio])
        inicio += 1
    while fin > inicio and texto[fin - 1].isspace():
        if texto[fin - 1] == "\u3000":
            sufijo.append(texto[fin - 1])
        fin -= 1
    return "".join(prefijo) + texto[inicio:fin] + "".join(reversed(sufijo))


def normalizar_identidad(texto: str, *, ancho_solo_letras_numeros: bool = False) -> str:
    """NFC y plegado directo de ancho; el modo de texto preserva signos y espacios."""
    def plegar(parte: str) -> str:
        salida = []
        for char in unicodedata.normalize("NFC", parte):
            codigo = ord(char)
            if codigo == 0x3000 and not ancho_solo_letras_numeros:
                salida.append(" ")
            elif (
                0xFF00 <= codigo <= 0xFFEF
                and (not ancho_solo_letras_numeros or unicodedata.category(char)[0] in "LN")
            ):
                partes = unicodedata.decomposition(char).split()
                if partes and partes[0] in ("<wide>", "<narrow>"):
                    salida.extend(chr(int(valor, 16)) for valor in partes[1:])
                else:
                    salida.append(char)
            else:
                salida.append(char)
        return unicodedata.normalize("NFC", "".join(salida))

    if not ancho_solo_letras_numeros:
        return plegar(texto)

    # NFC dentro de tramos de letras/marcas/números; nunca sobre signos,
    # símbolos o separadores, que conservan exactamente sus caracteres.
    resultado = []
    tramo = []
    for char in texto:
        if unicodedata.category(char)[0] in "LMN":
            tramo.append(char)
        else:
            if tramo:
                resultado.append(plegar("".join(tramo)))
                tramo.clear()
            resultado.append(char)
    if tramo:
        resultado.append(plegar("".join(tramo)))
    return "".join(resultado)

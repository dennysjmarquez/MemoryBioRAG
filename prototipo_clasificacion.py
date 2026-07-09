#!/usr/bin/env python3
"""
Prototipo: Clasificación Simbólica Sin Vectores
Prueba los 3 pilares: Lexname + Topic Domain + Frame ID
"""
from nltk.corpus import wordnet as wn
import sys

def clasificar(palabra):
    """Clasifica una palabra usando los 3 pilares de WordNet."""
    synsets = wn.synsets(palabra)
    if not synsets:
        print(f"'{palabra}': sin synsets en WordNet")
        return

    print(f"\n{'='*60}")
    print(f"PALABRA: {palabra}")
    print(f"Synsets encontrados: {len(synsets)}")
    print(f"{'='*60}")

    for s in synsets[:3]:
        print(f"\n--- {s.name()} ---")
        print(f"  Definición: {s.definition()}")
        print(f"  Ejemplos: {s.examples()}")
        print(f"  LEXNAME: {s.lexname()}")

        # Frame IDs (solo verbos)
        frames = s.frame_ids()
        if frames:
            print(f"  FRAMES: {frames}")

        # Topic domains
        domains = s.topic_domains()
        if domains:
            print(f"  DOMAINS: {[d.name() for d in domains]}")
        else:
            print(f"  DOMAINS: (none)")

        # Hypernyms (para ver grupo ontológico)
        hypers = s.hypernyms()
        if hypers:
            print(f"  HIPERÓNIMO: {hypers[0].name()}")

    # Búsqueda por lexname: encontrar sinónimos en el mismo grupo
    if synsets:
        lex = synsets[0].lexname()
        print(f"\n--- GRUPO LEXNAME '{lex}' ---")
        print(f"  Palabras en el mismo grupo ontológico:")
        # Buscar todos los synsets del mismo lexname (muestra los primeros 10)
        count = 0
        for s in wn.all_synsets():
            if s.lexname() == lex and count < 10:
                lemmas = [l.name() for l in s.lemmas()[:3]]
                print(f"    {s.name()}: {', '.join(lemmas)}")
                count += 1

    # Frame expansion (solo verbos)
    if synsets and synsets[0].pos() == wn.VERB:
        frames = synsets[0].frame_ids()
        if frames:
            frame_id = frames[0]
            print(f"\n--- MISMO FRAME {frame_id} ---")
            print(f"  Verbos con la misma función:")
            for s in wn.synsets(synsets[0].lemmas()[0].name(), pos=wn.VERB):
                if frame_id in s.frame_ids():
                    lemmas = [l.name() for l in s.lemmas()[:5]]
                    print(f"    {s.name()}: {', '.join(lemmas)}")


if __name__ == "__main__":
    palabras = sys.argv[1:] if len(sys.argv) > 1 else [
        "decode", "translate", "computer", "error", "love"
    ]
    for p in palabras:
        clasificar(p)

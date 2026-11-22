"""Adaptador español limitado y abstencionista: actos completos, no keywords.

No comprende correcciones arbitrarias. No confirma, no escribe, no usa modelos.
Los offsets apuntan al mensaje original, nunca a una paráfrasis inventada.
"""
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Extraction:
    status: str
    reason: str
    fields: dict
    spans: dict


_FIELD = r"[\wÁÉÍÓÚÜÑáéíóúüñ /.-]+?"
_PATTERNS = (
    re.compile(rf'Corrijo:\s+(?:el|la)\s+(?P<attribute>{_FIELD})\s+de(?:l)?\s+'
               rf'(?P<entity>{_FIELD})\s+en\s+(?P<scope>{_FIELD})\s+es\s+'
               rf'(?P<new>{_FIELD}),\s+no\s+(?P<old>{_FIELD})\.?', re.I),
    re.compile(rf'Actualizo:\s+(?:el|la)\s+(?P<attribute>{_FIELD})\s+de(?:l)?\s+'
               rf'(?P<entity>{_FIELD})\s+en\s+(?P<scope>{_FIELD})\s+pasa de\s+'
               rf'(?P<old>{_FIELD})\s+a\s+(?P<new>{_FIELD})\.?', re.I),
)
# Marcadores de incertidumbre/negación/citas dentro de los campos, no dominios.
_UNSAFE = re.compile(r'\b(?:no|nunca|quizá|quizás|tal vez|podría|debería|si|según|dijo|dice|ejemplo)\b', re.I)
_AMBIGUOUS = re.compile(r'\s(?:de|del|en|es|a|pasa)\s', re.I)


def normalize(value):
    return ' '.join(value.casefold().split())


def extract(message):
    if not isinstance(message, str):
        raise ValueError('message debe ser texto')
    if len(message) > 4096:
        return Extraction('abstain', 'message_too_long', {}, {})
    # Presupuesto estructural antes del regex: evita explorar combinaciones de
    # delimitadores en mensajes adversariales. Los campos con esas partículas
    # se consideran ambiguos en esta gramática inicial.
    tokens = re.findall(r'\w+', message.casefold())
    counts = {word: tokens.count(word) for word in ('de', 'del', 'en', 'es', 'pasa', 'a')}
    update = message.lstrip().casefold().startswith('actualizo:')
    if (counts['en'] != 1 or counts['de'] + counts['del'] != (2 if update else 1)
            or counts['es'] != (0 if update else 1)
            or counts['pasa'] != int(update) or (update and counts['a'] != 1)):
        return Extraction('abstain', 'unsupported_or_ambiguous_structure', {}, {})
    for pattern in _PATTERNS:
        match = pattern.fullmatch(message.strip())
        if match is None:
            continue
        offset = len(message) - len(message.lstrip())
        fields, spans = {}, {}
        for name in ('entity', 'attribute', 'scope', 'old', 'new'):
            start, end = match.span(name)
            # Quitar espacios y punto final pertenecientes a la puntuación.
            while end > start and message.strip()[end-1] in ' .':
                end -= 1
            while start < end and message.strip()[start].isspace():
                start += 1
            raw = message[start+offset:end+offset]
            if not raw or _UNSAFE.search(raw) or _AMBIGUOUS.search(raw):
                return Extraction('abstain', 'ambiguous_or_modal_field', {}, {})
            fields[name] = normalize(raw)
            spans[name] = (start+offset, end+offset)
        if fields['old'] == fields['new']:
            return Extraction('abstain', 'no_value_change', {}, {})
        return Extraction('proposal', 'explicit_direct_revision', fields, spans)
    return Extraction('abstain', 'unsupported_or_indirect_statement', {}, {})

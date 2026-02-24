import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_SPACES_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class CompiledTerm:
    raw: str
    normalized: str
    tokens: Tuple[str, ...]


def remove_accents(value: str) -> str:
    """Compatibilidad con código legacy: remueve acentos sin limpiar puntuación."""
    if not value:
        return ""
    nfkd_form = unicodedata.normalize("NFKD", str(value))
    return "".join(c for c in nfkd_form if not unicodedata.combining(c))


def normalize_text(value: Any) -> str:
    """
    Normaliza texto para matching robusto:
    - NFKD
    - sin acentos
    - lowercase (casefold)
    - sin puntuación (solo a-z0-9)
    - espacios colapsados
    """
    if value in (None, ""):
        return ""
    text = remove_accents(str(value)).casefold()
    text = _NON_ALNUM_RE.sub(" ", text)
    text = _SPACES_RE.sub(" ", text).strip()
    return text


def _iter_synonym_terms(search_synonyms: Any) -> Iterable[str]:
    if not search_synonyms:
        return
    if isinstance(search_synonyms, dict):
        for base_term, variants in search_synonyms.items():
            if base_term not in (None, ""):
                yield str(base_term)
            if isinstance(variants, str):
                if variants.strip():
                    yield variants
                continue
            if isinstance(variants, (list, tuple, set)):
                for variant in variants:
                    if variant not in (None, ""):
                        yield str(variant)
        return
    if isinstance(search_synonyms, (list, tuple, set)):
        for term in search_synonyms:
            if term not in (None, ""):
                yield str(term)


def compile_match_terms(
    base_terms: Sequence[str],
    search_synonyms: Optional[Any] = None,
) -> List[CompiledTerm]:
    """
    Compila términos de búsqueda + sinónimos, deduplicados por versión normalizada.
    Acepta sinónimos como:
    - dict[str, list[str] | str]
    - list[str]
    """
    unique: Dict[str, CompiledTerm] = {}

    candidates: List[str] = []
    for term in base_terms or []:
        if term not in (None, ""):
            candidates.append(str(term))
    for syn in _iter_synonym_terms(search_synonyms):
        candidates.append(syn)

    for raw in candidates:
        normalized = normalize_text(raw)
        if not normalized:
            continue
        if normalized in unique:
            continue
        tokens = tuple(t for t in normalized.split(" ") if t)
        unique[normalized] = CompiledTerm(raw=raw, normalized=normalized, tokens=tokens)

    return list(unique.values())


def match_text_against_terms(text: str, terms: Sequence[CompiledTerm]) -> Tuple[bool, Optional[str]]:
    """
    Devuelve (match, term_raw) comparando:
    - término completo por tokens
    - contains por frase normalizada
    """
    normalized_text = normalize_text(text)
    if not normalized_text or not terms:
        return False, None

    text_tokens_list = [token for token in normalized_text.split(" ") if token]
    text_tokens = set(text_tokens_list)

    for term in terms:
        if not term.normalized:
            continue

        # Término completo por tokens.
        # Un solo token: match exacto por token.
        if len(term.tokens) == 1 and term.tokens[0] in text_tokens:
            return True, term.raw

        # Múltiples tokens: exigir secuencia contigua en el texto normalizado.
        if len(term.tokens) > 1:
            window = len(term.tokens)
            for idx in range(0, len(text_tokens_list) - window + 1):
                if tuple(text_tokens_list[idx: idx + window]) == term.tokens:
                    return True, term.raw

        # Contains por frase normalizada (para variantes dentro de cadenas largas)
        if term.normalized in normalized_text:
            return True, term.raw

    return False, None


def match_email_candidate(
    subject: str,
    sender: str,
    attachment_names: Sequence[str],
    terms: Sequence[CompiledTerm],
    fallback_sender_match: bool = False,
    fallback_attachment_match: bool = False,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Orden de matching:
    1) asunto (siempre)
    2) remitente (opcional)
    3) adjuntos (opcional)
    """
    matched, term = match_text_against_terms(subject, terms)
    if matched:
        return True, "subject", term

    if fallback_sender_match:
        matched, term = match_text_against_terms(sender, terms)
        if matched:
            return True, "sender", term

    if fallback_attachment_match and attachment_names:
        for name in attachment_names:
            matched, term = match_text_against_terms(name, terms)
            if matched:
                return True, "attachment", term

    return False, None, None

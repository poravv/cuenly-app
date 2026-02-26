import pytest

from app.modules.email_processor.subject_matcher import (
    compile_match_terms,
    match_email_candidate,
    normalize_text,
)


def _compile_default_terms():
    return compile_match_terms(
        ["factura electronica", "comprobante"],
        search_synonyms={
            "factura electronica": ["facturación", "documento electrónico"],
            "comprobante": ["comprobante de pago"],
        },
    )


def test_normalize_text_removes_accents_and_punctuation():
    normalized = normalize_text("Factura electrónica Nº 001/ABC - Óptimo!")
    assert "factura" in normalized
    assert "electronica" in normalized
    assert "001" in normalized
    assert "optimo" in normalized
    assert "/" not in normalized
    assert "-" not in normalized


def test_compile_terms_supports_tenant_synonyms_and_deduplicates():
    terms = compile_match_terms(
        ["factura"],
        search_synonyms={
            "factura": ["facturación", "facturacion"],
            "comprobante": "Comprobante",
        },
    )
    normalized_terms = {t.normalized for t in terms}

    assert "factura" in normalized_terms
    assert "facturacion" in normalized_terms
    assert "comprobante" in normalized_terms
    assert len([t for t in normalized_terms if t == "facturacion"]) == 1


@pytest.mark.parametrize(
    "subject",
    [
        "Factura electrónica SET - febrero",
        "Factura electronica SET - marzo",
        "FACTURACIÓN mensual proveedor ACME",
        "Comprobante de pago #381",
        "Documento Electronico recibido",
    ],
)
def test_real_cases_match_with_or_without_accents(subject):
    terms = _compile_default_terms()
    matched, source, term = match_email_candidate(
        subject=subject,
        sender="",
        attachment_names=[],
        terms=terms,
    )

    assert matched is True
    assert source == "subject"
    assert term is not None


def test_subject_match_uses_full_term_and_contains():
    terms = compile_match_terms(["factura electronica", "comprob"])

    # full-term por tokens (con puntuación intermedia)
    matched_phrase, source_phrase, _ = match_email_candidate(
        subject="Se envia Factura - Electronica correspondiente al periodo",
        sender="",
        attachment_names=[],
        terms=terms,
    )
    assert matched_phrase is True
    assert source_phrase == "subject"

    # contains parcial
    matched_contains, source_contains, _ = match_email_candidate(
        subject="Comprobante tributario adjunto",
        sender="",
        attachment_names=[],
        terms=terms,
    )
    assert matched_contains is True
    assert source_contains == "subject"


def test_fallback_sender_optional():
    terms = _compile_default_terms()

    # Sin fallback por remitente no debe pasar
    matched_without_fallback, _, _ = match_email_candidate(
        subject="Actualización de cuenta",
        sender="facturacion@proveedor.com.py",
        attachment_names=[],
        terms=terms,
        fallback_sender_match=False,
        fallback_attachment_match=False,
    )
    assert matched_without_fallback is False

    # Con fallback por remitente sí debe pasar
    matched_with_fallback, source, _ = match_email_candidate(
        subject="Actualización de cuenta",
        sender="facturacion@proveedor.com.py",
        attachment_names=[],
        terms=terms,
        fallback_sender_match=True,
        fallback_attachment_match=False,
    )
    assert matched_with_fallback is True
    assert source == "sender"


def test_fallback_attachment_optional():
    terms = _compile_default_terms()

    # Sin fallback por adjunto no debe pasar
    matched_without_fallback, _, _ = match_email_candidate(
        subject="Resumen de movimientos",
        sender="notificaciones@proveedor.com.py",
        attachment_names=["comprobante_febrero.xml"],
        terms=terms,
        fallback_sender_match=False,
        fallback_attachment_match=False,
    )
    assert matched_without_fallback is False

    # Con fallback por adjunto sí debe pasar
    matched_with_fallback, source, _ = match_email_candidate(
        subject="Resumen de movimientos",
        sender="notificaciones@proveedor.com.py",
        attachment_names=["comprobante_febrero.xml"],
        terms=terms,
        fallback_sender_match=False,
        fallback_attachment_match=True,
    )
    assert matched_with_fallback is True
    assert source == "attachment"

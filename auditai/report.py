"""EU AI Act Deployer Compliance Report generator — Art. 26."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm, mm
    from reportlab.platypus import (
        HRFlowable,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


# SOC 2 Trust Services Criteria mapped from EU AI Act obligations
SOC2_MAPPING = [
    {
        "eu_article": "Art. 12 — Automatic event logging",
        "soc2": "CC7.1, CC7.2",
        "description": "System activity monitored; anomalies detected",
        "auditai_covered": True,
    },
    {
        "eu_article": "Art. 14 — Human oversight (HITL)",
        "soc2": "CC7.3, CC7.4",
        "description": "Security events evaluated; incidents identified and responded to",
        "auditai_covered": True,
    },
    {
        "eu_article": "Risk classification per call",
        "soc2": "CC7.3",
        "description": "Ongoing evaluation of AI system risk events",
        "auditai_covered": True,
    },
    {
        "eu_article": "Art. 11 — Technical documentation",
        "soc2": "CC8.1",
        "description": "Changes to AI system documented, authorized and tested",
        "auditai_covered": False,
    },
    {
        "eu_article": "Art. 13 — Transparency to users",
        "soc2": "CC6.7",
        "description": "Transmission and disclosure of information restricted and controlled",
        "auditai_covered": False,
    },
    {
        "eu_article": "Art. 26 — Access to AI system",
        "soc2": "CC6.1, CC6.6",
        "description": "Logical access security; protection from external threats",
        "auditai_covered": False,
    },
]

# DORA (Reg. 2022/2554) mapping for EU financial entities
DORA_MAPPING = [
    {
        "dora_article": "Art. 9 — ICT security (Protection)",
        "eu_ai_act": "Risk classification + access controls",
        "auditai_covered": True,
    },
    {
        "dora_article": "Art. 10 — Detection",
        "eu_ai_act": "Art. 12 — Automatic logging of AI interactions",
        "auditai_covered": True,
    },
    {
        "dora_article": "Art. 11 — Response & recovery",
        "eu_ai_act": "Art. 14 — HITL escalation on high-risk calls",
        "auditai_covered": True,
    },
    {
        "dora_article": "Art. 17 — ICT incident reporting",
        "eu_ai_act": "Art. 26 — Deployer declaration + audit trail",
        "auditai_covered": False,
    },
]

RISK_COLOR = {
    "unacceptable": "#DC2626",
    "high": "#EA580C",
    "limited": "#D97706",
    "minimal": "#16A34A",
    "low": "#16A34A",
    "unknown": "#6B7280",
}

RISK_LABEL = {
    "unacceptable": "PROHIBIDO (Art. 5)",
    "high": "ALTO RIESGO (Annex III)",
    "limited": "RIESGO LIMITADO (Art. 52)",
    "minimal": "RIESGO MÍNIMO",
    "low": "RIESGO MÍNIMO",
    "unknown": "NO CLASIFICADO",
}


def generate_report(
    project: str,
    company_name: str,
    contact_email: str,
    risk_assessment: Optional[dict] = None,
    log_dir: Optional[str] = None,
    output_path: Optional[str] = None,
    extra_info: Optional[dict] = None,
    reviewed_by: Optional[str] = None,
) -> str:
    """Generate EU AI Act Deployer Compliance Report (PDF).

    Args:
        project: Project/system name.
        company_name: Legal name of the deploying company.
        contact_email: Compliance contact email.
        risk_assessment: Dict with keys: category, score, reasons, obligations.
        log_dir: Directory with JSONL logs (reads stats automatically).
        output_path: Where to save the PDF. Defaults to ~/auditai_report_{project}.pdf
        extra_info: Additional fields: system_description, use_case, deployment_date.

    Returns:
        Absolute path to the generated PDF.
    """
    if not REPORTLAB_AVAILABLE:
        return _generate_markdown_fallback(
            project, company_name, contact_email,
            risk_assessment, log_dir, output_path, extra_info
        )

    # Load stats from logs if available
    stats = _load_stats(project, log_dir)

    if output_path is None:
        output_path = str(Path.home() / f"auditai_report_{project}_{_today()}.pdf")

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=2.5 * cm,
        rightMargin=2.5 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
    )

    styles = _build_styles()
    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    story.append(Paragraph("auditai", styles["BrandSmall"]))
    story.append(Paragraph("EU AI Act Deployer Compliance Report", styles["Title"]))
    story.append(Paragraph("Regulation (EU) 2024/1689 — Article 26", styles["Subtitle"]))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1E3A5F")))
    story.append(Spacer(1, 0.5 * cm))

    # ── Report metadata table ─────────────────────────────────────────────────
    ei = extra_info or {}
    meta_data = [
        ["Campo", "Valor"],
        ["Empresa / Deployer", company_name],
        ["Proyecto / Sistema IA", project],
        ["Contacto Compliance", contact_email],
        ["Descripción del sistema", ei.get("system_description", "No especificada")],
        ["Caso de uso principal", ei.get("use_case", "No especificado")],
        ["Fecha de generación", _today_full()],
        ["Versión de auditai", "0.1.1"],
    ]
    meta_table = Table(meta_data, colWidths=[5.5 * cm, 11 * cm])
    meta_table.setStyle(_meta_table_style())
    story.append(meta_table)
    story.append(Spacer(1, 0.6 * cm))

    # ── Risk classification ───────────────────────────────────────────────────
    story.append(Paragraph("1. Clasificación de Riesgo EU AI Act", styles["H1"]))

    ra = risk_assessment or {}
    category = _normalize_category(ra.get("category", "unknown"))
    score = ra.get("score", 0)
    reasons = ra.get("reasons", [])
    obligations = ra.get("obligations", [])

    risk_color = colors.HexColor(RISK_COLOR.get(str(category), "#6B7280"))
    risk_label = RISK_LABEL.get(str(category), "NO CLASIFICADO")

    risk_box = Table(
        [[Paragraph(f"<b>{risk_label}</b>", styles["RiskLabel"])]],
        colWidths=[16.5 * cm],
    )
    risk_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), risk_color),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
    ]))
    story.append(risk_box)
    story.append(Spacer(1, 0.3 * cm))

    if reasons:
        story.append(Paragraph("<b>Factores que determinan esta clasificación:</b>", styles["Body"]))
        for r in reasons:
            story.append(Paragraph(f"• {r}", styles["Bullet"]))
    story.append(Spacer(1, 0.4 * cm))

    # ── Obligations ───────────────────────────────────────────────────────────
    story.append(Paragraph("2. Obligaciones Aplicables (Art. 26)", styles["H1"]))
    if obligations:
        for o in obligations:
            done = "auditai" in o.lower() or "✅" in o
            icon = "✅" if done else "⬜"
            story.append(Paragraph(f"{icon} {o}", styles["Bullet"]))
    else:
        story.append(Paragraph(
            "No se identificaron obligaciones específicas para este sistema. "
            "Se recomienda adoptar buenas prácticas voluntarias.",
            styles["Body"]
        ))
    story.append(Spacer(1, 0.4 * cm))

    # ── Technical evidence (from JSONL logs) ─────────────────────────────────
    story.append(Paragraph("3. Evidencia Técnica — Registro de Actividad (Art. 12)", styles["H1"]))
    if stats:
        ev_data = [
            ["Métrica", "Valor"],
            ["Total de llamadas registradas", str(stats.get("total_calls", 0))],
            ["Tokens de entrada (acumulado)", f"{stats.get('total_input_tokens', 0):,}"],
            ["Tokens de salida (acumulado)", f"{stats.get('total_output_tokens', 0):,}"],
            ["Eventos HITL (supervisión humana)", str(stats.get("hitl_events", 0))],
            ["Modelos utilizados", ", ".join(stats.get("models_used", [])) or "—"],
            ["Distribución de riesgo por llamada", _format_risk_breakdown(stats.get("risk_breakdown", {}))],
        ]
        ev_table = Table(ev_data, colWidths=[8 * cm, 8.5 * cm])
        ev_table.setStyle(_meta_table_style())
        story.append(ev_table)
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph(
            f"Logs almacenados en: ~/.auditai/logs/{project}.jsonl",
            styles["Code"]
        ))
    else:
        story.append(Paragraph(
            "No se encontraron logs de actividad para este proyecto. "
            "Instala auditai y usa wrap_client() para comenzar a registrar llamadas.",
            styles["Body"]
        ))
    story.append(Spacer(1, 0.4 * cm))

    # ── Transparency declaration ──────────────────────────────────────────────
    story.append(Paragraph("4. Declaración de Transparencia (Art. 13 & 52)", styles["H1"]))
    story.append(Paragraph(
        f"{company_name} declara que el sistema de IA identificado como "
        f"<b>'{project}'</b> utiliza modelos de inteligencia artificial de terceros "
        "mediante API. Los usuarios afectados por decisiones de este sistema son "
        "informados de la naturaleza automatizada de las mismas conforme al Art. 52.",
        styles["Body"]
    ))
    story.append(Spacer(1, 0.4 * cm))

    # ── Human oversight ───────────────────────────────────────────────────────
    story.append(Paragraph("5. Supervisión Humana (Art. 14)", styles["H1"]))
    hitl_events = stats.get("hitl_events", 0) if stats else 0
    story.append(Paragraph(
        f"El sistema registró <b>{hitl_events} evento(s) de supervisión humana (HITL)</b> "
        "en el período cubierto por este informe. "
        + ("Se recomienda incrementar la tasa de revisión humana para casos de riesgo alto."
           if hitl_events == 0 and str(category) in ("high", "unacceptable")
           else "La supervisión humana está activa conforme a los requisitos del sistema."),
        styles["Body"]
    ))
    story.append(Spacer(1, 0.4 * cm))

    # ── SOC 2 mapping ─────────────────────────────────────────────────────────
    story.append(Paragraph("6. SOC 2 Type II Mapping (Trust Services Criteria)", styles["H1"]))
    story.append(Paragraph(
        "The following table maps EU AI Act obligations to SOC 2 Trust Services Criteria. "
        "Criteria marked ✅ are automatically satisfied by auditai instrumentation.",
        styles["Body"]
    ))
    soc2_data = [["EU AI Act Obligation", "SOC 2 Criterion", "Evidence", "Status"]]
    for row in SOC2_MAPPING:
        status = "✅ auditai" if row["auditai_covered"] else "⬜ Manual"
        soc2_data.append([
            row["eu_article"],
            row["soc2"],
            row["description"],
            status,
        ])
    soc2_table = Table(soc2_data, colWidths=[4.8 * cm, 2.2 * cm, 6.5 * cm, 3 * cm])
    soc2_table.setStyle(_compliance_table_style())
    story.append(soc2_table)
    story.append(Spacer(1, 0.4 * cm))

    # ── DORA mapping ──────────────────────────────────────────────────────────
    story.append(Paragraph(
        "7. DORA Mapping — Digital Operational Resilience Act (Reg. 2022/2554)",
        styles["H1"]
    ))
    story.append(Paragraph(
        "For EU financial entities subject to DORA, the following table maps ICT resilience "
        "requirements to the EU AI Act obligations covered by this deployment.",
        styles["Body"]
    ))
    dora_data = [["DORA Article", "EU AI Act Mapping", "Status"]]
    for row in DORA_MAPPING:
        status = "✅ auditai" if row["auditai_covered"] else "⬜ Manual"
        dora_data.append([row["dora_article"], row["eu_ai_act"], status])
    dora_table = Table(dora_data, colWidths=[5.5 * cm, 8.5 * cm, 2.5 * cm])
    dora_table.setStyle(_compliance_table_style())
    story.append(dora_table)
    story.append(Spacer(1, 0.4 * cm))

    # ── Professional review & signature (optional) ────────────────────────────
    if reviewed_by:
        story.append(Paragraph("8. Professional Review &amp; Certification", styles["H1"]))
        navy = colors.HexColor("#1E3A5F")
        sig_box = Table(
            [[Paragraph(
                f"<b>This report has been manually reviewed and certified by:</b><br/><br/>"
                f"<b style='font-size:14'>{reviewed_by}</b><br/>"
                f"EU AI Act Compliance Consultant · auditaisdk.com<br/><br/>"
                f"The undersigned takes professional responsibility for the accuracy of the risk "
                f"classification and obligation mapping contained in this report, based on the "
                f"system description provided by the deployer. This certification is issued "
                f"under the understanding that the information provided by the client is accurate "
                f"and complete.<br/><br/>"
                f"Date: {_today_full()}<br/><br/>"
                f"Signature: ___________________________",
                styles["Body"]
            )]],
            colWidths=[16.5 * cm],
        )
        sig_box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EFF6FF")),
            ("BORDER", (0, 0), (-1, -1), 1.5, navy),
            ("BOX", (0, 0), (-1, -1), 1.5, navy),
            ("TOPPADDING", (0, 0), (-1, -1), 16),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
            ("LEFTPADDING", (0, 0), (-1, -1), 16),
            ("RIGHTPADDING", (0, 0), (-1, -1), 16),
        ]))
        story.append(sig_box)
        story.append(Spacer(1, 0.4 * cm))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#D1D5DB")))
    story.append(Spacer(1, 0.2 * cm))
    footer_text = (
        f"Reviewed and certified by {reviewed_by} · auditaisdk.com · {_today_full()}"
        if reviewed_by else
        "Este informe fue generado automáticamente por auditai v0.1.4. "
        "No constituye asesoramiento jurídico. Para decisiones de compliance definitivas, "
        "consulte con un especialista en derecho de IA europeo."
    )
    story.append(Paragraph(footer_text, styles["Footer"]))
    story.append(Paragraph(
        f"Generado: {_today_full()} · Contacto: {contact_email} · auditaisdk.com",
        styles["Footer"]
    ))

    doc.build(story)
    return output_path


# ── Markdown fallback (no reportlab) ─────────────────────────────────────────

def _generate_markdown_fallback(
    project, company_name, contact_email,
    risk_assessment, log_dir, output_path, extra_info
) -> str:
    stats = _load_stats(project, log_dir)
    ra = risk_assessment or {}
    ei = extra_info or {}
    category = _normalize_category(ra.get("category", "unknown"))
    risk_label = RISK_LABEL.get(category, "NO CLASIFICADO")

    if output_path is None:
        output_path = str(Path.home() / f"auditai_report_{project}_{_today()}.md")

    lines = [
        "# EU AI Act Deployer Compliance Report",
        f"**auditai v0.1.3** · Regulation (EU) 2024/1689 — Article 26",
        "",
        "## Información del Deployer",
        f"- **Empresa:** {company_name}",
        f"- **Proyecto:** {project}",
        f"- **Contacto:** {contact_email}",
        f"- **Descripción:** {ei.get('system_description', 'No especificada')}",
        f"- **Fecha:** {_today_full()}",
        "",
        f"## 1. Clasificación de Riesgo: {risk_label}",
    ]
    for r in ra.get("reasons", []):
        lines.append(f"- {r}")
    lines += ["", "## 2. Obligaciones Aplicables (Art. 26)"]
    for o in ra.get("obligations", []):
        done = "auditai" in o.lower() or "✅" in o
        lines.append(f"- [{'x' if done else ' '}] {o}")

    if stats:
        lines += [
            "", "## 3. Evidencia Técnica (Art. 12)",
            f"- Total llamadas: {stats['total_calls']}",
            f"- Tokens entrada: {stats['total_input_tokens']:,}",
            f"- Tokens salida: {stats['total_output_tokens']:,}",
            f"- Eventos HITL: {stats['hitl_events']}",
            f"- Modelos: {', '.join(stats['models_used']) or '—'}",
        ]

    lines += ["", "## 6. SOC 2 Type II Mapping"]
    lines.append("| EU AI Act | SOC 2 Criterion | Evidence | Status |")
    lines.append("|-----------|-----------------|----------|--------|")
    for row in SOC2_MAPPING:
        status = "✅ auditai" if row["auditai_covered"] else "⬜ Manual"
        lines.append(f"| {row['eu_article']} | {row['soc2']} | {row['description']} | {status} |")

    lines += ["", "## 7. DORA Mapping (Reg. 2022/2554)"]
    lines.append("| DORA Article | EU AI Act Mapping | Status |")
    lines.append("|-------------|-------------------|--------|")
    for row in DORA_MAPPING:
        status = "✅ auditai" if row["auditai_covered"] else "⬜ Manual"
        lines.append(f"| {row['dora_article']} | {row['eu_ai_act']} | {status} |")

    lines += [
        "", "---",
        "_Informe generado por auditai. No constituye asesoramiento jurídico._"
    ]

    Path(output_path).write_text("\n".join(lines), encoding="utf-8")
    return output_path


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalize_category(cat) -> str:
    """Accept RiskCategory enum, 'RiskCategory.HIGH' string, or plain 'high'."""
    if hasattr(cat, "value"):
        return cat.value
    s = str(cat)
    # Handle 'RiskCategory.HIGH' → 'high'
    if "." in s:
        s = s.split(".")[-1].lower()
    return s.lower()


def _load_stats(project: str, log_dir: Optional[str]) -> Optional[dict]:
    try:
        from .logger import AuditLogger
        logger = AuditLogger(project=project, log_dir=log_dir)
        s = logger.stats()
        return s if s["total_calls"] > 0 else None
    except Exception:
        return None


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _today_full() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _format_risk_breakdown(breakdown: dict) -> str:
    if not breakdown:
        return "—"
    return " / ".join(f"{k}: {v}" for k, v in breakdown.items())


def _build_styles():
    base = getSampleStyleSheet()
    navy = colors.HexColor("#1E3A5F")
    dark = colors.HexColor("#111827")
    gray = colors.HexColor("#6B7280")
    return {
        "BrandSmall": ParagraphStyle("BrandSmall", fontSize=9, textColor=gray,
                                     spaceAfter=2, fontName="Helvetica-Bold"),
        "Title": ParagraphStyle("Title", fontSize=22, textColor=navy,
                                spaceAfter=4, fontName="Helvetica-Bold", leading=28),
        "Subtitle": ParagraphStyle("Subtitle", fontSize=11, textColor=gray,
                                   spaceAfter=10, fontName="Helvetica"),
        "H1": ParagraphStyle("H1", fontSize=13, textColor=navy,
                             spaceBefore=12, spaceAfter=6,
                             fontName="Helvetica-Bold", leading=18),
        "Body": ParagraphStyle("Body", fontSize=10, textColor=dark,
                               spaceAfter=6, leading=14, fontName="Helvetica"),
        "Bullet": ParagraphStyle("Bullet", fontSize=10, textColor=dark,
                                 leftIndent=12, spaceAfter=3, leading=14),
        "Code": ParagraphStyle("Code", fontSize=8, textColor=gray,
                               fontName="Courier", spaceAfter=4),
        "RiskLabel": ParagraphStyle("RiskLabel", fontSize=16, textColor=colors.white,
                                    alignment=TA_CENTER, fontName="Helvetica-Bold"),
        "Footer": ParagraphStyle("Footer", fontSize=8, textColor=gray,
                                 spaceAfter=2, alignment=TA_CENTER),
    }


def _meta_table_style():
    navy = colors.HexColor("#1E3A5F")
    light_blue = colors.HexColor("#EFF6FF")
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), navy),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("BACKGROUND", (0, 1), (-1, -1), light_blue),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, light_blue]),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
    ])


def _compliance_table_style():
    """Compact table style for SOC 2 / DORA mapping tables."""
    dark_blue = colors.HexColor("#1E3A5F")
    green_tint = colors.HexColor("#F0FDF4")
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), dark_blue),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, green_tint]),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
        ("WORDWRAP", (0, 0), (-1, -1), True),
    ])

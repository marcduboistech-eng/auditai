"""EU AI Act Deployer Compliance Report generator — Art. 26."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm, mm
    from reportlab.platypus import (
        HRFlowable,
        Image as RLImage,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
        KeepTogether,
    )
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


SOC2_MAPPING = [
    {
        "eu_article": "Art. 12 — Automatic event logging",
        "soc2": "CC7.1, CC7.2",
        "description": "System activity monitored; anomalies detected and evaluated",
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
        "description": "Ongoing evaluation of AI system risk events per interaction",
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

DORA_MAPPING = [
    {
        "dora_article": "Art. 9 — ICT security (Protection)",
        "eu_ai_act": "Risk classification + access controls per AI interaction",
        "auditai_covered": True,
    },
    {
        "dora_article": "Art. 10 — Detection",
        "eu_ai_act": "Art. 12 — Automatic logging of all AI interactions",
        "auditai_covered": True,
    },
    {
        "dora_article": "Art. 11 — Response & recovery",
        "eu_ai_act": "Art. 14 — HITL escalation on high-risk calls",
        "auditai_covered": True,
    },
    {
        "dora_article": "Art. 17 — ICT incident reporting",
        "eu_ai_act": "Art. 26 — Deployer declaration + full audit trail",
        "auditai_covered": False,
    },
]

RISK_COLOR = {
    "unacceptable": "#DC2626",
    "high":         "#EA580C",
    "limited":      "#D97706",
    "minimal":      "#16A34A",
    "low":          "#16A34A",
    "unknown":      "#6B7280",
}

RISK_LABEL = {
    "unacceptable": "PROHIBITED (Art. 5)",
    "high":         "HIGH RISK (Annex III)",
    "limited":      "LIMITED RISK (Art. 52)",
    "minimal":      "MINIMAL RISK",
    "low":          "MINIMAL RISK",
    "unknown":      "UNCLASSIFIED",
}

_VERSION = "0.1.5"


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
    if not REPORTLAB_AVAILABLE:
        return _generate_markdown_fallback(
            project, company_name, contact_email,
            risk_assessment, log_dir, output_path, extra_info,
        )

    stats = _load_stats(project, log_dir)

    if output_path is None:
        output_path = str(Path.home() / f"auditai_report_{project}_{_today()}.pdf")

    PAGE_W = A4[0]
    PAGE_H = A4[1]
    L = R = 2.5 * cm
    T = B = 2.0 * cm
    CONTENT_W = PAGE_W - L - R  # ≈ 16.5 cm

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=L,
        rightMargin=R,
        topMargin=T,
        bottomMargin=B,
    )

    S = _build_styles(CONTENT_W)
    story = []

    # ── Logo / Header bar ─────────────────────────────────────────────────────
    navy = colors.HexColor("#1E3A5F")
    white = colors.white

    _LOGO_PATH = Path(__file__).parent.parent / "assets" / "logo.png"
    logo_h = 1.1 * cm

    if _LOGO_PATH.exists():
        from PIL import Image as _PILImage
        _pil = _PILImage.open(str(_LOGO_PATH))
        _ratio = _pil.width / _pil.height
        logo_img = RLImage(str(_LOGO_PATH), width=logo_h * _ratio, height=logo_h)
        logo_cell = logo_img
    else:
        logo_cell = Paragraph(
            "<b>auditai</b>",
            ParagraphStyle("LogoBig", fontSize=18, textColor=white,
                           fontName="Helvetica-Bold", leading=22),
        )

    version_cell = Paragraph(
        f"v{_VERSION} · EU AI Act SDK",
        ParagraphStyle("LogoSub", fontSize=8, textColor=colors.HexColor("#93C5FD"),
                       fontName="Helvetica", leading=11, alignment=TA_RIGHT),
    )

    logo_table = Table(
        [[logo_cell, version_cell]],
        colWidths=[CONTENT_W * 0.6, CONTENT_W * 0.4],
    )
    logo_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), navy),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING",   (0, 0), (-1, -1), 14),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
    ]))
    story.append(logo_table)
    story.append(Spacer(1, 0.15 * cm))

    # Title strip (lighter navy)
    title_table = Table(
        [[Paragraph("EU AI Act Deployer Compliance Report", S["TitleStrip"]),
          Paragraph("Regulation (EU) 2024/1689 — Article 26", S["SubtitleStrip"])]],
        colWidths=[CONTENT_W * 0.65, CONTENT_W * 0.35],
    )
    title_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#2D4E7E")),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 16),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 16),
    ]))
    story.append(title_table)
    story.append(Spacer(1, 0.5 * cm))

    # ── Metadata table ────────────────────────────────────────────────────────
    ei = extra_info or {}
    meta_rows = [
        [_ph("Field", S["CellHeader"]),   _ph("Value", S["CellHeader"])],
        [_ph("Company / Deployer",   S["CellBold"]), _ph(company_name,                             S["Cell"])],
        [_ph("Project / AI System",  S["CellBold"]), _ph(project,                                  S["Cell"])],
        [_ph("Compliance Contact",   S["CellBold"]), _ph(contact_email,                            S["Cell"])],
        [_ph("System Description",   S["CellBold"]), _ph(ei.get("system_description", "—"),        S["Cell"])],
        [_ph("Primary Use Case",     S["CellBold"]), _ph(ei.get("use_case", "—"),                  S["Cell"])],
        [_ph("Report Generated",     S["CellBold"]), _ph(_today_full(),                            S["Cell"])],
        [_ph("auditai Version",      S["CellBold"]), _ph(_VERSION,                                 S["Cell"])],
    ]
    meta_t = Table(meta_rows, colWidths=[5 * cm, CONTENT_W - 5 * cm])
    meta_t.setStyle(_meta_style())
    story.append(meta_t)
    story.append(Spacer(1, 0.6 * cm))

    # ── 1. Risk classification ────────────────────────────────────────────────
    story.append(Paragraph("1. EU AI Act Risk Classification", S["H1"]))

    ra = risk_assessment or {}
    category  = _normalize_category(ra.get("category", "unknown"))
    score     = ra.get("score", 0)
    reasons   = ra.get("reasons", [])
    obligations = ra.get("obligations", [])

    risk_color = colors.HexColor(RISK_COLOR.get(str(category), "#6B7280"))
    risk_label = RISK_LABEL.get(str(category), "UNCLASSIFIED")

    risk_t = Table(
        [[Paragraph(f"<b>{risk_label}</b>", S["RiskLabel"])]],
        colWidths=[CONTENT_W],
    )
    risk_t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), risk_color),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
    ]))
    story.append(risk_t)
    story.append(Spacer(1, 0.3 * cm))

    if reasons:
        story.append(Paragraph("<b>Factors determining this classification:</b>", S["Body"]))
        for r in reasons:
            story.append(Paragraph(f"• {r}", S["Bullet"]))
    story.append(Spacer(1, 0.4 * cm))

    # ── 2. Obligations ────────────────────────────────────────────────────────
    story.append(Paragraph("2. Applicable Obligations (Art. 26)", S["H1"]))
    if obligations:
        for o in obligations:
            done = "auditai" in o.lower() or "✅" in o
            icon = "✅" if done else "⬜"
            story.append(Paragraph(f"{icon}  {o}", S["Bullet"]))
    else:
        story.append(Paragraph(
            "No specific obligations identified for this system. "
            "Voluntary best practices are recommended.",
            S["Body"],
        ))
    story.append(Spacer(1, 0.4 * cm))

    # ── 3. Technical evidence ─────────────────────────────────────────────────
    story.append(Paragraph("3. Technical Evidence — Activity Log (Art. 12)", S["H1"]))
    if stats:
        ev_rows = [
            [_ph("Metric", S["CellHeader"]),               _ph("Value", S["CellHeader"])],
            [_ph("Total calls logged",    S["CellBold"]),  _ph(str(stats.get("total_calls", 0)),     S["Cell"])],
            [_ph("Input tokens (total)",  S["CellBold"]),  _ph(f"{stats.get('total_input_tokens',0):,}",  S["Cell"])],
            [_ph("Output tokens (total)", S["CellBold"]),  _ph(f"{stats.get('total_output_tokens',0):,}", S["Cell"])],
            [_ph("HITL events",           S["CellBold"]),  _ph(str(stats.get("hitl_events", 0)),     S["Cell"])],
            [_ph("Models used",           S["CellBold"]),  _ph(", ".join(stats.get("models_used", [])) or "—", S["Cell"])],
            [_ph("Risk breakdown",        S["CellBold"]),  _ph(_format_risk_breakdown(stats.get("risk_breakdown", {})), S["Cell"])],
        ]
        ev_t = Table(ev_rows, colWidths=[7 * cm, CONTENT_W - 7 * cm])
        ev_t.setStyle(_meta_style())
        story.append(ev_t)
        story.append(Spacer(1, 0.25 * cm))
        story.append(Paragraph(
            f"Log path: ~/.auditai/logs/{project}.jsonl",
            S["Code"],
        ))
    else:
        story.append(Paragraph(
            "No activity logs found for this project. "
            "Install auditai and use wrap_client() to begin logging.",
            S["Body"],
        ))
    story.append(Spacer(1, 0.4 * cm))

    # ── 4. Transparency declaration ───────────────────────────────────────────
    story.append(Paragraph("4. Transparency Declaration (Art. 13 & 52)", S["H1"]))
    story.append(Paragraph(
        f"<b>{company_name}</b> declares that the AI system identified as "
        f"<i>{project}</i> uses third-party AI models via API. Users affected by "
        "decisions of this system are informed of their automated nature in accordance "
        "with Article 52 of Regulation (EU) 2024/1689.",
        S["Body"],
    ))
    story.append(Spacer(1, 0.4 * cm))

    # ── 5. Human oversight ────────────────────────────────────────────────────
    story.append(Paragraph("5. Human Oversight (Art. 14)", S["H1"]))
    hitl = stats.get("hitl_events", 0) if stats else 0
    story.append(Paragraph(
        f"The system recorded <b>{hitl} human oversight event(s) (HITL)</b> "
        "in the period covered by this report. "
        + ("Human review rate should be increased for high-risk outputs."
           if hitl == 0 and str(category) in ("high", "unacceptable")
           else "Human oversight is active and consistent with system requirements."),
        S["Body"],
    ))
    story.append(Spacer(1, 0.4 * cm))

    # ── 6. SOC 2 mapping ──────────────────────────────────────────────────────
    story.append(Paragraph("6. SOC 2 Type II Mapping (Trust Services Criteria)", S["H1"]))
    story.append(Paragraph(
        "Criteria marked ✅ are automatically satisfied by auditai instrumentation.",
        S["Body"],
    ))
    story.append(Spacer(1, 0.2 * cm))

    CW_SOC = [4.5 * cm, 2.0 * cm, 7.5 * cm, 2.5 * cm]
    soc2_rows = [[
        _ph("EU AI Act Obligation", S["CellHeader"]),
        _ph("SOC 2",                S["CellHeader"]),
        _ph("Evidence",             S["CellHeader"]),
        _ph("Status",               S["CellHeader"]),
    ]]
    for row in SOC2_MAPPING:
        status = "✅ auditai" if row["auditai_covered"] else "⬜ Manual"
        soc2_rows.append([
            _ph(row["eu_article"],  S["CellBold"]),
            _ph(row["soc2"],        S["Cell"]),
            _ph(row["description"], S["Cell"]),
            _ph(status,             S["Cell"]),
        ])
    soc2_t = Table(soc2_rows, colWidths=CW_SOC, repeatRows=1)
    soc2_t.setStyle(_compliance_style())
    story.append(KeepTogether(soc2_t))
    story.append(Spacer(1, 0.5 * cm))

    # ── 7. DORA mapping ───────────────────────────────────────────────────────
    story.append(Paragraph(
        "7. DORA Mapping — Digital Operational Resilience Act (Reg. 2022/2554)",
        S["H1"],
    ))
    story.append(Paragraph(
        "For EU financial entities subject to DORA, the table below maps ICT resilience "
        "requirements to the EU AI Act obligations covered by this deployment.",
        S["Body"],
    ))
    story.append(Spacer(1, 0.2 * cm))

    CW_DORA = [5.0 * cm, 9.0 * cm, 2.5 * cm]
    dora_rows = [[
        _ph("DORA Article",      S["CellHeader"]),
        _ph("EU AI Act Mapping", S["CellHeader"]),
        _ph("Status",            S["CellHeader"]),
    ]]
    for row in DORA_MAPPING:
        status = "✅ auditai" if row["auditai_covered"] else "⬜ Manual"
        dora_rows.append([
            _ph(row["dora_article"], S["CellBold"]),
            _ph(row["eu_ai_act"],    S["Cell"]),
            _ph(status,              S["Cell"]),
        ])
    dora_t = Table(dora_rows, colWidths=CW_DORA, repeatRows=1)
    dora_t.setStyle(_compliance_style())
    story.append(KeepTogether(dora_t))
    story.append(Spacer(1, 0.4 * cm))

    # ── 8. Professional review (optional) ────────────────────────────────────
    if reviewed_by:
        story.append(Paragraph("8. Professional Review &amp; Certification", S["H1"]))
        sig_content = (
            f"<b>This report has been manually reviewed and certified by:</b><br/><br/>"
            f"<b>{reviewed_by}</b><br/>"
            f"EU AI Act Compliance Consultant · auditaisdk.com<br/><br/>"
            f"The undersigned takes professional responsibility for the accuracy of the "
            f"risk classification and obligation mapping contained in this report, based "
            f"on the system description provided by the deployer. This certification is "
            f"issued under the understanding that the information provided by the client "
            f"is accurate and complete.<br/><br/>"
            f"Date: {_today_full()}<br/><br/>"
            f"Signature: ___________________________"
        )
        sig_t = Table(
            [[Paragraph(sig_content, S["Body"])]],
            colWidths=[CONTENT_W],
        )
        sig_t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#EFF6FF")),
            ("BOX",           (0, 0), (-1, -1), 1.5, navy),
            ("TOPPADDING",    (0, 0), (-1, -1), 16),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
            ("LEFTPADDING",   (0, 0), (-1, -1), 16),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 16),
        ]))
        story.append(sig_t)
        story.append(Spacer(1, 0.4 * cm))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.75,
                             color=colors.HexColor("#D1D5DB")))
    story.append(Spacer(1, 0.2 * cm))

    if reviewed_by:
        footer_line1 = f"Reviewed and certified by {reviewed_by} · auditaisdk.com"
    else:
        footer_line1 = (
            "This report was generated automatically by auditai. "
            "It does not constitute legal advice. Consult an EU AI law specialist for definitive compliance decisions."
        )
    story.append(Paragraph(footer_line1, S["Footer"]))
    story.append(Paragraph(
        f"Generated: {_today_full()} · {contact_email} · auditaisdk.com",
        S["Footer"],
    ))

    doc.build(story)
    return output_path


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ph(text: str, style) -> Paragraph:
    """Wrap text in a Paragraph so table cells wrap correctly."""
    return Paragraph(str(text), style)


def _normalize_category(cat) -> str:
    if hasattr(cat, "value"):
        return cat.value
    s = str(cat)
    if "." in s:
        s = s.split(".")[-1]
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
    return " · ".join(f"{k.split('.')[-1]}: {v}" for k, v in breakdown.items())


def _build_styles(content_w: float) -> dict:
    navy = colors.HexColor("#1E3A5F")
    dark = colors.HexColor("#111827")
    gray = colors.HexColor("#6B7280")
    white = colors.white

    return {
        "TitleStrip": ParagraphStyle(
            "TitleStrip", fontSize=13, textColor=white,
            fontName="Helvetica-Bold", leading=17,
        ),
        "SubtitleStrip": ParagraphStyle(
            "SubtitleStrip", fontSize=8, textColor=colors.HexColor("#93C5FD"),
            fontName="Helvetica", leading=11, alignment=TA_RIGHT,
        ),
        "H1": ParagraphStyle(
            "H1", fontSize=11, textColor=navy,
            spaceBefore=10, spaceAfter=5,
            fontName="Helvetica-Bold", leading=15,
            borderPad=(0, 0, 4, 0),
        ),
        "Body": ParagraphStyle(
            "Body", fontSize=9, textColor=dark,
            spaceAfter=5, leading=13, fontName="Helvetica",
        ),
        "Bullet": ParagraphStyle(
            "Bullet", fontSize=9, textColor=dark,
            leftIndent=10, spaceAfter=3, leading=13, fontName="Helvetica",
        ),
        "Code": ParagraphStyle(
            "Code", fontSize=8, textColor=gray,
            fontName="Courier", spaceAfter=4, leading=11,
        ),
        "RiskLabel": ParagraphStyle(
            "RiskLabel", fontSize=14, textColor=white,
            alignment=TA_CENTER, fontName="Helvetica-Bold", leading=18,
        ),
        "Footer": ParagraphStyle(
            "Footer", fontSize=7.5, textColor=gray,
            spaceAfter=2, alignment=TA_CENTER, leading=11,
        ),
        # Table cell styles
        "CellHeader": ParagraphStyle(
            "CellHeader", fontSize=8.5, textColor=white,
            fontName="Helvetica-Bold", leading=12,
        ),
        "CellBold": ParagraphStyle(
            "CellBold", fontSize=8.5, textColor=dark,
            fontName="Helvetica-Bold", leading=12,
        ),
        "Cell": ParagraphStyle(
            "Cell", fontSize=8.5, textColor=dark,
            fontName="Helvetica", leading=12,
        ),
    }


def _meta_style() -> TableStyle:
    navy = colors.HexColor("#1E3A5F")
    light = colors.HexColor("#F0F4FF")
    return TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  navy),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, light]),
        ("ALIGN",         (0, 0), (-1, -1), "LEFT"),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
    ])


def _compliance_style() -> TableStyle:
    navy = colors.HexColor("#1E3A5F")
    green = colors.HexColor("#F0FDF4")
    return TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  navy),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, green]),
        ("ALIGN",         (0, 0), (-1, -1), "LEFT"),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
    ])


# ── Markdown fallback (no reportlab) ─────────────────────────────────────────

def _generate_markdown_fallback(
    project, company_name, contact_email,
    risk_assessment, log_dir, output_path, extra_info,
) -> str:
    stats = _load_stats(project, log_dir)
    ra = risk_assessment or {}
    ei = extra_info or {}
    category = _normalize_category(ra.get("category", "unknown"))
    risk_label = RISK_LABEL.get(category, "UNCLASSIFIED")

    if output_path is None:
        output_path = str(Path.home() / f"auditai_report_{project}_{_today()}.md")

    lines = [
        "# EU AI Act Deployer Compliance Report",
        f"**auditai v{_VERSION}** · Regulation (EU) 2024/1689 — Article 26",
        "",
        "## Deployer Information",
        f"- **Company:** {company_name}",
        f"- **Project:** {project}",
        f"- **Contact:** {contact_email}",
        f"- **Description:** {ei.get('system_description', '—')}",
        f"- **Date:** {_today_full()}",
        "",
        f"## 1. Risk Classification: {risk_label}",
    ]
    for r in ra.get("reasons", []):
        lines.append(f"- {r}")
    lines += ["", "## 2. Applicable Obligations (Art. 26)"]
    for o in ra.get("obligations", []):
        done = "auditai" in o.lower() or "✅" in o
        lines.append(f"- [{'x' if done else ' '}] {o}")

    if stats:
        lines += [
            "", "## 3. Technical Evidence (Art. 12)",
            f"- Total calls: {stats['total_calls']}",
            f"- Input tokens: {stats['total_input_tokens']:,}",
            f"- Output tokens: {stats['total_output_tokens']:,}",
            f"- HITL events: {stats['hitl_events']}",
            f"- Models: {', '.join(stats['models_used']) or '—'}",
        ]

    lines += ["", "## 6. SOC 2 Type II Mapping"]
    lines.append("| EU AI Act Obligation | SOC 2 Criterion | Evidence | Status |")
    lines.append("|----------------------|-----------------|----------|--------|")
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
        "_Report generated by auditai. Does not constitute legal advice._",
    ]

    Path(output_path).write_text("\n".join(lines), encoding="utf-8")
    return output_path

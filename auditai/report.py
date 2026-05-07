"""EU AI Act Deployer Compliance Report generator — Art. 26."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        BaseDocTemplate,
        Frame,
        HRFlowable,
        KeepTogether,
        PageTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
    )
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


SOC2_MAPPING = [
    {"eu_article": "Art. 12 — Automatic event logging",  "soc2": "CC7.1, CC7.2", "description": "System activity monitored; anomalies detected and evaluated",               "auditai_covered": True},
    {"eu_article": "Art. 14 — Human oversight (HITL)",   "soc2": "CC7.3, CC7.4", "description": "Security events evaluated; incidents identified and responded to",          "auditai_covered": True},
    {"eu_article": "Risk classification per call",        "soc2": "CC7.3",        "description": "Ongoing evaluation of AI system risk events per interaction",               "auditai_covered": True},
    {"eu_article": "Art. 11 — Technical documentation",  "soc2": "CC8.1",        "description": "Changes to AI system documented, authorized and tested",                   "auditai_covered": False},
    {"eu_article": "Art. 13 — Transparency to users",    "soc2": "CC6.7",        "description": "Transmission and disclosure of information restricted and controlled",     "auditai_covered": False},
    {"eu_article": "Art. 26 — Access to AI system",      "soc2": "CC6.1, CC6.6", "description": "Logical access security; protection from external threats",                "auditai_covered": False},
]

DORA_MAPPING = [
    {"dora_article": "Art. 9 — ICT security (Protection)", "eu_ai_act": "Risk classification + access controls per AI interaction",  "auditai_covered": True},
    {"dora_article": "Art. 10 — Detection",                "eu_ai_act": "Art. 12 — Automatic logging of all AI interactions",       "auditai_covered": True},
    {"dora_article": "Art. 11 — Response & recovery",      "eu_ai_act": "Art. 14 — HITL escalation on high-risk calls",            "auditai_covered": True},
    {"dora_article": "Art. 17 — ICT incident reporting",   "eu_ai_act": "Art. 26 — Deployer declaration + full audit trail",       "auditai_covered": False},
]

RISK_HEX = {
    "unacceptable": "#DC2626", "high": "#EA580C",
    "limited": "#D97706",      "minimal": "#16A34A",
    "low": "#16A34A",          "unknown": "#6B7280",
}
RISK_LABEL = {
    "unacceptable": "PROHIBITED — Art. 5",
    "high":         "HIGH RISK — Annex III",
    "limited":      "LIMITED RISK — Art. 52",
    "minimal":      "MINIMAL RISK",
    "low":          "MINIMAL RISK",
    "unknown":      "UNCLASSIFIED",
}

_VERSION = "0.1.5"
_NAVY    = "#1E3A5F"
_DARK    = "#111827"
_GRAY    = "#6B7280"
_LGRAY   = "#F3F4F6"
_BORDER  = "#E5E7EB"


# ── Public API ────────────────────────────────────────────────────────────────

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
        return _markdown_fallback(project, company_name, contact_email,
                                  risk_assessment, log_dir, output_path, extra_info)

    stats = _load_stats(project, log_dir)
    if output_path is None:
        output_path = str(Path.home() / f"auditai_report_{project}_{_today()}.pdf")

    PAGE_W, PAGE_H = A4
    ML = MR = 2.5 * cm
    MT = 2.8 * cm   # leave room for running header
    MB = 2.2 * cm   # leave room for footer
    CW = PAGE_W - ML - MR   # ≈ 16.2 cm

    S = _styles(CW)

    # ── Canvas callbacks (running header + footer on every page) ──────────────
    def _header_footer(canvas, doc):
        canvas.saveState()
        navy = colors.HexColor(_NAVY)
        gray = colors.HexColor(_GRAY)

        # Top accent line
        canvas.setStrokeColor(navy)
        canvas.setLineWidth(2.5)
        canvas.line(ML, PAGE_H - 1.2 * cm, PAGE_W - MR, PAGE_H - 1.2 * cm)

        # Brand name top-left
        canvas.setFont("Helvetica-Bold", 9)
        canvas.setFillColor(navy)
        canvas.drawString(ML, PAGE_H - 0.9 * cm, "auditai")

        # Doc title top-right (muted)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(gray)
        canvas.drawRightString(PAGE_W - MR, PAGE_H - 0.9 * cm,
                               "EU AI Act Deployer Compliance Report")

        # Footer line
        canvas.setStrokeColor(colors.HexColor(_BORDER))
        canvas.setLineWidth(0.5)
        canvas.line(ML, MB - 0.4 * cm, PAGE_W - MR, MB - 0.4 * cm)

        # Page number bottom-right
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(gray)
        canvas.drawRightString(PAGE_W - MR, MB - 0.7 * cm,
                               f"Page {doc.page}")

        # auditaisdk.com bottom-center
        canvas.drawCentredString(PAGE_W / 2, MB - 0.7 * cm, "auditaisdk.com")

        canvas.restoreState()

    frame = Frame(ML, MB, CW, PAGE_H - MT - MB, id="main")
    tmpl  = PageTemplate(id="all", frames=[frame], onPage=_header_footer)
    doc   = BaseDocTemplate(output_path, pagesize=A4, pageTemplates=[tmpl])

    story = []

    # ── Document title block ──────────────────────────────────────────────────
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("EU AI Act Deployer Compliance Report", S["DocTitle"]))
    story.append(Paragraph("Regulation (EU) 2024/1689 · Article 26", S["DocSub"]))
    story.append(Spacer(1, 0.15 * cm))
    story.append(HRFlowable(width="100%", thickness=0.5,
                             color=colors.HexColor(_BORDER)))
    story.append(Spacer(1, 0.5 * cm))

    # ── Metadata ──────────────────────────────────────────────────────────────
    ei = extra_info or {}
    meta = Table(
        [
            [_p("Company",            S["MetaKey"]), _p(company_name,                                  S["MetaVal"])],
            [_p("Project / AI System",S["MetaKey"]), _p(project,                                       S["MetaVal"])],
            [_p("Compliance contact", S["MetaKey"]), _p(contact_email,                                 S["MetaVal"])],
            [_p("System description", S["MetaKey"]), _p(ei.get("system_description", "—"),             S["MetaVal"])],
            [_p("Use case",           S["MetaKey"]), _p(ei.get("use_case", "—"),                       S["MetaVal"])],
            [_p("Report generated",   S["MetaKey"]), _p(_today_full(),                                 S["MetaVal"])],
            [_p("SDK version",        S["MetaKey"]), _p(_VERSION,                                      S["MetaVal"])],
        ],
        colWidths=[4.5 * cm, CW - 4.5 * cm],
    )
    meta.setStyle(_meta_ts())
    story.append(meta)
    story.append(Spacer(1, 0.7 * cm))

    # ── 1. Risk ───────────────────────────────────────────────────────────────
    ra       = risk_assessment or {}
    category = _norm(ra.get("category", "unknown"))
    reasons  = ra.get("reasons", [])
    obligations = ra.get("obligations", [])
    r_hex    = RISK_HEX.get(category, _GRAY)
    r_label  = RISK_LABEL.get(category, "UNCLASSIFIED")

    story.append(_h1("1. EU AI Act Risk Classification", S))
    story.append(Spacer(1, 0.15 * cm))

    badge = Table(
        [[_p(r_label, S["BadgeText"])]],
        colWidths=[6 * cm],
    )
    badge.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor(r_hex)),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 14),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
        ("ALIGN",         (0, 0), (-1, -1), "LEFT"),
    ]))
    # Left-align the badge (don't stretch full width)
    badge_row = Table([[badge, ""]], colWidths=[6.5 * cm, CW - 6.5 * cm])
    badge_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
    ]))
    story.append(badge_row)

    if reasons:
        story.append(Spacer(1, 0.25 * cm))
        for r in reasons:
            story.append(_p(f"· {r}", S["Bullet"]))
    story.append(Spacer(1, 0.5 * cm))

    # ── 2. Obligations ────────────────────────────────────────────────────────
    story.append(_h1("2. Applicable Obligations (Art. 26)", S))
    if obligations:
        for o in obligations:
            icon = "✓" if ("auditai" in o.lower() or "✅" in o) else "○"
            story.append(_p(f"{icon}  {o}", S["Bullet"]))
    else:
        story.append(_p(
            "No specific obligations identified. Voluntary best practices recommended.",
            S["Body"],
        ))
    story.append(Spacer(1, 0.5 * cm))

    # ── 3. Technical evidence ─────────────────────────────────────────────────
    story.append(_h1("3. Technical Evidence — Activity Log (Art. 12)", S))
    if stats:
        ev = Table(
            [
                [_p("Total calls logged",    S["MetaKey"]), _p(str(stats.get("total_calls", 0)),                                          S["MetaVal"])],
                [_p("Input tokens",          S["MetaKey"]), _p(f"{stats.get('total_input_tokens', 0):,}",                                 S["MetaVal"])],
                [_p("Output tokens",         S["MetaKey"]), _p(f"{stats.get('total_output_tokens', 0):,}",                                S["MetaVal"])],
                [_p("HITL events",           S["MetaKey"]), _p(str(stats.get("hitl_events", 0)),                                         S["MetaVal"])],
                [_p("Models used",           S["MetaKey"]), _p(", ".join(stats.get("models_used", [])) or "—",                           S["MetaVal"])],
                [_p("Risk distribution",     S["MetaKey"]), _p(_fmt_risk(stats.get("risk_breakdown", {})),                                S["MetaVal"])],
            ],
            colWidths=[4.5 * cm, CW - 4.5 * cm],
        )
        ev.setStyle(_meta_ts())
        story.append(ev)
        story.append(Spacer(1, 0.2 * cm))
        story.append(_p(f"Log: ~/.auditai/logs/{project}.jsonl", S["Code"]))
    else:
        story.append(_p(
            "No activity logs found. Use wrap_client() to begin logging.",
            S["Body"],
        ))
    story.append(Spacer(1, 0.5 * cm))

    # ── 4. Transparency ───────────────────────────────────────────────────────
    story.append(_h1("4. Transparency Declaration (Art. 13 & 52)", S))
    story.append(_p(
        f"<b>{company_name}</b> declares that the AI system <i>{project}</i> uses "
        "third-party AI models via API. Users affected by automated decisions are "
        "informed of their nature in accordance with Article 52 of Regulation (EU) 2024/1689.",
        S["Body"],
    ))
    story.append(Spacer(1, 0.5 * cm))

    # ── 5. Human oversight ────────────────────────────────────────────────────
    story.append(_h1("5. Human Oversight (Art. 14)", S))
    hitl = stats.get("hitl_events", 0) if stats else 0
    story.append(_p(
        f"The system recorded <b>{hitl} HITL event(s)</b> in the period covered. "
        + ("Consider increasing human review for high-risk outputs."
           if hitl == 0 and category in ("high", "unacceptable")
           else "Human oversight is active and consistent with system requirements."),
        S["Body"],
    ))
    story.append(Spacer(1, 0.5 * cm))

    # ── 6. SOC 2 ──────────────────────────────────────────────────────────────
    story.append(_h1("6. SOC 2 Type II Mapping (Trust Services Criteria)", S))
    story.append(_p(
        "Obligations marked (checkmark) are automatically covered by auditai instrumentation.",
        S["Body"],
    ))
    story.append(Spacer(1, 0.2 * cm))

    CW_SOC = [CW * 0.285, CW * 0.125, CW * 0.435, CW * 0.155]   # sums to CW
    soc_rows = [[_p(h, S["ThCell"]) for h in ["EU AI Act Obligation", "SOC 2", "Evidence", "Status"]]]
    for row in SOC2_MAPPING:
        soc_rows.append([
            _p(row["eu_article"],  S["TdBold"]),
            _p(row["soc2"],        S["Td"]),
            _p(row["description"], S["Td"]),
            _p("✓  auditai" if row["auditai_covered"] else "–  Manual", S["Td"]),
        ])
    soc_t = Table(soc_rows, colWidths=CW_SOC, repeatRows=1)
    soc_t.setStyle(_data_ts())
    story.append(KeepTogether(soc_t))
    story.append(Spacer(1, 0.5 * cm))

    # ── 7. DORA ───────────────────────────────────────────────────────────────
    story.append(_h1("7. DORA Mapping — Digital Operational Resilience Act (Reg. 2022/2554)", S))
    story.append(_p(
        "Maps ICT resilience requirements to EU AI Act obligations covered by this deployment.",
        S["Body"],
    ))
    story.append(Spacer(1, 0.2 * cm))

    CW_DORA = [CW * 0.30, CW * 0.575, CW * 0.125]   # sums to CW
    dora_rows = [[_p(h, S["ThCell"]) for h in ["DORA Article", "EU AI Act Mapping", "Status"]]]
    for row in DORA_MAPPING:
        dora_rows.append([
            _p(row["dora_article"], S["TdBold"]),
            _p(row["eu_ai_act"],    S["Td"]),
            _p("✓  auditai" if row["auditai_covered"] else "–  Manual", S["Td"]),
        ])
    dora_t = Table(dora_rows, colWidths=CW_DORA, repeatRows=1)
    dora_t.setStyle(_data_ts())
    story.append(KeepTogether(dora_t))
    story.append(Spacer(1, 0.5 * cm))

    # ── 8. Signature (optional) ───────────────────────────────────────────────
    if reviewed_by:
        story.append(_h1("8. Professional Review & Certification", S))
        sig_t = Table(
            [[_p(
                f"<b>Reviewed and certified by: {reviewed_by}</b><br/>"
                f"EU AI Act Compliance Consultant · auditaisdk.com<br/><br/>"
                "The undersigned takes professional responsibility for the accuracy of the "
                "risk classification and obligation mapping in this report, based on the "
                "system description provided by the deployer.<br/><br/>"
                f"Date: {_today_full()}<br/><br/>"
                "Signature: ___________________________",
                S["Body"],
            )]],
            colWidths=[CW],
        )
        sig_t.setStyle(TableStyle([
            ("BOX",           (0, 0), (-1, -1), 1, colors.HexColor(_NAVY)),
            ("TOPPADDING",    (0, 0), (-1, -1), 14),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
            ("LEFTPADDING",   (0, 0), (-1, -1), 14),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
        ]))
        story.append(sig_t)
        story.append(Spacer(1, 0.4 * cm))

    # ── Legal disclaimer ──────────────────────────────────────────────────────
    story.append(Spacer(1, 0.3 * cm))
    disclaimer = (
        f"Reviewed and certified by {reviewed_by} · auditaisdk.com · {_today_full()}"
        if reviewed_by else
        "This report was generated automatically by auditai and does not constitute legal advice. "
        "Consult a qualified EU AI law specialist for definitive compliance decisions."
    )
    story.append(_p(disclaimer, S["Disclaimer"]))

    doc.build(story)
    return output_path


# ── Helpers ───────────────────────────────────────────────────────────────────

def _p(text: str, style) -> Paragraph:
    return Paragraph(str(text), style)


def _h1(text: str, S: dict):
    """Section heading with left navy rule."""
    t = Table(
        [[_p(text, S["H1"])]],
        colWidths=["100%"],
    )
    t.setStyle(TableStyle([
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBEFORE",    (0, 0), (0, -1),  3, colors.HexColor(_NAVY)),
    ]))
    return t


def _norm(cat) -> str:
    if hasattr(cat, "value"):
        return cat.value
    s = str(cat)
    return s.split(".")[-1].lower() if "." in s else s.lower()


def _load_stats(project: str, log_dir: Optional[str]) -> Optional[dict]:
    try:
        from .logger import AuditLogger
        s = AuditLogger(project=project, log_dir=log_dir).stats()
        return s if s["total_calls"] > 0 else None
    except Exception:
        return None


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _today_full() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _fmt_risk(breakdown: dict) -> str:
    if not breakdown:
        return "—"
    return "  ·  ".join(f"{k.split('.')[-1]}: {v}" for k, v in breakdown.items())


def _styles(content_w: float) -> dict:
    navy = colors.HexColor(_NAVY)
    dark = colors.HexColor(_DARK)
    gray = colors.HexColor(_GRAY)
    white = colors.white

    return {
        "DocTitle": ParagraphStyle(
            "DocTitle", fontSize=20, fontName="Helvetica-Bold",
            textColor=navy, leading=24, spaceAfter=4,
        ),
        "DocSub": ParagraphStyle(
            "DocSub", fontSize=9, fontName="Helvetica",
            textColor=gray, leading=13, spaceAfter=8,
        ),
        "H1": ParagraphStyle(
            "H1", fontSize=10.5, fontName="Helvetica-Bold",
            textColor=navy, leading=14,
        ),
        "Body": ParagraphStyle(
            "Body", fontSize=9, fontName="Helvetica",
            textColor=dark, leading=13, spaceAfter=4,
        ),
        "Bullet": ParagraphStyle(
            "Bullet", fontSize=9, fontName="Helvetica",
            textColor=dark, leading=13, leftIndent=8, spaceAfter=3,
        ),
        "Code": ParagraphStyle(
            "Code", fontSize=7.5, fontName="Courier",
            textColor=gray, leading=11, spaceAfter=3,
        ),
        "Disclaimer": ParagraphStyle(
            "Disclaimer", fontSize=7.5, fontName="Helvetica",
            textColor=gray, leading=11, alignment=TA_CENTER,
        ),
        "BadgeText": ParagraphStyle(
            "BadgeText", fontSize=9, fontName="Helvetica-Bold",
            textColor=white, leading=13,
        ),
        # Metadata table
        "MetaKey": ParagraphStyle(
            "MetaKey", fontSize=8.5, fontName="Helvetica-Bold",
            textColor=dark, leading=12,
        ),
        "MetaVal": ParagraphStyle(
            "MetaVal", fontSize=8.5, fontName="Helvetica",
            textColor=dark, leading=12,
        ),
        # Data tables
        "ThCell": ParagraphStyle(
            "ThCell", fontSize=8, fontName="Helvetica-Bold",
            textColor=white, leading=11,
        ),
        "TdBold": ParagraphStyle(
            "TdBold", fontSize=8, fontName="Helvetica-Bold",
            textColor=dark, leading=11,
        ),
        "Td": ParagraphStyle(
            "Td", fontSize=8, fontName="Helvetica",
            textColor=dark, leading=11,
        ),
    }


def _meta_ts() -> TableStyle:
    """Metadata table: no colored header, just subtle alternating rows."""
    return TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor(_LGRAY)]),
        ("FONTNAME",       (0, 0), (0, -1),  "Helvetica-Bold"),
        ("ALIGN",          (0, 0), (-1, -1), "LEFT"),
        ("VALIGN",         (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",     (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 5),
        ("LEFTPADDING",    (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 8),
        ("LINEBELOW",      (0, 0), (-1, -2), 0.3, colors.HexColor(_BORDER)),
        ("LINEBELOW",      (0, -1), (-1, -1), 0.3, colors.HexColor(_BORDER)),
        ("LINEBEFORE",     (0, 0), (0, -1),  3,   colors.HexColor(_NAVY)),
    ])


def _data_ts() -> TableStyle:
    """Data tables (SOC 2, DORA): navy header, minimal borders."""
    return TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  colors.HexColor(_NAVY)),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, colors.HexColor(_LGRAY)]),
        ("ALIGN",         (0, 0), (-1, -1), "LEFT"),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 7),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 7),
        ("LINEBELOW",     (0, 0), (-1, -2), 0.3, colors.HexColor(_BORDER)),
        ("LINEBELOW",     (0, -1), (-1, -1), 0.3, colors.HexColor(_BORDER)),
    ])


# ── Markdown fallback ─────────────────────────────────────────────────────────

def _markdown_fallback(project, company_name, contact_email,
                       risk_assessment, log_dir, output_path, extra_info) -> str:
    stats = _load_stats(project, log_dir)
    ra = risk_assessment or {}
    ei = extra_info or {}
    category = _norm(ra.get("category", "unknown"))
    risk_label = RISK_LABEL.get(category, "UNCLASSIFIED")
    if output_path is None:
        output_path = str(Path.home() / f"auditai_report_{project}_{_today()}.md")
    lines = [
        "# EU AI Act Deployer Compliance Report",
        f"**auditai v{_VERSION}** · Regulation (EU) 2024/1689 — Article 26",
        "", "## Deployer Information",
        f"- **Company:** {company_name}", f"- **Project:** {project}",
        f"- **Contact:** {contact_email}",
        f"- **Description:** {ei.get('system_description', '—')}",
        f"- **Date:** {_today_full()}",
        "", f"## 1. Risk Classification: {risk_label}",
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
    lines += ["", "---", "_Does not constitute legal advice._"]
    Path(output_path).write_text("\n".join(lines), encoding="utf-8")
    return output_path

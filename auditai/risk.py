"""EU AI Act risk classifier — Art. 6 & Annex III categories."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RiskCategory(str, Enum):
    UNACCEPTABLE = "unacceptable"   # Art. 5 — banned
    HIGH = "high"                    # Annex III — full obligations
    LIMITED = "limited"              # Art. 52 — transparency only
    MINIMAL = "minimal"              # No specific obligations
    LOW = "low"                      # Alias for minimal


# EU AI Act Annex III high-risk domains
ANNEX_III_DOMAINS = [
    "biometric identification",
    "critical infrastructure",
    "education and vocational training",
    "employment and workers management",
    "essential private/public services",
    "law enforcement",
    "migration and border control",
    "administration of justice",
]

# Art. 5 prohibited use cases
PROHIBITED_PATTERNS = [
    "subliminal manipulation",
    "exploiting vulnerabilities",
    "social scoring",
    "real-time remote biometric",
    "emotion recognition workplace",
    "emotion recognition education",
]


@dataclass
class RiskAssessment:
    category: RiskCategory
    score: int                          # 0-100
    reasons: list[str] = field(default_factory=list)
    obligations: list[str] = field(default_factory=list)
    hitl_required: bool = False


class RiskClassifier:
    """Classifies a use case under EU AI Act risk tiers.

    Quick usage:
        clf = RiskClassifier()
        assessment = clf.classify_from_answers(answers_dict)

    Wizard questions (keys):
        affects_credit      : bool
        affects_employment  : bool
        affects_health      : bool
        affects_education   : bool
        affects_justice     : bool
        affects_infraestructure: bool
        uses_biometrics     : bool
        interacts_with_users: bool
        autonomous_decisions: bool
        use_case_description: str (optional, for keyword scan)
    """

    def classify_from_answers(self, answers: dict) -> RiskAssessment:
        reasons = []
        high_triggers = [
            ("affects_credit", "Afecta decisiones crediticias/financieras (Annex III §5)"),
            ("affects_employment", "Afecta empleo o gestión de trabajadores (Annex III §4)"),
            ("affects_health", "Afecta acceso a servicios de salud (Annex III §5)"),
            ("affects_education", "Afecta acceso a educación (Annex III §3)"),
            ("affects_justice", "Asiste en administración de justicia (Annex III §8)"),
            ("affects_infrastructure", "Gestiona infraestructura crítica (Annex III §2)"),
            ("uses_biometrics", "Usa identificación biométrica (Annex III §1)"),
        ]
        for key, reason in high_triggers:
            if answers.get(key):
                reasons.append(reason)

        # Keyword scan on description
        desc = (answers.get("use_case_description") or "").lower()
        for pattern in PROHIBITED_PATTERNS:
            if pattern in desc:
                return RiskAssessment(
                    category=RiskCategory.UNACCEPTABLE,
                    score=100,
                    reasons=[f"Posible caso de uso prohibido: '{pattern}' (Art. 5)"],
                    obligations=["PROHIBIDO — no puede desplegarse en la UE"],
                    hitl_required=False,
                )
        for domain in ANNEX_III_DOMAINS:
            if domain in desc and domain not in [r for r in reasons]:
                reasons.append(f"Descripción menciona dominio de alto riesgo: '{domain}'")

        if reasons:
            obligations = [
                "Registro en base de datos EU AI Act (Art. 51)",
                "Evaluación de conformidad antes del despliegue (Art. 43)",
                "Sistema de gestión de riesgos (Art. 9)",
                "Gobernanza de datos de entrenamiento (Art. 10)",
                "Documentación técnica completa (Art. 11)",
                "Registro automático de eventos (Art. 12) — ✅ cubierto por auditai",
                "Transparencia hacia usuarios (Art. 13)",
                "Supervisión humana (Art. 14)",
                "Exactitud, robustez y ciberseguridad (Art. 15)",
            ]
            return RiskAssessment(
                category=RiskCategory.HIGH,
                score=80,
                reasons=reasons,
                obligations=obligations,
                hitl_required=True,
            )

        if answers.get("interacts_with_users") or answers.get("autonomous_decisions"):
            return RiskAssessment(
                category=RiskCategory.LIMITED,
                score=40,
                reasons=["Sistema interactúa con personas o toma decisiones autónomas (Art. 52)"],
                obligations=[
                    "Informar a usuarios que interactúan con IA (Art. 52§1)",
                    "Etiquetar contenido generado por IA (Art. 52§3)",
                ],
                hitl_required=False,
            )

        return RiskAssessment(
            category=RiskCategory.MINIMAL,
            score=10,
            reasons=["Caso de uso no identificado como alto riesgo ni con obligaciones de transparencia específicas"],
            obligations=["Buenas prácticas recomendadas (código de conducta voluntario)"],
            hitl_required=False,
        )

    # Key terms extracted from ANNEX_III_DOMAINS for partial matching
    _HIGH_RISK_KEYWORDS = [
        "biometric", "biometría",
        "critical infrastructure", "infraestructura crítica",
        "education", "educación", "vocational",
        "employment", "empleo", "worker", "trabajador",
        "credit", "crédito", "loan", "préstamo", "insurance", "seguro",
        "health", "salud", "medical", "médico",
        "law enforcement", "police", "policía",
        "migration", "border control", "migración",
        "justice", "judicial", "court", "tribunal",
    ]

    def classify_call(
        self,
        model: str,
        input_messages: list,
        output_text: str,
        context: Optional[dict] = None,
    ) -> str:
        """Fast per-call classification for inline logging. Returns category string."""
        if context and context.get("risk_category"):
            return context["risk_category"]
        combined = " ".join(
            m.get("content", "") if isinstance(m, dict) else str(m)
            for m in input_messages
        ).lower() + (output_text or "").lower()
        for pattern in PROHIBITED_PATTERNS:
            if pattern in combined:
                return RiskCategory.UNACCEPTABLE
        for keyword in self._HIGH_RISK_KEYWORDS:
            if keyword in combined:
                return RiskCategory.HIGH
        return RiskCategory.MINIMAL

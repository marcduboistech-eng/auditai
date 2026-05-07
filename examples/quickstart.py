"""
auditai quickstart — simula llamadas sin necesitar claves reales.
Ejecuta: python examples/quickstart.py
"""

import json
import sys
from pathlib import Path

# Allow running from the project root without installing
sys.path.insert(0, str(Path(__file__).parent.parent))

from auditai import generate_report, wrap_client
from auditai.logger import AuditLogger
from auditai.risk import RiskClassifier


def simulate_calls():
    """Simulate logged calls without a real API key."""
    logger = AuditLogger(project="quickstart-demo")

    scenarios = [
        {
            "model": "claude-sonnet-4-6",
            "provider": "anthropic",
            "input_messages": [{"role": "user", "content": "¿Cuánto vale el euro hoy?"}],
            "output_text": "El tipo de cambio EUR/USD es aproximadamente 1.08...",
            "input_tokens": 15,
            "output_tokens": 40,
            "risk_category": "minimal",
        },
        {
            "model": "gpt-4o",
            "provider": "openai",
            "input_messages": [{"role": "user", "content": "Evalúa la solicitud de crédito del cliente #1234"}],
            "output_text": "Basándome en el historial crediticio, recomiendo...",
            "input_tokens": 120,
            "output_tokens": 85,
            "risk_category": "high",
            "hitl_required": True,
        },
        {
            "model": "claude-sonnet-4-6",
            "provider": "anthropic",
            "input_messages": [{"role": "user", "content": "Redacta un email de bienvenida"}],
            "output_text": "Estimado cliente, bienvenido a nuestro servicio...",
            "input_tokens": 30,
            "output_tokens": 95,
            "risk_category": "minimal",
        },
    ]

    print("📝 Registrando llamadas simuladas...")
    for s in scenarios:
        call_id = logger.log_call(**s)
        print(f"  ✅ {s['model']} · {s['risk_category']} · {call_id[:8]}...")

    stats = logger.stats()
    print(f"\n📊 Estadísticas:")
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    return stats


def demo_risk_classifier():
    """Show the risk wizard in action."""
    print("\n🔍 Clasificador de Riesgo EU AI Act:")
    clf = RiskClassifier()

    # High-risk scenario (credit decisions)
    answers_high = {
        "affects_credit": True,
        "affects_employment": False,
        "affects_health": False,
        "affects_education": False,
        "affects_justice": False,
        "affects_infrastructure": False,
        "uses_biometrics": False,
        "interacts_with_users": True,
        "autonomous_decisions": True,
        "use_case_description": "Automated credit scoring for loan applications",
    }
    result = clf.classify_from_answers(answers_high)
    print(f"\n  Escenario: decisiones de crédito")
    print(f"  → Clasificación: {result.category.upper()} (score: {result.score})")
    print(f"  → HITL requerido: {result.hitl_required}")
    print(f"  → Obligaciones: {len(result.obligations)}")

    # Low-risk scenario
    answers_low = {
        "affects_credit": False,
        "affects_employment": False,
        "affects_health": False,
        "affects_education": False,
        "affects_justice": False,
        "affects_infrastructure": False,
        "uses_biometrics": False,
        "interacts_with_users": True,
        "autonomous_decisions": False,
        "use_case_description": "Customer support chatbot for e-commerce",
    }
    result_low = clf.classify_from_answers(answers_low)
    print(f"\n  Escenario: chatbot de soporte")
    print(f"  → Clasificación: {result_low.category.upper()} (score: {result_low.score})")

    return {
        "category": str(result.category),
        "score": result.score,
        "hitl_required": result.hitl_required,
        "reasons": result.reasons,
        "obligations": result.obligations,
    }


def demo_report(assessment: dict):
    """Generate the compliance report."""
    print("\n📄 Generando EU AI Act Deployer Compliance Report...")
    path = generate_report(
        project="quickstart-demo",
        company_name="Demo Company S.L.",
        contact_email="compliance@demo.com",
        risk_assessment=assessment,
        extra_info={
            "system_description": "Sistema de scoring crediticio automatizado",
            "use_case": "Evaluación de solicitudes de préstamos para pymes",
        },
    )
    print(f"  ✅ Report guardado en: {path}")
    return path


if __name__ == "__main__":
    print("=" * 60)
    print("  auditai — EU AI Act Deployer Compliance SDK Demo")
    print("=" * 60)

    simulate_calls()
    assessment = demo_risk_classifier()
    report_path = demo_report(assessment)

    print("\n" + "=" * 60)
    print("✅ Demo completada.")
    print(f"   Log: ~/.auditai/logs/quickstart-demo.jsonl")
    print(f"   Report: {report_path}")
    print("\n🚀 Para usar en tu código:")
    print("   from auditai import wrap_client")
    print("   client = wrap_client(anthropic.Anthropic(), project='mi-app')")
    print("=" * 60)

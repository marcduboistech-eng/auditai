"""Streamlit dashboard — run with: streamlit run -m auditai.dashboard"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main():
    try:
        import streamlit as st
    except ImportError:
        print("Streamlit not installed. Run: pip install streamlit")
        sys.exit(1)

    from .logger import AuditLogger
    from .risk import RiskClassifier, RiskAssessment
    from .report import generate_report

    st.set_page_config(
        page_title="auditai — EU AI Act Dashboard",
        page_icon="⚖️",
        layout="wide",
    )

    # ── Sidebar ───────────────────────────────────────────────────────────────
    st.sidebar.image("https://placeholder.com/80x80", width=60)  # replace with logo
    st.sidebar.title("auditai")
    st.sidebar.caption("EU AI Act Deployer Compliance")

    project = st.sidebar.text_input("Nombre del proyecto", value="my-project")
    log_dir = st.sidebar.text_input("Directorio de logs", value=str(Path.home() / ".auditai" / "logs"))
    company = st.sidebar.text_input("Empresa (para el report)", value="Mi Empresa S.L.")
    email = st.sidebar.text_input("Email de compliance", value="compliance@empresa.com")

    st.sidebar.markdown("---")
    page = st.sidebar.radio("Sección", ["📊 Dashboard", "🔍 Clasificador de Riesgo", "📄 Generar Report"])

    # ── Load data ─────────────────────────────────────────────────────────────
    logger = AuditLogger(project=project, log_dir=log_dir if log_dir else None)
    stats = logger.stats()
    entries = logger.read_all()

    # ── Dashboard page ────────────────────────────────────────────────────────
    if page == "📊 Dashboard":
        st.title("📊 Panel de Actividad")
        st.caption(f"Proyecto: **{project}** · {stats['total_calls']} llamadas registradas")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total llamadas", stats["total_calls"])
        c2.metric("Tokens entrada", f"{stats['total_input_tokens']:,}")
        c3.metric("Tokens salida", f"{stats['total_output_tokens']:,}")
        c4.metric("Eventos HITL", stats["hitl_events"])

        if stats["risk_breakdown"]:
            st.subheader("Distribución de riesgo")
            risk_data = stats["risk_breakdown"]
            cols = st.columns(len(risk_data))
            colors_map = {
                "unacceptable": "🔴",
                "high": "🟠",
                "limited": "🟡",
                "minimal": "🟢",
                "low": "🟢",
                "unknown": "⚪",
            }
            for i, (cat, count) in enumerate(risk_data.items()):
                cols[i].metric(f"{colors_map.get(cat, '⚪')} {cat.upper()}", count)

        if stats["models_used"]:
            st.subheader("Modelos utilizados")
            st.write(", ".join(stats["models_used"]))

        if entries:
            st.subheader("Últimas llamadas")
            import pandas as pd
            df = pd.DataFrame(entries[-50:])
            display_cols = [c for c in [
                "timestamp", "model", "provider", "risk_category",
                "input_tokens", "output_tokens", "hitl_required", "output_preview"
            ] if c in df.columns]
            st.dataframe(df[display_cols], use_container_width=True)
        else:
            st.info(
                "No hay datos todavía. Usa `wrap_client()` en tu código para empezar a registrar llamadas.\n\n"
                "```python\n"
                "from auditai import wrap_client\n"
                "import anthropic\n\n"
                f"client = wrap_client(anthropic.Anthropic(), project='{project}')\n"
                "```"
            )

    # ── Risk classifier wizard ────────────────────────────────────────────────
    elif page == "🔍 Clasificador de Riesgo":
        st.title("🔍 Clasificador de Riesgo EU AI Act")
        st.caption("Responde 9 preguntas para saber si tu sistema es de alto riesgo bajo el EU AI Act.")

        with st.form("risk_wizard"):
            st.subheader("¿Tu sistema de IA afecta alguno de estos ámbitos?")
            c1, c2 = st.columns(2)
            affects_credit = c1.checkbox("Crédito o servicios financieros")
            affects_employment = c1.checkbox("Empleo o gestión de trabajadores")
            affects_health = c1.checkbox("Salud o servicios sanitarios")
            affects_education = c2.checkbox("Educación o formación profesional")
            affects_justice = c2.checkbox("Administración de justicia o orden público")
            affects_infrastructure = c2.checkbox("Infraestructura crítica")
            uses_biometrics = c1.checkbox("Identificación biométrica")

            st.subheader("Características del sistema")
            interacts_with_users = st.checkbox("El sistema interactúa directamente con personas")
            autonomous_decisions = st.checkbox("El sistema toma decisiones autónomas (sin revisión humana)")

            use_case_description = st.text_area(
                "Describe el caso de uso (opcional — mejora la clasificación)",
                height=100,
                placeholder="Ej: sistema de recomendación de préstamos para pymes..."
            )

            submitted = st.form_submit_button("Clasificar")

        if submitted:
            clf = RiskClassifier()
            answers = {
                "affects_credit": affects_credit,
                "affects_employment": affects_employment,
                "affects_health": affects_health,
                "affects_education": affects_education,
                "affects_justice": affects_justice,
                "affects_infrastructure": affects_infrastructure,
                "uses_biometrics": uses_biometrics,
                "interacts_with_users": interacts_with_users,
                "autonomous_decisions": autonomous_decisions,
                "use_case_description": use_case_description,
            }
            assessment = clf.classify_from_answers(answers)

            color_map = {
                "unacceptable": "error",
                "high": "warning",
                "limited": "warning",
                "minimal": "success",
                "low": "success",
            }
            severity = color_map.get(str(assessment.category), "info")
            getattr(st, severity)(f"**Clasificación: {assessment.category.upper()}** (puntuación de riesgo: {assessment.score}/100)")

            if assessment.reasons:
                st.subheader("Factores de riesgo identificados")
                for r in assessment.reasons:
                    st.write(f"• {r}")

            if assessment.obligations:
                st.subheader("Obligaciones aplicables")
                for o in assessment.obligations:
                    done = "auditai" in o.lower() or "✅" in o
                    st.write(f"{'✅' if done else '⬜'} {o}")

            st.session_state["last_assessment"] = {
                "category": str(assessment.category),
                "score": assessment.score,
                "reasons": assessment.reasons,
                "obligations": assessment.obligations,
                "hitl_required": assessment.hitl_required,
            }

    # ── Report generator ──────────────────────────────────────────────────────
    elif page == "📄 Generar Report":
        st.title("📄 Generar EU AI Act Deployer Report")
        st.caption("Genera el documento PDF exigido por el Art. 26 del EU AI Act.")

        system_desc = st.text_input("Descripción del sistema IA", placeholder="Sistema de recomendación de préstamos")
        use_case = st.text_input("Caso de uso principal", placeholder="Aprobación automatizada de créditos")

        last_assessment = st.session_state.get("last_assessment")
        if last_assessment:
            st.success(f"Clasificación guardada: **{last_assessment['category'].upper()}**")
        else:
            st.info("Ejecuta primero el Clasificador de Riesgo para incluir la evaluación en el report.")

        if st.button("🔄 Generar Report PDF"):
            with st.spinner("Generando report..."):
                try:
                    path = generate_report(
                        project=project,
                        company_name=company,
                        contact_email=email,
                        risk_assessment=last_assessment,
                        log_dir=log_dir if log_dir else None,
                        extra_info={
                            "system_description": system_desc,
                            "use_case": use_case,
                        },
                    )
                    st.success(f"Report generado: `{path}`")
                    with open(path, "rb") as f:
                        st.download_button(
                            "⬇️ Descargar PDF",
                            data=f,
                            file_name=Path(path).name,
                            mime="application/pdf" if path.endswith(".pdf") else "text/markdown",
                        )
                except Exception as e:
                    st.error(f"Error generando el report: {e}")


if __name__ == "__main__":
    main()

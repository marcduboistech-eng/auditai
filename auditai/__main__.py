"""CLI entry point: auditai <command>"""

import argparse
import json
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="auditai",
        description="EU AI Act Deployer Compliance SDK",
    )
    sub = parser.add_subparsers(dest="command")

    # auditai stats --project myapp
    p_stats = sub.add_parser("stats", help="Show audit log statistics")
    p_stats.add_argument("--project", required=True)
    p_stats.add_argument("--log-dir", default=None)

    # auditai report --project myapp --company "Mi Empresa" --email compliance@co.com
    p_report = sub.add_parser("report", help="Generate EU AI Act Deployer Compliance Report")
    p_report.add_argument("--project", required=True)
    p_report.add_argument("--company", required=True)
    p_report.add_argument("--email", required=True)
    p_report.add_argument("--output", default=None)
    p_report.add_argument("--log-dir", default=None)
    p_report.add_argument("--system-description", default=None)

    # auditai classify --answers '{"affects_credit": true, ...}'
    p_classify = sub.add_parser("classify", help="Classify risk from answers JSON")
    p_classify.add_argument("--answers", required=True, help="JSON string with wizard answers")

    # auditai proxy --port 8080 --target https://api.openai.com --project myapp
    p_proxy = sub.add_parser("proxy", help="Run transparent HTTP proxy for zero-code instrumentation")
    p_proxy.add_argument("--port", type=int, default=8080)
    p_proxy.add_argument("--target", default="https://api.openai.com", help="Upstream API base URL")
    p_proxy.add_argument("--project", required=True)
    p_proxy.add_argument("--log-dir", default=None)

    # auditai dashboard --project myapp
    p_dash = sub.add_parser("dashboard", help="Launch Streamlit dashboard")
    p_dash.add_argument("--project", default="default")

    args = parser.parse_args()

    if args.command == "stats":
        from auditai.logger import AuditLogger
        logger = AuditLogger(project=args.project, log_dir=args.log_dir)
        s = logger.stats()
        print(json.dumps(s, indent=2, ensure_ascii=False))

    elif args.command == "report":
        from auditai.report import generate_report
        path = generate_report(
            project=args.project,
            company_name=args.company,
            contact_email=args.email,
            output_path=args.output,
            log_dir=args.log_dir,
            extra_info={"system_description": args.system_description} if args.system_description else {},
        )
        print(f"Report generado: {path}")

    elif args.command == "classify":
        from auditai.risk import RiskClassifier
        try:
            answers = json.loads(args.answers)
        except json.JSONDecodeError as e:
            print(f"Error: JSON inválido — {e}", file=sys.stderr)
            sys.exit(1)
        clf = RiskClassifier()
        result = clf.classify_from_answers(answers)
        print(json.dumps({
            "category": str(result.category),
            "score": result.score,
            "hitl_required": result.hitl_required,
            "reasons": result.reasons,
            "obligations": result.obligations,
        }, indent=2, ensure_ascii=False))

    elif args.command == "proxy":
        from auditai.proxy import run_proxy
        run_proxy(
            target=args.target,
            project=args.project,
            port=args.port,
            log_dir=args.log_dir,
        )

    elif args.command == "dashboard":
        import subprocess
        subprocess.run([
            sys.executable, "-m", "streamlit", "run",
            "-c", f"auditai.dashboard",
            "--", f"--project={args.project}"
        ])

    else:
        parser.print_help()


if __name__ == "__main__":
    main()

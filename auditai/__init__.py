"""
auditai — EU AI Act Deployer Compliance SDK
Wrap your Claude/GPT calls. Log everything. Generate the Art. 26 report.
"""

from .wrapper import wrap_client
from .logger import AuditLogger
from .risk import RiskClassifier, RiskCategory
from .report import generate_report
from .langchain_callback import AuditAICallbackHandler

__version__ = "0.1.4"
__all__ = [
    "wrap_client", "AuditLogger", "RiskClassifier", "RiskCategory",
    "generate_report", "AuditAICallbackHandler",
]

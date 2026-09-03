from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def create_audit_log(
    db: Session,
    action: str,
    user_id: int | None = None,
    ip_address: str | None = None,
    details: str | None = None,
):
    log = AuditLog(
        user_id=user_id,
        action=action,
        ip_address=ip_address,
        details=details,
    )

    db.add(log)
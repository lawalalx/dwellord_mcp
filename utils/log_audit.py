from models import AuditLog
from models import AuditAction

async def log_audit(
    session,
    *,
    user_phone: str,
    action: AuditAction,
    property_id: str | None = None,
    related_id: str | None = None,
    metadata: dict | None = None
):
    session.add(
        AuditLog(
            user_phone=user_phone,
            action=action,
            property_id=property_id,
            related_id=related_id,
            metadata=metadata,
        )
    )

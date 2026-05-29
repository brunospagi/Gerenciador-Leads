from __future__ import annotations

from typing import Any

from core.models import AuditLog


SENSITIVE_HINTS = ("senha", "password", "token", "secret", "key", "csrf")


def _safe_text(value: Any, max_len: int = 300) -> str:
    if value is None:
        return ""
    text = str(value)
    return text[:max_len]


def _is_sensitive_key(key: str) -> bool:
    lowered = (key or "").strip().lower()
    return any(hint in lowered for hint in SENSITIVE_HINTS)


def sanitize_payload(data: dict[str, Any] | None) -> dict[str, Any]:
    if not data:
        return {}
    sanitized: dict[str, Any] = {}
    for key, value in data.items():
        if _is_sensitive_key(key):
            sanitized[key] = "***"
            continue
        if isinstance(value, (list, tuple)):
            sanitized[key] = [_safe_text(item, 150) for item in value][:20]
        elif isinstance(value, dict):
            sanitized[key] = sanitize_payload(value)
        else:
            sanitized[key] = _safe_text(value, 400)
    return sanitized


def get_client_ip(request) -> str:
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def create_audit_log(
    *,
    user=None,
    module: str,
    action: str,
    method: str = "",
    path: str = "",
    status_code: int | None = None,
    ip_address: str = "",
    user_agent: str = "",
    object_repr: str = "",
    payload: dict[str, Any] | None = None,
    success: bool = True,
    severity: str = AuditLog.SEVERITY_INFO,
) -> None:
    try:
        profile = getattr(user, "profile", None) if user else None
        AuditLog.objects.create(
            user=user if getattr(user, "is_authenticated", False) else None,
            username_snapshot=(getattr(user, "username", "") or "") if user else "",
            nivel_acesso_snapshot=getattr(profile, "nivel_acesso", "") if profile else "",
            module=_safe_text(module, 80) or "sistema",
            action=_safe_text(action, 160) or "acao_nao_informada",
            method=_safe_text(method, 10),
            path=_safe_text(path, 500),
            status_code=status_code,
            ip_address=_safe_text(ip_address, 45) or None,
            user_agent=_safe_text(user_agent, 300),
            object_repr=_safe_text(object_repr, 255),
            payload=sanitize_payload(payload),
            success=bool(success),
            severity=severity if severity in dict(AuditLog.SEVERITY_CHOICES) else AuditLog.SEVERITY_INFO,
        )
    except Exception:
        # Nunca interrompe fluxo principal por erro de auditoria.
        pass

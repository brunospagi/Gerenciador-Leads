from __future__ import annotations

from core.audit import create_audit_log, get_client_ip
from core.models import AuditLog


class AuditLogMiddleware:
    TRACKED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
    EXCLUDED_PATH_PREFIXES = (
        "/static/",
        "/media/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        try:
            if not self._should_log(request):
                return response

            status_code = getattr(response, "status_code", None)
            success = bool(status_code and status_code < 400)
            severity = AuditLog.SEVERITY_INFO if success else AuditLog.SEVERITY_ERROR

            create_audit_log(
                user=request.user if getattr(request, "user", None) else None,
                module=self._resolve_module(request),
                action=self._resolve_action(request),
                method=request.method,
                path=request.get_full_path(),
                status_code=status_code,
                ip_address=get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                payload=self._build_payload(request),
                success=success,
                severity=severity,
            )
        except Exception:
            # Nao quebra o request por falha de log.
            pass

        return response

    def _should_log(self, request) -> bool:
        if request.method not in self.TRACKED_METHODS:
            return False

        path = (request.path or "").lower()
        if any(path.startswith(prefix) for prefix in self.EXCLUDED_PATH_PREFIXES):
            return False

        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated)

    def _resolve_module(self, request) -> str:
        path = (request.path or "").strip("/")
        if not path:
            return "portal"
        first_segment = path.split("/", 1)[0]
        if first_segment == "painel-admin":
            return "administracao"
        return first_segment

    def _resolve_action(self, request) -> str:
        resolver_match = getattr(request, "resolver_match", None)
        if resolver_match and resolver_match.view_name:
            return resolver_match.view_name
        return f"{request.method}_{request.path}".replace("/", "_")

    def _build_payload(self, request) -> dict:
        payload = {
            "query_params": dict(request.GET.items()),
            "content_type": request.META.get("CONTENT_TYPE", ""),
        }

        if request.POST:
            payload["form_fields"] = sorted(request.POST.keys())
        else:
            raw_length = request.META.get("CONTENT_LENGTH")
            if raw_length:
                payload["body_length"] = raw_length

        return payload

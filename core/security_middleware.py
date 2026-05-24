from django.conf import settings


class SecurityHeadersMiddleware:
    """
    Adds defensive security headers with project-safe defaults.
    CSP remains permissive enough for existing CDN usage.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if "Referrer-Policy" not in response:
            response["Referrer-Policy"] = getattr(
                settings, "SECURE_REFERRER_POLICY", "strict-origin-when-cross-origin"
            )

        if "X-Content-Type-Options" not in response:
            response["X-Content-Type-Options"] = "nosniff"

        if "Permissions-Policy" not in response:
            response["Permissions-Policy"] = getattr(
                settings,
                "PERMISSIONS_POLICY",
                "camera=(self), microphone=(self), geolocation=(self)",
            )

        csp = getattr(settings, "CONTENT_SECURITY_POLICY", "").strip()
        if csp and "Content-Security-Policy" not in response:
            response["Content-Security-Policy"] = csp

        return response

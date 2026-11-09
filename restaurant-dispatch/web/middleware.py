class SecurityHeadersMiddleware:
    """Strict CSP (no inline script or style anywhere) plus a permissions policy
    that denies location, camera and microphone: the product never tracks staff."""

    CSP = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "font-src 'self'; connect-src 'self'; frame-src 'self'; frame-ancestors 'self'; "
        "form-action 'self'; base-uri 'none'; object-src 'none'"
    )
    PERMISSIONS = "geolocation=(), camera=(), microphone=(), payment=(), usb=()"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.headers.setdefault("Content-Security-Policy", self.CSP)
        response.headers.setdefault("Permissions-Policy", self.PERMISSIONS)
        return response

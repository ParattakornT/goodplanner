class ResponseHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response['Cache-Control'] = 'no-store'
        response['X-Frame-Options'] = 'DENY'
        style = "'self' 'unsafe-inline'" if request.path.startswith('/admin/') else "'self'"
        response['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src " + style + "; img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
        return response

from .auditoria_contexto import (
    establecer_request,
    limpiar_request,
)


class AuditoriaRequestMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        establecer_request(request)

        try:
            return self.get_response(request)
        finally:
            limpiar_request()
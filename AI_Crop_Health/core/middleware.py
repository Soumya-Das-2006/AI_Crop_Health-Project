import threading

_thread_locals = threading.local()

def get_current_request():
    """Returns the current HTTP request, if any."""
    return getattr(_thread_locals, 'request', None)

class RequestContextMiddleware:
    """
    Middleware that stores the current request in thread local storage.
    Used by the AuditService and signals to access the user and IP address.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _thread_locals.request = request
        
        try:
            response = self.get_response(request)
        finally:
            # Clean up the thread-local after the response is sent
            if hasattr(_thread_locals, 'request'):
                del _thread_locals.request
                
        return response

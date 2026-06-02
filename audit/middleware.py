"""Stash the request's user in a thread-local so model signals can read it.

Model ``post_save`` / ``post_delete`` signals have no access to the request,
so this middleware records the current user for the duration of the request.
"""
import threading

_state = threading.local()


def get_current_user():
    return getattr(_state, "user", None)


class CurrentUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _state.user = getattr(request, "user", None)
        try:
            return self.get_response(request)
        finally:
            _state.user = None

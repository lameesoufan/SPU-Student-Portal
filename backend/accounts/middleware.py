class JWTCookieMiddleware:
    """
    M-12 Fix: يقرأ التوكن من HttpOnly Cookie ويحطه بالـ Authorization header
    عشان SimpleJWT يقدر يتعرف عليه.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # لو ما في Authorization header، شوف إذا في Cookie
        access_token = request.COOKIES.get('access_token')
        if access_token and not request.META.get('HTTP_AUTHORIZATION'):
            request.META['HTTP_AUTHORIZATION'] = f'Bearer {access_token}'
        return self.get_response(request)
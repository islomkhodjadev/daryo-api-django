from django.http import JsonResponse
from .models import APIKey


class APIKeyMiddleware:
    """
    Middleware to check if the provided API key is valid.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Get the API key from the request headers
        if request.path.startswith("/daryo-api/admin"):
            return self.get_response(request)
        api_key = request.headers.get("X-API-KEY")

        if not api_key:
            return JsonResponse({"error": "API key required"}, status=401)

        # Check if the API key is valid and active
        try:
            key = APIKey.objects.get(key=api_key, is_active=True)
        except APIKey.DoesNotExist:
            return JsonResponse({"error": "Invalid or inactive API key"}, status=403)

        # Proceed with the request if the API key is valid
        response = self.get_response(request)
        return response

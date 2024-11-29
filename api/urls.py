from django.urls import path
from .views import ClientConversationView, AiDataCreateView


urlpatterns = [
    path("ai/conversation/", ClientConversationView.as_view()),
    path("api/ai-data/", AiDataCreateView.as_view(), name="ai-data-create"),
]

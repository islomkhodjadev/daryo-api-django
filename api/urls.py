from django.urls import path
from .views import ClientConversationView


urlpatterns = [path("ai/conversation/", ClientConversationView.as_view())]

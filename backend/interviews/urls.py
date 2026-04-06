from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import InterviewViewSet, InternalBridgeView, SpeakView

router = DefaultRouter()
router.register(r'interviews', InterviewViewSet, basename='interview')

urlpatterns = [
    path('', include(router.urls)),
    path('internal/submit-answer/', InternalBridgeView.as_view(), name='submit-answer'),
    path('speak/', SpeakView.as_view(), name='speak'),
]

from django.urls import path
from .views import UserUploadCreateView

urlpatterns = [
    path('upload/', UserUploadCreateView.as_view(), name='upload'),
]

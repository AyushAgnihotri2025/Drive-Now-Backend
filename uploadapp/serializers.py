from rest_framework import serializers
from .models import UserUpload

class UserUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserUpload
        fields = ['id', 'name', 'image']
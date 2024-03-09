from rest_framework import serializers
from FileProcessing.models import File, UserPersonalFileToken

class FileDetailsListSerializer(serializers.ModelSerializer):
  class Meta:
    model = File
    fields = ['original_file_name', 'file_size']

class FilesListSerializer(serializers.ModelSerializer):
  file_id = FileDetailsListSerializer()
  class Meta:
    model = UserPersonalFileToken
    fields = ['personalfiletoken', 'change_file_name', 'type', 'parent', 'modified_at', 'file_id', 'favourite', 'is_delete_init', 'views', 'uploaded_by']


class FileDetailsViewSerializer(serializers.ModelSerializer):
  class Meta:
    model = File
    fields = ['original_file_name', 'file_type', 'file_size', 'created_at', 'upload_finished_at']

class FileDetailsSerializer(serializers.ModelSerializer):
  class Meta:
    model = File
    fields = ['file', 'original_file_name', 'file_type', 'created_at', 'upload_finished_at']

class TokentoFileIdSerializer(serializers.ModelSerializer):
  class Meta:
    model = UserPersonalFileToken
    fields = ['file_id', 'is_delete_init', 'uploaded_by', 'is_deleted', 'change_file_name']

class UserFileTokenListSerializer(serializers.ModelSerializer):
  class Meta:
    model = UserPersonalFileToken
    fields = ['personalfiletoken']

  
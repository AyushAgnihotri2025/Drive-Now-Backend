import re
import requests
from urllib import parse
from urllib.parse import unquote

from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from FileProcessing.models import File
from rest_framework.permissions import IsAuthenticated
from FileProcessing.renderers import FileRenderer
from FileProcessing.serializers import FileDetailsSerializer, FileDetailsViewSerializer
from FileProcessing.services import (
    FileDirectUploadService,
    FileGetService,
    FileMultipartUploadService,
    FileStandardUploadService,
)

class FolderCreationView(APIView):
    pass
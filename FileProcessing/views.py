import re
import requests
from urllib import parse
from urllib.parse import unquote

from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from Account.serializers import UserFullProfileSerializer

from FileProcessing.models import File, UserPersonalFileToken
from rest_framework.permissions import IsAuthenticated
from FileProcessing.renderers import FileRenderer
from FileProcessing.serializers import FileDetailsSerializer, FileDetailsViewSerializer, FilesListSerializer, TokentoFileIdSerializer
from FileProcessing.services import (
    EmptyRecycleBinservice,
    FileCopyService,
    FileDeleteService,
    FileDirectUploadService,
    FileFavouriteservice,
    FileGetService,
    FileMultipartUploadService,
    FileRenameservice,
    FileRestoreService,
    FileStandardUploadService,
    FileUpdateViewsservice,
)

class FileStandardUploadApi(APIView):
    renderer_classes = [FileRenderer]
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        if 'file' not in request.FILES:
            return Response({'errors': "File Not Found"}, status=status.HTTP_404_NOT_FOUND)
        service = FileStandardUploadService(user=request.user, file_obj=request.FILES["file"])
        file = service.create()

        return Response(data={"id": file.personalfiletoken}, status=status.HTTP_201_CREATED)


class FileDirectUploadStartApi(APIView):
    renderer_classes = [FileRenderer]
    permission_classes = [IsAuthenticated]
    
    class InputSerializer(serializers.Serializer):
        file_name = serializers.CharField()
        file_type = serializers.CharField()

    def post(self, request, *args, **kwargs):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = FileDirectUploadService(request.user)
        presigned_data = service.start(**serializer.validated_data)

        return Response(data=presigned_data)


class FileDirectUploadLocalApi(APIView):
    renderer_classes = [FileRenderer]
    permission_classes = [IsAuthenticated]
    
    def post(self, request, file_id):
        file = get_object_or_404(File, fileID=file_id)

        file_obj = request.FILES["file"]

        service = FileDirectUploadService(request.user)
        file = service.upload_local(file=file, file_obj=file_obj)

        return Response({"id": file.fileID})


class FileDirectUploadFinishApi(APIView):
    renderer_classes = [FileRenderer]
    permission_classes = [IsAuthenticated]
    
    class InputSerializer(serializers.Serializer):
        file_id = serializers.CharField()

    def post(self, request):
        serializer = self.InputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        file_id = serializer.validated_data["file_id"]

        file = get_object_or_404(File, fileID=file_id)

        service = FileDirectUploadService(request.user)
        service.finish(file=file)

        return Response({"id": file.fileID})
    
class FileDetailsView(APIView):
    renderer_classes = [FileRenderer]

    def post(self, request, format=None):
        try:
            data= UserPersonalFileToken.objects.select_related('file_id').get(personalfiletoken=request.data["fileID"])
            filedetails=FilesListSerializer(data).data

            if filedetails['is_delete_init']:
                return Response(data={"error": "File Has Been Already Deleted by You"}, status=status.HTTP_403_FORBIDDEN)
            
            if filedetails['change_file_name'] == None:
                filename=filedetails['file_id']["original_file_name"]
            else:
                filename=filedetails["change_file_name"]

            res = {
            "FileID" : filedetails['personalfiletoken'],
            "File_type" : filedetails['type'],
            "Modified_At" : filedetails['modified_at'],
            "Original_File_Name" : filename,
            "File_size" : filedetails['file_id']['file_size'],
            }
            if res == {}:
                return Response(data={"error": "No File Found"}, status=status.HTTP_404_NOT_FOUND)
            else:
                return Response(res, status=status.HTTP_200_OK)
        except UserPersonalFileToken.DoesNotExist:
            return Response(data={"error": "No File Found"}, status=status.HTTP_404_NOT_FOUND)
        
    def get(self, request, format=None):
        try:
            if ((not request.user) or (not request.user.is_authenticated)):
                return Response(data={"errors": { "detail": "Authentication credentials were not provided." }}, status=status.HTTP_401_UNAUTHORIZED)
        
            data= UserPersonalFileToken.objects.select_related('file_id').get(personalfiletoken=request.headers['x-file-token'])
            filedetails=FilesListSerializer(data).data

            if filedetails['change_file_name'] == None:
                    filename=filedetails['file_id']["original_file_name"]
            else:
                filename=filedetails["change_file_name"]

            owner = False

            if filedetails['is_delete_init']:
                return Response(data={"error": "File Has Been Already Deleted by You"}, status=status.HTTP_403_FORBIDDEN)
            elif filedetails['uploaded_by'] == UserFullProfileSerializer(request.user).data['userId']:
                owner = True
        
            res = {
            "FileID" : filedetails['personalfiletoken'],
            "File_type" : filedetails['type'],
            "Parent" : filedetails['parent'],
            "Modified_At" : filedetails['modified_at'],
            "Original_File_Name" : filename,
            "File_size" : filedetails['file_id']['file_size'],
            "Favourite" : filedetails['favourite'],
            "is_owner" : owner,
            }
            if res == {}:
                return Response(data={"error": "No File Found"}, status=status.HTTP_404_NOT_FOUND)
            else:
                return Response(res, status=status.HTTP_200_OK)
        except UserPersonalFileToken.DoesNotExist:
            return Response(data={"error": "No File Found"}, status=status.HTTP_404_NOT_FOUND)
    
class FileMultipartUploadView(APIView):
    renderer_classes = [FileRenderer]
    permission_classes = [IsAuthenticated]

    class FileInitSerializer(serializers.Serializer):
        file_name = serializers.CharField()
        file_type = serializers.CharField()
        file_size = serializers.IntegerField()

    class FileUploadSerializer(serializers.Serializer):
        file_id = serializers.CharField()
        part_number = serializers.IntegerField()

    class FileFinishSerializer(serializers.Serializer):
        file_id = serializers.CharField()

    def post(self, request, *args, **kwargs):
        if request.headers['x-req-type'] == "start":
            serializer = self.FileInitSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            service = FileMultipartUploadService(request.user)
            fileID = service.start(**serializer.validated_data)

            return Response(data=fileID, status=status.HTTP_201_CREATED)
        
        elif request.headers['x-req-type'] == "upload":
            serializer = self.FileUploadSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            if 'file' not in request.FILES:
                return Response({'errors': "File Not Found"}, status=status.HTTP_404_NOT_FOUND)

            service = FileMultipartUploadService(user=request.user)
            service.upload(**serializer.validated_data, file_obj=request.FILES['file'])

            return Response(status=status.HTTP_202_ACCEPTED)
        
        elif request.headers['x-req-type'] == "finish":
            serializer = self.FileFinishSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            file_id = serializer.validated_data["file_id"]

            file = get_object_or_404(File, fileID=file_id)

            service = FileMultipartUploadService(user=request.user)
            finish_status = service.finish(**serializer.validated_data, file=file)

            if finish_status:
                return Response(data={"id": finish_status.personalfiletoken}, status=status.HTTP_200_OK)
            else :
                return Response(status=status.HTTP_400_BAD_REQUEST)

class RangeFileWrapper:
    def __init__(self, response, blksize=8192, offset=0, length=None):
        self.response = response
        self.blksize = blksize
        self.offset = offset
        self.remaining = length

        # Move to the specified offset
        response.read(offset)

    def close(self):
        # HTTPResponse objects need to be explicitly closed
        self.response.close()

    def __iter__(self):
        return self

    def __next__(self):
        if self.remaining is None:
            # If remaining is None, we're reading the entire file.
            data = self.response.read(self.blksize)
            if data:
                return data
            raise StopIteration()
        else:
            if self.remaining <= 0:
                raise StopIteration()
            data = self.response.read(min(self.blksize, self.remaining))
            if not data:
                raise StopIteration()
            self.remaining -= len(data)
            return data


class FileWrapper:
    """Wrapper to convert file-like objects to iterables"""

    def __init__(self, filelike, blksize=8192):
        self.filelike = filelike
        self.blksize = blksize
        if hasattr(filelike, 'close'):
            self.close = filelike.close

    def __iter__(self):
        return self

    def __next__(self):
        data = self.filelike.read(self.blksize)
        if data:
            return data
        raise StopIteration

    def close(self):
        if hasattr(self.filelike, 'close'):
            self.filelike.close()

range_re = re.compile(r'bytes\s*=\s*(\d+)\s*-\s*(\d*)', re.I)

class FileGetView(APIView):
    renderer_classes = [FileRenderer]

    def get(self, request, token):
        # onhold
        # file_id = request.headers["x-header-token"]
        try:
            file = TokentoFileIdSerializer(UserPersonalFileToken.objects.get(personalfiletoken=token)).data
            if file['is_delete_init']:
                return Response({'msg': "File Deleted by Owner"}, status=status.HTTP_400_BAD_REQUEST)
            else:
                data = File.objects.get(fileID=file['file_id'])
                filedetails = FileDetailsSerializer(data).data

                if file['change_file_name'] == None:
                    filename=filedetails["original_file_name"]
                else:
                    filename=file["change_file_name"]

                range_header = request.META.get('HTTP_RANGE', '').strip()
                range_match = range_re.match(range_header)

                # service = FileGetService(user=request.user)
                # url = service.geturl(file_path= filedetails['file'])

                # url = unquote(url.split("/", 3)[-1])

                # __parsed = parse.urlparse(unquote(url.split("/", 3)[-1]))
                # _parsed = parse.urlparse(url)
                # final = f"{_parsed.scheme}://{_parsed.netloc}/{__parsed.path.lstrip('/')}?{_parsed.query}"

                streaming_body = requests.get(url=filedetails['file'], stream=True)
                streaming_body.raise_for_status()

                if streaming_body is None:
                    return Response({'Error': "Error Retreiving the File"}, status=500)

                size = int(streaming_body.headers["Content-length"])
                if range_match:
                    first_byte, last_byte = range_match.groups()
                    first_byte = int(first_byte) if first_byte else 0
                    last_byte = int(last_byte) if last_byte else size - 1
                    if last_byte >= size:
                        last_byte = size - 1
                    length = last_byte - first_byte + 1
                    response = StreamingHttpResponse(RangeFileWrapper(streaming_body.raw, offset=first_byte, length=length), status=206, content_type=filedetails['file_type'])
                    response['Content-Length'] = str(length)
                    response['Content-Range'] = 'bytes %s-%s/%s' % (first_byte, last_byte, size)
                else:
                    response = StreamingHttpResponse(FileWrapper(streaming_body.raw), content_type=filedetails['file_type'])
                    response['Content-Length'] = str(size)

                response['Access-Control-Expose-Headers'] = 'Content-Disposition,Content-Length,Content-Type'
                response['Content-Disposition'] = f'inline; filename={filename}'
                response['Accept-Ranges'] = 'bytes'

                return response
        except Exception as e:
            return Response({'msg': "File Not Found"}, status=status.HTTP_404_NOT_FOUND)

class FileDownloadView(APIView):
    renderer_classes = [FileRenderer]

    def get(self, request, token):
        # onhold
        # file_id = request.headers["x-header-token"]
        try:
            file = TokentoFileIdSerializer(UserPersonalFileToken.objects.get(personalfiletoken=token)).data
            if file['is_delete_init']:
                return Response({'msg': "File Deleted by Owner"}, status=status.HTTP_400_BAD_REQUEST)
            else:
                data = File.objects.get(fileID=file['file_id'])
                filedetails = FileDetailsSerializer(data).data

                if file['change_file_name'] == None:
                    filename=filedetails["original_file_name"]
                else:
                    filename=file["change_file_name"]

                # service = FileGetService(user=request.user)
                # url = service.geturl(file_path= filedetails['file'])

                # url = unquote(url.split("/", 3)[-1])

                # __parsed = parse.urlparse(unquote(url.split("/", 3)[-1]))
                # _parsed = parse.urlparse(url)
                # final = f"{_parsed.scheme}://{_parsed.netloc}/{__parsed.path.lstrip('/')}?{_parsed.query}"

                streaming_body = requests.get(url=filedetails['file'], stream=True)
                streaming_body.raise_for_status()

                if streaming_body is None:
                    return Response({'Error': "Error Retreiving the File"}, status=500)

                response = StreamingHttpResponse(streaming_body, status=200, content_type=filedetails['file_type'])
            
                response['Content-Length'] = streaming_body.headers["Content-length"]
                response['Access-Control-Expose-Headers'] = 'Content-Disposition,Content-Length,Content-Type'
                response['Content-Disposition'] = f'attachment; filename={filename}'
                response['Accept-Ranges'] = 'bytes'

                return response
        except Exception as e:
            return Response({'msg': "File Not Found"}, status=status.HTTP_404_NOT_FOUND)
    
class FileDeleteView(APIView):
    renderer_classes = [FileRenderer]
    permission_classes = [IsAuthenticated]
    class FileDeleteSerializer(serializers.Serializer):
        file_token = serializers.ListField(child=serializers.CharField())

    def post(self, request, format=None):
        serializer = self.FileDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        service = FileDeleteService(user=request.user)
        msg, delete_status=service.deleteFile(**serializer.validated_data)
        if delete_status:
            return Response(data={"msg": msg},status=status.HTTP_200_OK)
        else:
            return Response(data={"error": msg},status=status.HTTP_400_BAD_REQUEST)
        
class FileRestoreView(APIView):
    renderer_classes = [FileRenderer]
    permission_classes = [IsAuthenticated]
    class FileRestoreSerializer(serializers.Serializer):
        file_token = serializers.ListField(child=serializers.CharField())

    def post(self, request, format=None):
        serializer = self.FileRestoreSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        service = FileRestoreService(user=request.user)
        msg, restore_status=service.restoreFile(**serializer.validated_data)
        if restore_status:
            return Response(data={"msg": msg},status=status.HTTP_200_OK)
        else:
            return Response(data={"error": msg},status=status.HTTP_400_BAD_REQUEST)

class FileMoveView(APIView):
    renderer_classes = [FileRenderer]
    permission_classes = [IsAuthenticated]
    
    pass

class FileCopyView(APIView):
    renderer_classes = [FileRenderer]
    permission_classes = [IsAuthenticated]

    class FileCopySerializer(serializers.Serializer):
        file_token = serializers.ListField(child=serializers.CharField())

    def post(self, request, format=None):
        serializer = self.FileCopySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        service = FileCopyService(user=request.user)
        data,copy_status=service.copyFile(**serializer.validated_data)
        if copy_status:
            return Response(data={"id": data.personalfiletoken},status=status.HTTP_200_OK)
        else:
            return Response(data={"msg": data},status=status.HTTP_400_BAD_REQUEST)

class FileFavouriteView(APIView):
    renderer_classes = [FileRenderer]
    permission_classes = [IsAuthenticated]
    
    class FileFavouriteSerializer(serializers.Serializer):
        file_token = serializers.ListField(child=serializers.CharField())

    def post(self, request, format=None):
        serializer = self.FileFavouriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        service = FileFavouriteservice(user=request.user)
        data,favourites_status=service.favouriteFile(**serializer.validated_data)
        if favourites_status:
            return Response(data={"msg": data},status=status.HTTP_200_OK)
        else:
            return Response(data={"error": data},status=status.HTTP_400_BAD_REQUEST)
        
class FileUnFavouriteView(APIView):
    renderer_classes = [FileRenderer]
    permission_classes = [IsAuthenticated]
    
    class FileUnFavouriteSerializer(serializers.Serializer):
        file_token = serializers.ListField(child=serializers.CharField())

    def post(self, request, format=None):
        serializer = self.FileUnFavouriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        service = FileFavouriteservice(user=request.user)
        data,unfavourites_status=service.unfavouriteFile(**serializer.validated_data)
        if unfavourites_status:
            return Response(data={"msg": data},status=status.HTTP_200_OK)
        else:
            return Response(data={"error": data},status=status.HTTP_400_BAD_REQUEST)
        
class FileUpdateFileViewsView(APIView):
    renderer_classes = [FileRenderer]

    class FileViewSerializer(serializers.Serializer):
        fileId = serializers.CharField()

    def put(self, request, format=None):
        serializer = self.FileViewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        service = FileUpdateViewsservice(user=request.user)
        _ , views_status=service.updateViews(**serializer.validated_data)
        if views_status:
            return Response(status=status.HTTP_200_OK)
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_400_BAD_REQUEST)
        
class EmptyRecycleBinView(APIView):
    renderer_classes = [FileRenderer]
    permission_classes = [IsAuthenticated]

    class FileViewSerializer(serializers.Serializer):
        file_token = serializers.CharField()

    def delete(self, request, format=None):
        service = EmptyRecycleBinservice(user=request.user)
        views_status=service.emptybin()
        if views_status:
            return Response(status=status.HTTP_200_OK)
        
class FileRenameView(APIView):
    renderer_classes = [FileRenderer]
    permission_classes = [IsAuthenticated]

    class FileRenameSerializer(serializers.Serializer):
        file_token = serializers.CharField()
        file_name = serializers.CharField()
        file_name_new = serializers.CharField()

    def post(self, request, format=None):
        serializer = self.FileRenameSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        service = FileRenameservice(user=request.user)
        data, rename_status=service.renameFile(**serializer.validated_data)
        if rename_status:
            return Response(data={"msg": data},status=status.HTTP_200_OK)
        else:
            return Response(data={"error": data},status=status.HTTP_400_BAD_REQUEST)
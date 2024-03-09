from django.conf import settings
from django.db import models

# from DriveNow.common.models import BaseModel
from FileProcessing.enums import FileUploadStorage
from FileProcessing.utils import file_generate_upload_path
from Account.models import User


class File(models.Model):
    fileID = models.CharField(primary_key=True, max_length=255, unique=True)
    file = models.FileField(upload_to=file_generate_upload_path, blank=True, null=True)

    original_file_name = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    file_name = models.CharField(max_length=255, unique=True)
    file_type = models.CharField(max_length=255)
    file_size = models.IntegerField()

    # As a specific behavior,
    # We might want to preserve files after the uploader has been deleted.
    # In case you want to delete the files too, use models.CASCADE & drop the null=True
    uploaded_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)

    upload_finished_at = models.DateTimeField(blank=True, null=True)

    is_delete_init = models.BooleanField(default=False)
    delete_init_at = models.DateTimeField(blank=True, null=True)


    @property
    def is_valid(self):
        """
        We consider a file "valid" if the the datetime flag has value.
        """
        return bool(self.upload_finished_at)

    @property
    def url(self):
        if settings.FILE_UPLOAD_STORAGE == FileUploadStorage.S3.value:
            return self.file.url

        return f"{settings.APP_DOMAIN}{self.file.url}"

class UserPersonalFileToken(models.Model):
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    personalfiletoken = models.CharField(primary_key=True, max_length=200, unique=True, null=False)
    file_id = models.ForeignKey(File, on_delete=models.RESTRICT)
    is_delete_init = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    is_copied = models.BooleanField(default=False)
    file_size = models.IntegerField()
    type = models.CharField(max_length=255)
    parent = models.CharField(max_length=255, default="*")
    modified_at = models.DateTimeField(auto_now_add=True)
    delete_init_at = models.DateTimeField(blank=True, null=True)
    favourite = models.BooleanField(default=False)
    change_file_name = models.TextField(blank=True, null=True)
    views = models.IntegerField(default=0)

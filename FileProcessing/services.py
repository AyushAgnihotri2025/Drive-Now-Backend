import mimetypes
from typing import Any, Dict, Tuple

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from Account.serializers import UserFullProfileSerializer, UserReferralTokenSerializer
from django.db.models import Sum,Q,Count,F

from FileProcessing.enums import FileUploadStorage
from FileProcessing.models import File, UserPersonalFileToken
from FileProcessing.serializers import FileDetailsViewSerializer, FilesListSerializer, TokentoFileIdSerializer, UserFileTokenListSerializer
from FileProcessing.utils import (
    bytes_to_mib,
    file_generate_local_upload_url,
    file_generate_name,
    file_generate_upload_path,
)
from integrations.aws.client import s3_generate_download_presigned_url, s3_generate_presigned_post, s3_multipart_upload_finish, s3_multipart_upload_init, s3_multipart_upload_data
from Account.models import User, UserReferral
from FileProcessing.utils import Util


def _validate_file_size(file_obj):
    max_size = settings.FILE_MAX_SIZE

    if file_obj.size > max_size:
        raise ValidationError(f"File is too large. It should not exceed {bytes_to_mib(max_size)} MiB")


class FileStandardUploadService:
    """
    This also serves as an example of a service class,
    which encapsulates 2 different behaviors (create & update) under a namespace.

    Meaning, we use the class here for:

    1. The namespace
    2. The ability to reuse `_infer_file_name_and_type` (which can also be an util)
    """

    def __init__(self, user: User, file_obj):
        self.user = user
        self.file_obj = file_obj

    def _infer_file_name_and_type(self, file_name: str = "", file_type: str = "") -> Tuple[str, str]:
        if not file_name:
            file_name = self.file_obj.name

        if not file_type:
            guessed_file_type, encoding = mimetypes.guess_type(file_name)

            if guessed_file_type is None:
                file_type = ""
            else:
                file_type = guessed_file_type

        return file_name, file_type

    @transaction.atomic
    def create(self, file_name: str = "", file_type: str = "") -> File:
        _validate_file_size(self.file_obj)

        file_name, file_type = self._infer_file_name_and_type(file_name, file_type)
        encrypt_filename =file_generate_name(file_name)
        file_size = self.file_obj.size

        obj = File(
            file=self.file_obj,
            original_file_name=file_name,
            file_name=encrypt_filename,
            fileID=encrypt_filename.split(".")[0],
            file_type=file_type,
            file_size=file_size,
            uploaded_by=self.user,
            upload_finished_at=timezone.now(),
        )

        obj.full_clean()
        obj.save()

        # Personal FIle Token
        file_id = obj.fileID
        personal_token = Util.GenratePersonalFileToken(self.user, file_id)

        obj_ptoken = UserPersonalFileToken(
            uploaded_by = self.user,
            personalfiletoken = personal_token,
            file_id = File.objects.get(fileID = file_id),
            type = file_type
        )
        obj_ptoken.full_clean()
        obj_ptoken.save()

        return obj_ptoken

    @transaction.atomic
    def update(self, file: File, file_name: str = "", file_type: str = "") -> File:
        _validate_file_size(self.file_obj)

        file_name, file_type = self._infer_file_name_and_type(file_name, file_type)

        file.file = self.file_obj
        file.original_file_name = file_name
        file.file_name = file_generate_name(file_name)
        file.file_type = file_type
        file.uploaded_by = self.user
        file.upload_finished_at = timezone.now()

        file.full_clean()
        file.save()

        return file


class FileDirectUploadService:
    """
    This also serves as an example of a service class,
    which encapsulates a flow (start & finish) + one-off action (upload_local) into a namespace.

    Meaning, we use the class here for:

    1. The namespace
    """

    def __init__(self, user: User):
        self.user = user

    @transaction.atomic
    def start(self, *, file_name: str, file_type: str) -> Dict[str, Any]:
        encrypt_filename =file_generate_name(file_name)
        file = File(
            original_file_name=file_name,
            file_name=encrypt_filename,
            fileID=encrypt_filename.split(".")[0],
            file_type=file_type,
            uploaded_by=self.user,
            file=None,
        )
        file.full_clean()
        file.save()

        upload_path = file_generate_upload_path(file, file.file_name)

        """
        We are doing this in order to have an associated file for the field.
        """
        file.file = file.file.field.attr_class(file, file.file.field, upload_path)
        file.save()

        presigned_data: Dict[str, Any] = {}

        if settings.FILE_UPLOAD_STORAGE == FileUploadStorage.S3.value:
            presigned_data = s3_generate_presigned_post(file_path=upload_path, file_type=file.file_type)
        else:
            presigned_data = {
                "url": file_generate_local_upload_url(file_id=str(file.fileID)),
            }

        return {"id": file.fileID, **presigned_data}

    @transaction.atomic
    def finish(self, *, file: File) -> File:
        # Potentially, check against user
        file.upload_finished_at = timezone.now()
        file.full_clean()
        file.save()

        return file

    @transaction.atomic
    def upload_local(self, *, file: File, file_obj) -> File:
        _validate_file_size(file_obj)

        # Potentially, check against user
        file.file = file_obj
        file.full_clean()
        file.save()

        return file
    
class FileMultipartUploadService:
    """
    This also serves as an example of a service class,
    which encapsulates a flow (start & finish) + one-off action (upload_local) into a namespace.

    Meaning, we use the class here for:

    1. The namespace
    """

    def __init__(self, user: User):
        self.user = user

    @transaction.atomic
    def start(self, *, file_name: str, file_type: str, file_size:int) -> Dict[str, Any]:
        encrypt_filename =file_generate_name(file_name)
        file = File(
            original_file_name=file_name,
            file_name=encrypt_filename,
            fileID=encrypt_filename.split(".")[0],
            file_type=file_type,
            file_size=file_size,
            uploaded_by=self.user,
            file=None,
        )
        file.full_clean()
        file.save()

        upload_path = file_generate_upload_path(file, file.file_name)

        """
        We are doing this in order to have an associated file for the field.
        """
        file.file = file.file.field.attr_class(file, file.file.field, upload_path)
        file.save()

        upload_data: Dict[str, Any] = {}

        if settings.FILE_UPLOAD_STORAGE == FileUploadStorage.S3.value:
            upload_data = s3_multipart_upload_init(file_path=upload_path)
            settings.ON_GOING_UPLOADS[file.fileID] = dict(
                Bucket=upload_data.get("Bucket", settings.AWS_STORAGE_BUCKET_NAME),
                Key=upload_data['Key'],
                UploadId=upload_data['UploadId'],
                Parts=[]
            )

        return {"id": file.fileID}

    @transaction.atomic
    def upload(self, file_id: str, part_number: int, file_obj=None) -> File:
        # Multipart File Upload Logic

        return s3_multipart_upload_data(file_object=file_obj, part_num=part_number, file_id=file_id)
    
    @transaction.atomic
    def finish(self, file_id: str, file: File) -> Dict[str, str]:
        # Multipart File Finsih Logic
        try:
            s3_multipart_upload_finish(file_id=file_id)

            # Updating in DB about File Upload Finished
            file.upload_finished_at = timezone.now()
            file.full_clean()
            file.save()

            # Personal FIle Token
            personal_token = Util.GenratePersonalFileToken(self.user, file_id)
            FileDetails = FileDetailsViewSerializer(File.objects.get(fileID = file_id)).data


            obj_ptoken = UserPersonalFileToken(
                uploaded_by = self.user,
                personalfiletoken = personal_token,
                file_id = File.objects.get(fileID = file_id),
                type = FileDetails['file_type'],
                file_size =FileDetails['file_size'],
            )
            obj_ptoken.full_clean()
            obj_ptoken.save()

            return obj_ptoken
        except Exception as e:
            print(e)
            return False
        
class FileGetService:
    """
    This also serves as a file to stream,
    which encapsulates a flow (start & finish) + one-off action (upload_local) into a namespace.

    Meaning, we use the class here for:

    1. The namespace
    """

    def __init__(self, user: User):
        self.user = user

    @transaction.atomic
    def geturl(self, file_path: str) -> Dict[str, Any]:
        
        return s3_generate_download_presigned_url(file_key = file_path)
    
class FileCopyService:
    """
    This also serves as a file to stream,
    which encapsulates a flow (start & finish) + one-off action (upload_local) into a namespace.

    Meaning, we use the class here for:

    1. The namespace
    """

    def __init__(self, user: User):
        self.user = user

    @transaction.atomic
    def copyFile(self, file_token: str) -> Dict[str, Any]:
        file_info=TokentoFileIdSerializer(UserPersonalFileToken.objects.get(personalfiletoken = file_token[0])).data
        if file_info['is_delete_init']:
            return "File Has Been Already Deleted by User or User has moved it to RecycleBin", 0
        elif file_info['uploaded_by'] == UserFullProfileSerializer(self.user).data['userId']:
            return "File is already owned by you", 0
        else:
            file_id = file_info['file_id']
            FileDetails = FileDetailsViewSerializer(File.objects.get(fileID = file_id)).data
            personal_token = Util.GenratePersonalFileToken(self.user, file_id)

            obj_ptoken = UserPersonalFileToken(
                uploaded_by = self.user,
                personalfiletoken = personal_token,
                file_id = File.objects.get(fileID = file_id),
                type = FileDetails["file_type"],
                is_copied = True
            )
            obj_ptoken.full_clean()
            obj_ptoken.save()

            return obj_ptoken, 1
        
class FileDeleteService:
    """
    This also serves as a file to stream,
    which encapsulates a flow (start & finish) + one-off action (upload_local) into a namespace.

    Meaning, we use the class here for:

    1. The namespace
    """

    def __init__(self, user: User):
        self.user = user

    @transaction.atomic
    def deleteFile(self, file_token: str) -> Dict[str, Any]:
        usertoken = UserPersonalFileToken.objects.get(personalfiletoken = file_token[0])
        file_info=TokentoFileIdSerializer(usertoken).data
        if not file_info['uploaded_by'] == UserFullProfileSerializer(self.user).data['userId']:
            return "File is not owned by you", 0
        elif file_info['is_delete_init']:
            return "File Has Been Already Deleted by You", 0
        else:
            usertoken.is_delete_init = True
            usertoken.delete_init_at = timezone.now()
            usertoken.full_clean()
            usertoken.save()

            if UserPersonalFileToken.objects.filter(file_id = file_info['file_id']).exclude(Q(is_delete_init = True)).exists():
                pass
            else :
                file_id = file_info['file_id']
                usertoken = File.objects.get(fileID = file_id)
                usertoken.is_delete_init = True
                usertoken.delete_init_at = timezone.now()
                usertoken.full_clean()
                usertoken.save()

            return "File Moved to Recycle Bin", True
        
class FileRestoreService:
    """
    This also serves as a file to stream,
    which encapsulates a flow (start & finish) + one-off action (upload_local) into a namespace.

    Meaning, we use the class here for:

    1. The namespace
    """

    def __init__(self, user: User):
        self.user = user

    @transaction.atomic
    def restoreFile(self, file_token: str) -> Dict[str, Any]:
        try:
            for token in file_token:
                usertoken = UserPersonalFileToken.objects.get(personalfiletoken = token)
                file_info=TokentoFileIdSerializer(usertoken).data
                if not file_info['uploaded_by'] == UserFullProfileSerializer(self.user).data['userId']:
                    return "File is not owned by you", 0
                elif not file_info['is_delete_init']:
                    return "File Has Been Already Recovered", 0
                elif file_info['is_deleted']:
                    return "File Has Been Permanently Deleted", 0
                else:
                    usertoken.is_delete_init = False
                    usertoken.delete_init_at = None
                    usertoken.full_clean()
                    usertoken.save()

                    file_id = file_info['file_id']
                    usertoken = File.objects.get(fileID = file_id)
                    usertoken.is_delete_init = False
                    usertoken.delete_init_at = None
                    usertoken.full_clean()
                    usertoken.save()

            return "Files has been Recovered", True
        except Exception as e:
            return e, False

class FileFavouriteservice:
    """
    This also serves as a file to stream,
    which encapsulates a flow (start & finish) + one-off action (upload_local) into a namespace.

    Meaning, we use the class here for:

    1. The namespace
    """

    def __init__(self, user: User):
        self.user = user

    @transaction.atomic
    def favouriteFile(self, file_token: str) -> Dict[str, Any]:
        usertoken = UserPersonalFileToken.objects.get(personalfiletoken = file_token[0])
        file_info=TokentoFileIdSerializer(usertoken).data
        if not file_info['uploaded_by'] == UserFullProfileSerializer(self.user).data['userId']:
            return "File is not owned by you", 0
        elif file_info['is_delete_init']:
            return "File Has Been Already Deleted by You", 0
        else:
            usertoken.favourite = True
            usertoken.full_clean()
            usertoken.save()

            return "File Marked As Favourite", True
        
    @transaction.atomic
    def unfavouriteFile(self, file_token: str) -> Dict[str, Any]:
        usertoken = UserPersonalFileToken.objects.get(personalfiletoken = file_token[0])
        file_info=TokentoFileIdSerializer(usertoken).data
        if not file_info['uploaded_by'] == UserFullProfileSerializer(self.user).data['userId']:
            return "File is not owned by you", 0
        elif file_info['is_delete_init']:
            return "File Has Been Already Deleted by You", 0
        else:
            usertoken.favourite = False
            usertoken.full_clean()
            usertoken.save()

            return "File Marked As UnFavourite", True
        
class FileUpdateViewsservice:
    """
    This also serves as a file to stream,
    which encapsulates a flow (start & finish) + one-off action (upload_local) into a namespace.

    Meaning, we use the class here for:

    1. The namespace
    """

    def __init__(self, user: User):
        self.user = user

    @transaction.atomic
    def updateViews(self, fileId: str) -> Dict[str, Any]:
        try:
            usertoken = UserPersonalFileToken.objects.get(personalfiletoken = fileId)
            file_info=TokentoFileIdSerializer(usertoken).data
            if not file_info['uploaded_by'] == UserFullProfileSerializer(self.user).data['userId']:
                return "File is not owned by you", False
            elif file_info['is_delete_init']:
                return "File Has Been Already Deleted by You", False
            else:
                usertoken.views += 1
                usertoken.full_clean()
                usertoken.save()
                return "File Views get Updated", True
        except UserPersonalFileToken.DoesNotExist:
            return "File not Found", False
        
class EmptyRecycleBinservice:
    """
    This also serves as a file to stream,
    which encapsulates a flow (start & finish) + one-off action (upload_local) into a namespace.

    Meaning, we use the class here for:

    1. The namespace
    """

    def __init__(self, user: User):
        self.user = user

    @transaction.atomic
    def emptybin(self) -> Dict[str, Any]:
        try:
            user_id = UserFullProfileSerializer(self.user).data['userId']
            data= UserPersonalFileToken.objects.filter(Q(uploaded_by=user_id), Q(is_deleted = False)).exclude(Q(is_delete_init = False))
            serializer=UserFileTokenListSerializer(data, many=True)
            for i in serializer.data:
                print(i)
                file = UserPersonalFileToken.objects.get(personalfiletoken = i['personalfiletoken'])
                file.is_deleted = True
                file.full_clean()
                file.save()
            return True
        except UserPersonalFileToken.DoesNotExist:
            return False
        
class UserService:
    """
    This also serves as a file to stream,
    which encapsulates a flow (start & finish) + one-off action (upload_local) into a namespace.

    Meaning, we use the class here for:

    1. The namespace
    """

    def __init__(self, user: User):
        self.user = user

    @transaction.atomic
    def getStats(self) -> Dict[str, Any]:
        try:
            user_id = UserFullProfileSerializer(self.user).data['userId']
            data= UserPersonalFileToken.objects
            totalstorage = data.filter(uploaded_by=user_id).exclude(Q(is_deleted = True)).aggregate(Sum('file_size')).get('file_size__sum')
            binusedstorage = data.filter(Q(uploaded_by=user_id), Q(is_delete_init = True)).exclude(Q(is_deleted = True)).aggregate(Sum('file_size')).get('file_size__sum')
            totalfileupload = data.filter(uploaded_by=user_id).exclude(Q(is_deleted = True)).count()
            totalrecyclebinfile = data.filter(Q(uploaded_by=user_id), Q(is_delete_init = True)).exclude(Q(is_deleted = True)).count()

            totalimagesupload = data.filter(Q(uploaded_by=user_id), Q(type__startswith="image/")).exclude(is_delete_init = True).count()
            totalvideosupload = data.filter(Q(uploaded_by=user_id), Q(type__startswith="video/")).exclude(is_delete_init = True).count()
            totalaudioupload = data.filter(Q(uploaded_by=user_id), Q(type__startswith="audio/")).exclude(is_delete_init = True).count()
            totaldocumentupload = data.filter(Q(uploaded_by=user_id), Q(type="application/pdf") | Q(type__startswith="application/vnd.openxmlformats-officedocument.")).exclude(is_delete_init = True).count()
            totalothersupload = data.filter(Q(uploaded_by=user_id), ~Q(type__startswith="image/"), ~Q(type__startswith="video/"), ~Q(type__startswith="audio/"), ~Q(type="application/pdf") , ~Q(type__startswith="application/vnd.openxmlformats-officedocument.")).exclude(is_delete_init = True).count()
            totalsharedfiles = data.filter(Q(uploaded_by=user_id), Q(is_copied = True)).exclude(Q(is_delete_init = True)).count()
            totalfavouritefiles = data.filter(Q(uploaded_by=user_id)).exclude(is_delete_init = True).exclude(favourite = False).count()

            res={
                "allocatedstorage" : int(settings.STORAGE_PER_USER),
                "totalstorage" : totalstorage,
                "binusedstorage" : binusedstorage,
                "leftstorage" : int(settings.STORAGE_PER_USER) - totalstorage,
                "totalfileupload" : totalfileupload,
                "totalrecyclebinfile" : totalrecyclebinfile,
                "totalimagesupload" : totalimagesupload,
                "totalvideosupload" : totalvideosupload,
                "totalaudioupload" : totalaudioupload,
                "totaldocumentupload" : totaldocumentupload,
                "totalothersupload" : totalothersupload,
                "totalsharedfiles" : totalsharedfiles,
                "totalfavouritefiles" : totalfavouritefiles,
            }
            
            return res, True
        except UserPersonalFileToken.DoesNotExist:
            return "", False
    
    @transaction.atomic
    def getEarnings(self) -> Dict[str, Any]:
        try:
            cpmrate = float(settings.CPM)

            user_data = UserFullProfileSerializer(self.user).data
            user_id = user_data['userId']

            ReferralToken = UserReferralTokenSerializer(UserReferral.objects.get(user = user_id))
            totalreferrals = User.objects.filter(referred_by = ReferralToken).count()

            data= UserPersonalFileToken.objects
            totalviews = data.filter(uploaded_by=user_id).exclude(Q(is_deleted = True)).aggregate(Sum('views')).get('views__sum')

            lastearnings=int(user_data['lastearnings'])
            lastviews=int(user_data['lastviews'])
            lastpayout_on=user_data['lastpayout_on']

            totalearnings = cpmrate * (totalviews/1000)
            earnings = cpmrate * ((totalviews-lastviews)/1000)

            
            res={
                "lastpayout_on" : lastpayout_on,
                "lastearnings" : lastearnings,
                "cpm" : cpmrate,
                "totalviews" : totalviews,
                "totalearnings" : totalearnings,
                "earnings" : earnings,
                "totalreferrals" : totalreferrals,
            }

            return res, True
        except UserPersonalFileToken.DoesNotExist:
            return "", False
        
    @transaction.atomic
    def getTopViewFileList(self) -> Dict[str, Any]:
        try:
            user_id = UserFullProfileSerializer(self.user).data['userId']

            data= UserPersonalFileToken.objects.select_related('file_id').filter(Q(uploaded_by=user_id), Q(is_deleted = False)).exclude(Q(is_delete_init = True)).order_by('-views')
            serializer=FilesListSerializer(data, many=True)

            res = []
            count = 0
            for i in serializer.data:
                if count >= 10 :
                    break
                if i['change_file_name'] == None:
                    filename=i['file_id']["original_file_name"]
                else:
                    filename=i["change_file_name"]
                res.append({
                    "FileID" : i['personalfiletoken'],
                    "File_type" : i['type'],
                    "Original_File_Name" : filename,
                    "File_size" : i['file_id']['file_size'],
                    "Views" : i['views']
                })
                count += 1
            if len(res) == 0:
                return "No File Found", False
            else:
                return res, True
        except UserPersonalFileToken.DoesNotExist:
            return "No File Found", False
        
class FileRenameservice:
    """
    This also serves as a file to stream,
    which encapsulates a flow (start & finish) + one-off action (upload_local) into a namespace.

    Meaning, we use the class here for:

    1. The namespace
    """

    def __init__(self, user: User):
        self.user = user

    @transaction.atomic
    def renameFile(self, file_token: str, file_name: str, file_name_new: str) -> Dict[str, Any]:
        try:
            usertoken = UserPersonalFileToken.objects.get(personalfiletoken = file_token)
            file_info=TokentoFileIdSerializer(usertoken).data
            if not file_info['uploaded_by'] == UserFullProfileSerializer(self.user).data['userId']:
                return "File is not owned by you", False
            elif file_info['is_delete_init']:
                return "File Has Been Already Deleted by You", False
            else:
                usertoken.change_file_name = file_name_new
                usertoken.full_clean()
                usertoken.save()
                return "File Name get Updated", True
        except UserPersonalFileToken.DoesNotExist:
            return "File not Found", False
        
from django.shortcuts import render
from django.db import transaction
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from Account.models import User, UserReferral
from Account.serializers import SendPasswordResetEmailSerializer, UserChangePasswordSerializer, UserFullProfileSerializer, UserLoginSerializer, UserPasswordResetSerializer, UserProfileSerializer, UserReferralSerializer, UserReferralTokenSerializer, UserRegistrationSerializer
from django.contrib.auth import authenticate
from django.db.models import Q
from Account.renderers import UserRenderer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated

from FileProcessing.models import File, UserPersonalFileToken
from FileProcessing.serializers import FileDetailsListSerializer, FilesListSerializer
from FileProcessing.services import UserService

# Create your views here.

# Generate Token Manually
def get_tokens_for_user(user):
  refresh = RefreshToken.for_user(user)
  return {
      'refresh': str(refresh),
      'access': str(refresh.access_token),
  }

class UserRegistrationView(APIView):
  renderer_classes = [UserRenderer]

  @transaction.atomic
  def post(self, request, format=None):
    referral = request.query_params.get('referral')
    serializer = UserRegistrationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    token = get_tokens_for_user(user)
    userdata = UserFullProfileSerializer(user).data
    userdata = {'user': userdata['userId']}
    Referralserializer = UserReferralSerializer(data=userdata)
    Referralserializer.is_valid(raise_exception=True)
    Referralserializer.save()
    try:
      if referral:
        referralcount = UserReferral.objects.get(token = referral)
        userdata = User.objects.get(userId = userdata['user'])
        userdata.referred_by = referral
        userdata.full_clean()
        userdata.save()
        referralcount.views += 1
        referralcount.full_clean()
        referralcount.save()
    except UserReferral.DoesNotExist:
      pass
    return Response({'token':token, 'msg':'Registration Successful'}, status=status.HTTP_201_CREATED)

class UserLoginView(APIView):
  renderer_classes = [UserRenderer]
  def post(self, request, format=None):
    serializer = UserLoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    email = serializer.data.get('email')
    password = serializer.data.get('password')
    user = authenticate(email=email, password=password)
    if user is not None:
      token = get_tokens_for_user(user)
      return Response({'token':token, 'msg':'Login Success'}, status=status.HTTP_200_OK)
    else:
      return Response({'errors':{'non_field_errors':['Email or Password is not Valid']}}, status=status.HTTP_404_NOT_FOUND)

class UserProfileView(APIView):
  renderer_classes = [UserRenderer]
  permission_classes = [IsAuthenticated]
  def get(self, request, format=None):
    serializer = UserProfileSerializer(request.user)
    return Response(serializer.data, status=status.HTTP_200_OK)
  
class ReferralToken(APIView):
  renderer_classes = [UserRenderer]
  permission_classes = [IsAuthenticated]
  
  def get(self, request, format=None):
    serializer = UserFullProfileSerializer(request.user)
    ReferralToken = UserReferralTokenSerializer(UserReferral.objects.get(user = serializer.data['userId']))
    return Response({'data':ReferralToken.data}, status=status.HTTP_200_OK)

class UserChangePasswordView(APIView):
  renderer_classes = [UserRenderer]
  permission_classes = [IsAuthenticated]
  def post(self, request, format=None):
    serializer = UserChangePasswordSerializer(data=request.data, context={'user':request.user})
    serializer.is_valid(raise_exception=True)
    return Response({'msg':'Password Changed Successfully'}, status=status.HTTP_200_OK)

class SendPasswordResetEmailView(APIView):
  renderer_classes = [UserRenderer]
  def post(self, request, format=None):
    serializer = SendPasswordResetEmailSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return Response({'msg':'Password Reset link send. Please check your Email'}, status=status.HTTP_200_OK)

class UserPasswordResetView(APIView):
  renderer_classes = [UserRenderer]
  def post(self, request, uid, token, format=None):
    serializer = UserPasswordResetSerializer(data=request.data, context={'uid':uid, 'token':token})
    serializer.is_valid(raise_exception=True)
    return Response({'msg':'Password Reset Successfully'}, status=status.HTTP_200_OK)

class LogOutAPIView(APIView):
  def post(self, request, format=None):
      try:
          refresh_token = request.data.get('refresh_token')
          token_obj = RefreshToken(refresh_token)
          token_obj.blacklist()
          return Response(status=status.HTTP_200_OK)
      except Exception as e:
          return Response(status=status.HTTP_400_BAD_REQUEST)
      
class UserFilesListView(APIView):
  renderer_classes = [UserRenderer]
  permission_classes = [IsAuthenticated]

  def get(self, request):
    try:
      user_id = UserFullProfileSerializer(request.user).data['userId']

      data= UserPersonalFileToken.objects.select_related('file_id').filter(uploaded_by=user_id).exclude(Q(is_delete_init = True)).order_by('-modified_at')
      serializer=FilesListSerializer(data, many=True)

      res = []
      for i in serializer.data:
        if i['change_file_name'] == None:
          filename=i['file_id']["original_file_name"]
        else:
          filename=i["change_file_name"]
        res.append({
          "FileID" : i['personalfiletoken'],
          "File_type" : i['type'],
          "Parent" : i['parent'],
          "Modified_At" : i['modified_at'],
          "Original_File_Name" : filename,
          "File_size" : i['file_id']['file_size'],
          "Favourite" : i['favourite'],
        })
      if len(res) == 0:
        return Response(data={"error": "No File Found"}, status=status.HTTP_404_NOT_FOUND)
      else:
        return Response(res, status=status.HTTP_200_OK)
    except UserPersonalFileToken.DoesNotExist:
      return Response(data={"error": "No File Found"}, status=status.HTTP_404_NOT_FOUND)

class UserSharedFilesListView(APIView):
  renderer_classes = [UserRenderer]
  permission_classes = [IsAuthenticated]

  def get(self, request):
    try:
      user_id = UserFullProfileSerializer(request.user).data['userId']

      data= UserPersonalFileToken.objects.select_related('file_id').filter(Q(uploaded_by=user_id), Q(is_copied = True)).exclude(Q(is_delete_init = True)).order_by('-modified_at')
      serializer=FilesListSerializer(data, many=True)

      res = []
      for i in serializer.data:
        if i['change_file_name'] == None:
          filename=i['file_id']["original_file_name"]
        else:
          filename=i["change_file_name"]
        res.append({
          "FileID" : i['personalfiletoken'],
          "File_type" : i['type'],
          "Parent" : i['parent'],
          "Modified_At" : i['modified_at'],
          "Original_File_Name" : filename,
          "File_size" : i['file_id']['file_size'],
          "Favourite" : i['favourite'],
        })
      if len(res) == 0:
        return Response(data={"error": "No File Found"}, status=status.HTTP_404_NOT_FOUND)
      else:
        return Response(res, status=status.HTTP_200_OK)
    except UserPersonalFileToken.DoesNotExist:
      return Response(data={"error": "No File Found"}, status=status.HTTP_404_NOT_FOUND)
    
class UserDeleteFilesListView(APIView):
  renderer_classes = [UserRenderer]
  permission_classes = [IsAuthenticated]

  def get(self, request):
    try:
      user_id = UserFullProfileSerializer(request.user).data['userId']

      data= UserPersonalFileToken.objects.select_related('file_id').filter(Q(uploaded_by=user_id), Q(is_deleted = False)).exclude(Q(is_delete_init = False)).order_by('-modified_at')
      serializer=FilesListSerializer(data, many=True)

      res = []
      for i in serializer.data:
        if i['change_file_name'] == None:
          filename=i['file_id']["original_file_name"]
        else:
          filename=i["change_file_name"]
        res.append({
          "FileID" : i['personalfiletoken'],
          "File_type" : i['type'],
          "Parent" : i['parent'],
          "Modified_At" : i['modified_at'],
          "Original_File_Name" : filename,
          "File_size" : i['file_id']['file_size'],
          "Favourite" : i['favourite'],
        })
      if len(res) == 0:
        return Response(data={"error": "No File Found"}, status=status.HTTP_404_NOT_FOUND)
      else:
        return Response(res, status=status.HTTP_200_OK)
    except UserPersonalFileToken.DoesNotExist:
      return Response(data={"error": "No File Found"}, status=status.HTTP_404_NOT_FOUND)
  
class UserFavouriteFilesListView(APIView):
  renderer_classes = [UserRenderer]
  permission_classes = [IsAuthenticated]

  def get(self, request):
    try:
      user_id = UserFullProfileSerializer(request.user).data['userId']
      data= UserPersonalFileToken.objects.select_related('file_id').filter(Q(uploaded_by=user_id)).exclude(is_delete_init = True).exclude(favourite = False).order_by('-modified_at')
      serializer=FilesListSerializer(data, many=True)

      res = []
      for i in serializer.data:
        if i['change_file_name'] == None:
          filename=i['file_id']["original_file_name"]
        else:
          filename=i["change_file_name"]
        res.append({
          "FileID" : i['personalfiletoken'],
          "File_type" : i['type'],
          "Parent" : i['parent'],
          "Modified_At" : i['modified_at'],
          "Original_File_Name" : filename,
          "File_size" : i['file_id']['file_size'],
          "Favourite" : i['favourite'],
        })
      if len(res) == 0:
        return Response(data={"error": "No File Found"}, status=status.HTTP_404_NOT_FOUND)
      else:
        return Response(res, status=status.HTTP_200_OK)
    except UserPersonalFileToken.DoesNotExist:
      return Response(data={"error": "No File Found"}, status=status.HTTP_404_NOT_FOUND)
  
class UserImagesFilesListView(APIView):
  renderer_classes = [UserRenderer]
  permission_classes = [IsAuthenticated]

  def get(self, request):
    try:
      user_id = UserFullProfileSerializer(request.user).data['userId']
      data= UserPersonalFileToken.objects.select_related('file_id').filter(Q(uploaded_by=user_id), Q(type__startswith="image/")).exclude(is_delete_init = True).order_by('-modified_at')
      serializer=FilesListSerializer(data, many=True)

      res = []
      for i in serializer.data:
        if i['change_file_name'] == None:
          filename=i['file_id']["original_file_name"]
        else:
          filename=i["change_file_name"]
        res.append({
          "FileID" : i['personalfiletoken'],
          "File_type" : i['type'],
          "Parent" : i['parent'],
          "Modified_At" : i['modified_at'],
          "Original_File_Name" : filename,
          "File_size" : i['file_id']['file_size'],
          "Favourite" : i['favourite'],
        })
      if len(res) == 0:
        return Response(data={"error": "No File Found"}, status=status.HTTP_404_NOT_FOUND)
      else:
        return Response(res, status=status.HTTP_200_OK)
    except UserPersonalFileToken.DoesNotExist:
      return Response(data={"error": "No File Found"}, status=status.HTTP_404_NOT_FOUND)
  
class UserVideoFilesListView(APIView):
  renderer_classes = [UserRenderer]
  permission_classes = [IsAuthenticated]

  def get(self, request):
    try:
      user_id = UserFullProfileSerializer(request.user).data['userId']
      data= UserPersonalFileToken.objects.select_related('file_id').filter(Q(uploaded_by=user_id), Q(type__startswith="video/")).exclude(is_delete_init = True).order_by('-modified_at')
      serializer=FilesListSerializer(data, many=True)

      res = []
      for i in serializer.data:
        if i['change_file_name'] == None:
          filename=i['file_id']["original_file_name"]
        else:
          filename=i["change_file_name"]
        res.append({
          "FileID" : i['personalfiletoken'],
          "File_type" : i['type'],
          "Parent" : i['parent'],
          "Modified_At" : i['modified_at'],
          "Original_File_Name" : filename,
          "File_size" : i['file_id']['file_size'],
          "Favourite" : i['favourite'],
        })
      if len(res) == 0:
        return Response(data={"error": "No File Found"}, status=status.HTTP_404_NOT_FOUND)
      else:
        return Response(res, status=status.HTTP_200_OK)
    except UserPersonalFileToken.DoesNotExist:
      return Response(data={"error": "No File Found"}, status=status.HTTP_404_NOT_FOUND)

class UserAudioFilesListView(APIView):
  renderer_classes = [UserRenderer]
  permission_classes = [IsAuthenticated]

  def get(self, request):
    try:
      user_id = UserFullProfileSerializer(request.user).data['userId']
      data= UserPersonalFileToken.objects.select_related('file_id').filter(Q(uploaded_by=user_id), Q(type__startswith="audio/")).exclude(is_delete_init = True).order_by('-modified_at')
      serializer=FilesListSerializer(data, many=True)

      res = []
      for i in serializer.data:
        if i['change_file_name'] == None:
          filename=i['file_id']["original_file_name"]
        else:
          filename=i["change_file_name"]
        res.append({
          "FileID" : i['personalfiletoken'],
          "File_type" : i['type'],
          "Parent" : i['parent'],
          "Modified_At" : i['modified_at'],
          "Original_File_Name" : filename,
          "File_size" : i['file_id']['file_size'],
          "Favourite" : i['favourite'],
        })
      if len(res) == 0:
        return Response(data={"error": "No File Found"}, status=status.HTTP_404_NOT_FOUND)
      else:
        return Response(res, status=status.HTTP_200_OK)
    except UserPersonalFileToken.DoesNotExist:
      return Response(data={"error": "No File Found"}, status=status.HTTP_404_NOT_FOUND)
  
class UserDocumentsFilesListView(APIView):
  renderer_classes = [UserRenderer]
  permission_classes = [IsAuthenticated]

  def get(self, request):
    try:
      user_id = UserFullProfileSerializer(request.user).data['userId']
      data= UserPersonalFileToken.objects.select_related('file_id').filter(Q(uploaded_by=user_id), Q(type="application/pdf") | Q(type__startswith="application/vnd.openxmlformats-officedocument.")).exclude(is_delete_init = True).order_by('-modified_at')
      serializer=FilesListSerializer(data, many=True)

      res = []
      for i in serializer.data:
        if i['change_file_name'] == None:
          filename=i['file_id']["original_file_name"]
        else:
          filename=i["change_file_name"]
        res.append({
          "FileID" : i['personalfiletoken'],
          "File_type" : i['type'],
          "Parent" : i['parent'],
          "Modified_At" : i['modified_at'],
          "Original_File_Name" : filename,
          "File_size" : i['file_id']['file_size'],
          "Favourite" : i['favourite'],
        })
      if len(res) == 0:
        return Response(data={"error": "No File Found"}, status=status.HTTP_404_NOT_FOUND)
      else:
        return Response(res, status=status.HTTP_200_OK)
    except UserPersonalFileToken.DoesNotExist:
      return Response(data={"error": "No File Found"}, status=status.HTTP_404_NOT_FOUND)
  
class UserOthersFilesListView(APIView):
  renderer_classes = [UserRenderer]
  permission_classes = [IsAuthenticated]

  def get(self, request):
    try:
      user_id = UserFullProfileSerializer(request.user).data['userId']
      data= UserPersonalFileToken.objects.select_related('file_id').filter(Q(uploaded_by=user_id), ~Q(type__startswith="image/"), ~Q(type__startswith="video/"), ~Q(type__startswith="audio/"), ~Q(type="application/pdf") , ~Q(type__startswith="application/vnd.openxmlformats-officedocument.")).exclude(is_delete_init = True).order_by('-modified_at')
      serializer=FilesListSerializer(data, many=True)

      res = []
      for i in serializer.data:
        if i['change_file_name'] == None:
          filename=i['file_id']["original_file_name"]
        else:
          filename=i["change_file_name"]
        res.append({
          "FileID" : i['personalfiletoken'],
          "File_type" : i['type'],
          "Parent" : i['parent'],
          "Modified_At" : i['modified_at'],
          "Original_File_Name" : filename,
          "File_size" : i['file_id']['file_size'],
          "Favourite" : i['favourite'],
        })
      if len(res) == 0:
        return Response(data={"error": "No File Found"}, status=status.HTTP_404_NOT_FOUND)
      else:
        return Response(res, status=status.HTTP_200_OK)
    except UserPersonalFileToken.DoesNotExist:
      return Response(data={"error": "No File Found"}, status=status.HTTP_404_NOT_FOUND)

class UserStatsView(APIView):
    renderer_classes = [UserRenderer]
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        service = UserService(user=request.user)
        data,stats_status=service.getStats()
        if stats_status:
            return Response(data=data,status=status.HTTP_200_OK)
        else:
            return Response(data={"error": data},status=status.HTTP_400_BAD_REQUEST)
        
class UserEarningsView(APIView):
    renderer_classes = [UserRenderer]
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        service = UserService(user=request.user)
        data,earnings_status=service.getEarnings()
        if earnings_status:
            return Response(data=data,status=status.HTTP_200_OK)
        else:
            return Response(data={"error": data},status=status.HTTP_400_BAD_REQUEST)
        
class UserTopViewFilesView(APIView):
    renderer_classes = [UserRenderer]
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        service = UserService(user=request.user)
        data,topviewfile_status=service.getTopViewFileList()
        if topviewfile_status:
            return Response(data=data,status=status.HTTP_200_OK)
        else:
            return Response(data={"error": data},status=status.HTTP_400_BAD_REQUEST)
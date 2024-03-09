from django.urls import include, path
from Account.views import ReferralToken, SendPasswordResetEmailView, UserAudioFilesListView, UserChangePasswordView, UserDeleteFilesListView, UserDocumentsFilesListView, UserEarningsView, UserFavouriteFilesListView, UserFilesListView, UserImagesFilesListView, UserLoginView, UserOthersFilesListView, UserProfileView, UserRegistrationView, UserPasswordResetView, LogOutAPIView, UserSharedFilesListView, UserStatsView, UserTopViewFilesView, UserVideoFilesListView
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
urlpatterns = [
    path('register/', UserRegistrationView.as_view(), name='register'),
    path('login/', UserLoginView.as_view(), name='login'),
    path('logout/', LogOutAPIView.as_view(), name='logout_view'),
    path('profile/', UserProfileView.as_view(), name='profile'),
    path('changepassword/', UserChangePasswordView.as_view(), name='changepassword'),
    path('send-reset-password-email/', SendPasswordResetEmailView.as_view(), name='send-reset-password-email'),
    path('reset-password/<uid>/<token>/', UserPasswordResetView.as_view(), name='reset-password'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh_view'),
    path('referral/', ReferralToken.as_view(), name='token_refresh_view'),
    path(
        "getfiles/",
        include(
            (
                [
                    path("fulllist/", UserFilesListView.as_view(), name="GetFileList"),
                    path("sharedlist/", UserSharedFilesListView.as_view(), name="GetSharedList"),
                    path('deletelist/', UserDeleteFilesListView.as_view(), name='GetDeleteFileList'),
                    path('favouritelist/', UserFavouriteFilesListView.as_view(), name='GetFavouriteFileList'),
                    path('imageslist/', UserImagesFilesListView.as_view(), name='GetImagesFileList'),
                    path('videolist/', UserVideoFilesListView.as_view(), name='GetVideoFileList'),
                    path('audiolist/', UserAudioFilesListView.as_view(), name='GetAudioFileList'),
                    path('documentlist/', UserDocumentsFilesListView.as_view(), name='GetDocumnetsFileList'),
                    path('otherslist/', UserOthersFilesListView.as_view(), name='GetOthersFileList'),
                ],
                "getfiles",
            )
        ),
    ),
    path('earnings/', UserEarningsView.as_view(), name='Earnings'),
    path('topviewfiles/', UserTopViewFilesView.as_view(), name='TopViewFil List'),
    path('stats/', UserStatsView.as_view(), name='UserStats'),
]
from django.urls import include, path
from FileProcessing.folder_views import FolderCreationView

from FileProcessing.views import (
    EmptyRecycleBinView,
    FileCopyView,
    FileDeleteView,
    FileDirectUploadFinishApi,
    FileDirectUploadLocalApi,
    FileDirectUploadStartApi,
    FileFavouriteView,
    FileGetView,
    FileDownloadView,
    FileMoveView,
    FileMultipartUploadView,
    FileRenameView,
    FileRestoreView,
    FileStandardUploadApi,
    FileDetailsView,
    FileUnFavouriteView,
    FileUpdateFileViewsView,
)

# Depending on your case, you might want to exclude certain urls, based on the values of
# FILE_UPLOAD_STRATEGY and FILE_UPLOAD_STORAGE
# For the sake fo simplicity and to serve as an example project, we are including everything here.

urlpatterns = [
    path(
        "upload/",
        include(
            (
                [
                    path("standard/", FileStandardUploadApi.as_view(), name="standard"),
                    path('multipart/', FileMultipartUploadView.as_view(), name='MultiPartUpload'),
                ],
                "upload",
            )
        ),
    ),
    path('create/', FolderCreationView.as_view(), name='Folder'),
    path('details/', FileDetailsView.as_view(), name='FileDetails'),
    path('delete/', FileDeleteView.as_view(), name='FileDelete'),
    path('restore/', FileRestoreView.as_view(), name='FileRestore'),
    path('emptyrecyclebin/', EmptyRecycleBinView.as_view(), name='EmptyRecycleBin'),
    path('copy/', FileCopyView.as_view(), name='FileCopy'),
    path('move/', FileMoveView.as_view(), name='FileMove'),
    path('favourite/', FileFavouriteView.as_view(), name='FileFavourite'),
    path('unfavourite/', FileUnFavouriteView.as_view(), name='FileUnFavourite'),
    path('rename/', FileRenameView.as_view(), name='FileRename'),
    path('get/<token>/', FileGetView.as_view(), name='FileGet'),
    path('get/d/<token>/', FileDownloadView.as_view(), name='FileDownload'),
    path('updated/fileviews/', FileUpdateFileViewsView.as_view(), name='UpdatedFileViews'),
]

import os
import time
import random
import string
import hashlib
import pathlib
from uuid import uuid4

from django.conf import settings
from django.urls import reverse


def file_generate_name(original_file_name):
    extension = pathlib.Path(original_file_name).suffix

    return f"{uuid4().hex}{extension}"


def file_generate_upload_path(instance, filename):
    return f"files/{instance.file_type}/{instance.file_name}"


def file_generate_local_upload_url(*, file_id: str):
    url = reverse("api:files:upload:direct:local", kwargs={"file_id": file_id})
    app_domain: str = settings.APP_DOMAIN  # type: ignore
    return f"{app_domain}{url}"


def bytes_to_mib(value: int) -> float:
    # 1 bytes = 9.5367431640625E-7 mebibytes
    return value * 9.5367431640625e-7

class Util:
    @staticmethod
    def GenratePersonalFileToken(userid, fileid):
        # Generate a unique identifier based on epoch time
        epoch_time = str(int(time.time()))

        # Generate 12 random characters
        random_chars = ''.join(random.choice(string.ascii_letters + string.digits + string.punctuation) for _ in range(12))

        # Combine all the components
        unique_string = f"uid_{epoch_time}_{random_chars}"

        # Hash the unique string using SHA-256
        hash_object = hashlib.sha256(unique_string.encode())
        hash_string = hash_object.hexdigest()

        return hash_string
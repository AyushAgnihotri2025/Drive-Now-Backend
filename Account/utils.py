from django.core.mail import EmailMessage

import os
import time
import random
import string
import hashlib

class Util:
    @staticmethod
    def send_email(data):
        email = EmailMessage(
        subject=data['subject'],
        body=data['body'],
        from_email=os.environ.get('EMAIL_FROM'),
        to=[data['to_email']]
        )
        email.send()

    @staticmethod
    def genrateUserId():
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
    
    @staticmethod
    def genrateToken():
        # Generate a unique identifier based on epoch time
        epoch_time = str(int(time.time()))

        # Generate 12 random characters
        random_chars = ''.join(random.choice(string.ascii_letters + string.digits + string.punctuation) for _ in range(7))

        # Combine all the components
        unique_string = f"uid_{epoch_time}_{random_chars}"

        # Hash the unique string using SHA-256
        hash_object = hashlib.sha256(unique_string.encode())
        hash_string = hash_object.hexdigest()

        return hash_string

import os
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST", default="localhost"),
        "PORT": os.getenv("DB_PORT", default="5432"),
        "OPTIONS": {
            "sslmode": os.getenv("DB_SSLMODE", default="disable"),
        },
    }
}

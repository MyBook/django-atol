import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRET_KEY = 'super-secret-string'
DEBUG = False


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'atol',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'tests.test_app.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


# Database
# https://docs.djangoproject.com/en/1.11/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'atol'
    }
}


# Caches
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.11/howto/static-files/

CELERY_ALWAYS_EAGER = True
CELERY_IGNORE_RESULT = True

RECEIPTS_ATOL_LOGIN = 'login'
RECEIPTS_ATOL_PASSWORD = 'secret'
RECEIPTS_ATOL_GROUP_CODE = 'ATOL-ProdTest-1'
RECEIPTS_ATOL_TAX_NAME = 'vat18'
RECEIPTS_ATOL_INN = '112233445573'
RECEIPTS_ATOL_CALLBACK_URL = None
RECEIPTS_ATOL_PAYMENT_ADDRESS = 'г. Москва, ул. Оранжевая, д.22 к.11'
RECEIPTS_OFD_URL_TEMPLATE = u'https://lk.platformaofd.ru/web/noauth/cheque?fn={fn}&fp={fp}'

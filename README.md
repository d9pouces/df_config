df_config
=========

Django, *the web framework for perfectionists with deadlines*, is based on a single settings Python module (defined in a environment variable).

`df-config` helps you to manage your settings in a more flexible way:
- most common settings are **defined out-of-the-box with good, auto-discovered, defaults**,
- other settings can be defined in **environment variables**, in a **.ini file**, or in **a Python module**,
- settings can be **dynamically defined, based on other settings**.

These settings could be organized into three categories:

  * settings that are very common and that can be kept as-is for most projects (`USE_TZ = True` or `MEDIA_URL = '/media/'`),
  * settings that are specific to your project but common to all instances of your project (like `INSTALLED_APPS`),
  * settings that are installation-dependent (`DATABASE_PASSWORD`, …)

Moreover, there are dependencies between settings. For example, `ADMIN_EMAIL`, `ALLOWED_HOSTS` and `CSRF_COOKIE_DOMAIN` depend
 on the same domain name of your site,  and `SESSION_COOKIE_SECURE` and `CSRF_COOKIE_SECURE` can be set only when you use TLS.
`df_config` allows to use functions to dynamically define these settings using some other settings as parameters.

Finally, df_config dynamically merges several sources to define the final settings:

  * :mod:`df_config.config.defaults` that aims at providing good default values,
  * `yourproject.defaults` for your project-specific settings,
  * `/etc/yourproject/settings(.py|.ini)` for installation-dependent settings,
  * environment variables are also read if you prefer to use them.

df_config also defines settings that should be valid for most sites, based on common installed Django apps.

You can define a list of settings that are read from a traditionnal text configuration file (`.ini format <https://docs.python.org/3/library/configparser.html>`_).
Finally, df_config also searches for environment variables, or `local_settings.py` and `local_settings.ini` setting files in the working directory.


Requirements and installation
-----------------------------

df_config works with:

  * Python 3.6+,
  * Django 2.0+.
  
```bash
python -m pip install df_config
```
  
How to use it?
--------------

df_config assumes that your project has a main module `yourproject`.
Then you just have two steps to follow:

- update your `manage.py` file: 

```python
#!/usr/bin/env python
from df_config.manage import manage, set_env

set_env(module_name="yourproject")
if __name__ == "__main__":
    manage()

```

- copy your current settings (as-is) into `yourproject/defaults.py`,


You can take a look to the resulting settings and from which source they are read:
```bash
python3 manage.py config python -v 2
```

If you want a single settings file, you can also create it:

```bash
python3 manage.py config python --filename settings.py
```


update your setup.py
--------------------

You should the entry point in your `setup.py` file:

```python
entry_points = {"console_scripts": ["yourproject-ctl = df_config.manage:manage"]}
``` 

Once installed, the command `yourproject-ctl` (in fact, you can change `ctl` by anything without hyphen) executes the standard `maanage` command. 


dynamize your settings!
-----------------------

First, you can provide sensible defaults settings in `yourproject.py` and overwrite the dev settings in `local_settings.py`.
Then real things can begin:
For example, imagine that you currently have the following settings:

```python
LOG_DIRECTORY = '/var/myproject/logs'
STATIC_ROOT = '/var/myproject/static'
MEDIA_ROOT = '/var/myproject/media'
FILE_UPLOAD_TEMP_DIR = '/var/myproject/tmp'
```

If you change the base directory `/var/myproject`, four variables needs to be changed (and you will forget to change at least one).
Now, you can write:

```python
LOCAL_PATH = '/var/myproject'
LOG_DIRECTORY = '{LOCAL_PATH}/logs'
STATIC_ROOT = '{LOCAL_PATH}/static'
MEDIA_ROOT = '{LOCAL_PATH}/media'
FILE_UPLOAD_TEMP_DIR = '{LOCAL_PATH}/tmp'
```

Now, you just have to redefine `LOCAL_PATH`; but you can even go slightly further:

```python
from df_config.config.dynamic_settings import Directory
LOCAL_PATH = Directory('/var/myproject')
LOG_DIRECTORY = Directory('{LOCAL_PATH}/logs')
STATIC_ROOT = Directory('{LOCAL_PATH}/static')
MEDIA_ROOT = Directory('{LOCAL_PATH}/media')
FILE_UPLOAD_TEMP_DIR = Directory('{LOCAL_PATH}/tmp')
```

If you run the `check` command, you will be warned for missing directories, and the `collectstatic` and `migrate` commands
will attempt to create them.
Of course, you still have `settings.MEDIA_ROOT == '/var/myproject/media'` in your code, when settings are loaded.


You can use more complex things, instead of:

```python
SERVER_BASE_URL = 'http://www.example.com'
SERVER_NAME = 'www.example.com'
USE_SSL = False
ALLOWED_HOSTS = ['www.example.com']
CSRF_COOKIE_DOMAIN = 'www.example.com'
```

You could just write:

```python
from urllib.parse import urlparse
from df_config.config.dynamic_settings import CallableSetting

SERVER_BASE_URL = 'http://www.example.com'
SERVER_NAME = CallableSetting(lambda x: urlparse(x['SERVER_BASE_URL']).hostname, 'SERVER_BASE_URL')
USE_SSL = CallableSetting(lambda x: urlparse(x['SERVER_BASE_URL']).scheme == 'https', 'SERVER_BASE_URL')
ALLOWED_HOSTS = CallableSetting(lambda x: [urlparse(x['SERVER_BASE_URL']).hostname], 'SERVER_BASE_URL')
CSRF_COOKIE_DOMAIN = CallableSetting(lambda x: urlparse(x['SERVER_BASE_URL']).hostname, 'SERVER_BASE_URL')
```

Ok, it looks a bit more complex but df-config defines them for you by default, based on the `SERVER_BASE_URL` setting. 
In fact, you just have to write the right `SERVER_BASE_URL` and all the other settings are automatically defined.

Configuration files and environment variables
---------------------------------------------

Your user probably prefer use .ini files instead of Python ones or use environment variables.
By default, df_config searches for a list `INI_MAPPING` into the module `yourproject.iniconf` or uses `df_config.iniconf.INI_MAPPING`.

```python
from df_config.config.fields import ConfigField
INI_MAPPING = [ConfigField("global.server_url", "SERVER_BASE_URL", help_str="Public URL of your website.", env_name="SERVER_BASE_URL")]
```

Some specialized classes are available in `df_config.config.fields`: `CharConfigField`, `IntegerConfigField`, `FloatConfigField`, `ListConfigField`, `BooleanConfigField`, `ChoiceConfigFile`.
You can also pickup some predefined list in `df_config.iniconf`.

You can also use environment variables instead of an .ini file (only for values in the INI_MAPPING list):
```bash
export SERVER_URL=http://www.example-2.com
export DATABASE_URL=postgres://user:password@localhost:5432/dbname?sslmode=disable
export REDIS_URL=rediss://:password@localhost:6379/1
python3 manage.py config python -v 2 | grep SERVER_BASE_URL
```

You can check the current config as a .ini file or as environment variables: 
```bash
export SERVER_URL=http://www.example-2.com
export DATABASE_URL=postgres://user:password@localhost:5432/dbname?sslmode=disable
export REDIS_URL=rediss://:password@localhost:6379/1
python3 manage.py config env
python3 manage.py config ini
```

dynamic settings
----------------

By default, any `str` is assumed to be a template string: for example, `LOG_DIRECTORY = '{LOCAL_PATH}/logs'` needs `LOCAL_PATH` to be defined.
So, if one of your setting include such values, it need to be encapsulated:

```python
from df_config.config.dynamic_settings import RawValue
LOG_DIRECTORY = RawValue('{LOCAL_PATH}/logs')
```

Other dynamic classes are:
```python
from df_config.config.dynamic_settings import Directory, AutocreateFileContent, SettingReference, CallableSetting, ExpandIterable
from df_config.guesses.misc import generate_secret_key, secure_hsts_seconds
DIRNAME = Directory("/tmp/directory")
# creates /tmp/directory with collectstatic/migrate commands, otherwise you have a warning 
SECRET_KEY = AutocreateFileContent("{LOCAL_PATH}/secret_key.txt", generate_secret_key, mode=0o600, use_collectstatic=False,use_migrate=True)
# if the file does not exist, SECRET_KEY = generate_secret_key()
# if the file does exist, SECRET_KEY is equal to its content
# if the migrate command is called and the file does not exist, it is created and the result of generate_secret_key() is written to it
TEMPLATE_DEBUG = SettingReference('DEBUG')
# TEMPLATE_DEBUG is always equal to DEBUG, even if DEBUG is defined in another file
SECURE_HSTS_SECONDS = CallableSetting(secure_hsts_seconds, "USE_SSL")
# the secure_hsts_seconds is called with a dict that contains the currently resolved settings
# at least USE_SSL is present in this dict (maybe some other values are also defined)
# the list of required settings can be directly set as an attribute of the callable:
# secure_hsts_seconds.required_settings = ["USE_SSL"]
# SECURE_HSTS_SECONDS = CallableSetting(secure_hsts_seconds)
INSTALLED_APPS = ["django.contrib.admin", ..., ExpandIterable("EXTRA_APPS"), "django.contrib.auth"]
# EXTRA_APPS must be a list, whose values are inserted in the final valaues

```

server command
--------------

You can choose the application server used in production:
```python
DF_SERVER = "gunicorn"  # "gunicorn" or "daphne"
```
A new Django command `server` is available and launches `gunicorn` or `daphne`. The application and the listen address/port are specified so you do no have to set them. 


Heroku
------

Environment variable names have been chosen to be compatible with the Heroku default environment: 

  * `SECRET_KEY`: should set it in your `app.json` file
  * `DATABASE_URL`: automatically set by the "heroku-postgresql" addon
  * `PORT`: set by default
  * `HEROKU_APP_NAME`: you should set it in your `app.json` file
  
Django app detection
--------------------

A few well-known Django applications are automatically detected and added to the list of `INSTALLED_APPS`:

  * `django-pipeline`
  * `django-debug-toolbar`
  * `django-allauth`
  * `whitenoise`
  * `django-csp`
  * `celery`
  * `df_websockets`
  * `django-channels`
  * `django-auth-ldap`
  * `django-cors-headers`
  * `django-hosts`
  * `django-minio-storage`
  * `django—pam`
  * `django-prometheus`
  * `django-radius`
  * `django-redis-sessions`
  * `django-smart-selects`
  * `sentry.io`
 
Defaults settings are also proposed so these applications should be working out of the box.


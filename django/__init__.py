from django.utils.version import get_version

VERSION = (2, 0, 14, 'alpha', 0)

__version__ = get_version(VERSION)


def setup(set_prefix=True):
    """
    Configure the settings (this happens as a side effect of accessing the
    first setting), configure logging and populate the app registry.
    Set the thread-local urlresolvers script prefix if `set_prefix` is True.

    加载所有的应用和模型
    """
    from django.apps import apps
    from django.conf import settings
    from django.urls import set_script_prefix
    from django.utils.log import configure_logging

    # 从 settings 文件下读取 LOGGING_CONFIG 配置日志文件
    configure_logging(settings.LOGGING_CONFIG, settings.LOGGING)
    if set_prefix:
        set_script_prefix(
            '/' if settings.FORCE_SCRIPT_NAME is None else settings.FORCE_SCRIPT_NAME
        )
    # 从 settings 文件获取 INSTALLED_APPS 配置
    apps.populate(settings.INSTALLED_APPS)

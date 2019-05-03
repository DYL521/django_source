from django.utils.version import get_version

VERSION = (2, 0, 14, 'alpha', 0)

__version__ = get_version(VERSION)


def setup(set_prefix=True):
    """
    Configure the settings (this happens as a side effect of accessing the
    first setting), configure logging and populate the app registry.
    Set the thread-local urlresolvers script prefix if `set_prefix` is True.
    配置设置（这是访问
    第一个设置），配置日志记录并填充应用程序注册表。
    如果'set_prefix'为真，则设置线程本地urlresolvers脚本前缀。
    """
    from django.apps import apps
    from django.conf import settings
    from django.urls import set_script_prefix
    from django.utils.log import configure_logging

    import pdb;pdb.set_trace()
    configure_logging(settings.LOGGING_CONFIG, settings.LOGGING)
    # settings.LOGGING_CONFIG = 'logging.config.dictConfig' settings.LOGGING ={} 但是这个是在那个位置设置的呢？
    if set_prefix:
        set_script_prefix('/' if settings.FORCE_SCRIPT_NAME is None else settings.FORCE_SCRIPT_NAME
        ) # FORCE_SCRIPT_NAME = None ,直接为/
    apps.populate(settings.INSTALLED_APPS) # 加载app、model等等。。。。

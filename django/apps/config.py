import os
from importlib import import_module

from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import module_has_submodule

MODELS_MODULE_NAME = 'models'


class AppConfig:  ##123123
    """Class representing a Django application and its configuration."""

    def __init__(self, app_name, app_module):
        # Full Python path to the application e.g. 'django.contrib.admin'.
        # name 表示app的全路径
        self.name = app_name

        # Root module for the application e.g. <module 'django.contrib.admin'
        # from 'django/contrib/admin/__init__.py'>.
        # 应用的__init__
        self.module = app_module

        # Reference to the Apps registry that holds this AppConfig. Set by the
        # registry when it registers the AppConfig instance.
        self.apps = None

        # The following attributes could be defined at the class level in a
        # subclass, hence the test-and-set pattern.

        # Last component of the Python path to the application e.g. 'admin'.
        # This value must be unique across a Django project.
        # 应用程序的Python路径的最后一个组件，例如“admin”。他的值在Django项目中必须是唯一的。
        if not hasattr(self, 'label'):
            self.label = app_name.rpartition(".")[2]

        # Human-readable name for the application e.g. "Admin". admin展示的名字
        if not hasattr(self, 'verbose_name'):
            self.verbose_name = self.label.title()

        # Filesystem path to the application directory e.g.
        # '/path/to/django/contrib/admin'. admin 
        if not hasattr(self, 'path'):
            self.path = self._path_from_module(app_module)

        # Module containing models e.g. <module 'django.contrib.admin.models'
        # from 'django/contrib/admin/models.py'>. Set by import_models().
        # None if the application doesn't have a models module.
        self.models_module = None

        # Mapping of lower case model names to model classes. Initially set to
        # None to prevent accidental access before import_models() runs.
        self.models = None

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, self.label)

    def _path_from_module(self, module):
        """Attempt to determine app's filesystem path from its module."""
        # See #21874 for extended discussion of the behavior of this method in
        # various cases.
        # Convert paths to list because Python's _NamespacePath doesn't support
        # indexing.
        paths = list(getattr(module, '__path__', []))
        if len(paths) != 1:
            filename = getattr(module, '__file__', None)
            if filename is not None:
                paths = [os.path.dirname(filename)]
            else:
                # For unknown reasons, sometimes the list returned by __path__
                # contains duplicates that must be removed (#25246).
                paths = list(set(paths))
        if len(paths) > 1:
            raise ImproperlyConfigured(
                "The app module %r has multiple filesystem locations (%r); "
                "you must configure this app with an AppConfig subclass "
                "with a 'path' class attribute." % (module, paths))
        elif not paths:
            raise ImproperlyConfigured(
                "The app module %r has no filesystem location, "
                "you must configure this app with an AppConfig subclass "
                "with a 'path' class attribute." % (module,))
        return paths[0]

    @classmethod
    def create(cls, entry):
        """
        Factory that creates an app config from an entry in INSTALLED_APPS.
        从已安装的应用程序中的条目创建应用程序配置的工厂。
        """
        try:
            # If import_module succeeds, entry is a path to an app module,
            # which may specify an app config class with default_app_config.
            # Otherwise, entry is a path to an app config class or an error.
            module = import_module(entry)  # 加载

        except ImportError:
            # Track that importing as an app module failed. If importing as an
            # app config class fails too, we'll trigger the ImportError again.
            module = None

            mod_path, _, cls_name = entry.rpartition('.')  # 分割字符串 apps.app.app .APPconfig

            # Raise the original exception when entry cannot be a path to an
            # app config class.
            if not mod_path:
                raise

        else:
            try:
                # 这里的entry是每个django app中对应配置类，对应于apps.py
                # If this works, the app module specifies an app config class.
                entry = module.default_app_config
            except AttributeError:
                # Otherwise, it simply uses the default app config class.
                return cls(entry, module)
            else:
                mod_path, _, cls_name = entry.rpartition('.')

        # If we're reaching this point, we must attempt to load the app config
        # class located at <mod_path>.<cls_name>
        mod = import_module(mod_path)  # 引入模块！
        try:
            # 这里我们拿到了项目中某个app下面的apps.py中的XXConfig类，继承自AppConfig
            cls = getattr(mod, cls_name)  # 加载类
        except AttributeError:
            if module is None:
                # If importing as an app module failed, that error probably
                # contains the most informative traceback. Trigger it again.
                import_module(entry)
            else:
                raise

        # Check for obvious errors. (This check prevents duck typing, but
        # it could be removed if it became a problem in practice.)
        if not issubclass(cls, AppConfig):  # 检查是否是AppConfig的实例
            raise ImproperlyConfigured(
                "'%s' isn't a subclass of AppConfig." % entry)

        # Obtain app name here rather than in AppClass.__init__ to keep
        # all error checking for entries in INSTALLED_APPS in one place.
        try:
            # 这个是我们生成app指定的那个名字，会自动填充到xxConfig的name属性中去
            app_name = cls.name
        except AttributeError:
            raise ImproperlyConfigured(
                "'%s' must supply a name attribute." % entry)

        # Ensure app_name points to a valid module.
        try:
            app_module = import_module(app_name)
        except ImportError:
            raise ImproperlyConfigured(
                "Cannot import '%s'. Check that '%s.%s.name' is correct." % (
                    app_name, mod_path, cls_name,
                )
            )

        # Entry is a path to an app config class.
        return cls(app_name, app_module)  # 返回一个app的实例

    def get_model(self, model_name, require_ready=True):
        """
        Return the model with the given case-insensitive model_name.

        Raise LookupError if no model exists with this name.
        """
        if require_ready:
            self.apps.check_models_ready()
        else:
            self.apps.check_apps_ready()
        try:
            return self.models[model_name.lower()]
        except KeyError:
            raise LookupError(
                "App '%s' doesn't have a '%s' model." % (self.label, model_name))

    def get_models(self, include_auto_created=False, include_swapped=False):
        """
        Return an iterable of models.

        By default, the following models aren't included:

        - auto-created models for many-to-many relations without
          an explicit intermediate table,
        - models that have been swapped out.

        Set the corresponding keyword argument to True to include such models.
        Keyword arguments aren't documented; they're a private API.
        """
        self.apps.check_models_ready()
        for model in self.models.values():
            if model._meta.auto_created and not include_auto_created:
                continue
            if model._meta.swapped and not include_swapped:
                continue
            yield model

    #这里可以看到，import_models其实是从总的apps管理器对象那里去取自己对应的models存起来。
    # 这是因为如Apps类中所注释的：
    # Every time a model is imported, ModelBase.__new__ calls apps.register_model which creates an entry in all_models.
    # 总的apps管理器会在import的时候注册所有的model，
    # 所以在注册某一个app配置实例的时候，反而是app配置实例去apps管理器那里拿属于自己的models进行属性赋值。
    def import_models(self):
        # Dictionary of models for this app, primarily maintained in the
        # 'all_models' attribute of the Apps this AppConfig is attached to.
        # 此应用程序的模型字典，主要维护在
        # 此AppConfig附加到的应用程序的“所有模型”属性。
        self.models = self.apps.all_models[self.label]

        if module_has_submodule(self.module, MODELS_MODULE_NAME):  #
            models_module_name = '%s.%s' % (self.name, MODELS_MODULE_NAME)
            self.models_module = import_module(models_module_name)

    def ready(self):
        """
        Override this method in subclasses to run code when Django starts.
        是为了给开发者在需要在启动项目时候做一些一次性的事情留了一个接口，
        只需要在apps.py中重写ready函数就可以了，而且确实会在启动过程中执行
        """

"""
到这里，django项目启动部分配置相关的源码就算是分析完了，感觉还是很有收获的。

首先，我们了解了django项目的入口程序其实就是manage.py通过对命令行参数进行解析，然后对不同的命令进行不同的处理。
针对runserver（django项目启动），其实最最关键的地方就在于django/__init__.py中的setup函数，在这里先设置了url解析的前缀，让开发者既可以自定义，也可以在开发过程中的urls.py中不用添加前置'/'，接下来就是对于所有app的相关配置。
app的相关配置有两个关键部分，一个是对单个app的配置类AppConfig，一个是对所有app的管理类Apps，这两个类紧密相关，是总分关系，同时相互索引。在初始化过程中，Apps在控制流程，主要包括对所有app进行路径解析、名字去重、对每个app配置类进行初始化、赋予每个app配置类它们的相关models、还有就是执行每个app开发者自己定义的ready函数。
所以，看完源码，结合开发经验，我认为要想成功启动项目，最重要的就是把settings里面的installed_app变量写对，而且添加app之后记得把相对的路径加到配置文件中。同时，apps.py下的ready函数可以给我们一个不错的做启动的初始化的钩子，这个要记住并好好利用。

https://zhuanlan.zhihu.com/p/94679262
"""

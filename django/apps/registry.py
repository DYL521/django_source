import functools
import sys
import threading
import warnings
from collections import Counter, OrderedDict, defaultdict
from functools import partial

from django.core.exceptions import AppRegistryNotReady, ImproperlyConfigured

from .config import AppConfig


class Apps:
    """
    A registry that stores the configuration of installed applications.
    注册并且存储app信息
    It also keeps track of models, e.g. to provide reverse relations.
    他也会跟踪模型
    """

    def __init__(self, installed_apps=()):
        # installed_apps is set to None when creating the master registry
        # 创建主注册表时，已安装的app设置为None
        # because it cannot be populated at that point. Other registries must
        # 因为他在那个时候不能填入，其他注册必须
        # provide a list of installed apps and are populated immediately.
        # 提供已经安装的app列表，并且立即填充
        if installed_apps is None and hasattr(sys.modules[__name__], 'apps'):
            raise RuntimeError("You must supply an installed_apps argument.")

        # Mapping of app labels => model names => model classes. Every time a
        #         # model is imported, ModelBase.__new__ calls apps.register_model which
        #         # creates an entry in all_models. All imported models are registered,
        #         # regardless of whether they're defined in an installed application
        #         # and whether the registry has been populated. Since it isn't possible
        #         # to reimport a module safely (it could reexecute initialization code)
        #         # all_models is never overridden or reset.
        """
        应用标映射 => 模型名称 => 模型类，每一次
        模型被导入，ModelBase.__new__ 调用 apps.register_model在all_models创建
        无论是否在已安装的应用程序中定义它们
        以及是否已填充注册表。既然不可能
        安全地重新导入模块（它可以重新执行初始化代码）
        all_models永远不会被覆盖或重置。
        """
        self.all_models = defaultdict(OrderedDict)

        # Mapping of labels to AppConfig instances for installed apps.
        # 将标签映射到已安装应用程序的AppConfig实例
        self.app_configs = OrderedDict()

        # Stack of app_configs. Used to store the current state in
        # set_available_apps and set_installed_apps.
        # 堆栈的app_configs。用于将当前状态存储在set_available_apps和set_installed_apps中
        self.stored_app_configs = []

        # Whether the registry is populated.
        # 是否填充了注册表
        self.apps_ready = self.models_ready = self.ready = False

        # Lock for thread-safe population.
        self._lock = threading.RLock()  # 线程安全锁！
        self.loading = False

        # Maps ("app_label", "modelname") tuples to lists of functions to be
        # called when the corresponding model is ready. Used by this class's
        # `lazy_model_operation()` and `do_pending_operations()` methods.
        self._pending_operations = defaultdict(list)

        # Populate apps and models, unless it's the master registry.
        if installed_apps is not None:
            self.populate(installed_apps)

    def populate(self, installed_apps=None):
        """
        Load application configurations and models.

        Import each application module and then each model module.

        It is thread-safe and idempotent, but not reentrant.

        1 - 加载应用程序配置和模型。
        2 - 导入每个应用程序模块，然后导入每个模型模块。
        3 - 它是线程安全和等幂的，但不可重入。 调用加载完成的ready事件！（check检查）
        """
        if self.ready:  # Flase
            return

        # populate() might be called by two threads in parallel on servers
        # that create threads before initializing the WSGI callable.
        # 服务器上的两个线程可以并行调用populate（）。
        # 在初始化wsgi可调用文件之前创建线程。
        with self._lock:
            if self.ready:
                return
            # 这里因为self._lock用的是可重入锁，所以同一个线程是可以在配置过程中多次进入
            # An RLock prevents other threads from entering this section. The
            # compare and set operation below is atomic.
            if self.loading:
                # Prevent reentrant calls to avoid running AppConfig.ready()
                # methods twice.
                raise RuntimeError("populate() isn't reentrant")
            self.loading = True

            # Phase 1: initialize app configs and import app modules.
            # 阶段1：初始化应用程序配置并导入应用程序模块 - installed_apps是设置文件的installed_app列表
            # import pdb; pdb.set_trace()
            for entry in installed_apps:
                if isinstance(entry, AppConfig):  # 如果配置apps配置文件写的AppConfig的实例
                    app_config = entry
                else:  # 否则应该是字符串！！
                    app_config = AppConfig.create(entry)  # 创建配置
                # 配置完成之后，检查是否有重复的app配置实例lable
                if app_config.label in self.app_configs:
                    raise ImproperlyConfigured(
                        "Application labels aren't unique, "
                        "duplicates: %s" % app_config.label)
                # 把每一个app的配置实例都添加到self.app_configs中
                self.app_configs[app_config.label] = app_config
                app_config.apps = self  # self 就是下面全局的模块级变量 - 当前对象赋值到各个app的实例中

            """
            面试题：
                一个字符串各个字符出现的频率，并且排序？
            """

            # Check for duplicate app names.
            # 检查重复的app名称，确保对象的名字不会重复
            counts = Counter(
                app_config.name for app_config in self.app_configs.values())  # odict_values([])
            duplicates = [
                name for name, count in counts.most_common() if count > 1]  # []
            if duplicates:
                raise ImproperlyConfigured(
                    "Application names aren't unique, "
                    "duplicates: %s" % ", ".join(duplicates))

            self.apps_ready = True

            # Phase 2: import models modules.
            # 阶段2：导入模型模块
            import pdb;
            pdb.set_trace()  # 加载model
            for app_config in self.app_configs.values():
                app_config.import_models()

                # 执行完，app_config就有model这个模块了
            self.clear_cache()

            self.models_ready = True

            # Phase 3: run ready() methods of app configs.
            # 阶段3：运行app配置的ready（）方法
            import pdb;
            pdb.set_trace()  # ready
            for app_config in self.get_app_configs():  # odict_values([])
                # AppConfig.ready() 这例可以做一些我们想要的事情，在项目启动的时候!!
                app_config.ready()  # contrib/admin/apps.py

            self.ready = True

    def check_apps_ready(self):
        """Raise an exception if all apps haven't been imported yet."""
        """如果尚未导入所有应用程序，则引发异常"""
        if not self.apps_ready:
            raise AppRegistryNotReady("Apps aren't loaded yet.")

    def check_models_ready(self):
        """Raise an exception if all models haven't been imported yet."""
        if not self.models_ready:
            raise AppRegistryNotReady("Models aren't loaded yet.")

    def get_app_configs(self):
        """Import applications and return an iterable of app configs."""
        """ 导入应用程序并且返回可迭代 的app配置"""
        self.check_apps_ready()  # 检查app
        return self.app_configs.values()

    def get_app_config(self, app_label):
        """
        Import applications and returns an app config for the given label.

        Raise LookupError if no application exists with this label.
        """
        self.check_apps_ready()
        try:
            return self.app_configs[app_label]
        except KeyError:
            message = "No installed app with label '%s'." % app_label
            for app_config in self.get_app_configs():
                if app_config.name == app_label:
                    message += " Did you mean '%s'?" % app_config.label
                    break
            raise LookupError(message)

    # This method is performance-critical at least for Django's test suite.
    @functools.lru_cache(maxsize=None)
    def get_models(self, include_auto_created=False, include_swapped=False):
        """
        Return a list of all installed models.

        By default, the following models aren't included:

        - auto-created models for many-to-many relations without
          an explicit intermediate table,
        - models that have been swapped out.

        Set the corresponding keyword argument to True to include such models.
        """
        self.check_models_ready()

        result = []
        for app_config in self.app_configs.values():
            result.extend(list(app_config.get_models(include_auto_created, include_swapped)))
        return result

    def get_model(self, app_label, model_name=None, require_ready=True):
        """
        Return the model matching the given app_label and model_name.

        As a shortcut, app_label may be in the form <app_label>.<model_name>.

        model_name is case-insensitive.

        Raise LookupError if no application exists with this label, or no
        model exists with this name in the application. Raise ValueError if
        called with a single argument that doesn't contain exactly one dot.
        """
        if require_ready:
            self.check_models_ready()
        else:
            self.check_apps_ready()

        if model_name is None:
            app_label, model_name = app_label.split('.')

        app_config = self.get_app_config(app_label)

        if not require_ready and app_config.models is None:
            app_config.import_models()

        return app_config.get_model(model_name, require_ready=require_ready)

    def register_model(self, app_label, model):
        # Since this method is called when models are imported, it cannot
        # perform imports because of the risk of import loops. It mustn't
        # call get_app_config().
        model_name = model._meta.model_name
        app_models = self.all_models[app_label]
        if model_name in app_models:
            if (model.__name__ == app_models[model_name].__name__ and
                model.__module__ == app_models[model_name].__module__):
                warnings.warn(
                    "Model '%s.%s' was already registered. "
                    "Reloading models is not advised as it can lead to inconsistencies, "
                    "most notably with related models." % (app_label, model_name),
                    RuntimeWarning, stacklevel=2)
            else:
                raise RuntimeError(
                    "Conflicting '%s' models in application '%s': %s and %s." %
                    (model_name, app_label, app_models[model_name], model))
        app_models[model_name] = model
        self.do_pending_operations(model)
        self.clear_cache()

    def is_installed(self, app_name):
        """
        Check whether an application with this name exists in the registry.

        app_name is the full name of the app e.g. 'django.contrib.admin'.
        """
        self.check_apps_ready()
        return any(ac.name == app_name for ac in self.app_configs.values())

    def get_containing_app_config(self, object_name):
        """
        Look for an app config containing a given object.

        object_name is the dotted Python path to the object.

        Return the app config for the inner application in case of nesting.
        Return None if the object isn't in any registered app config.
        """
        self.check_apps_ready()
        candidates = []
        for app_config in self.app_configs.values():
            if object_name.startswith(app_config.name):
                subpath = object_name[len(app_config.name):]
                if subpath == '' or subpath[0] == '.':
                    candidates.append(app_config)
        if candidates:
            return sorted(candidates, key=lambda ac: -len(ac.name))[0]

    def get_registered_model(self, app_label, model_name):
        """
        Similar to get_model(), but doesn't require that an app exists with
        the given app_label.

        It's safe to call this method at import time, even while the registry
        is being populated.
        """
        model = self.all_models[app_label].get(model_name.lower())
        if model is None:
            raise LookupError(
                "Model '%s.%s' not registered." % (app_label, model_name))
        return model

    @functools.lru_cache(maxsize=None)
    def get_swappable_settings_name(self, to_string):
        """
        For a given model string (e.g. "auth.User"), return the name of the
        corresponding settings name if it refers to a swappable model. If the
        referred model is not swappable, return None.

        This method is decorated with lru_cache because it's performance
        critical when it comes to migrations. Since the swappable settings don't
        change after Django has loaded the settings, there is no reason to get
        the respective settings attribute over and over again.
        """
        for model in self.get_models(include_swapped=True):
            swapped = model._meta.swapped
            # Is this model swapped out for the model given by to_string?
            if swapped and swapped == to_string:
                return model._meta.swappable
            # Is this model swappable and the one given by to_string?
            if model._meta.swappable and model._meta.label == to_string:
                return model._meta.swappable
        return None

    def set_available_apps(self, available):
        """
        Restrict the set of installed apps used by get_app_config[s].

        available must be an iterable of application names.

        set_available_apps() must be balanced with unset_available_apps().

        Primarily used for performance optimization in TransactionTestCase.

        This method is safe in the sense that it doesn't trigger any imports.
        """
        available = set(available)
        installed = {app_config.name for app_config in self.get_app_configs()}
        if not available.issubset(installed):
            raise ValueError(
                "Available apps isn't a subset of installed apps, extra apps: %s"
                % ", ".join(available - installed)
            )

        self.stored_app_configs.append(self.app_configs)
        self.app_configs = OrderedDict(
            (label, app_config)
            for label, app_config in self.app_configs.items()
            if app_config.name in available)
        self.clear_cache()

    def unset_available_apps(self):
        """Cancel a previous call to set_available_apps()."""
        self.app_configs = self.stored_app_configs.pop()
        self.clear_cache()

    def set_installed_apps(self, installed):
        """
        Enable a different set of installed apps for get_app_config[s].

        installed must be an iterable in the same format as INSTALLED_APPS.

        set_installed_apps() must be balanced with unset_installed_apps(),
        even if it exits with an exception.

        Primarily used as a receiver of the setting_changed signal in tests.

        This method may trigger new imports, which may add new models to the
        registry of all imported models. They will stay in the registry even
        after unset_installed_apps(). Since it isn't possible to replay
        imports safely (e.g. that could lead to registering listeners twice),
        models are registered when they're imported and never removed.
        """
        if not self.ready:
            raise AppRegistryNotReady("App registry isn't ready yet.")
        self.stored_app_configs.append(self.app_configs)
        self.app_configs = OrderedDict()
        self.apps_ready = self.models_ready = self.loading = self.ready = False
        self.clear_cache()
        self.populate(installed)

    def unset_installed_apps(self):
        """Cancel a previous call to set_installed_apps()."""
        self.app_configs = self.stored_app_configs.pop()
        self.apps_ready = self.models_ready = self.ready = True
        self.clear_cache()

    def clear_cache(self):
        """
        Clear all internal caches, for methods that alter the app registry.
        清除所有内部缓存，用于更改app注册表的方法
        This is mostly used in tests.
        """
        # Call expire cache on each model. This will purge
        # the relation tree and the fields cache.
        self.get_models.cache_clear()
        if self.ready:
            # Circumvent self.get_models() to prevent that the cache is refilled.
            # This particularly prevents that an empty value is cached while cloning.
            for app_config in self.app_configs.values():
                for model in app_config.get_models(include_auto_created=True):
                    model._meta._expire_cache()

    def lazy_model_operation(self, function, *model_keys):
        """
        Take a function and a number of ("app_label", "modelname") tuples, and
        when all the corresponding models have been imported and registered,
        call the function with the model classes as its arguments.

        The function passed to this method must accept exactly n models as
        arguments, where n=len(model_keys).
        """
        # Base case: no arguments, just execute the function.
        if not model_keys:
            function()
        # Recursive case: take the head of model_keys, wait for the
        # corresponding model class to be imported and registered, then apply
        # that argument to the supplied function. Pass the resulting partial
        # to lazy_model_operation() along with the remaining model args and
        # repeat until all models are loaded and all arguments are applied.
        else:
            next_model, more_models = model_keys[0], model_keys[1:]

            # This will be executed after the class corresponding to next_model
            # has been imported and registered. The `func` attribute provides
            # duck-type compatibility with partials.
            def apply_next_model(model):
                next_function = partial(apply_next_model.func, model)
                self.lazy_model_operation(next_function, *more_models)

            apply_next_model.func = function

            # If the model has already been imported and registered, partially
            # apply it to the function now. If not, add it to the list of
            # pending operations for the model, where it will be executed with
            # the model class as its sole argument once the model is ready.
            try:
                model_class = self.get_registered_model(*next_model)
            except LookupError:
                self._pending_operations[next_model].append(apply_next_model)
            else:
                apply_next_model(model_class)

    def do_pending_operations(self, model):
        """
        Take a newly-prepared model and pass it to each function waiting for
        it. This is called at the very end of Apps.register_model().
        """
        key = model._meta.app_label, model._meta.model_name
        for function in self._pending_operations.pop(key, []):
            function(model)


apps = Apps(installed_apps=None)

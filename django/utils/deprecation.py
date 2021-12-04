import inspect
import warnings
import logging

logger = logging.getLogger(__name__)


class RemovedInDjango30Warning(PendingDeprecationWarning):
    pass


class RemovedInDjango21Warning(DeprecationWarning):
    pass


RemovedInNextVersionWarning = RemovedInDjango21Warning


class warn_about_renamed_method:
    def __init__(self, class_name, old_method_name, new_method_name, deprecation_warning):
        self.class_name = class_name
        self.old_method_name = old_method_name
        self.new_method_name = new_method_name
        self.deprecation_warning = deprecation_warning

    def __call__(self, f):
        def wrapped(*args, **kwargs):
            warnings.warn(
                "`%s.%s` is deprecated, use `%s` instead." %
                (self.class_name, self.old_method_name, self.new_method_name),
                self.deprecation_warning, 2)
            return f(*args, **kwargs)

        return wrapped


class RenameMethodsBase(type):
    """
    Handles the deprecation paths when renaming a method.

    It does the following:
        1) Define the new method if missing and complain about it.
        2) Define the old method if missing.
        3) Complain whenever an old method is called.

    See #15363 for more details.
    """

    renamed_methods = ()

    def __new__(cls, name, bases, attrs):
        new_class = super().__new__(cls, name, bases, attrs)

        for base in inspect.getmro(new_class):
            class_name = base.__name__
            for renamed_method in cls.renamed_methods:
                old_method_name = renamed_method[0]
                old_method = base.__dict__.get(old_method_name)
                new_method_name = renamed_method[1]
                new_method = base.__dict__.get(new_method_name)
                deprecation_warning = renamed_method[2]
                wrapper = warn_about_renamed_method(class_name, *renamed_method)

                # Define the new method if missing and complain about it
                if not new_method and old_method:
                    warnings.warn(
                        "`%s.%s` method should be renamed `%s`." %
                        (class_name, old_method_name, new_method_name),
                        deprecation_warning, 2)
                    setattr(base, new_method_name, old_method)
                    setattr(base, old_method_name, wrapper(old_method))

                # Define the old method as a wrapped call to the new method.
                if not old_method and new_method:
                    setattr(base, old_method_name, wrapper(new_method))

        return new_class


class DeprecationInstanceCheck(type):
    def __instancecheck__(self, instance):
        warnings.warn(
            "`%s` is deprecated, use `%s` instead." % (self.__name__, self.alternative),
            self.deprecation_warning, 2
        )
        return super().__instancecheck__(instance)


class MiddlewareMixin:
    """
        中间件的方法调用：继承它的子类并没有实现 __call__ 方法
    """

    def __init__(self, get_response=None):
        self.get_response = get_response
        super().__init__()

    def __call__(self, request):
        """
            只要调用中间件都转入到类这里
            HttpRequest -> Middleware -> View -> Middleware -> HttpResponse
        """
        logger.info("<============开始执行中间件=================>")
        response = None
        # 1、执行视图前
        if hasattr(self, 'process_request'):
            response = self.process_request(request)
        # 2、执行视图: 它将调用列表中的下一个中间件。如果这是最后一个中间件，则将调用该视图
        if not response:
            response = self.get_response(request)
        # 3、执行视图后
        if hasattr(self, 'process_response'):
            response = self.process_response(request, response)
        logger.info("<============执行中间件结束=================>")
        return response

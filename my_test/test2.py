def add_argument(self, *args, **kwargs):
    """
    add_argument(dest, ..., name=value, ...)
    add_argument(option_string, option_string, ..., name=value, ...)
    """

    # if no positional args are supplied or only one is supplied and
    # it doesn't look like an option string, parse a positional
    # argument
    chars = "_"  # __settings
    print(args)
    print(type(args))  # tuple
    print(len(args))

    if not args or len(args) == 1 and args[0][0] not in chars:
        print('=====')

    # otherwise, we're adding an optional argument
    else:
        pass


from threading import local

_prefixes = local()


def set_script_prefix(prefix):
    """
    Set the script prefix for the current thread.

    设置当前脚本的前缀
    """
    if not prefix.endswith('/'):
        prefix += '/'
    _prefixes.value = prefix


if __name__ == '__main__':
    # add_argument("__settings")
    set_script_prefix("aaa")
    print(_prefixes.value)

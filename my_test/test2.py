def add_argument(self, *args, **kwargs):
    """
    add_argument(dest, ..., name=value, ...)
    add_argument(option_string, option_string, ..., name=value, ...)
    """

    # if no positional args are supplied or only one is supplied and
    # it doesn't look like an option string, parse a positional
    # argument
    chars = "_" # __settings
    print(args)
    if not args or len(args) == 1 and args[0][0] not in chars:
        pass

    # otherwise, we're adding an optional argument
    else:
        pass

if __name__ == '__main__':
    add_argument("__settings")



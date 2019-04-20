from django.core.management.templates import TemplateCommand

from ..utils import get_random_secret_key


class Command(TemplateCommand):
    help = (
        "Creates a Django project directory structure for the given project "
        "name in the current directory or optionally in the given directory."
    )
    missing_args_message = "You must provide a project name."

    def handle(self, **options):
        '''
         无论前面做了啥，这个就是django command 的入口，都会到这里来
        :param options:
        :return:
        '''
        project_name = options.pop('name')
        target = options.pop('directory') # 弹出directory， 所以target = None

        # Create a random SECRET_KEY to put it in the main settings.
        options['secret_key'] = get_random_secret_key() # 生成一个secret_key

        super().handle('project', project_name, target, **options) # 再执行父类的handle

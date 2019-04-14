import re
import threading
import unittest

from django.core.exceptions import ImproperlyConfigured
from django.db import connection, transaction
from django.db.models import Avg, StdDev, Sum, Variance
from django.db.models.fields import CharField
from django.db.utils import NotSupportedError
from django.test import (
    TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature,
)
from django.test.utils import isolate_apps

from ..models import Author, Item, Object, Square


@unittest.skipUnless(connection.vendor == 'sqlite', 'SQLite tests')
class Tests(TestCase):
    longMessage = True

    def test_aggregation(self):
        """
        Raise NotImplementedError when aggregating on date/time fields (#19360).
        """
        for aggregate in (Sum, Avg, Variance, StdDev):
            with self.assertRaises(NotImplementedError):
                Item.objects.all().aggregate(aggregate('time'))
            with self.assertRaises(NotImplementedError):
                Item.objects.all().aggregate(aggregate('date'))
            with self.assertRaises(NotImplementedError):
                Item.objects.all().aggregate(aggregate('last_modified'))
            with self.assertRaises(NotImplementedError):
                Item.objects.all().aggregate(
                    **{'complex': aggregate('last_modified') + aggregate('last_modified')}
                )

    def test_memory_db_test_name(self):
        """A named in-memory db should be allowed where supported."""
        from django.db.backends.sqlite3.base import DatabaseWrapper
        settings_dict = {
            'TEST': {
                'NAME': 'file:memorydb_test?mode=memory&cache=shared',
            }
        }
        wrapper = DatabaseWrapper(settings_dict)
        creation = wrapper.creation
        if creation.connection.features.can_share_in_memory_db:
            expected = creation.connection.settings_dict['TEST']['NAME']
            self.assertEqual(creation._get_test_db_name(), expected)
        else:
            msg = (
                "Using a shared memory database with `mode=memory` in the "
                "database name is not supported in your environment, "
                "use `:memory:` instead."
            )
            with self.assertRaisesMessage(ImproperlyConfigured, msg):
                creation._get_test_db_name()


@unittest.skipUnless(connection.vendor == 'sqlite', 'SQLite tests')
@isolate_apps('backends')
class SchemaTests(TransactionTestCase):

    available_apps = ['backends']

    def test_autoincrement(self):
        """
        auto_increment fields are created with the AUTOINCREMENT keyword
        in order to be monotonically increasing (#10164).
        """
        with connection.schema_editor(collect_sql=True) as editor:
            editor.create_model(Square)
            statements = editor.collected_sql
        match = re.search('"id" ([^,]+),', statements[0])
        self.assertIsNotNone(match)
        self.assertEqual(
            'integer NOT NULL PRIMARY KEY AUTOINCREMENT',
            match.group(1),
            'Wrong SQL used to create an auto-increment column on SQLite'
        )

    def test_disable_constraint_checking_failure_disallowed(self):
        """
        SQLite schema editor is not usable within an outer transaction if
        foreign key constraint checks are not disabled beforehand.
        """
        msg = (
            'SQLite schema editor cannot be used while foreign key '
            'constraint checks are enabled. Make sure to disable them '
            'before entering a transaction.atomic() context because '
            'SQLite3 does not support disabling them in the middle of '
            'a multi-statement transaction.'
        )
        with self.assertRaisesMessage(NotSupportedError, msg):
            with transaction.atomic(), connection.schema_editor(atomic=True):
                pass

    def test_constraint_checks_disabled_atomic_allowed(self):
        """
        SQLite3 schema editor is usable within an outer transaction as long as
        foreign key constraints checks are disabled beforehand.
        """
        def constraint_checks_enabled():
            with connection.cursor() as cursor:
                return bool(cursor.execute('PRAGMA foreign_keys').fetchone()[0])
        with connection.constraint_checks_disabled(), transaction.atomic():
            with connection.schema_editor(atomic=True):
                self.assertFalse(constraint_checks_enabled())
            self.assertFalse(constraint_checks_enabled())
        self.assertTrue(constraint_checks_enabled())

    def test_field_rename_inside_atomic_block(self):
        """
        NotImplementedError is raised when a model field rename is attempted
        inside an atomic block.
        """
        new_field = CharField(max_length=255, unique=True)
        new_field.set_attributes_from_name('renamed')
        msg = (
            "Renaming the 'backends_author'.'name' column while in a "
            "transaction is not supported on SQLite because it would break "
            "referential integrity. Try adding `atomic = False` to the "
            "Migration class."
        )
        with self.assertRaisesMessage(NotSupportedError, msg):
            with connection.schema_editor(atomic=True) as editor:
                editor.alter_field(Author, Author._meta.get_field('name'), new_field)

    def test_table_rename_inside_atomic_block(self):
        """
        NotImplementedError is raised when a table rename is attempted inside
        an atomic block.
        """
        msg = (
            "Renaming the 'backends_author' table while in a transaction is "
            "not supported on SQLite because it would break referential "
            "integrity. Try adding `atomic = False` to the Migration class."
        )
        with self.assertRaisesMessage(NotSupportedError, msg):
            with connection.schema_editor(atomic=True) as editor:
                editor.alter_db_table(Author, "backends_author", "renamed_table")


@unittest.skipUnless(connection.vendor == 'sqlite', 'Test only for SQLite')
@override_settings(DEBUG=True)
class LastExecutedQueryTest(TestCase):

    def test_no_interpolation(self):
        # This shouldn't raise an exception (#17158)
        query = "SELECT strftime('%Y', 'now');"
        connection.cursor().execute(query)
        self.assertEqual(connection.queries[-1]['sql'], query)

    def test_parameter_quoting(self):
        # The implementation of last_executed_queries isn't optimal. It's
        # worth testing that parameters are quoted (#14091).
        query = "SELECT %s"
        params = ["\"'\\"]
        connection.cursor().execute(query, params)
        # Note that the single quote is repeated
        substituted = "SELECT '\"''\\'"
        self.assertEqual(connection.queries[-1]['sql'], substituted)

    def test_large_number_of_parameters(self):
        # If SQLITE_MAX_VARIABLE_NUMBER (default = 999) has been changed to be
        # greater than SQLITE_MAX_COLUMN (default = 2000), last_executed_query
        # can hit the SQLITE_MAX_COLUMN limit (#26063).
        cursor = connection.cursor()
        sql = "SELECT MAX(%s)" % ", ".join(["%s"] * 2001)
        params = list(range(2001))
        # This should not raise an exception.
        cursor.db.ops.last_executed_query(cursor.cursor, sql, params)


@unittest.skipUnless(connection.vendor == 'sqlite', 'SQLite tests')
class EscapingChecks(TestCase):
    """
    All tests in this test case are also run with settings.DEBUG=True in
    EscapingChecksDebug test case, to also test CursorDebugWrapper.
    """
    def test_parameter_escaping(self):
        # '%s' escaping support for sqlite3 (#13648).
        cursor = connection.cursor()
        cursor.execute("select strftime('%s', date('now'))")
        response = cursor.fetchall()[0][0]
        # response should be an non-zero integer
        self.assertTrue(int(response))


@unittest.skipUnless(connection.vendor == 'sqlite', 'SQLite tests')
@override_settings(DEBUG=True)
class EscapingChecksDebug(EscapingChecks):
    pass


@unittest.skipUnless(connection.vendor == 'sqlite', 'SQLite tests')
@skipUnlessDBFeature('can_share_in_memory_db')
class ThreadSharing(TransactionTestCase):
    available_apps = ['backends']

    def test_database_sharing_in_threads(self):
        def create_object():
            Object.objects.create()
        create_object()
        thread = threading.Thread(target=create_object)
        thread.start()
        thread.join()
        self.assertEqual(Object.objects.count(), 2)

from __future__ import unicode_literals

from datetime import date
import traceback
import warnings

from django.db import IntegrityError, DatabaseError
from django.utils.encoding import DjangoUnicodeDecodeError
from django.test import TestCase, TransactionTestCase

from .models import (DefaultPerson, Person, ManualPrimaryKeyTest, Profile,
    Tag, Thing, Publisher, Author)


class GetOrCreateTests(TestCase):

    def setUp(self):
        self.lennon = Person.objects.create(
            first_name='John', last_name='Lennon', birthday=date(1940, 10, 9)
        )

    def test_get_or_create_method_with_get(self):
        created = Person.objects.get_or_create(
            first_name="John", last_name="Lennon", defaults={
                "birthday": date(1940, 10, 9)
            }
        )[1]
        self.assertFalse(created)
        self.assertEqual(Person.objects.count(), 1)

    def test_get_or_create_method_with_create(self):
        created = Person.objects.get_or_create(
            first_name='George', last_name='Harrison', defaults={
                'birthday': date(1943, 2, 25)
            }
        )[1]
        self.assertTrue(created)
        self.assertEqual(Person.objects.count(), 2)

    def test_get_or_create_redundant_instance(self):
        """
        If we execute the exact same statement twice, the second time,
        it won't create a Person.
        """
        Person.objects.get_or_create(
            first_name='George', last_name='Harrison', defaults={
                'birthday': date(1943, 2, 25)
            }
        )
        created = Person.objects.get_or_create(
            first_name='George', last_name='Harrison', defaults={
                'birthday': date(1943, 2, 25)
            }
        )[1]

        self.assertFalse(created)
        self.assertEqual(Person.objects.count(), 2)

    def test_get_or_create_invalid_params(self):
        """
        If you don't specify a value or default value for all required
        fields, you will get an error.
        """
        self.assertRaises(
            IntegrityError,
            Person.objects.get_or_create, first_name="Tom", last_name="Smith"
        )


class GetOrCreateTestsWithManualPKs(TestCase):

    def setUp(self):
        self.first_pk = ManualPrimaryKeyTest.objects.create(id=1, data="Original")

    def test_create_with_duplicate_primary_key(self):
        """
        If you specify an existing primary key, but different other fields,
        then you will get an error and data will not be updated.
        """
        self.assertRaises(
            IntegrityError,
            ManualPrimaryKeyTest.objects.get_or_create, id=1, data="Different"
        )
        self.assertEqual(ManualPrimaryKeyTest.objects.get(id=1).data, "Original")

    def test_get_or_create_raises_IntegrityError_plus_traceback(self):
        """
        get_or_create should raise IntegrityErrors with the full traceback.
        This is tested by checking that a known method call is in the traceback.
        We cannot use assertRaises here because we need to inspect
        the actual traceback. Refs #16340.
        """
        try:
            ManualPrimaryKeyTest.objects.get_or_create(id=1, data="Different")
        except IntegrityError:
            formatted_traceback = traceback.format_exc()
            self.assertIn(str('obj.save'), formatted_traceback)

    def test_savepoint_rollback(self):
        """
        Regression test for #20463: the database connection should still be
        usable after a DataError or ProgrammingError in .get_or_create().
        """
        try:
            # Hide warnings when broken data is saved with a warning (MySQL).
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                Person.objects.get_or_create(
                    birthday=date(1970, 1, 1),
                    defaults={'first_name': b"\xff", 'last_name': b"\xff"})
        except (DatabaseError, DjangoUnicodeDecodeError):
            Person.objects.create(
                first_name="Bob", last_name="Ross", birthday=date(1950, 1, 1))
        else:
            self.skipTest("This backend accepts broken utf-8.")

    def test_get_or_create_empty(self):
        """
        Regression test for #16137: get_or_create does not require kwargs.
        """
        try:
            DefaultPerson.objects.get_or_create()
        except AssertionError:
            self.fail("If all the attributes on a model have defaults, we "
                      "shouldn't need to pass any arguments.")


class GetOrCreateTransactionTests(TransactionTestCase):

    available_apps = ['get_or_create']

    def test_get_or_create_integrityerror(self):
        """
        Regression test for #15117. Requires a TransactionTestCase on
        databases that delay integrity checks until the end of transactions,
        otherwise the exception is never raised.
        """
        try:
            Profile.objects.get_or_create(person=Person(id=1))
        except IntegrityError:
            pass
        else:
            self.skipTest("This backend does not support integrity checks.")


class GetOrCreateThroughManyToMany(TestCase):

    def test_get_get_or_create(self):
        tag = Tag.objects.create(text='foo')
        a_thing = Thing.objects.create(name='a')
        a_thing.tags.add(tag)
        obj, created = a_thing.tags.get_or_create(text='foo')

        self.assertFalse(created)
        self.assertEqual(obj.pk, tag.pk)

    def test_create_get_or_create(self):
        a_thing = Thing.objects.create(name='a')
        obj, created = a_thing.tags.get_or_create(text='foo')

        self.assertTrue(created)
        self.assertEqual(obj.text, 'foo')
        self.assertIn(obj, a_thing.tags.all())

    def test_something(self):
        Tag.objects.create(text='foo')
        a_thing = Thing.objects.create(name='a')
        self.assertRaises(IntegrityError, a_thing.tags.get_or_create, text='foo')


class UpdateOrCreateTests(TestCase):

    def test_update(self):
        Person.objects.create(
            first_name='John', last_name='Lennon', birthday=date(1940, 10, 9)
        )
        p, created = Person.objects.update_or_create(
            first_name='John', last_name='Lennon', defaults={
                'birthday': date(1940, 10, 10)
            }
        )
        self.assertFalse(created)
        self.assertEqual(p.first_name, 'John')
        self.assertEqual(p.last_name, 'Lennon')
        self.assertEqual(p.birthday, date(1940, 10, 10))

    def test_create(self):
        p, created = Person.objects.update_or_create(
            first_name='John', last_name='Lennon', defaults={
                'birthday': date(1940, 10, 10)
            }
        )
        self.assertTrue(created)
        self.assertEqual(p.first_name, 'John')
        self.assertEqual(p.last_name, 'Lennon')
        self.assertEqual(p.birthday, date(1940, 10, 10))

    def test_create_twice(self):
        params = {
            'first_name': 'John',
            'last_name': 'Lennon',
            'birthday': date(1940, 10, 10),
        }
        Person.objects.update_or_create(**params)
        # If we execute the exact same statement, it won't create a Person.
        p, created = Person.objects.update_or_create(**params)
        self.assertFalse(created)

    def test_integrity(self):
        """
        If you don't specify a value or default value for all required
        fields, you will get an error.
        """
        self.assertRaises(IntegrityError,
            Person.objects.update_or_create, first_name="Tom", last_name="Smith")

    def test_manual_primary_key_test(self):
        """
        If you specify an existing primary key, but different other fields,
        then you will get an error and data will not be updated.
        """
        ManualPrimaryKeyTest.objects.create(id=1, data="Original")
        self.assertRaises(
            IntegrityError,
            ManualPrimaryKeyTest.objects.update_or_create, id=1, data="Different"
        )
        self.assertEqual(ManualPrimaryKeyTest.objects.get(id=1).data, "Original")

    def test_error_contains_full_traceback(self):
        """
        update_or_create should raise IntegrityErrors with the full traceback.
        This is tested by checking that a known method call is in the traceback.
        We cannot use assertRaises/assertRaises here because we need to inspect
        the actual traceback. Refs #16340.
        """
        try:
            ManualPrimaryKeyTest.objects.update_or_create(id=1, data="Different")
        except IntegrityError:
            formatted_traceback = traceback.format_exc()
            self.assertIn('obj.save', formatted_traceback)

    def test_related(self):
        p = Publisher.objects.create(name="Acme Publishing")
        # Create a book through the publisher.
        book, created = p.books.get_or_create(name="The Book of Ed & Fred")
        self.assertTrue(created)
        # The publisher should have one book.
        self.assertEqual(p.books.count(), 1)

        # Try get_or_create again, this time nothing should be created.
        book, created = p.books.get_or_create(name="The Book of Ed & Fred")
        self.assertFalse(created)
        # And the publisher should still have one book.
        self.assertEqual(p.books.count(), 1)

        # Add an author to the book.
        ed, created = book.authors.get_or_create(name="Ed")
        self.assertTrue(created)
        # The book should have one author.
        self.assertEqual(book.authors.count(), 1)

        # Try get_or_create again, this time nothing should be created.
        ed, created = book.authors.get_or_create(name="Ed")
        self.assertFalse(created)
        # And the book should still have one author.
        self.assertEqual(book.authors.count(), 1)

        # Add a second author to the book.
        fred, created = book.authors.get_or_create(name="Fred")
        self.assertTrue(created)

        # The book should have two authors now.
        self.assertEqual(book.authors.count(), 2)

        # Create an Author not tied to any books.
        Author.objects.create(name="Ted")

        # There should be three Authors in total. The book object should have two.
        self.assertEqual(Author.objects.count(), 3)
        self.assertEqual(book.authors.count(), 2)

        # Try creating a book through an author.
        _, created = ed.books.get_or_create(name="Ed's Recipes", publisher=p)
        self.assertTrue(created)

        # Now Ed has two Books, Fred just one.
        self.assertEqual(ed.books.count(), 2)
        self.assertEqual(fred.books.count(), 1)

        # Use the publisher's primary key value instead of a model instance.
        _, created = ed.books.get_or_create(name='The Great Book of Ed', publisher_id=p.id)
        self.assertTrue(created)

        # Try get_or_create again, this time nothing should be created.
        _, created = ed.books.get_or_create(name='The Great Book of Ed', publisher_id=p.id)
        self.assertFalse(created)

        # The publisher should have three books.
        self.assertEqual(p.books.count(), 3)

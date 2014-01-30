from __future__ import absolute_import, unicode_literals

from django.contrib.contenttypes.models import ContentType
from django.db import models, router
from django.db.utils import ConnectionRouter
from django.test import TestCase
from django.utils.functional import cached_property

from .models import Author, Article

class ContentTypesViewsTests(TestCase):
    fixtures = ['testdata.json']
    urls = 'contenttypes_tests.urls'

    def test_shortcut_with_absolute_url(self):
        "Can view a shortcut for an Author object that has a get_absolute_url method"
        for obj in Author.objects.all():
            short_url = '/shortcut/%s/%s/' % (ContentType.objects.get_for_model(Author).id, obj.pk)
            response = self.client.get(short_url)
            self.assertRedirects(response, 'http://testserver%s' % obj.get_absolute_url(),
                                 status_code=302, target_status_code=404)

    def test_shortcut_no_absolute_url(self):
        "Shortcuts for an object that has no get_absolute_url method raises 404"
        for obj in Article.objects.all():
            short_url = '/shortcut/%s/%s/' % (ContentType.objects.get_for_model(Article).id, obj.pk)
            response = self.client.get(short_url)
            self.assertEqual(response.status_code, 404)

    def test_wrong_type_pk(self):
        short_url = '/shortcut/%s/%s/' % (ContentType.objects.get_for_model(Author).id, 'nobody/expects')
        response = self.client.get(short_url)
        self.assertEqual(response.status_code, 404)

    def test_shortcut_bad_pk(self):
        short_url = '/shortcut/%s/%s/' % (ContentType.objects.get_for_model(Author).id, '42424242')
        response = self.client.get(short_url)
        self.assertEqual(response.status_code, 404)

    def test_nonint_content_type(self):
        an_author = Author.objects.all()[0]
        short_url = '/shortcut/%s/%s/' % ('spam', an_author.pk)
        response = self.client.get(short_url)
        self.assertEqual(response.status_code, 404)

    def test_bad_content_type(self):
        an_author = Author.objects.all()[0]
        short_url = '/shortcut/%s/%s/' % (42424242, an_author.pk)
        response = self.client.get(short_url)
        self.assertEqual(response.status_code, 404)

    def test_create_contenttype_on_the_spot(self):
        """
        Make sure ContentTypeManager.get_for_model creates the corresponding
        content type if it doesn't exist in the database (for some reason).
        """

        class ModelCreatedOnTheFly(models.Model):
            name = models.CharField()

            class Meta:
                verbose_name = 'a model created on the fly'
                app_label = 'my_great_app'

        ct = ContentType.objects.get_for_model(ModelCreatedOnTheFly)
        self.assertEqual(ct.app_label, 'my_great_app')
        self.assertEqual(ct.model, 'modelcreatedonthefly')
        self.assertEqual(ct.name, 'a model created on the fly')


class MasterSlaveRouter(object):
    def db_for_read(self, model, **hints):
        return 'other'

    def db_for_write(self, model, **hints):
        return 'default'


class ContentTypesMultidbTestCase(TestCase):

    def setUp(self):
        """
        We need to override the database routers; this is not possible with
        override_settings, because they are cached. The cache is not supposed
        to be overriden, hence the slightly complicated hack.
        """
        self.orig_routers = router._routers
        router._routers = ['contenttypes_tests.tests.MasterSlaveRouter']
        cached_property(ConnectionRouter.routers.func).__get__(router)

    def tearDown(self):
            router._routers = self.orig_routers
            cached_property(ConnectionRouter.routers.func).__get__(router)

    def test_multidb(self):
        """
        Test that, when using multiple databases, we use the db_for_read (see
        #20401).
        """
        ContentType.objects.clear_cache()
        with self.assertNumQueries(0, using='default'), \
                self.assertNumQueries(1, using='other'):
            ContentType.objects.get_for_model(Author)

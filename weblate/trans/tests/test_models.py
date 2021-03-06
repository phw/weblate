# -*- coding: utf-8 -*-
#
# Copyright © 2012 - 2015 Michal Čihař <michal@cihar.com>
#
# This file is part of Weblate <https://weblate.org/>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

"""
Tests for translation models.
"""

from django.test import TestCase
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import Permission, User
from django.core.exceptions import ValidationError
import shutil
import os
from weblate.trans.models import (
    Project, SubProject, Source, Unit, WhiteboardMessage, Check, Suggestion,
    get_related_units,
)
from weblate import appsettings
from weblate.trans.tests import OverrideSettings
from weblate.trans.tests.utils import get_test_file
from weblate.trans.vcs import GitRepository, HgRepository
from weblate.trans.search import clean_indexes

REPOWEB_URL = \
    'https://github.com/nijel/weblate-test/blob/master/%(file)s#L%(line)s'
GIT_URL = 'git://github.com/nijel/weblate-test.git'
HG_URL = 'https://nijel@bitbucket.org/nijel/weblate-test'


class RepoTestCase(TestCase):
    """
    Generic class for tests working with repositories.
    """
    def setUp(self):
        # Path where to clone remote repo for tests
        self.git_base_repo_path = os.path.join(
            settings.DATA_DIR,
            'test-base-repo.git'
        )
        # Repository on which tests will be performed
        self.git_repo_path = os.path.join(
            settings.DATA_DIR,
            'test-repo.git'
        )

        # Path where to clone remote repo for tests
        self.hg_base_repo_path = os.path.join(
            settings.DATA_DIR,
            'test-base-repo.hg'
        )
        # Repository on which tests will be performed
        self.hg_repo_path = os.path.join(
            settings.DATA_DIR,
            'test-repo.hg'
        )

        # Clone repo for testing
        if not os.path.exists(self.git_base_repo_path):
            print(
                'Cloning Git test repository to {0}...'.format(
                    self.git_base_repo_path
                )
            )
            GitRepository.clone(
                GIT_URL,
                self.git_base_repo_path,
                bare=True
            )

        # Remove possibly existing directory
        if os.path.exists(self.git_repo_path):
            shutil.rmtree(self.git_repo_path)

        # Create repository copy for the test
        shutil.copytree(self.git_base_repo_path, self.git_repo_path)

        # Clone repo for testing
        if not os.path.exists(self.hg_base_repo_path):
            print(
                'Cloning Mercurial test repository to {0}...'.format(
                    self.hg_base_repo_path
                )
            )
            HgRepository.clone(
                HG_URL,
                self.hg_base_repo_path,
                bare=True
            )

        # Remove possibly existing directory
        if os.path.exists(self.hg_repo_path):
            shutil.rmtree(self.hg_repo_path)

        # Create repository copy for the test
        shutil.copytree(self.hg_base_repo_path, self.hg_repo_path)

        # Remove possibly existing project directory
        test_repo_path = os.path.join(settings.DATA_DIR, 'vcs', 'test')
        if os.path.exists(test_repo_path):
            shutil.rmtree(test_repo_path)

        # Remove indexes
        clean_indexes()

    def create_project(self):
        """
        Creates test project.
        """
        project = Project.objects.create(
            name='Test',
            slug='test',
            web='https://weblate.org/'
        )
        self.addCleanup(shutil.rmtree, project.get_path(), True)
        return project

    def _create_subproject(self, file_format, mask, template='',
                           new_base='', vcs='git', **kwargs):
        """
        Creates real test subproject.
        """
        project = self.create_project()

        if vcs == 'mercurial':
            branch = 'default'
            repo = self.hg_repo_path
            push = self.hg_repo_path
        else:
            branch = 'master'
            repo = self.git_repo_path
            push = self.git_repo_path

        return SubProject.objects.create(
            name='Test',
            slug='test',
            project=project,
            repo=repo,
            push=push,
            branch=branch,
            filemask=mask,
            template=template,
            file_format=file_format,
            repoweb=REPOWEB_URL,
            save_history=True,
            new_base=new_base,
            vcs=vcs,
            **kwargs
        )

    def create_subproject(self):
        """
        Wrapper method for providing test subproject.
        """
        return self._create_subproject(
            'auto',
            'po/*.po',
        )

    def create_po(self):
        return self._create_subproject(
            'po',
            'po/*.po',
        )

    def create_po_empty(self):
        return self._create_subproject(
            'po',
            'po-empty/*.po',
            new_base='po-empty/hello.pot',
            new_lang='add',
        )

    def create_po_mercurial(self):
        return self._create_subproject(
            'po',
            'po/*.po',
            vcs='mercurial'
        )

    def create_po_new_base(self):
        return self._create_subproject(
            'po',
            'po/*.po',
            new_base='po/hello.pot'
        )

    def create_po_link(self):
        return self._create_subproject(
            'po',
            'po-link/*.po',
        )

    def create_po_mono(self):
        return self._create_subproject(
            'po-mono',
            'po-mono/*.po',
            'po-mono/en.po',
        )

    def create_ts(self, suffix=''):
        return self._create_subproject(
            'ts',
            'ts{0}/*.ts'.format(suffix),
        )

    def create_ts_mono(self):
        return self._create_subproject(
            'ts',
            'ts-mono/*.ts',
            'ts-mono/en.ts',
        )

    def create_iphone(self):
        return self._create_subproject(
            'strings',
            'iphone/*.lproj/Localizable.strings',
        )

    def create_android(self):
        return self._create_subproject(
            'aresource',
            'android/values-*/strings.xml',
            'android/values/strings.xml',
        )

    def create_json(self):
        return self._create_subproject(
            'json',
            'json/*.json',
        )

    def create_json_mono(self):
        return self._create_subproject(
            'json',
            'json-mono/*.json',
            'json-mono/en.json',
        )

    def create_csv(self):
        return self._create_subproject(
            'csv',
            'csv/*.txt',
        )

    def create_csv_mono(self):
        return self._create_subproject(
            'csv',
            'csv-mono/*.csv',
            'csv-mono/en.csv',
        )

    def create_java(self):
        return self._create_subproject(
            'properties',
            'java/swing_messages_*.properties',
            'java/swing_messages.properties',
        )

    def create_xliff(self, name='default'):
        return self._create_subproject(
            'xliff',
            'xliff/*/%s.xlf' % name,
        )

    def create_xliff_mono(self):
        return self._create_subproject(
            'xliff',
            'xliff-mono/*.xlf',
            'xliff-mono/en.xlf',
        )

    def create_link(self):
        parent = self.create_iphone()
        return SubProject.objects.create(
            name='Test2',
            slug='test2',
            project=parent.project,
            repo='weblate://test/test',
            file_format='po',
            filemask='po/*.po',
        )


class ProjectTest(RepoTestCase):
    """
    Project object testing.
    """

    def test_create(self):
        project = self.create_project()
        self.assertTrue(os.path.exists(project.get_path()))
        self.assertTrue(project.slug in project.get_path())

    def test_rename(self):
        project = self.create_project()
        old_path = project.get_path()
        self.assertTrue(os.path.exists(old_path))
        project.slug = 'changed'
        project.save()
        new_path = project.get_path()
        self.addCleanup(shutil.rmtree, new_path, True)
        self.assertFalse(os.path.exists(old_path))
        self.assertTrue(os.path.exists(new_path))

    def test_delete(self):
        project = self.create_project()
        self.assertTrue(os.path.exists(project.get_path()))
        project.delete()
        self.assertFalse(os.path.exists(project.get_path()))

    def test_delete_all(self):
        project = self.create_project()
        self.assertTrue(os.path.exists(project.get_path()))
        Project.objects.all().delete()
        self.assertFalse(os.path.exists(project.get_path()))

    def test_wrong_path(self):
        project = self.create_project()

        with OverrideSettings(DATA_DIR='/weblate-nonexisting-path'):
            # Invalidate cache, pylint: disable=W0212
            project._dir_path = None

            self.assertRaisesMessage(
                ValidationError,
                'Could not create project directory',
                project.full_clean
            )

    def test_acl(self):
        """
        Test for ACL handling.
        """
        # Create user to verify ACL
        user = User.objects.create_user(
            username='testuser',
            password='testpassword'
        )

        # Create project
        project = self.create_project()

        # Enable ACL
        project.enable_acl = True
        project.save()

        # Check user does not have access
        self.assertFalse(project.has_acl(user))

        # Add ACL
        permission = Permission.objects.get(codename='weblate_acl_test')
        user.user_permissions.add(permission)

        # Need to fetch user again to clear permission cache
        user = User.objects.get(username='testuser')

        # We now should have access
        self.assertTrue(project.has_acl(user))


class SubProjectTest(RepoTestCase):
    """
    SubProject object testing.
    """
    def verify_subproject(self, project, translations, lang=None, units=0,
                          unit='Hello, world!\n', fail=False):
        # Validation
        if fail:
            self.assertRaises(
                ValidationError,
                project.full_clean
            )
        else:
            project.full_clean()
        # Correct path
        self.assertTrue(os.path.exists(project.get_path()))
        # Count translations
        self.assertEqual(
            project.translation_set.count(), translations
        )
        if lang is not None:
            # Grab translation
            translation = project.translation_set.get(language_code=lang)
            # Count units in it
            self.assertEqual(translation.unit_set.count(), units)
            # Check whether unit exists
            self.assertTrue(translation.unit_set.filter(source=unit).exists())

    def test_create(self):
        project = self.create_subproject()
        self.verify_subproject(project, 3, 'cs', 4)
        self.assertTrue(os.path.exists(project.get_path()))

    def test_create_dot(self):
        project = self._create_subproject(
            'auto',
            './po/*.po',
        )
        self.verify_subproject(project, 3, 'cs', 4)
        self.assertTrue(os.path.exists(project.get_path()))
        self.assertEqual('po/*.po', project.filemask)

    def test_rename(self):
        subproject = self.create_subproject()
        old_path = subproject.get_path()
        self.assertTrue(os.path.exists(old_path))
        subproject.slug = 'changed'
        subproject.save()
        self.assertFalse(os.path.exists(old_path))
        self.assertTrue(os.path.exists(subproject.get_path()))

    def test_delete(self):
        project = self.create_subproject()
        self.assertTrue(os.path.exists(project.get_path()))
        project.delete()
        self.assertFalse(os.path.exists(project.get_path()))

    def test_delete_link(self):
        project = self.create_link()
        main_project = SubProject.objects.get(slug='test')
        self.assertTrue(os.path.exists(main_project.get_path()))
        project.delete()
        self.assertTrue(os.path.exists(main_project.get_path()))

    def test_delete_all(self):
        project = self.create_subproject()
        self.assertTrue(os.path.exists(project.get_path()))
        SubProject.objects.all().delete()
        self.assertFalse(os.path.exists(project.get_path()))

    def test_create_iphone(self):
        project = self.create_iphone()
        self.verify_subproject(project, 1, 'cs', 4)

    def test_create_ts(self):
        project = self.create_ts('-translated')
        self.verify_subproject(project, 1, 'cs', 4)

        unit = Unit.objects.get(source__startswith='Orangutan')
        self.assertTrue(unit.is_plural())
        self.assertFalse(unit.translated)
        self.assertFalse(unit.fuzzy)

        unit = Unit.objects.get(source__startswith='Hello')
        self.assertFalse(unit.is_plural())
        self.assertTrue(unit.translated)
        self.assertFalse(unit.fuzzy)
        self.assertEqual(unit.target, 'Hello, world!\n')

        unit = Unit.objects.get(source__startswith='Thank ')
        self.assertFalse(unit.is_plural())
        self.assertFalse(unit.translated)
        self.assertTrue(unit.fuzzy)
        self.assertEqual(unit.target, 'Thanks')

    def test_create_ts_mono(self):
        project = self.create_ts_mono()
        self.verify_subproject(project, 2, 'cs', 4)

    def test_create_po_pot(self):
        project = self._create_subproject(
            'po',
            'po/*.po',
            'po/project.pot'
        )
        self.verify_subproject(project, 3, 'cs', 4, fail=True)

    def test_create_filtered(self):
        project = self._create_subproject(
            'po',
            'po/*.po',
            language_regex='^cs$',
        )
        self.verify_subproject(project, 1, 'cs', 4)

    def test_create_auto_pot(self):
        project = self._create_subproject(
            'auto',
            'po/*.po',
            'po/project.pot'
        )
        self.verify_subproject(project, 3, 'cs', 4, fail=True)

    def test_create_po(self):
        project = self.create_po()
        self.verify_subproject(project, 3, 'cs', 4)

    def test_create_po_mercurial(self):
        project = self.create_po_mercurial()
        self.verify_subproject(project, 3, 'cs', 4)

    def test_create_po_empty(self):
        project = self.create_po_empty()
        self.verify_subproject(project, 0)

    def test_create_po_link(self):
        project = self.create_po_link()
        self.verify_subproject(project, 4, 'cs', 4)

    def test_create_po_mono(self):
        project = self.create_po_mono()
        self.verify_subproject(project, 4, 'cs', 4)

    def test_create_android(self):
        project = self.create_android()
        self.verify_subproject(project, 2, 'cs', 4)

    def test_create_json(self):
        project = self.create_json()
        self.verify_subproject(project, 1, 'cs', 4)

    def test_create_json_mono(self):
        project = self.create_json_mono()
        self.verify_subproject(project, 2, 'cs', 4)

    def test_create_csv(self):
        project = self.create_csv()
        self.verify_subproject(project, 1, 'cs', 4)

    def test_create_csv_mono(self):
        project = self.create_csv_mono()
        self.verify_subproject(project, 2, 'cs', 4)

    def test_create_java(self):
        project = self.create_java()
        self.verify_subproject(project, 3, 'cs', 4)

    def test_create_xliff(self):
        project = self.create_xliff()
        self.verify_subproject(project, 1, 'cs', 4)

    def test_create_xliff_mono(self):
        project = self.create_xliff_mono()
        self.verify_subproject(project, 2, 'cs', 4)

    def test_create_xliff_dph(self):
        project = self.create_xliff('DPH')
        self.verify_subproject(project, 1, 'en', 9, 'DPH')

    def test_create_xliff_empty(self):
        project = self.create_xliff('EMPTY')
        self.verify_subproject(project, 1, 'en', 6, 'DPH')

    def test_create_xliff_resname(self):
        project = self.create_xliff('Resname')
        self.verify_subproject(project, 1, 'en', 2, 'Hi')

    def test_link(self):
        project = self.create_link()
        self.verify_subproject(project, 3, 'cs', 4)

    def test_extra_file(self):
        """
        Extra commit file validation.
        """
        project = self.create_subproject()
        project.full_clean()

        project.extra_commit_file = 'locale/list.txt'
        project.full_clean()

        project.extra_commit_file = 'locale/%(language)s.txt'
        project.full_clean()

        project.extra_commit_file = 'locale/%(bar)s.txt'
        self.assertRaisesMessage(
            ValidationError,
            "Bad format string ('bar')",
            project.full_clean
        )

    def test_check_flags(self):
        """
        Check flags validation.
        """
        project = self.create_subproject()
        project.full_clean()

        project.check_flags = 'ignore-inconsistent'
        project.full_clean()

        project.check_flags = 'rst-text,ignore-inconsistent'
        project.full_clean()

        project.check_flags = 'nonsense'
        self.assertRaisesMessage(
            ValidationError,
            'Invalid check flag: "nonsense"',
            project.full_clean
        )

        project.check_flags = 'rst-text,ignore-nonsense'
        self.assertRaisesMessage(
            ValidationError,
            'Invalid check flag: "ignore-nonsense"',
            project.full_clean
        )

    def test_validation(self):
        project = self.create_subproject()
        # Correct project
        project.full_clean()

        # Invalid commit message
        project.commit_message = '%(foo)s'
        self.assertRaisesMessage(
            ValidationError,
            'Bad format string',
            project.full_clean
        )

        # Invalid mask
        project.filemask = 'foo/x.po'
        self.assertRaisesMessage(
            ValidationError,
            'File mask does not contain * as a language placeholder!',
            project.full_clean
        )
        # Not matching mask
        project.filemask = 'foo/*.po'
        self.assertRaisesMessage(
            ValidationError,
            'The mask did not match any files!',
            project.full_clean
        )
        # Unknown file format
        project.filemask = 'iphone/*.lproj/Localizable.strings'
        self.assertRaisesMessage(
            ValidationError,
            'Format of 1 matched files could not be recognized.',
            project.full_clean
        )

        # Repoweb
        project.repoweb = 'http://%(foo)s/%(bar)s/%72'
        self.assertRaisesMessage(
            ValidationError,
            "Bad format string ('foo')",
            project.full_clean
        )
        project.repoweb = ''

        # Bad link
        project.repo = 'weblate://foo'
        project.push = ''
        self.assertRaisesMessage(
            ValidationError,
            'Invalid link to a Weblate project, '
            'use weblate://project/component.',
            project.full_clean
        )

        # Bad link
        project.repo = 'weblate://foo/bar'
        project.push = ''
        self.assertRaisesMessage(
            ValidationError,
            'Invalid link to a Weblate project, '
            'use weblate://project/component.',
            project.full_clean
        )

        # Bad link
        project.repo = 'weblate://test/test'
        project.push = ''
        self.assertRaisesMessage(
            ValidationError,
            'Invalid link to a Weblate project, '
            'can not link to self!',
            project.full_clean
        )

    def test_validation_mono(self):
        project = self.create_po_mono()
        # Correct project
        project.full_clean()
        # Not existing file
        project.template = 'not-existing'
        self.assertRaisesMessage(
            ValidationError,
            'Template file not found!',
            project.full_clean
        )

    def test_validation_languge_re(self):
        subproject = self.create_subproject()
        subproject.language_regex = '[-'
        self.assertRaisesMessage(
            ValidationError,
            'Failed to compile: unexpected end of regular expression',
            subproject.full_clean
        )

    def test_validation_newlang(self):
        subproject = self.create_subproject()
        subproject.new_base = 'po/project.pot'
        subproject.save()

        # Check that it warns about unused pot
        self.assertRaisesMessage(
            ValidationError,
            'Base file for new translations is not used '
            'because of component settings.',
            subproject.full_clean
        )

        subproject.new_lang = 'add'
        subproject.save()

        # Check that it warns about not supported format
        self.assertRaisesMessage(
            ValidationError,
            'Chosen file format does not support adding new '
            'translations as chosen in project settings.',
            subproject.full_clean
        )

        subproject.file_format = 'po'
        subproject.save()

        # Clean class cache, pylint: disable=W0212
        subproject._file_format = None

        # With correct format it should validate
        subproject.full_clean()

    def test_change_to_mono(self):
        """Test swtiching to monolingual format on the fly."""
        component = self._create_subproject(
            'po',
            'po-mono/*.po',
        )
        self.assertEqual(component.translation_set.count(), 4)
        component.file_format = 'po-mono'
        component.template = 'po-mono/en.po'
        component.save()
        self.assertEqual(component.translation_set.count(), 4)

    def test_lang_code(self):
        subproject = SubProject()
        subproject.filemask = 'Solution/Project/Resources.*.resx'
        self.assertEqual(
            subproject.get_lang_code('Solution/Project/Resources.es-mx.resx'),
            'es-mx'
        )
        self.assertEqual(
            subproject.get_lang_code('Solution/Project/Resources.resx'),
            ''
        )
        self.assertRaisesMessage(
            ValidationError,
            'Got empty language code for '
            'Solution/Project/Resources.resx, please check filemask!',
            subproject.clean_lang_codes,
            [
                'Solution/Project/Resources.resx',
                'Solution/Project/Resources.de.resx',
                'Solution/Project/Resources.es.resx',
                'Solution/Project/Resources.es-mx.resx',
                'Solution/Project/Resources.fr.resx',
                'Solution/Project/Resources.fr-fr.resx',
            ]
        )

    def test_lang_code_template(self):
        subproject = SubProject(project=Project())
        subproject.filemask = 'Solution/Project/Resources.*.resx'
        subproject.template = 'Solution/Project/Resources.resx'
        self.assertEqual(
            subproject.get_lang_code('Solution/Project/Resources.resx'),
            'en'
        )

    def test_change_project(self):
        subproject = self.create_subproject()

        # Create and verify suggestion
        Suggestion.objects.create(
            project=subproject.project,
            contentsum='x',
            language=subproject.translation_set.all()[0].language,
        )
        self.assertEqual(subproject.project.suggestion_set.count(), 1)

        # Check current path exists
        old_path = subproject.get_path()
        self.assertTrue(os.path.exists(old_path))

        # Crete target project
        second = Project.objects.create(
            name='Test2',
            slug='test2',
            web='https://weblate.org/'
        )

        # Move component
        subproject.project = second
        subproject.save()

        # Check new path exists
        new_path = subproject.get_path()
        self.assertTrue(os.path.exists(new_path))

        # Check paths differ
        self.assertNotEqual(old_path, new_path)

        # Check suggestion has been copied
        self.assertEqual(subproject.project.suggestion_set.count(), 1)


class TranslationTest(RepoTestCase):
    """
    Translation testing.
    """
    def test_basic(self):
        project = self.create_subproject()
        translation = project.translation_set.get(language_code='cs')
        self.assertEqual(translation.translated, 0)
        self.assertEqual(translation.total, 4)
        self.assertEqual(translation.fuzzy, 0)

    def test_extra_file(self):
        """
        Test extra commit file handling.
        """
        subproject = self.create_subproject()
        subproject.pre_commit_script = get_test_file(
            '../../../../examples/hook-generate-mo'
        )
        appsettings.PRE_COMMIT_SCRIPT_CHOICES.append(
            (subproject.pre_commit_script, 'hook-generate-mo')
        )
        subproject.pre_commit_script = get_test_file(
            '../../../../examples/hook-update-linguas'
        )
        appsettings.PRE_COMMIT_SCRIPT_CHOICES.append(
            (subproject.pre_commit_script, 'hook-update-linguas')
        )
        subproject.extra_commit_file = 'po/%(language)s.mo\npo/LINGUAS'
        subproject.save()
        subproject.full_clean()
        translation = subproject.translation_set.get(language_code='cs')
        # change backend file
        with open(translation.get_filename(), 'a') as handle:
            handle.write(' ')
        # Test committing
        translation.git_commit(
            None, 'TEST <test@example.net>', timezone.now(),
            force_commit=True
        )
        linguas = os.path.join(subproject.get_path(), 'po', 'LINGUAS')
        with open(linguas, 'r') as handle:
            data = handle.read()
            self.assertIn('\ncs\n', data)
        self.assertFalse(translation.repo_needs_commit())

    def test_validation(self):
        """
        Translation validation
        """
        project = self.create_subproject()
        translation = project.translation_set.get(language_code='cs')
        translation.full_clean()

    def test_update_stats(self):
        """
        Check update stats with no units.
        """
        project = self.create_subproject()
        translation = project.translation_set.get(language_code='cs')
        translation.update_stats()
        translation.unit_set.all().delete()
        translation.update_stats()


class WhiteboardMessageTest(TestCase):
    """Test(s) for WhiteboardMessage model."""

    def test_can_be_imported(self):
        """Test that whiteboard model can be imported.

        Rather dumb test just to make sure there are no obvious parsing errors.
        """
        WhiteboardMessage()


class ModelTestCase(RepoTestCase):
    def setUp(self):
        super(ModelTestCase, self).setUp()
        self.create_subproject()


class SourceTest(ModelTestCase):
    """
    Source objects testing.
    """
    def test_exists(self):
        self.assertTrue(Source.objects.exists())

    def test_source_info(self):
        unit = Unit.objects.all()[0]
        self.assertIsNotNone(unit.source_info)

    def test_priority(self):
        unit = Unit.objects.all()[0]
        self.assertEqual(unit.priority, 100)
        source = unit.source_info
        source.priority = 200
        source.save()
        unit2 = Unit.objects.get(pk=unit.pk)
        self.assertEqual(unit2.priority, 200)

    def test_check_flags(self):
        """
        Setting of Source check_flags changes checks for related units.
        """
        self.assertEqual(Check.objects.count(), 3)
        check = Check.objects.all()[0]
        unit = get_related_units(check)[0]
        source = unit.source_info
        source.check_flags = 'ignore-{0}'.format(check.check)
        source.save()
        self.assertEqual(Check.objects.count(), 0)


class UnitTest(ModelTestCase):
    @OverrideSettings(MT_WEBLATE_LIMIT=15)
    def test_more_like(self):
        unit = Unit.objects.all()[0]
        self.assertEqual(Unit.objects.more_like_this(unit).count(), 0)

    @OverrideSettings(MT_WEBLATE_LIMIT=0)
    def test_more_like_timeout(self):
        unit = Unit.objects.all()[0]
        self.assertRaisesMessage(
            Exception, 'Request timed out.', Unit.objects.more_like_this, unit
        )

    @OverrideSettings(MT_WEBLATE_LIMIT=-1)
    def test_more_like_no_fork(self):
        unit = Unit.objects.all()[0]
        self.assertEqual(Unit.objects.more_like_this(unit).count(), 0)

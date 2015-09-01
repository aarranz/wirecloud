# -*- coding: utf-8 -*-

# Copyright (c) 2014-2015 CoNWeT Lab., Universidad Politécnica de Madrid

# This file is part of Wirecloud.

# Wirecloud is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# Wirecloud is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with Wirecloud.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

from io import BytesIO
import os
import zipfile

from django.http import Http404, UnreadablePostError
from django.test import TestCase
from django.test.utils import override_settings
from mock import DEFAULT, patch, Mock

from wirecloud.commons.exceptions import ErrorResponse
from wirecloud.commons.utils.html import clean_html
from wirecloud.commons.utils.http import build_sendfile_response, get_current_domain, get_current_scheme, get_content_type, normalize_boolean_param, produces, validate_url_param
from wirecloud.commons.utils.log import SkipUnreadablePosts
from wirecloud.commons.utils.mimeparser import best_match, parse_mime_type
from wirecloud.commons.utils.wgt import WgtFile


# Avoid nose to repeat these tests (they are run through wirecloud/commons/tests/__init__.py)
__test__ = False


class HTMLCleanupTestCase(TestCase):

    tags = ('wirecloud-utils', 'wirecloud-html-cleanup')

    def test_scripts_are_removed(self):
        self.assertEqual(clean_html('<script>asdfas</script>'), '')
        self.assertEqual(clean_html('start content <script>asdfas</script> valid content'), 'start content  valid content')

    def test_event_attributes_are_removed(self):
        self.assertEqual(clean_html('<div onclick="evil_script();" class="alert">content</div>'), '<div class="alert">content</div>')

    def test_processing_instructions_are_removed(self):
        self.assertEqual(clean_html('<div class="alert"><?php echo "<p>Hello World</p>"; ?>content</div>'), '<div class="alert">content</div>')

    def test_audio_elements_are_removed(self):
        initial_code = '<div class="alert"><audio controls="controls"><source src="sound.ogg" type="audio/ogg"/><source src="sound.mp3" type="audio/mpeg"/>Your browser does not support the audio tag.</audio>content</div>'
        self.assertEqual(clean_html(initial_code), '<div class="alert">content</div>')

    def test_video_elements_need_controls(self):
        initial_code = '<video><source src="movie.mp4" type="video/mp4"/><source src="movie.ogg" type="video/ogg"/>Your browser does not support the video tag.</video>content'
        expected_code = '<video controls="controls"><source src="movie.mp4" type="video/mp4"/><source src="movie.ogg" type="video/ogg"/>Your browser does not support the video tag.</video>content'
        self.assertEqual(clean_html(initial_code), expected_code)

    def test_links_are_forced_to_target_blank(self):
        self.assertEqual(clean_html('<div class="alert">Follow this <a href="http://example.com">link</a></div>'), '<div class="alert">Follow this <a href="http://example.com" target="_blank">link</a></div>')

    def test_relative_links_are_removed(self):
        initial_code = '<div class="alert">Follow this <a href="files/insecure_content.exe">link</a></div>'
        expected_code = '<div class="alert">Follow this link</div>'
        self.assertEqual(clean_html(initial_code), expected_code)

    def test_relative_image_urls(self):
        initial_code = 'Example image: <img src="images/example.png"/>'
        expected_code = 'Example image: <img src="http://example.com/images/example.png"/>'
        self.assertEqual(clean_html(initial_code, base_url='http://example.com'), expected_code)


class GeneralUtilsTestCase(TestCase):

    tags = ('wirecloud-utils', 'wirecloud-general-utils')

    def test_skipunreadableposts_filter(self):

        record = Mock()
        record.exc_info = (None, UnreadablePostError())
        filter = SkipUnreadablePosts()
        self.assertFalse(filter.filter(record))

    def test_skipunreadableposts_filter_should_ignore_general_exceptions(self):

        record = Mock()
        record.exc_info = (None, Exception())
        filter = SkipUnreadablePosts()
        self.assertTrue(filter.filter(record))

    def test_skipunreadableposts_filter_should_ignore_records_without_exc_info(self):

        record = Mock()
        record.exc_info = None
        filter = SkipUnreadablePosts()
        self.assertTrue(filter.filter(record))

    def test_mimeparser_parse_mime_type(self):

        self.assertEqual(parse_mime_type('application/xhtml;q=0.5'), ('application/xhtml', {'q': '0.5'}))

    def test_mimeparser_parse_mime_type_should_accept_single_wildcard(self):

        self.assertEqual(parse_mime_type('*;q=0.5'), ('*/*', {'q': '0.5'}))

    def test_mimeparser_parse_mime_type_split_type(self):

        self.assertEqual(parse_mime_type('application/xhtml;q=0.5', split_type=True), ('application', 'xhtml', {'q': '0.5'}))

    def test_mimeparser_best_match_should_ignore_blank_media_ranges(self):

        self.assertEqual(best_match(['application/xbel+xml', 'text/xml'], 'text/*;q=0.5, , */*; q=0.1'), 'text/xml')

    def test_mimeparser_best_match_should_ignore_blank_media_ranges(self):

        self.assertEqual(best_match(['application/xbel+xml; a=1; b=2', 'application/xml'], 'application/*, application/xbel+xml; a=1; b=2'), 'application/xbel+xml; a=1; b=2')


class WGTTestCase(TestCase):

    tags = ('wirecloud-utils', 'wirecloud-wgt',)

    def build_simple_wgt(self, other_files=()):

        f = BytesIO()
        zf = zipfile.ZipFile(f, 'w')
        zf.writestr('config.xml', b'')
        zf.writestr('test.html', b'')
        for of in other_files:
            zf.writestr(of, b'')
        zf.close()
        return WgtFile(f)

    def test_extract_inexistent_dir(self):

        with patch('wirecloud.commons.utils.wgt.os', autospec=True) as os_mock:
            with patch('wirecloud.commons.utils.wgt.open', create=True) as open_mock:
                os_mock.path.normpath = os.path.normpath
                wgt_file = self.build_simple_wgt()
                self.assertRaises(KeyError, wgt_file.extract_dir, 'doc', '/tmp/test')
                self.assertEqual(os_mock.makedirs.call_count, 0)
                self.assertEqual(os_mock.mkdir.call_count, 0)
                self.assertEqual(open_mock.call_count, 0)

    def test_extract_empty_dir(self):

        with patch('wirecloud.commons.utils.wgt.os', autospec=True) as os_mock:
            with patch('wirecloud.commons.utils.wgt.open', create=True) as open_mock:
                os_mock.path.normpath = os.path.normpath
                os_mock.path.exists.return_value = False
                wgt_file = self.build_simple_wgt(other_files=('doc/',))
                wgt_file.extract_dir('doc', '/tmp/test')

                self.assertEqual(os_mock.makedirs.call_count, 1)
                self.assertEqual(os_mock.mkdir.call_count, 0)
                self.assertEqual(open_mock.call_count, 0)

    def test_extract_empty_dir_existing_output_dir(self):

        with patch('wirecloud.commons.utils.wgt.os', autospec=True) as os_mock:
            with patch('wirecloud.commons.utils.wgt.open', create=True) as open_mock:
                os_mock.path.normpath = os.path.normpath
                os_mock.path.exists.return_value = True
                wgt_file = self.build_simple_wgt(other_files=('doc/',))
                wgt_file.extract_dir('doc', '/tmp/test')

                self.assertEqual(os_mock.makedirs.call_count, 0)
                self.assertEqual(open_mock.call_count, 0)

    def test_extract_dir(self):

        def exists_side_effect(path):
            if path != '/tmp/test/folder1':
                return False
            else:
                result = not exists_side_effect.first_time
                exists_side_effect.first_time = False
                return result
        exists_side_effect.first_time = True

        with patch('wirecloud.commons.utils.wgt.os', autospec=True) as os_mock:
            with patch('wirecloud.commons.utils.wgt.open', create=True) as open_mock:

                os_mock.path.normpath = os.path.normpath
                os_mock.path.exists.side_effect = exists_side_effect
                os_mock.sep = '/'
                wgt_file = self.build_simple_wgt(other_files=('doc/folder1/', 'doc/folder1/file1', 'doc/folder1/file2', 'doc/folder2/folder3/file3'))
                wgt_file.extract_dir('doc/', '/tmp/test')

                self.assertEqual(os_mock.makedirs.call_count, 1)
                self.assertEqual(os_mock.mkdir.call_count, 3)
                self.assertEqual(open_mock.call_count, 3)

    def test_extract(self):

        with patch('wirecloud.commons.utils.wgt.os', autospec=True) as os_mock:
            with patch('wirecloud.commons.utils.wgt.open', create=True) as open_mock:
                os_mock.path.normpath = os.path.normpath
                os_mock.path.exists.return_value = False
                os_mock.sep = '/'
                wgt_file = self.build_simple_wgt(other_files=('folder1/', 'folder2/'))
                wgt_file.extract('/tmp/test')
                self.assertEqual(os_mock.mkdir.call_count, 3)
                self.assertEqual(open_mock.call_count, 2)

    def test_extract_inexistent_file(self):

        with patch('wirecloud.commons.utils.wgt.os', autospec=True) as os_mock:
            with patch('wirecloud.commons.utils.wgt.open', create=True) as open_mock:
                os_mock.path.normpath = os.path.normpath
                wgt_file = self.build_simple_wgt()
                self.assertRaises(KeyError, wgt_file.extract_file, 'doc/index.md', '/tmp/test')
                self.assertEqual(os_mock.makedirs.call_count, 0)
                self.assertEqual(os_mock.mkdir.call_count, 0)
                self.assertEqual(open_mock.call_count, 0)

    def test_invalid_file(self):

        with self.assertRaises(ValueError):
            self.build_simple_wgt(other_files=('../../invalid1.html',))

        with self.assertRaises(ValueError):
            self.build_simple_wgt(other_files=('folder1/../../invalid2.html',))

        with self.assertRaises(ValueError):
            self.build_simple_wgt(other_files=('/invalid3.html',))


class HTTPUtilsTestCase(TestCase):

    tags = ('wirecloud-utils', 'wirecloud-general-utils', 'wirecloud-http-utils',)

    def _prepare_request_mock(self):

        request = Mock()
        request.get_host.return_value = 'example.com'
        request.META = {
            'HTTP_ACCEPT': 'application/json',
            'SERVER_PROTOCOL': 'http',
            'SERVER_PORT': '80',
            'REMOTE_ADDR': '127.0.0.1',
            'HTTP_HOST': 'localhost',
        }

        return request

    def _prepare_site_mock(self):

        site = Mock()
        site.domain = 'site.example.com:8000'

        return site

    def test_build_sendfile_response(self):

        with patch('wirecloud.commons.utils.http.os.path.isfile', return_value=True):
            response = build_sendfile_response('file.js', '/folder')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['X-Sendfile'], '/folder/file.js')

    def test_build_sendfile_response_remove_extra_path_separators(self):

        with patch('wirecloud.commons.utils.http.os.path.isfile', return_value=True) as isfile_mock:
            response = build_sendfile_response('js///file.js', '/folder')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['X-Sendfile'], '/folder/js/file.js')
            isfile_mock.assert_called_once_with('/folder/js/file.js')

    def test_build_sendfile_response_not_found(self):

        with patch('wirecloud.commons.utils.http.os.path.isfile', return_value=False) as isfile_mock:
            self.assertRaises(Http404, build_sendfile_response, 'js/notfound.js', '/folder')

    def test_build_sendfile_response_redirect_on_invalid_path(self):

        response = build_sendfile_response('../a/../file.js', '/folder')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], 'file.js')

    def test_normalize_boolean_param_string(self):

        request = self._prepare_request_mock()
        normalize_boolean_param(request, 'param', 'true')

    def test_normalize_boolean_param_boolean(self):

        request = self._prepare_request_mock()
        normalize_boolean_param(request, 'param', True)

    def test_normalize_boolean_param_number(self):

        request = self._prepare_request_mock()
        try:
            normalize_boolean_param(request, 'param', 5)
            self.fail('ErrorResponse not raised by normalize_boolean_param')
        except ErrorResponse as e:
            self.assertEqual(e.response.status_code, 422)

    def test_normalize_boolean_param_invalid_string(self):

        request = self._prepare_request_mock()
        try:
            normalize_boolean_param(request, 'param', 'invalid')
            self.fail('ErrorResponse not raised by normalize_boolean_param')
        except ErrorResponse as e:
            self.assertEqual(e.response.status_code, 422)

    def test_validate_url_param_string(self):

        request = self._prepare_request_mock()
        validate_url_param(request, 'param', 'index.html', force_absolute=False)

    def test_validate_url_param_string_empty_and_required(self):

        request = self._prepare_request_mock()
        try:
            validate_url_param(request, 'param', '', force_absolute=False, required=True)
            self.fail('ErrorResponse not raised by validate_url_param')
        except ErrorResponse as e:
            self.assertEqual(e.response.status_code, 422)

    def test_validate_url_param_string_force_absolute(self):

        request = self._prepare_request_mock()
        validate_url_param(request, 'param', 'http://example.com/index.html', force_absolute=True)

    def test_validate_url_param_string_invalid_schema(self):

        request = self._prepare_request_mock()
        try:
            validate_url_param(request, 'param', 'file:///etc/password', force_absolute=False)
            self.fail('ErrorResponse not raised by validate_url_param')
        except ErrorResponse as e:
            self.assertEqual(e.response.status_code, 422)

    def test_validate_url_param_string_relative_urls_not_allowed(self):
        request = self._prepare_request_mock()
        try:
            validate_url_param(request, 'param', 'index.html', force_absolute=True)
            self.fail('ErrorResponse not raised by validate_url_param')
        except ErrorResponse as e:
            self.assertEqual(e.response.status_code, 422)

    def test_validate_url_param_none_and_required(self):
        request = self._prepare_request_mock()
        try:
            validate_url_param(request, 'param', None, force_absolute=False, required=True)
            self.fail('ErrorResponse not raised by validate_url_param')
        except ErrorResponse as e:
            self.assertEqual(e.response.status_code, 422)

    def test_validate_url_param_number(self):
        request = self._prepare_request_mock()
        try:
            validate_url_param(request, 'param', 5, force_absolute=False)
            self.fail('ErrorResponse not raised by validate_url_param')
        except ErrorResponse as e:
            self.assertEqual(e.response.status_code, 422)

    def test_produces_decorator_supported_accept_header(self):
        func = Mock()
        wrapped_func = produces(('application/json',))(func)

        request = self._prepare_request_mock()
        wrapped_func(Mock(), request)

        self.assertEqual(func.call_count, 1)

    def test_produces_decorator_unsupported_accept_header(self):
        func = Mock()
        wrapped_func = produces(('application/xml',))(func)

        request = self._prepare_request_mock()
        result = wrapped_func(Mock(), request)

        self.assertEqual(func.call_count, 0)
        self.assertEqual(result.status_code, 406)

    def test_get_content_type(self):
        request = self._prepare_request_mock()
        request.META['CONTENT_TYPE'] = 'application/json'
        self.assertEqual(get_content_type(request), ('application/json', {}))

    def test_get_content_type_no_provided(self):
        request = self._prepare_request_mock()
        self.assertEqual(get_content_type(request), ('', {}))

    @override_settings(FORCE_PROTO=None)
    def test_get_current_scheme_http(self):
        request = self._prepare_request_mock()
        request.is_secure.return_value = False
        self.assertEqual(get_current_scheme(request), 'http')

    @override_settings(FORCE_PROTO=None)
    def test_get_current_scheme_https(self):
        request = self._prepare_request_mock()
        request.is_secure.return_value = True
        self.assertEqual(get_current_scheme(request), 'https')

    @override_settings(FORCE_PROTO='https')
    def test_get_current_scheme_forced_http(self):
        request = self._prepare_request_mock()
        request.is_secure.return_value = False
        self.assertEqual(get_current_scheme(request), 'https')

    @override_settings(FORCE_PROTO='http')
    def test_get_current_scheme_forced_http(self):
        request = self._prepare_request_mock()
        request.is_secure.return_value = True
        self.assertEqual(get_current_scheme(request), 'http')

    @override_settings(FORCE_PROTO=None)
    def test_get_current_scheme_fallback(self):
        self.assertEqual(get_current_scheme(None), 'http')

    @override_settings(FORCE_PROTO=None, FORCE_DOMAIN=None, FORCE_PORT=None)
    def test_get_current_domain(self):
        request = self._prepare_request_mock()
        with patch('django.contrib.sites.models.get_current_site') as get_current_site_mock:
            with patch.multiple('wirecloud.commons.utils.http', socket=DEFAULT, get_current_scheme=DEFAULT) as mocks:
                get_current_site_mock.return_value = self._prepare_site_mock()
                mocks['get_current_scheme'].return_value = 'http'
                self.assertEqual(get_current_domain(request), 'site.example.com:8000')
                self.assertEqual(mocks['socket'].getfqdn.call_count, 0)

    @override_settings(FORCE_PROTO=None, FORCE_DOMAIN='myserver.com', FORCE_PORT=8080)
    def test_get_current_domain_forced(self):
        request = self._prepare_request_mock()
        with patch('django.contrib.sites.models.get_current_site') as get_current_site_mock:
            with patch.multiple('wirecloud.commons.utils.http', socket=DEFAULT, get_current_scheme=DEFAULT) as mocks:
                mocks['get_current_scheme'].return_value = 'http'
                self.assertEqual(get_current_domain(request), 'myserver.com:8080')
                self.assertEqual(mocks['socket'].getfqdn.call_count, 0)
                self.assertEqual(get_current_site_mock.call_count, 0)

    @override_settings(FORCE_PROTO=None, FORCE_DOMAIN='forced.example.com', FORCE_PORT=8000)
    def test_get_current_domain_forced_domain(self):
        request = self._prepare_request_mock()
        with patch('django.contrib.sites.models.get_current_site') as get_current_site_mock:
            with patch.multiple('wirecloud.commons.utils.http', socket=DEFAULT, get_current_scheme=DEFAULT) as mocks:
                get_current_site_mock.return_value = self._prepare_site_mock()
                mocks['get_current_scheme'].return_value = 'http'
                self.assertEqual(get_current_domain(request), 'forced.example.com:8000')
                self.assertEqual(mocks['socket'].getfqdn.call_count, 0)

    @override_settings(FORCE_PROTO=None, FORCE_DOMAIN=None, FORCE_PORT=81)
    def test_get_current_domain_forced_port(self):
        request = self._prepare_request_mock()
        with patch('django.contrib.sites.models.get_current_site') as get_current_site_mock:
            with patch.multiple('wirecloud.commons.utils.http', socket=DEFAULT, get_current_scheme=DEFAULT) as mocks:
                get_current_site_mock.return_value = self._prepare_site_mock()
                mocks['get_current_scheme'].return_value = 'http'
                self.assertEqual(get_current_domain(request), 'site.example.com:81')
                self.assertEqual(mocks['socket'].getfqdn.call_count, 0)

    @override_settings(FORCE_PROTO=None, FORCE_DOMAIN=None, FORCE_PORT=80)
    def test_get_current_domain_fallback_http(self):
        request = self._prepare_request_mock()
        with patch('django.contrib.sites.models.get_current_site') as get_current_site_mock:
            with patch.multiple('wirecloud.commons.utils.http', socket=DEFAULT, get_current_scheme=DEFAULT) as mocks:
                get_current_site_mock.side_effect = Exception
                mocks['socket'].getfqdn.return_value = 'fqdn.example.com'
                mocks['get_current_scheme'].return_value = 'http'
                self.assertEqual(get_current_domain(request), 'fqdn.example.com')

    @override_settings(FORCE_PROTO=None, FORCE_DOMAIN=None, FORCE_PORT=81)
    def test_get_current_domain_fallback_http_custom_port(self):
        request = self._prepare_request_mock()
        with patch('django.contrib.sites.models.get_current_site') as get_current_site_mock:
            with patch.multiple('wirecloud.commons.utils.http', socket=DEFAULT, get_current_scheme=DEFAULT) as mocks:
                get_current_site_mock.side_effect = Exception
                mocks['socket'].getfqdn.return_value = 'fqdn.example.com'
                mocks['get_current_scheme'].return_value = 'http'
                self.assertEqual(get_current_domain(request), 'fqdn.example.com:81')

    @override_settings(FORCE_DOMAIN=None, FORCE_PORT=443)
    def test_get_current_domain_fallback_https(self):
        request = self._prepare_request_mock()
        with patch('django.contrib.sites.models.get_current_site') as get_current_site_mock:
            with patch.multiple('wirecloud.commons.utils.http', socket=DEFAULT, get_current_scheme=DEFAULT) as mocks:
                get_current_site_mock.side_effect = Exception
                mocks['socket'].getfqdn.return_value = 'fqdn.example.com'
                mocks['get_current_scheme'].return_value = 'https'
                self.assertEqual(get_current_domain(request), 'fqdn.example.com')

    @override_settings(FORCE_DOMAIN=None, FORCE_PORT=8443)
    def test_get_current_domain_fallback_https_custom_port(self):
        request = self._prepare_request_mock()
        with patch('django.contrib.sites.models.get_current_site') as get_current_site_mock:
            with patch.multiple('wirecloud.commons.utils.http', socket=DEFAULT, get_current_scheme=DEFAULT) as mocks:
                get_current_site_mock.side_effect = Exception
                mocks['socket'].getfqdn.return_value = 'example.com'
                mocks['get_current_scheme'].return_value = 'http'
                self.assertEqual(get_current_domain(request), 'fqdn.example.com:8443')

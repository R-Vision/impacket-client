import os
import subprocess
import textwrap

import pytest
from mock import Mock, patch
from pretend import stub

import pip._internal.index
from pip._internal.download import PipSession
from pip._internal.exceptions import (
    InstallationError, RequirementsFileParseError,
)
from pip._internal.index import PackageFinder
from pip._internal.models.format_control import FormatControl
from pip._internal.req.constructors import (
    install_req_from_editable, install_req_from_line,
)
from pip._internal.req.req_file import (
    break_args_options, ignore_comments, join_lines, parse_requirements,
    preprocess, process_line, skip_regex,
)
from tests.lib import requirements_file


@pytest.fixture
def session():
    return PipSession()


@pytest.fixture
def finder(session):
    return PackageFinder([], [], session=session)


@pytest.fixture
def options(session):
    return stub(
        isolated_mode=False, index_url='default_url',
        skip_requirements_regex=False,
        format_control=FormatControl(set(), set()))


class TestPreprocess(object):
    """tests for `preprocess`"""

    def test_comments_and_joins_case1(self):
        content = textwrap.dedent("""\
          req1 \\
          # comment \\
          req2
        """)
        result = preprocess(content, None)
        assert list(result) == [(1, 'req1'), (3, 'req2')]

    def test_comments_and_joins_case2(self):
        content = textwrap.dedent("""\
          req1\\
          # comment
        """)
        result = preprocess(content, None)
        assert list(result) == [(1, 'req1')]

    def test_comments_and_joins_case3(self):
        content = textwrap.dedent("""\
          req1 \\
          # comment
          req2
        """)
        result = preprocess(content, None)
        assert list(result) == [(1, 'req1'), (3, 'req2')]

    def test_skip_regex_after_joining_case1(self, options):
        content = textwrap.dedent("""\
          patt\\
          ern
          line2
        """)
        options.skip_requirements_regex = 'pattern'
        result = preprocess(content, options)
        assert list(result) == [(3, 'line2')]

    def test_skip_regex_after_joining_case2(self, options):
        content = textwrap.dedent("""\
          pattern \\
          line2
          line3
        """)
        options.skip_requirements_regex = 'pattern'
        result = preprocess(content, options)
        assert list(result) == [(3, 'line3')]


class TestIgnoreComments(object):
    """tests for `ignore_comment`"""

    def test_ignore_line(self):
        lines = [(1, ''), (2, 'req1'), (3, 'req2')]
        result = ignore_comments(lines)
        assert list(result) == [(2, 'req1'), (3, 'req2')]

    def test_ignore_comment(self):
        lines = [(1, 'req1'), (2, '# comment'), (3, 'req2')]
        result = ignore_comments(lines)
        assert list(result) == [(1, 'req1'), (3, 'req2')]

    def test_strip_comment(self):
        lines = [(1, 'req1'), (2, 'req # comment'), (3, 'req2')]
        result = ignore_comments(lines)
        assert list(result) == [(1, 'req1'), (2, 'req'), (3, 'req2')]


class TestJoinLines(object):
    """tests for `join_lines`"""

    def test_join_lines(self):
        lines = enumerate([
            'line 1',
            'line 2:1 \\',
            'line 2:2',
            'line 3:1 \\',
            'line 3:2 \\',
            'line 3:3',
            'line 4'
        ], start=1)
        expect = [
            (1, 'line 1'),
            (2, 'line 2:1 line 2:2'),
            (4, 'line 3:1 line 3:2 line 3:3'),
            (7, 'line 4'),
        ]
        assert expect == list(join_lines(lines))

    def test_last_line_with_escape(self):
        lines = enumerate([
            'line 1',
            'line 2 \\',
        ], start=1)
        expect = [
            (1, 'line 1'),
            (2, 'line 2 '),
        ]
        assert expect == list(join_lines(lines))


class TestSkipRegex(object):
    """tests for `skip_reqex``"""

    def test_skip_regex_pattern_match(self):
        options = stub(skip_requirements_regex='.*Bad.*')
        line = '--extra-index-url Bad'
        assert [] == list(skip_regex(enumerate([line]), options))

    def test_skip_regex_pattern_not_match(self):
        options = stub(skip_requirements_regex='.*Bad.*')
        line = '--extra-index-url Good'
        assert [(0, line)] == list(skip_regex(enumerate([line]), options))

    def test_skip_regex_no_options(self):
        options = None
        line = '--extra-index-url Good'
        assert [(0, line)] == list(skip_regex(enumerate([line]), options))

    def test_skip_regex_no_skip_option(self):
        options = stub(skip_requirements_regex=None)
        line = '--extra-index-url Good'
        assert [(0, line)] == list(skip_regex(enumerate([line]), options))


class TestProcessLine(object):
    """tests for `process_line`"""

    def test_parser_error(self):
        with pytest.raises(RequirementsFileParseError):
            list(process_line("--bogus", "file", 1))

    def test_parser_offending_line(self):
        line = 'pkg==1.0.0 --hash=somehash'
        with pytest.raises(RequirementsFileParseError) as err:
            list(process_line(line, 'file', 1))
        assert line in str(err.value)

    def test_parser_non_offending_line(self):
        try:
            list(process_line('pkg==1.0.0 --hash=sha256:somehash', 'file', 1))
        except RequirementsFileParseError:
            pytest.fail('Reported offending line where it should not.')

    def test_only_one_req_per_line(self):
        # pkg_resources raises the ValueError
        with pytest.raises(InstallationError):
            list(process_line("req1 req2", "file", 1))

    def test_yield_line_requirement(self):
        line = 'SomeProject'
        filename = 'filename'
        comes_from = '-r %s (line %s)' % (filename, 1)
        req = install_req_from_line(line, comes_from=comes_from)
        assert repr(list(process_line(line, filename, 1))[0]) == repr(req)

    def test_yield_line_constraint(self):
        line = 'SomeProject'
        filename = 'filename'
        comes_from = '-c %s (line %s)' % (filename, 1)
        req = install_req_from_line(
            line, comes_from=comes_from, constraint=True)
        found_req = list(process_line(line, filename, 1, constraint=True))[0]
        assert repr(found_req) == repr(req)
        assert found_req.constraint is True

    def test_yield_line_requirement_with_spaces_in_specifier(self):
        line = 'SomeProject >= 2'
        filename = 'filename'
        comes_from = '-r %s (line %s)' % (filename, 1)
        req = install_req_from_line(line, comes_from=comes_from)
        assert repr(list(process_line(line, filename, 1))[0]) == repr(req)
        assert str(req.req.specifier) == '>=2'

    def test_yield_editable_requirement(self):
        url = 'git+https://url#egg=SomeProject'
        line = '-e %s' % url
        filename = 'filename'
        comes_from = '-r %s (line %s)' % (filename, 1)
        req = install_req_from_editable(url, comes_from=comes_from)
        assert repr(list(process_line(line, filename, 1))[0]) == repr(req)

    def test_yield_editable_constraint(self):
        url = 'git+https://url#egg=SomeProject'
        line = '-e %s' % url
        filename = 'filename'
        comes_from = '-c %s (line %s)' % (filename, 1)
        req = install_req_from_editable(
            url, comes_from=comes_from, constraint=True)
        found_req = list(process_line(line, filename, 1, constraint=True))[0]
        assert repr(found_req) == repr(req)
        assert found_req.constraint is True

    def test_nested_requirements_file(self, monkeypatch):
        line = '-r another_file'
        req = install_req_from_line('SomeProject')
        import pip._internal.req.req_file

        def stub_parse_requirements(req_url, finder, comes_from, options,
                                    session, wheel_cache, constraint):
            return [(req, constraint)]
        parse_requirements_stub = stub(call=stub_parse_requirements)
        monkeypatch.setattr(pip._internal.req.req_file, 'parse_requirements',
                            parse_requirements_stub.call)
        assert list(process_line(line, 'filename', 1)) == [(req, False)]

    def test_nested_constraints_file(self, monkeypatch):
        line = '-c another_file'
        req = install_req_from_line('SomeProject')
        import pip._internal.req.req_file

        def stub_parse_requirements(req_url, finder, comes_from, options,
                                    session, wheel_cache, constraint):
            return [(req, constraint)]
        parse_requirements_stub = stub(call=stub_parse_requirements)
        monkeypatch.setattr(pip._internal.req.req_file, 'parse_requirements',
                            parse_requirements_stub.call)
        assert list(process_line(line, 'filename', 1)) == [(req, True)]

    def test_options_on_a_requirement_line(self):
        line = 'SomeProject --install-option=yo1 --install-option yo2 '\
               '--global-option="yo3" --global-option "yo4"'
        filename = 'filename'
        req = list(process_line(line, filename, 1))[0]
        assert req.options == {
            'global_options': ['yo3', 'yo4'],
            'install_options': ['yo1', 'yo2']}

    def test_hash_options(self):
        """Test the --hash option: mostly its value storage.

        Make sure it reads and preserve multiple hashes.

        """
        line = ('SomeProject --hash=sha256:2cf24dba5fb0a30e26e83b2ac5b9e29e1b1'
                '61e5c1fa7425e73043362938b9824 '
                '--hash=sha384:59e1748777448c69de6b800d7a33bbfb9ff1b463e44354c'
                '3553bcdb9c666fa90125a3c79f90397bdf5f6a13de828684f '
                '--hash=sha256:486ea46224d1bb4fb680f34f7c9ad96a8f24ec88be73ea8'
                'e5a6c65260e9cb8a7')
        filename = 'filename'
        req = list(process_line(line, filename, 1))[0]
        assert req.options == {'hashes': {
            'sha256': ['2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e730433'
                       '62938b9824',
                       '486ea46224d1bb4fb680f34f7c9ad96a8f24ec88be73ea8e5a6c65'
                       '260e9cb8a7'],
            'sha384': ['59e1748777448c69de6b800d7a33bbfb9ff1b463e44354c3553bcd'
                       'b9c666fa90125a3c79f90397bdf5f6a13de828684f']}}

    def test_set_isolated(self, options):
        line = 'SomeProject'
        filename = 'filename'
        options.isolated_mode = True
        result = process_line(line, filename, 1, options=options)
        assert list(result)[0].isolated

    def test_set_finder_no_index(self, finder):
        list(process_line("--no-index", "file", 1, finder=finder))
        assert finder.index_urls == []

    def test_set_finder_index_url(self, finder):
        list(process_line("--index-url=url", "file", 1, finder=finder))
        assert finder.index_urls == ['url']

    def test_set_finder_find_links(self, finder):
        list(process_line("--find-links=url", "file", 1, finder=finder))
        assert finder.find_links == ['url']

    def test_set_finder_extra_index_urls(self, finder):
        list(process_line("--extra-index-url=url", "file", 1, finder=finder))
        assert finder.index_urls == ['url']

    def test_set_finder_trusted_host(self, finder):
        list(process_line("--trusted-host=url", "file", 1, finder=finder))
        assert finder.secure_origins == [('*', 'url', '*')]

    def test_noop_always_unzip(self, finder):
        # noop, but confirm it can be set
        list(process_line("--always-unzip", "file", 1, finder=finder))

    def test_set_finder_allow_all_prereleases(self, finder):
        list(process_line("--pre", "file", 1, finder=finder))
        assert finder.allow_all_prereleases

    def test_relative_local_find_links(self, finder, monkeypatch):
        """
        Test a relative find_links path is joined with the req file directory
        """
        # Make sure the test also passes on windows
        req_file = os.path.normcase(os.path.abspath(
            os.path.normpath('/path/req_file.txt')))
        nested_link = os.path.normcase(os.path.abspath(
            os.path.normpath('/path/rel_path')))
        exists_ = os.path.exists

        def exists(path):
            if path == nested_link:
                return True
            else:
                exists_(path)
        monkeypatch.setattr(os.path, 'exists', exists)
        list(process_line("--find-links=rel_path", req_file, 1,
                          finder=finder))
        assert finder.find_links == [nested_link]

    def test_relative_http_nested_req_files(self, finder, monkeypatch):
        """
        Test a relative nested req file path is joined with the req file url
        """
        req_file = 'http://me.com/me/req_file.txt'

        def parse(*args, **kwargs):
            return iter([])
        mock_parse = Mock()
        mock_parse.side_effect = parse
        monkeypatch.setattr(pip._internal.req.req_file, 'parse_requirements',
                            mock_parse)
        list(process_line("-r reqs.txt", req_file, 1, finder=finder))
        call = mock_parse.mock_calls[0]
        assert call[1][0] == 'http://me.com/me/reqs.txt'

    def test_relative_local_nested_req_files(self, finder, monkeypatch):
        """
        Test a relative nested req file path is joined with the req file dir
        """
        req_file = os.path.normpath('/path/req_file.txt')

        def parse(*args, **kwargs):
            return iter([])
        mock_parse = Mock()
        mock_parse.side_effect = parse
        monkeypatch.setattr(pip._internal.req.req_file, 'parse_requirements',
                            mock_parse)
        list(process_line("-r reqs.txt", req_file, 1, finder=finder))
        call = mock_parse.mock_calls[0]
        assert call[1][0] == os.path.normpath('/path/reqs.txt')

    def test_absolute_local_nested_req_files(self, finder, monkeypatch):
        """
        Test an absolute nested req file path
        """
        req_file = '/path/req_file.txt'

        def parse(*args, **kwargs):
            return iter([])
        mock_parse = Mock()
        mock_parse.side_effect = parse
        monkeypatch.setattr(pip._internal.req.req_file, 'parse_requirements',
                            mock_parse)
        list(process_line("-r /other/reqs.txt", req_file, 1, finder=finder))
        call = mock_parse.mock_calls[0]
        assert call[1][0] == '/other/reqs.txt'

    def test_absolute_http_nested_req_file_in_local(self, finder, monkeypatch):
        """
        Test a nested req file url in a local req file
        """
        req_file = '/path/req_file.txt'

        def parse(*args, **kwargs):
            return iter([])
        mock_parse = Mock()
        mock_parse.side_effect = parse
        monkeypatch.setattr(pip._internal.req.req_file, 'parse_requirements',
                            mock_parse)
        list(process_line("-r http://me.com/me/reqs.txt", req_file, 1,
                          finder=finder))
        call = mock_parse.mock_calls[0]
        assert call[1][0] == 'http://me.com/me/reqs.txt'

    def test_set_finder_process_dependency_links(self, finder):
        list(process_line(
            "--process-dependency-links", "file", 1, finder=finder))
        assert finder.process_dependency_links


class TestBreakOptionsArgs(object):

    def test_no_args(self):
        assert ('', '--option') == break_args_options('--option')

    def test_no_options(self):
        assert ('arg arg', '') == break_args_options('arg arg')

    def test_args_short_options(self):
        result = break_args_options('arg arg -s')
        assert ('arg arg', '-s') == result

    def test_args_long_options(self):
        result = break_args_options('arg arg --long')
        assert ('arg arg', '--long') == result


class TestOptionVariants(object):

    # this suite is really just testing optparse, but added it anyway

    def test_variant1(self, finder):
        list(process_line("-i url", "file", 1, finder=finder))
        assert finder.index_urls == ['url']

    def test_variant2(self, finder):
        list(process_line("-i 'url'", "file", 1, finder=finder))
        assert finder.index_urls == ['url']

    def test_variant3(self, finder):
        list(process_line("--index-url=url", "file", 1, finder=finder))
        assert finder.index_urls == ['url']

    def test_variant4(self, finder):
        list(process_line("--index-url url", "file", 1, finder=finder))
        assert finder.index_urls == ['url']

    def test_variant5(self, finder):
        list(process_line("--index-url='url'", "file", 1, finder=finder))
        assert finder.index_urls == ['url']


class TestParseRequirements(object):
    """tests for `parse_requirements`"""

    @pytest.mark.network
    def test_remote_reqs_parse(self):
        """
        Test parsing a simple remote requirements file
        """
        # this requirements file just contains a comment previously this has
        # failed in py3: https://github.com/pypa/pip/issues/760
        for req in parse_requirements(
                'https://raw.githubusercontent.com/pypa/'
                'pip-test-package/master/'
                'tests/req_just_comment.txt', session=PipSession()):
            pass

    def test_multiple_appending_options(self, tmpdir, finder, options):
        with open(tmpdir.join("req1.txt"), "w") as fp:
            fp.write("--extra-index-url url1 \n")
            fp.write("--extra-index-url url2 ")

        list(parse_requirements(tmpdir.join("req1.txt"), finder=finder,
                                session=PipSession(), options=options))

        assert finder.index_urls == ['url1', 'url2']

    def test_skip_regex(self, tmpdir, finder, options):
        options.skip_requirements_regex = '.*Bad.*'
        with open(tmpdir.join("req1.txt"), "w") as fp:
            fp.write("--extra-index-url Bad \n")
            fp.write("--extra-index-url Good ")

        list(parse_requirements(tmpdir.join("req1.txt"), finder=finder,
                                options=options, session=PipSession()))

        assert finder.index_urls == ['Good']

    def test_expand_existing_env_variables(self, tmpdir, finder):
        template = (
            'https://%s:x-oauth-basic@github.com/user/%s/archive/master.zip'
        )

        env_vars = (
            ('GITHUB_TOKEN', 'notarealtoken'),
            ('DO_12_FACTOR', 'awwyeah'),
        )

        with open(tmpdir.join('req1.txt'), 'w') as fp:
            fp.write(template % tuple(['${%s}' % k for k, _ in env_vars]))

        with patch('pip._internal.req.req_file.os.getenv') as getenv:
            getenv.side_effect = lambda n: dict(env_vars)[n]

            reqs = list(parse_requirements(
                tmpdir.join('req1.txt'),
                finder=finder,
                session=PipSession()
            ))

            assert len(reqs) == 1, \
                'parsing requirement file with env variable failed'

            expected_url = template % tuple([v for _, v in env_vars])
            assert reqs[0].link.url == expected_url, \
                'variable expansion in req file failed'

    def test_expand_missing_env_variables(self, tmpdir, finder):
        req_url = (
            'https://${NON_EXISTENT_VARIABLE}:$WRONG_FORMAT@'
            '%WINDOWS_FORMAT%github.com/user/repo/archive/master.zip'
        )

        with open(tmpdir.join('req1.txt'), 'w') as fp:
            fp.write(req_url)

        with patch('pip._internal.req.req_file.os.getenv') as getenv:
            getenv.return_value = ''

            reqs = list(parse_requirements(
                tmpdir.join('req1.txt'),
                finder=finder,
                session=PipSession()
            ))

            assert len(reqs) == 1, \
                'parsing requirement file with env variable failed'
            assert reqs[0].link.url == req_url, \
                'ignoring invalid env variable in req file failed'

    def test_join_lines(self, tmpdir, finder):
        with open(tmpdir.join("req1.txt"), "w") as fp:
            fp.write("--extra-index-url url1 \\\n--extra-index-url url2")

        list(parse_requirements(tmpdir.join("req1.txt"), finder=finder,
                                session=PipSession()))

        assert finder.index_urls == ['url1', 'url2']

    def test_req_file_parse_no_only_binary(self, data, finder):
        list(parse_requirements(
            data.reqfiles.join("supported_options2.txt"), finder,
            session=PipSession()))
        expected = FormatControl({'fred'}, {'wilma'})
        assert finder.format_control == expected

    def test_req_file_parse_comment_start_of_line(self, tmpdir, finder):
        """
        Test parsing comments in a requirements file
        """
        with open(tmpdir.join("req1.txt"), "w") as fp:
            fp.write("# Comment ")

        reqs = list(parse_requirements(tmpdir.join("req1.txt"), finder,
                    session=PipSession()))

        assert not reqs

    def test_req_file_parse_comment_end_of_line_with_url(self, tmpdir, finder):
        """
        Test parsing comments in a requirements file
        """
        with open(tmpdir.join("req1.txt"), "w") as fp:
            fp.write("https://example.com/foo.tar.gz # Comment ")

        reqs = list(parse_requirements(tmpdir.join("req1.txt"), finder,
                    session=PipSession()))

        assert len(reqs) == 1
        assert reqs[0].link.url == "https://example.com/foo.tar.gz"

    def test_req_file_parse_egginfo_end_of_line_with_url(self, tmpdir, finder):
        """
        Test parsing comments in a requirements file
        """
        with open(tmpdir.join("req1.txt"), "w") as fp:
            fp.write("https://example.com/foo.tar.gz#egg=wat")

        reqs = list(parse_requirements(tmpdir.join("req1.txt"), finder,
                    session=PipSession()))

        assert len(reqs) == 1
        assert reqs[0].name == "wat"

    def test_req_file_no_finder(self, tmpdir):
        """
        Test parsing a requirements file without a finder
        """
        with open(tmpdir.join("req.txt"), "w") as fp:
            fp.write("""
    --find-links https://example.com/
    --index-url https://example.com/
    --extra-index-url https://two.example.com/
    --no-use-wheel
    --no-index
            """)

        parse_requirements(tmpdir.join("req.txt"), session=PipSession())

    def test_install_requirements_with_options(self, tmpdir, finder, session,
                                               options):
        global_option = '--dry-run'
        install_option = '--prefix=/opt'

        content = '''
        --only-binary :all:
        INITools==2.0 --global-option="{global_option}" \
                        --install-option "{install_option}"
        '''.format(global_option=global_option, install_option=install_option)

        with requirements_file(content, tmpdir) as reqs_file:
            req = next(parse_requirements(reqs_file.abspath,
                                          finder=finder,
                                          options=options,
                                          session=session))

        req.source_dir = os.curdir
        with patch.object(subprocess, 'Popen') as popen:
            popen.return_value.stdout.readline.return_value = b""
            try:
                req.install([])
            except Exception:
                pass

            last_call = popen.call_args_list[-1]
            args = last_call[0][0]
            assert (
                0 < args.index(global_option) < args.index('install') <
                args.index(install_option)
            )
        assert options.format_control.no_binary == {':all:'}
        assert options.format_control.only_binary == set()

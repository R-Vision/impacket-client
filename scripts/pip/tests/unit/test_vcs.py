import pytest
from mock import Mock, patch
from pip._vendor.packaging.version import parse as parse_version

from pip._internal.vcs import RevOptions, VersionControl
from pip._internal.vcs.bazaar import Bazaar
from pip._internal.vcs.git import Git, looks_like_hash
from pip._internal.vcs.mercurial import Mercurial
from pip._internal.vcs.subversion import Subversion
from tests.lib import pyversion

if pyversion >= '3':
    VERBOSE_FALSE = False
else:
    VERBOSE_FALSE = 0


def test_rev_options_repr():
    rev_options = RevOptions(Git(), 'develop')
    assert repr(rev_options) == "<RevOptions git: rev='develop'>"


@pytest.mark.parametrize(('vcs', 'expected1', 'expected2', 'kwargs'), [
    # First check VCS-specific RevOptions behavior.
    (Bazaar(), [], ['-r', '123'], {}),
    (Git(), ['HEAD'], ['123'], {}),
    (Mercurial(), [], ['123'], {}),
    (Subversion(), [], ['-r', '123'], {}),
    # Test extra_args.  For this, test using a single VersionControl class.
    (Git(), ['HEAD', 'opt1', 'opt2'], ['123', 'opt1', 'opt2'],
        dict(extra_args=['opt1', 'opt2'])),
])
def test_rev_options_to_args(vcs, expected1, expected2, kwargs):
    """
    Test RevOptions.to_args().
    """
    assert RevOptions(vcs, **kwargs).to_args() == expected1
    assert RevOptions(vcs, '123', **kwargs).to_args() == expected2


def test_rev_options_to_display():
    """
    Test RevOptions.to_display().
    """
    # The choice of VersionControl class doesn't matter here since
    # the implementation is the same for all of them.
    vcs = Git()

    rev_options = RevOptions(vcs)
    assert rev_options.to_display() == ''

    rev_options = RevOptions(vcs, 'master')
    assert rev_options.to_display() == ' (to revision master)'


def test_rev_options_make_new():
    """
    Test RevOptions.make_new().
    """
    # The choice of VersionControl class doesn't matter here since
    # the implementation is the same for all of them.
    vcs = Git()

    rev_options = RevOptions(vcs, 'master', extra_args=['foo', 'bar'])
    new_options = rev_options.make_new('develop')

    assert new_options is not rev_options
    assert new_options.extra_args == ['foo', 'bar']
    assert new_options.rev == 'develop'
    assert new_options.vcs is vcs


@pytest.fixture
def git():
    git_url = 'https://github.com/pypa/pip-test-package'
    sha = '5547fa909e83df8bd743d3978d6667497983a4b7'
    git = Git()
    git.get_url = Mock(return_value=git_url)
    git.get_revision = Mock(return_value=sha)
    return git


@pytest.fixture
def dist():
    dist = Mock()
    dist.egg_name = Mock(return_value='pip_test_package')
    return dist


def test_looks_like_hash():
    assert looks_like_hash(40 * 'a')
    assert looks_like_hash(40 * 'A')
    # Test a string containing all valid characters.
    assert looks_like_hash(18 * 'a' + '0123456789abcdefABCDEF')
    assert not looks_like_hash(40 * 'g')
    assert not looks_like_hash(39 * 'a')


@pytest.mark.network
def test_git_get_src_requirements(git, dist):
    ret = git.get_src_requirement(dist, location='.')

    assert ret == ''.join([
        'git+https://github.com/pypa/pip-test-package',
        '@5547fa909e83df8bd743d3978d6667497983a4b7',
        '#egg=pip_test_package'
    ])


@patch('pip._internal.vcs.git.Git.get_revision_sha')
def test_git_resolve_revision_rev_exists(get_sha_mock):
    get_sha_mock.return_value = ('123456', False)
    git = Git()
    rev_options = git.make_rev_options('develop')

    url = 'git+https://git.example.com'
    new_options = git.resolve_revision('.', url, rev_options)
    assert new_options.rev == '123456'


@patch('pip._internal.vcs.git.Git.get_revision_sha')
def test_git_resolve_revision_rev_not_found(get_sha_mock):
    get_sha_mock.return_value = (None, False)
    git = Git()
    rev_options = git.make_rev_options('develop')

    url = 'git+https://git.example.com'
    new_options = git.resolve_revision('.', url, rev_options)
    assert new_options.rev == 'develop'


@patch('pip._internal.vcs.git.Git.get_revision_sha')
def test_git_resolve_revision_not_found_warning(get_sha_mock, caplog):
    get_sha_mock.return_value = (None, False)
    git = Git()

    url = 'git+https://git.example.com'
    sha = 40 * 'a'
    rev_options = git.make_rev_options(sha)
    new_options = git.resolve_revision('.', url, rev_options)
    assert new_options.rev == sha

    rev_options = git.make_rev_options(sha[:6])
    new_options = git.resolve_revision('.', url, rev_options)
    assert new_options.rev == 'aaaaaa'

    # Check that a warning got logged only for the abbreviated hash.
    messages = [r.getMessage() for r in caplog.records]
    messages = [msg for msg in messages if msg.startswith('Did not find ')]
    assert messages == [
        "Did not find branch or tag 'aaaaaa', assuming revision or ref."
    ]


@pytest.mark.parametrize('rev_name,result', (
    ('5547fa909e83df8bd743d3978d6667497983a4b7', True),
    ('5547fa909', False),
    ('5678', False),
    ('abc123', False),
    ('foo', False),
    (None, False),
))
def test_git_is_commit_id_equal(git, rev_name, result):
    """
    Test Git.is_commit_id_equal().
    """
    assert git.is_commit_id_equal('/path', rev_name) is result


# The non-SVN backends all use the same get_netloc_and_auth(), so only test
# Git as a representative.
@pytest.mark.parametrize('args, expected', [
    # Test a basic case.
    (('example.com', 'https'), ('example.com', (None, None))),
    # Test with username and password.
    (('user:pass@example.com', 'https'),
     ('user:pass@example.com', (None, None))),
])
def test_git__get_netloc_and_auth(args, expected):
    """
    Test VersionControl.get_netloc_and_auth().
    """
    netloc, scheme = args
    actual = Git().get_netloc_and_auth(netloc, scheme)
    assert actual == expected


@pytest.mark.parametrize('args, expected', [
    # Test https.
    (('example.com', 'https'), ('example.com', (None, None))),
    # Test https with username and no password.
    (('user@example.com', 'https'), ('example.com', ('user', None))),
    # Test https with username and password.
    (('user:pass@example.com', 'https'), ('example.com', ('user', 'pass'))),
    # Test ssh with username and password.
    (('user:pass@example.com', 'ssh'),
     ('user:pass@example.com', (None, None))),
])
def test_subversion__get_netloc_and_auth(args, expected):
    """
    Test Subversion.get_netloc_and_auth().
    """
    netloc, scheme = args
    actual = Subversion().get_netloc_and_auth(netloc, scheme)
    assert actual == expected


def test_git__get_url_rev__idempotent():
    """
    Check that Git.get_url_rev_and_auth() is idempotent for what the code calls
    "stub URLs" (i.e. URLs that don't contain "://").

    Also check that it doesn't change self.url.
    """
    url = 'git+git@git.example.com:MyProject#egg=MyProject'
    vcs = Git(url)
    result1 = vcs.get_url_rev_and_auth(url)
    assert vcs.url == url
    result2 = vcs.get_url_rev_and_auth(url)
    expected = ('git@git.example.com:MyProject', None, (None, None))
    assert result1 == expected
    assert result2 == expected


@pytest.mark.parametrize('url, expected', [
    ('svn+https://svn.example.com/MyProject',
     ('https://svn.example.com/MyProject', None, (None, None))),
    # Test a "+" in the path portion.
    ('svn+https://svn.example.com/My+Project',
     ('https://svn.example.com/My+Project', None, (None, None))),
])
def test_version_control__get_url_rev_and_auth(url, expected):
    """
    Test the basic case of VersionControl.get_url_rev_and_auth().
    """
    actual = VersionControl().get_url_rev_and_auth(url)
    assert actual == expected


@pytest.mark.parametrize('url', [
    'https://svn.example.com/MyProject',
    # Test a URL containing a "+" (but not in the scheme).
    'https://svn.example.com/My+Project',
])
def test_version_control__get_url_rev_and_auth__missing_plus(url):
    """
    Test passing a URL to VersionControl.get_url_rev_and_auth() with a "+"
    missing from the scheme.
    """
    with pytest.raises(ValueError) as excinfo:
        VersionControl().get_url_rev_and_auth(url)

    assert 'malformed VCS url' in str(excinfo.value)


@pytest.mark.parametrize('url, expected', [
    # Test http.
    ('bzr+http://bzr.myproject.org/MyProject/trunk/#egg=MyProject',
     'http://bzr.myproject.org/MyProject/trunk/'),
    # Test https.
    ('bzr+https://bzr.myproject.org/MyProject/trunk/#egg=MyProject',
     'https://bzr.myproject.org/MyProject/trunk/'),
    # Test ftp.
    ('bzr+ftp://bzr.myproject.org/MyProject/trunk/#egg=MyProject',
     'ftp://bzr.myproject.org/MyProject/trunk/'),
    # Test sftp.
    ('bzr+sftp://bzr.myproject.org/MyProject/trunk/#egg=MyProject',
     'sftp://bzr.myproject.org/MyProject/trunk/'),
    # Test launchpad.
    ('bzr+lp:MyLaunchpadProject#egg=MyLaunchpadProject',
     'lp:MyLaunchpadProject'),
    # Test ssh (special handling).
    ('bzr+ssh://bzr.myproject.org/MyProject/trunk/#egg=MyProject',
     'bzr+ssh://bzr.myproject.org/MyProject/trunk/'),
])
def test_bazaar__get_url_rev_and_auth(url, expected):
    """
    Test Bazaar.get_url_rev_and_auth().
    """
    bzr = Bazaar(url=url)
    actual = bzr.get_url_rev_and_auth(url)
    assert actual == (expected, None, (None, None))


@pytest.mark.parametrize('url, expected', [
    # Test an https URL.
    ('svn+https://svn.example.com/MyProject#egg=MyProject',
     ('https://svn.example.com/MyProject', None, (None, None))),
    # Test an https URL with a username and password.
    ('svn+https://user:pass@svn.example.com/MyProject#egg=MyProject',
     ('https://svn.example.com/MyProject', None, ('user', 'pass'))),
    # Test an ssh URL.
    ('svn+ssh://svn.example.com/MyProject#egg=MyProject',
     ('svn+ssh://svn.example.com/MyProject', None, (None, None))),
    # Test an ssh URL with a username.
    ('svn+ssh://user@svn.example.com/MyProject#egg=MyProject',
     ('svn+ssh://user@svn.example.com/MyProject', None, (None, None))),
])
def test_subversion__get_url_rev_and_auth(url, expected):
    """
    Test Subversion.get_url_rev_and_auth().
    """
    actual = Subversion().get_url_rev_and_auth(url)
    assert actual == expected


# The non-SVN backends all use the same make_rev_args(), so only test
# Git as a representative.
@pytest.mark.parametrize('username, password, expected', [
    (None, None, []),
    ('user', None, []),
    ('user', 'pass', []),
])
def test_git__make_rev_args(username, password, expected):
    """
    Test VersionControl.make_rev_args().
    """
    actual = Git().make_rev_args(username, password)
    assert actual == expected


@pytest.mark.parametrize('username, password, expected', [
    (None, None, []),
    ('user', None, ['--username', 'user']),
    ('user', 'pass', ['--username', 'user', '--password', 'pass']),
])
def test_subversion__make_rev_args(username, password, expected):
    """
    Test Subversion.make_rev_args().
    """
    actual = Subversion().make_rev_args(username, password)
    assert actual == expected


def test_subversion__get_url_rev_options():
    """
    Test Subversion.get_url_rev_options().
    """
    url = 'svn+https://user:pass@svn.example.com/MyProject@v1.0#egg=MyProject'
    url, rev_options = Subversion().get_url_rev_options(url)
    assert url == 'https://svn.example.com/MyProject'
    assert rev_options.rev == 'v1.0'
    assert rev_options.extra_args == (
        ['--username', 'user', '--password', 'pass']
    )


def test_get_git_version():
    git_version = Git().get_git_version()
    assert git_version >= parse_version('1.0.0')

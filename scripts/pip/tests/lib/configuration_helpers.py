"""Helpers for tests that check configuration
"""

import contextlib
import functools
import os
import tempfile
import textwrap

import pip._internal.configuration
from pip._internal.utils.misc import ensure_dir

# This is so that tests don't need to import pip.configuration
kinds = pip._internal.configuration.kinds


class ConfigurationMixin(object):

    def setup(self):
        self.configuration = pip._internal.configuration.Configuration(
            isolated=False,
        )
        self._files_to_clear = []

        self._old_environ = os.environ.copy()

    def teardown(self):
        for fname in self._files_to_clear:
            fname.stop()

        os.environ = self._old_environ

    def patch_configuration(self, variant, di):
        old = self.configuration._load_config_files

        @functools.wraps(old)
        def overidden():
            # Manual Overload
            self.configuration._config[variant].update(di)
            self.configuration._parsers[variant].append((None, None))
            return old()

        self.configuration._load_config_files = overidden

    @contextlib.contextmanager
    def tmpfile(self, contents):
        # Create a temporary file
        fd, path = tempfile.mkstemp(
            prefix="pip_", suffix="_config.ini", text=True
        )
        os.close(fd)

        contents = textwrap.dedent(contents).lstrip()
        ensure_dir(os.path.dirname(path))
        with open(path, "w") as f:
            f.write(contents)

        yield path

        os.remove(path)

    @staticmethod
    def get_file_contents(path):
        with open(path) as f:
            return f.read()

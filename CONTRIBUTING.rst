Releases and Changelog
----------------------

We use `auto <https://intuit.github.io/auto/>`_ (triggered via GitHub Actions)
to generate the changelog and automatically release the project.  Changelog
entries are generated from pull request titles and classified using pull
request labels.  Every PR should therefore have a label; unlabelled PRs are
treated as though they had the "semver-patch" label by default.

The following pull request labels are recognized (see ``.autorc``):

* semver-major: Increment the major version when merged
* semver-minor: Increment the minor version when merged
* semver-patch: Increment the patch version when merged
* release: Create a release when this PR is merged
* semver-internal: Changes only affect the internal API
* semver-documentation: Changes only affect the documentation
* semver-tests: Add or improve existing tests
* semver-dependencies: Update one or more dependencies version
* semver-performance: Improve performance of an existing feature


Precommit
---------

The project uses a number of automated checks to limit tedious work.  The
checks will be run automatically prior to commit if `pre-commit
<https://pre-commit.com>`_ is installed in your environment.

One of them is a code duplication check (`jscpd <https://jscpd.dev>`_,
configured in ``.jscpd.json``) with a 0% threshold: any repeated block of 5 or
more lines fails it.
Factor the repetition out (a helper, or ``pytest.mark.parametrize`` in tests),
or, if it is intended, raise ``minTokens``/``minLines`` or add an ignore in
``.jscpd.json``.
The hook scans the whole working tree, so untracked files that git does not
ignore count too.
Its Linux wheels need glibc 2.34 or newer; where it cannot install, skip it
locally with ``SKIP=jscpd git commit ...``, since pre-commit.ci still runs it
on every pull request.


Installation
------------

When installing from a remote fork (such as from primary maintainer @asmacdo), it is possible that the branch to be installed locally does not have any Git tags.

This confuses the `versioningit` tool, which is used by `pip` to set package versions based on these tags, which can cause `pip install` to fail with various errors.

To resolve this, manually link the upstream and pull all tags::

    git remote add upstream https://github.com/con/duct
    git fetch upstream



Testing
-------
If you are contributing code, please consider adding a unit test.

To run the tests::

    tox

To run tests on one file (args after ``--`` are passed to pytest)::

    tox -- test/test_my_thing.py

It is also possible to use pytest directly, but you will need to override the options passed from
`tox.ini` with `addopts`. Invocation in this way can be faster while developing::

    python -m pytest -o addopts="" test/test_thething.py::specific_test

Some tests need the ``setsid`` command and are skipped where it is missing.
macOS does not ship it; to run those tests there, install util-linux and put it on ``PATH``::

    brew install util-linux
    export PATH="$(brew --prefix util-linux)/bin:$PATH"

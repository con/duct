Releases and Changelog
----------------------

We use `auto <https://intuit.github.io/auto/>`_ (triggered via GitHub Actions)
to generate the changelog and automatically release the project.  Changelog
entries are generated from pull request titles and classified using pull
request labels.  Every PR should therefore have a label; unlabelled PRs are
treated as though they had the "patch" label by default.

The following pull request labels are recognized:

* major: Increment the major version when merged
* minor: Increment the minor version when merged
* patch: Increment the patch version when merged
* skip-release: Preserve the current version when merged
* release: Create a release when this PR is merged
* internal: Changes only affect the internal API
* documentation: Changes only affect the documentation
* tests: Add or improve existing tests
* dependencies: Update one or more dependencies version
* performance: Improve performance of an existing feature


Precommit
---------

The project uses a number of automated checks to limit tedious work.  The
checks will be run automatically prior to commit if `pre-commit
<https://pre-commit.com>`_ is installed in your environment.


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

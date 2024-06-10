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

Note: ``README.md`` is automatically updated to include the help text, but
because argparse changed its output in Python 3.10+, CI enforces the 3.10+ help
text.  Please either use 3.10+ or drop the "optional arguments" vs "options"
diff.


Testing
-------
If you are contributing code, please consider adding a unit test.

To run the tests::

    tox

To run tests on one file (args after ``--`` are passed to pytest)::

    tox -- test/test_my_thing.py

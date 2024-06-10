Releases and Changelog
----------------------

We use the `auto <https://intuit.github.io/auto/>`_ tool to generate the changelog and automatically release the project.

`auto` is used in by GitHub actions, which monitors the labels on the pull request.
This automation can add entries to the changelog, cut releases, and
push new images to `dockerhub <https://hub.docker.com/r/centerforopenneuroscience/duct>`_.

The following pull request labels are respected:

    * major: Increment the major version when merged
    * minor: Increment the minor version when merged
    * patch: Increment the patch version when merged
    * skip-release: Preserve the current version when merged
    * release: Create a release when this pr is merged
    * internal: Changes only affect the internal API
    * documentation: Changes only affect the documentation
    * tests: Add or improve existing tests
    * dependencies: Update one or more dependencies version
    * performance: Improve performance of an existing feature


Precommit
---------

The project uses a number of automated checks to limit tedious work.
The checks will be run automatically prior to commit if `pre-commit` is installed in your
environment.

`pip install pre-commit`

Note: the README.md is automatically updated to include the helptext, but because argparse changed its
output in python 3.10+, CI enforces the 3.10+ helptext.
Please either use 3.10+ or drop the `optional arguments` vs `options` diff.


Testing
-------
If you are contributing code, please consider adding a unit test.

To run the tests:
`tox`

To run tests on one file (args after -- are passed to pytest):
`tox -- test/test_my_thing.py`

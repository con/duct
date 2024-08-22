# v0.2.0 (Thurs Aug 22 2024)

 #### 🚀 Enhancement

- Add log level NONE and deprecate quiet [#159](https://github.com/con/duct/pull/159) ([@asmacdo](https://github.com/asmacdo))
- Collect hostname in sys info [#153](https://github.com/con/duct/pull/153) ([@asmacdo](https://github.com/asmacdo))
- RF+BF: make explicit wall_clock_time separate from elapsed_time [#141](https://github.com/con/duct/pull/141) ([@yarikoptic](https://github.com/yarikoptic))
- RF: Add logging, dissolve duct_print (INFO level), add CLI option -l, dissolve --quiet [#140](https://github.com/con/duct/pull/140) ([@yarikoptic](https://github.com/yarikoptic))
- ENH: give "typical" shell behavior when command is not found to be executed [#138](https://github.com/con/duct/pull/138) ([@yarikoptic](https://github.com/yarikoptic))
- Use None rather than 0 prior to measurement [#135](https://github.com/con/duct/pull/135) ([@asmacdo](https://github.com/asmacdo))
- RF+ENH: output messages to stderr not stdout + move printing out of "controllers/models" [#136](https://github.com/con/duct/pull/136) ([@yarikoptic](https://github.com/yarikoptic))
- Remove units for machine readability [#125](https://github.com/con/duct/pull/125) ([@asmacdo](https://github.com/asmacdo))
- Make execute return returncode of the process and use it for duct CLI process exit code [#119](https://github.com/con/duct/pull/119) ([@yarikoptic](https://github.com/yarikoptic))

#### 🐛 Bug Fix

- Add direct pytest usage to CONTRIBUTING [#161](https://github.com/con/duct/pull/161) ([@asmacdo](https://github.com/asmacdo))
- Improve helptext top-level description [#158](https://github.com/con/duct/pull/158) ([@asmacdo](https://github.com/asmacdo))
- Check that each PR has one of the semver labels [#156](https://github.com/con/duct/pull/156) ([@asmacdo](https://github.com/asmacdo))
- Do not use setsid directly, use dedicated start_new_session [#155](https://github.com/con/duct/pull/155) ([@yarikoptic](https://github.com/yarikoptic))
- Disable MacOS tests [#151](https://github.com/con/duct/pull/151) ([@asmacdo](https://github.com/asmacdo))
- Fix pmem calculation [#151](https://github.com/con/duct/pull/151) ([@asmacdo](https://github.com/asmacdo))
- Collect sys info and env in parallel [#152](https://github.com/con/duct/pull/152) ([@asmacdo](https://github.com/asmacdo))
- Fix GPU info collection [#147](https://github.com/con/duct/pull/147) ([@asmacdo](https://github.com/asmacdo) [@yarikoptic](https://github.com/yarikoptic))
- RF+BF: update maxes on each sample, more logging during monitoring [#146](https://github.com/con/duct/pull/146) ([@yarikoptic](https://github.com/yarikoptic))
- RF: no shebang since file is no longer can be executed [#139](https://github.com/con/duct/pull/139) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 2

- Austin Macdonald ([@asmacdo](https://github.com/asmacdo))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

# v0.1.1 (Wed Jul 31 2024)

#### 🐛 Bug Fix

- SC_PAGESIZE should work on macOS and Linux [#115](https://github.com/con/duct/pull/115) ([@asmacdo](https://github.com/asmacdo))

#### Authors: 1

- Austin Macdonald ([@asmacdo](https://github.com/asmacdo))

---

# v0.1.0 (Mon Jul 29 2024)

#### 🚀 Enhancement

- Fixup autorc syntax [#110](https://github.com/con/duct/pull/110) ([@asmacdo](https://github.com/asmacdo))
- Explain totals [#110](https://github.com/con/duct/pull/110) ([@asmacdo](https://github.com/asmacdo))
- Fix test [#110](https://github.com/con/duct/pull/110) ([@asmacdo](https://github.com/asmacdo))
- Improve usage.json schema [#110](https://github.com/con/duct/pull/110) ([@asmacdo](https://github.com/asmacdo))

#### 🐛 Bug Fix

- Use datalad labels to avoid future collision with Dependabot [#113](https://github.com/con/duct/pull/113) ([@asmacdo](https://github.com/asmacdo))
- release on PR merge [#113](https://github.com/con/duct/pull/113) ([@asmacdo](https://github.com/asmacdo))
- Prepare for auto-powered releases [#113](https://github.com/con/duct/pull/113) ([@asmacdo](https://github.com/asmacdo))
- sorted + output-capture [#112](https://github.com/con/duct/pull/112) ([@asmacdo](https://github.com/asmacdo))
- Add pypi keywords [#112](https://github.com/con/duct/pull/112) ([@asmacdo](https://github.com/asmacdo))
- Fixup ignore new location of egginfo [#112](https://github.com/con/duct/pull/112) ([@asmacdo](https://github.com/asmacdo))

#### ⚠️ Pushed to `main`

- Update README for release ([@asmacdo](https://github.com/asmacdo))

#### Authors: 1

- Austin Macdonald ([@asmacdo](https://github.com/asmacdo))

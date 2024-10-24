# v0.7.1 (Thu Oct 24 2024)

#### 🐛 Bug Fix

- Persistently open usage file until the end and open info as "w" not "a" [#209](https://github.com/con/duct/pull/209) ([@yarikoptic](https://github.com/yarikoptic) [@asmacdo](https://github.com/asmacdo))

#### Authors: 2

- Austin Macdonald ([@asmacdo](https://github.com/asmacdo))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# v0.7.0 (Thu Oct 24 2024)

#### 🚀 Enhancement

- Rm num_samples & num_reports from summary_format [#200](https://github.com/con/duct/pull/200) ([@asmacdo](https://github.com/asmacdo))
- Add start and end time to info.json [#201](https://github.com/con/duct/pull/201) ([@asmacdo](https://github.com/asmacdo))

#### Authors: 1

- Austin Macdonald ([@asmacdo](https://github.com/asmacdo))

---

# v0.6.0 (Mon Oct 14 2024)

#### 🚀 Enhancement

- Drop Python 3.8, which is EOL [#199](https://github.com/con/duct/pull/199) ([@asmacdo](https://github.com/asmacdo))
- Create structure for full con-duct suite [#164](https://github.com/con/duct/pull/164) ([@asmacdo](https://github.com/asmacdo))
- Add ps stat counter [#182](https://github.com/con/duct/pull/182) ([@asmacdo](https://github.com/asmacdo))

#### 🐛 Bug Fix

- Explicitly mention con-duct command in the summary [#204](https://github.com/con/duct/pull/204) ([@asmacdo](https://github.com/asmacdo))
- BF: Do not rely on having sources under ./src and __main__.py to be executable [#196](https://github.com/con/duct/pull/196) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 2

- Austin Macdonald ([@asmacdo](https://github.com/asmacdo))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# v0.5.0 (Wed Oct 02 2024)

#### 🚀 Enhancement

- Report $USER as .user, and store actual numeric UID as .uid [#195](https://github.com/con/duct/pull/195) ([@yarikoptic](https://github.com/yarikoptic))
- Move all logic into single file [#191](https://github.com/con/duct/pull/191) ([@asmacdo](https://github.com/asmacdo))

#### Authors: 2

- Austin Macdonald ([@asmacdo](https://github.com/asmacdo))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# v0.4.0 (Mon Sep 30 2024)

#### 🚀 Enhancement

- Add custom formatter conversion flags and colors based on datalad ls [#183](https://github.com/con/duct/pull/183) ([@yarikoptic](https://github.com/yarikoptic) [@asmacdo](https://github.com/asmacdo))

#### Authors: 2

- Austin Macdonald ([@asmacdo](https://github.com/asmacdo))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# v0.3.1 (Fri Sep 20 2024)

#### 🐛 Bug Fix

- BF: Fix sample aggregation [#180](https://github.com/con/duct/pull/180) ([@asmacdo](https://github.com/asmacdo))
- Fix operator precedence involving or and addition [#179](https://github.com/con/duct/pull/179) ([@asmacdo](https://github.com/asmacdo))

#### Authors: 1

- Austin Macdonald ([@asmacdo](https://github.com/asmacdo))

---

# v0.3.0 (Thu Sep 12 2024)

#### 🚀 Enhancement

- (Re)add etime and cmd into process stats [#175](https://github.com/con/duct/pull/175) ([@asmacdo](https://github.com/asmacdo))
- Modify exit code if cmd terminated by signal [#169](https://github.com/con/duct/pull/169) ([@asmacdo](https://github.com/asmacdo))
- Add output files and schema version to info.json [#168](https://github.com/con/duct/pull/168) ([@asmacdo](https://github.com/asmacdo))

#### 🐛 Bug Fix

- Catchup to actual version for auto releases [#177](https://github.com/con/duct/pull/177) ([@asmacdo](https://github.com/asmacdo))
- Argparse abbreviation affects and breaks cmd args [#167](https://github.com/con/duct/pull/167) ([@asmacdo](https://github.com/asmacdo))
- Add tests for correct handling of args [#166](https://github.com/con/duct/pull/166) ([@asmacdo](https://github.com/asmacdo))

#### Authors: 1

- Austin Macdonald ([@asmacdo](https://github.com/asmacdo))

---

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

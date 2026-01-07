# v0.19.0 (Wed Jan 07 2026)

#### 🚀 Enhancement

- Added Mac (M-series) support [#351](https://github.com/con/duct/pull/351) (codycbakerphd@gmail.com [@CodyCBakerPhD](https://github.com/CodyCBakerPhD) [@asmacdo](https://github.com/asmacdo))
- Add --reverse option to con-duct ls command [#308](https://github.com/con/duct/pull/308) ([@asmacdo](https://github.com/asmacdo) [@yarikoptic](https://github.com/yarikoptic))

#### 🐛 Bug Fix

- Fix formatting for upstream linking instructions [#360](https://github.com/con/duct/pull/360) ([@CodyCBakerPhD](https://github.com/CodyCBakerPhD))
- filter pyparsing deprecation warnings instead of pinning [#355](https://github.com/con/duct/pull/355) ([@asmacdo](https://github.com/asmacdo))
- pin pyparsing for oldestdeps environment [#353](https://github.com/con/duct/pull/353) ([@asmacdo](https://github.com/asmacdo))

#### 🏠 Internal

- Improve handler of SIGINT signals [#357](https://github.com/con/duct/pull/357) ([@candleindark](https://github.com/candleindark))

#### Authors: 5

- Austin Macdonald ([@asmacdo](https://github.com/asmacdo))
- Cody Baker ([@CodyCBakerPhD](https://github.com/CodyCBakerPhD))
- CodyCBakerPhD (codycbakerphd@gmail.com)
- Isaac To ([@candleindark](https://github.com/candleindark))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# v0.18.0 (Mon Dec 15 2025)

#### 🚀 Enhancement

- Add matplotlib backwards compatibility to 3.5 [#322](https://github.com/con/duct/pull/322) ([@asmacdo](https://github.com/asmacdo))
- Add dotenv config [#333](https://github.com/con/duct/pull/333) ([@asmacdo](https://github.com/asmacdo))
- Use jsonl suffix [#345](https://github.com/con/duct/pull/345) ([@asmacdo](https://github.com/asmacdo))
- Modernize python [#346](https://github.com/con/duct/pull/346) ([@asmacdo](https://github.com/asmacdo))
- Combine clis [#327](https://github.com/con/duct/pull/327) ([@asmacdo](https://github.com/asmacdo))

#### 🐛 Bug Fix

- Skip test_permission_denied_handling when running as root [#349](https://github.com/con/duct/pull/349) ([@Copilot](https://github.com/Copilot) [@actions-user](https://github.com/actions-user) [@asmacdo](https://github.com/asmacdo))
- Reorganize tests [#329](https://github.com/con/duct/pull/329) ([@asmacdo](https://github.com/asmacdo))
- Add installation instructions for remote forks [#337](https://github.com/con/duct/pull/337) ([@CodyCBakerPhD](https://github.com/CodyCBakerPhD))
- remove rpds pin for non-pypy [#334](https://github.com/con/duct/pull/334) ([@asmacdo](https://github.com/asmacdo))
- Add demo and reference plot example in README [#310](https://github.com/con/duct/pull/310) ([@asmacdo](https://github.com/asmacdo))
- pin rpds-py so pypy 3.10 tests pass [#331](https://github.com/con/duct/pull/331) ([@asmacdo](https://github.com/asmacdo))
- Revert mergify integration (PRs #270 and #271) [#328](https://github.com/con/duct/pull/328) ([@asmacdo](https://github.com/asmacdo))
- test: Make tests invoke at least with INFO level so we see what is wrong [#321](https://github.com/con/duct/pull/321) ([@yarikoptic](https://github.com/yarikoptic))
- fix: plot usage with info.json abs path [#301](https://github.com/con/duct/pull/301) ([@asmacdo](https://github.com/asmacdo))
- Add CLAUDE.md for reusable base prompt for claude code [#307](https://github.com/con/duct/pull/307) ([@yarikoptic](https://github.com/yarikoptic) [@actions-user](https://github.com/actions-user))

#### Authors: 5

- [@actions-user](https://github.com/actions-user)
- [@Copilot](https://github.com/Copilot)
- Austin Macdonald ([@asmacdo](https://github.com/asmacdo))
- Cody Baker ([@CodyCBakerPhD](https://github.com/CodyCBakerPhD))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# v0.17.0 (Thu Sep 18 2025)

#### 🚀 Enhancement

- enh: Human-readable axis values/units on con-duct plots [#302](https://github.com/con/duct/pull/302) ([@asmacdo](https://github.com/asmacdo))

#### 🐛 Bug Fix

- plot: allow for -o in addition to --output [#300](https://github.com/con/duct/pull/300) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 2

- Austin Macdonald ([@asmacdo](https://github.com/asmacdo))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# v0.16.0 (Fri Sep 05 2025)

#### 🚀 Enhancement

- Change: Replace print statements with logger for error handling [#296](https://github.com/con/duct/pull/296) ([@asmacdo](https://github.com/asmacdo))
- Handle noninteractive matplotlib backends [#293](https://github.com/con/duct/pull/293) ([@asmacdo](https://github.com/asmacdo))
- con-duct plot should accept info.json in addition to usage.json [#292](https://github.com/con/duct/pull/292) ([@asmacdo](https://github.com/asmacdo))

#### 🐛 Bug Fix

- Test against pre-release of 3.14 [#230](https://github.com/con/duct/pull/230) ([@yarikoptic](https://github.com/yarikoptic) [@asmacdo](https://github.com/asmacdo))
- List a version in "duct is executing" log message [#295](https://github.com/con/duct/pull/295) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 2

- Austin Macdonald ([@asmacdo](https://github.com/asmacdo))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# v0.15.0 (Fri Aug 15 2025)

#### 🚀 Enhancement

- add --messsage/-m and store in info.json [#285](https://github.com/con/duct/pull/285) ([@asmacdo](https://github.com/asmacdo))
- empty info files detected with con-duct ls should have debug message, not warnings [#284](https://github.com/con/duct/pull/284) ([@asmacdo](https://github.com/asmacdo))
- 228 human readable pp [#286](https://github.com/con/duct/pull/286) ([@asmacdo](https://github.com/asmacdo))

#### Authors: 1

- Austin Macdonald ([@asmacdo](https://github.com/asmacdo))

---

# v0.14.1 (Fri Aug 15 2025)

#### 🐛 Bug Fix

- fix: pypy-310 can sometimes produce empty usage files [#287](https://github.com/con/duct/pull/287) ([@asmacdo](https://github.com/asmacdo))

#### Authors: 1

- Austin Macdonald ([@asmacdo](https://github.com/asmacdo))

---

# v0.14.0 (Wed Aug 13 2025)

#### 🚀 Enhancement

- Current session mode [#283](https://github.com/con/duct/pull/283) ([@asmacdo](https://github.com/asmacdo))
- enh: add --version to con-duct [#280](https://github.com/con/duct/pull/280) ([@asmacdo](https://github.com/asmacdo))

#### 🐛 Bug Fix

- remove development artifact [#282](https://github.com/con/duct/pull/282) ([@asmacdo](https://github.com/asmacdo))
- auto push cleanup to PRs [#275](https://github.com/con/duct/pull/275) ([@asmacdo](https://github.com/asmacdo) [@actions-user](https://github.com/actions-user))
- Reduce flake: increase test_spawn_children sleep dur and add retries [#277](https://github.com/con/duct/pull/277) ([@asmacdo](https://github.com/asmacdo))
- bf: define pyci environment and there add pytest-mergify as dependency [#271](https://github.com/con/duct/pull/271) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 3

- [@actions-user](https://github.com/actions-user)
- Austin Macdonald ([@asmacdo](https://github.com/asmacdo))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# v0.13.2 (Fri May 09 2025)

#### 🐛 Bug Fix

- Allow con-duct ls to function back to schema 0.2.0 [#269](https://github.com/con/duct/pull/269) ([@asmacdo](https://github.com/asmacdo))
- Bolt on mergify support to get summaries from CI reported [#270](https://github.com/con/duct/pull/270) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 2

- Austin Macdonald ([@asmacdo](https://github.com/asmacdo))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# v0.13.1 (Tue May 06 2025)

#### 🐛 Bug Fix

- Test fix conda feedstock [#268](https://github.com/con/duct/pull/268) ([@asmacdo](https://github.com/asmacdo))
- Bugfix: do not truncate ps output [#267](https://github.com/con/duct/pull/267) ([@asmacdo](https://github.com/asmacdo))

#### Authors: 1

- Austin Macdonald ([@asmacdo](https://github.com/asmacdo))

---

# v0.13.0 (Fri May 02 2025)

#### 🚀 Enhancement

- Collect working directory for execution summary [#264](https://github.com/con/duct/pull/264) ([@asmacdo](https://github.com/asmacdo))
- Pass Ctrl+c interrupt to executed command [#260](https://github.com/con/duct/pull/260) ([@asmacdo](https://github.com/asmacdo))

#### 🐛 Bug Fix

- Add blog link to README [#265](https://github.com/con/duct/pull/265) ([@asmacdo](https://github.com/asmacdo))
- test: test various spawned children e2e cases [#258](https://github.com/con/duct/pull/258) ([@asmacdo](https://github.com/asmacdo))

#### Authors: 1

- Austin Macdonald ([@asmacdo](https://github.com/asmacdo))

---

# v0.12.0 (Wed Mar 12 2025)

#### 🚀 Enhancement

- Use versioningit for --version [#251](https://github.com/con/duct/pull/251) ([@asmacdo](https://github.com/asmacdo))

#### 🐛 Bug Fix

- When using pyout, use pyout color [#257](https://github.com/con/duct/pull/257) ([@asmacdo](https://github.com/asmacdo))

#### Authors: 1

- Austin Macdonald ([@asmacdo](https://github.com/asmacdo))

---

# v0.11.0 (Tue Mar 04 2025)

#### 🚀 Enhancement

- Add con-duct --log-levels [#253](https://github.com/con/duct/pull/253) ([@asmacdo](https://github.com/asmacdo))
- Add --eval-filter [#241](https://github.com/con/duct/pull/241) ([@asmacdo](https://github.com/asmacdo) [@yarikoptic](https://github.com/yarikoptic))

#### 🐛 Bug Fix

- docs: add RRID badge to README [#254](https://github.com/con/duct/pull/254) ([@asmacdo](https://github.com/asmacdo))
- Implement and use packaging.Version replacement [#247](https://github.com/con/duct/pull/247) ([@asmacdo](https://github.com/asmacdo))
- Add test: ls field list should contain all info.json fields [#243](https://github.com/con/duct/pull/243) ([@asmacdo](https://github.com/asmacdo))
- ls --help: list fields only once [#250](https://github.com/con/duct/pull/250) ([@asmacdo](https://github.com/asmacdo))
- bf: yaml should be optional [#248](https://github.com/con/duct/pull/248) ([@asmacdo](https://github.com/asmacdo))
- Fixup: blacken [#249](https://github.com/con/duct/pull/249) ([@asmacdo](https://github.com/asmacdo))

#### Authors: 2

- Austin Macdonald ([@asmacdo](https://github.com/asmacdo))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# v0.10.1 (Fri Feb 07 2025)

#### 🐛 Bug Fix

- bf: show ls results when no positional args given [#240](https://github.com/con/duct/pull/240) ([@asmacdo](https://github.com/asmacdo))

#### Authors: 1

- Austin Macdonald ([@asmacdo](https://github.com/asmacdo))

---

# v0.10.0 (Fri Feb 07 2025)

#### 🚀 Enhancement

- con-duct ls [#224](https://github.com/con/duct/pull/224) ([@asmacdo](https://github.com/asmacdo))

#### 🐛 Bug Fix

- Test abandoning parent [#226](https://github.com/con/duct/pull/226) ([@asmacdo](https://github.com/asmacdo) [@yarikoptic](https://github.com/yarikoptic))
- Fix issue where pillow fails to install on pypy 3.9 [#233](https://github.com/con/duct/pull/233) ([@asmacdo](https://github.com/asmacdo))
- Add Fail time unit [#229](https://github.com/con/duct/pull/229) ([@asmacdo](https://github.com/asmacdo))

#### Authors: 2

- Austin Macdonald ([@asmacdo](https://github.com/asmacdo))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# v0.9.0 (Tue Dec 03 2024)

#### 🚀 Enhancement

- Add --fail-time option and by default remove all outputs if command fails fast [#227](https://github.com/con/duct/pull/227) ([@yarikoptic](https://github.com/yarikoptic))

#### 🐛 Bug Fix

- Add FAQ with a question on git-annex and large files [#225](https://github.com/con/duct/pull/225) ([@yarikoptic](https://github.com/yarikoptic))
- Add released auto plugin to mark issues with releases where they were fixed [#216](https://github.com/con/duct/pull/216) ([@yarikoptic](https://github.com/yarikoptic))
- ENH/BF: render floats only to 2 digits after . . Allow for composing format + conversion [#214](https://github.com/con/duct/pull/214) ([@yarikoptic](https://github.com/yarikoptic))
- Various enhancements for plot command [#217](https://github.com/con/duct/pull/217) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 1

- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# v0.8.0 (Thu Oct 24 2024)

#### 🚀 Enhancement

- Add testing for Python 3.13 [#202](https://github.com/con/duct/pull/202) ([@asmacdo](https://github.com/asmacdo))
- Add `con-duct plot` with matplotlib backend [#198](https://github.com/con/duct/pull/198) ([@asmacdo](https://github.com/asmacdo))

#### Authors: 1

- Austin Macdonald ([@asmacdo](https://github.com/asmacdo))

---

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

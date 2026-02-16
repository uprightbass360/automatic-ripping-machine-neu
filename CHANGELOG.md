# Changelog


## Current pre-release v2.5.0
  - Only one large item for this version.

    Now added the possibility for users to use [TMDB](https://developers.themoviedb.org/3/getting-started/introduction) as their metadata provider, this only works for movies at the moment. 
    In time this will have the same functionality as OMDB (movies and tv shows)
    The idea driving this is that users should be able to choose their metadata provider.
    I also think this is safer route in the long term, its better to have multiple options than only focus on one provider.
    
    - Added method to let users send/submit their correctly identified movies to a new crc64 API (an api key required)
    - Added check for crc64 from remote database

## [1.2.2](https://github.com/uprightbass360/automatic-ripping-machine-neu/compare/v1.2.1...v1.2.2) (2026-02-16)


### Bug Fixes

* bump Flask-WTF to 1.2.2 for Flask 3.x compatibility ([5462e38](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/5462e388f34bae19f4ae6f64c188e3bd2593044b))
* bump itsdangerous and Werkzeug for Flask 3.1.2 compatibility ([adb4dda](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/adb4dda9635beaf1eae991123fa4305dc72fe4a1))
* drop Python 3.9 from CI matrix (alembic 1.18 requires &gt;=3.10) ([6ffd19b](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/6ffd19b5609afe209e1c25d44100f7b6ab4e125d))

## [1.2.1](https://github.com/uprightbass360/automatic-ripping-machine-neu/compare/v1.2.0...v1.2.1) (2026-02-16)


### Bug Fixes

* use PAT for release-please so releases trigger publish workflow ([c060ec1](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/c060ec1c8b9f343fd21245043512bca60a3c32d0))

## [1.2.0](https://github.com/uprightbass360/automatic-ripping-machine-neu/compare/v1.1.0...v1.2.0) (2026-02-16)


### Features

* add release bundle workflow to publish deploy zip as release asset ([9c27280](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/9c27280f0c9b3b819ceb4cf6065d133b7758fd4d))
* auto-update submodules on component releases ([5208420](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/5208420f12bc8f590a183e05099f8e052a2789d9))


### Bug Fixes

* build ARM from source in remote-transcoder compose, enable devices ([1a472ad](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/1a472adc734d495319a3a27e170c46ced573691f))
* correct Docker Hub image names for UI and transcoder ([4f0ec61](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/4f0ec61dcfd0e5b5c5e45486b96b014e62235c6f))

## [1.1.0](https://github.com/uprightbass360/automatic-ripping-machine-neu/compare/v1.0.0...v1.1.0) (2026-02-15)


### Features

* add AppState model for global ripping pause control ([f4b600c](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/f4b600ca5b400538cd3a47ff4dbcb956ca1a2c38))
* add Docker Compose orchestration for multi-service deployment ([5200d42](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/5200d42d2243f78bedadca864b9c25c139a9761d))
* Add drives API endpoint and harden drive matching logic ([4720cea](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/4720ceab36fc5353630fdd2c7060942fe8445639))
* Add REST API layer at /api/v1/ ([3ce2d7b](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/3ce2d7b7d1182f31ff8ae89d64098e913ac6e849))
* add system monitoring, ripping toggle, and job start endpoints ([c9c2b23](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/c9c2b23add90af72ff2b27b4ee4250ffdd403ee2))
* Add title update, settings, and system info API endpoints ([e3477d6](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/e3477d64de65d60908c76bf005712b957fb17e38))
* Centralize path logic, persist raw/transcode paths, enhance notifications ([0738575](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/07385757099fbaca318a6229e2090f09eaeb7d2a))
* GPU hardware detection via sysfs with WSL2 support ([45a6e71](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/45a6e71654a9f06e3bf8b72f88dda3512eea2040))
* implement global ripping pause and manual start in wait loop ([025622d](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/025622d20c321f3bd42583f97dda1edd1f2be04e))
* Remove login_required from API v1, add cancel endpoint and config validation ([5da273f](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/5da273fefe508d7bbddcbb56652ac6acc151c90b))


### Bug Fixes

* Detect abcde I/O errors despite zero exit code ([#1526](https://github.com/uprightbass360/automatic-ripping-machine-neu/issues/1526)) ([abc4f68](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/abc4f684ad415810515a201e87c05b0b1cda2d6b))
* Don't treat unparsed MakeMKV output as fatal when exit code is 0 ([#1688](https://github.com/uprightbass360/automatic-ripping-machine-neu/issues/1688)) ([d6623e9](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/d6623e9f5c2bc1705877c5e90899eea80575cfcf))
* Fall back to exact title match for short OMDb queries ([#1430](https://github.com/uprightbass360/automatic-ripping-machine-neu/issues/1430)) ([9a87349](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/9a87349cba50165c735ac63643708f3999c1b5ff))
* Guard HandBrake no_of_titles against None and string type ([#1628](https://github.com/uprightbass360/automatic-ripping-machine-neu/issues/1628)) ([c10d917](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/c10d917347f98c94cd7358baf12ad100bc278d32))
* Handle malformed BDMV XML and ensure umount ([#1650](https://github.com/uprightbass360/automatic-ripping-machine-neu/issues/1650), [#1664](https://github.com/uprightbass360/automatic-ripping-machine-neu/issues/1664)) ([ac33272](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/ac33272bb2da72f60683ea0f0570e3815b04a68d))
* Handle nameless drives in drives_update ([#1584](https://github.com/uprightbass360/automatic-ripping-machine-neu/issues/1584)) ([2e63381](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/2e63381ed2d56a145b9a36dadf7bb4429984011b))
* Handle None job.drive in makemkv.py ([#1665](https://github.com/uprightbass360/automatic-ripping-machine-neu/issues/1665)) ([0e465ee](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/0e465ee495e639df0a760ed1610e5fb15fcb1dc6))
* Harden calc_process_time against non-numeric input, downgrade log to DEBUG ([#1641](https://github.com/uprightbass360/automatic-ripping-machine-neu/issues/1641)) ([78ab2e9](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/78ab2e9c26f8021e8626094266c324fd121a29a3))
* Harden OMDb fallback with timeout and broad exception handling ([#1430](https://github.com/uprightbass360/automatic-ripping-machine-neu/issues/1430)) ([ed39afc](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/ed39afc02bd21226197f7355ea94eb60445fc5b9))
* lint issues ([a1ecbb9](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/a1ecbb912bd4114c3a514d9cb4bfa5b79e37cfd2))
* Log umount diagnostics and improve test isolation ([#1664](https://github.com/uprightbass360/automatic-ripping-machine-neu/issues/1664), [#1584](https://github.com/uprightbass360/automatic-ripping-machine-neu/issues/1584), [#1430](https://github.com/uprightbass360/automatic-ripping-machine-neu/issues/1430)) ([d939362](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/d939362c2998853c6911d4c107f42a93a5ac6943))
* Prevent duplicate file assignment in _reconcile_filenames ([#1355](https://github.com/uprightbass360/automatic-ripping-machine-neu/issues/1355), [#1281](https://github.com/uprightbass360/automatic-ripping-machine-neu/issues/1281)) ([c1f6caa](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/c1f6caabfdb5045c323c5382e6e120b536c6eba4))
* Prevent str(None) producing literal 'None' as bluray title ([#1650](https://github.com/uprightbass360/automatic-ripping-machine-neu/issues/1650)) ([efa139d](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/efa139d990815d8472da991eb3ce5069b369d1bf))
* Reconcile MakeMKV scan-time filenames with actual rip output ([#1355](https://github.com/uprightbass360/automatic-ripping-machine-neu/issues/1355), [#1281](https://github.com/uprightbass360/automatic-ripping-machine-neu/issues/1281)) ([2623b11](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/2623b116fa1123ad231681c944fd9c2d8ac6f4a1))
* remove executable bit from files which don't need it ([39e8409](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/39e8409deadd4dbfa71b5599d7db48f8b115c205))
* replace hard-coded paths with configurable ones ([824e720](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/824e720e4608cd520b2ae6f38ce4943cf057354f))
* resolve flake8 lint errors ([0c72660](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/0c726609307c8c09a8c3fd06aef5d82c81ba82fb))
* Resolve flake8 lint errors across codebase ([1654f76](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/1654f7614776d0e0fe8391d31c22b05859789b27))
* Rewrite Docker publish workflow for dual-registry push ([83adb0e](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/83adb0e723ac2d43f8e11d524ba81ae3b0c7a677))
* Set fallback no_of_titles on ffprobe failure, guard None comparison ([#1628](https://github.com/uprightbass360/automatic-ripping-machine-neu/issues/1628)) ([96697d1](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/96697d13202b84b6bdf7887b768aeb8eaa964808))
* Skip unrecognized MakeMKV output lines in parser ([#1688](https://github.com/uprightbass360/automatic-ripping-machine-neu/issues/1688)) ([7297893](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/7297893d2e17494f92095655eecb8cc94d519f5b))
* Strip whitespace from settings values, harden git version check ([#1684](https://github.com/uprightbass360/automatic-ripping-machine-neu/issues/1684), [#1345](https://github.com/uprightbass360/automatic-ripping-machine-neu/issues/1345)) ([edac6d2](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/edac6d2fd4cc5c69384b0ef03ec928911ab15e56))
* track numbering mismatch causes silent data loss ([#1475](https://github.com/uprightbass360/automatic-ripping-machine-neu/issues/1475)) ([35f091e](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/35f091eb08791d55f6233b50b7fd6da3938fd58a))
* Use consistent filename in rip_data and harden abcde log check ([#1651](https://github.com/uprightbass360/automatic-ripping-machine-neu/issues/1651), [#1526](https://github.com/uprightbass360/automatic-ripping-machine-neu/issues/1526)) ([830a743](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/830a7435156cb53b82ab45ea5e5f442cf3a83b9a))
* Use de-duplicated filename for data disc ISO output ([#1651](https://github.com/uprightbass360/automatic-ripping-machine-neu/issues/1651)) ([500e89d](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/500e89dc71b9f9999ac15c28f90d853b4d1481a9))
* use job.title to show meaningful music notifications ([1d2d22b](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/1d2d22b5f785588a3dfcd244aab46f7ca89ed5a5))
* use job.title to show meaningful music notifications ([754b972](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/754b9727f69f952178d1b41fdfb1fc74b5239091))
* Use list args for HandBrake subprocess to prevent shell quoting issues ([#1457](https://github.com/uprightbass360/automatic-ripping-machine-neu/issues/1457)) ([4f32270](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/4f32270fdce65ae3e627c53aedf3a1a0634a3026))
* Use total_seconds() for ETA calculation over 24 hours ([#1641](https://github.com/uprightbass360/automatic-ripping-machine-neu/issues/1641)) ([40bf39f](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/40bf39f3acc7f85f22efdc5bb774b39063491678))
* Use Union type syntax for Python 3.9 compatibility ([ffad9c7](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/ffad9c772da6844eec767df5c3cda570438d2625))

## [2.21.6](https://github.com/uprightbass360/automatic-ripping-machine-neu/compare/2.21.5...v2.21.6) (2026-02-11)


### Bug Fixes

* Resolve flake8 lint errors across codebase ([1654f76](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/1654f7614776d0e0fe8391d31c22b05859789b27))
* Use Union type syntax for Python 3.9 compatibility ([ffad9c7](https://github.com/uprightbass360/automatic-ripping-machine-neu/commit/ffad9c772da6844eec767df5c3cda570438d2625))

## v2.4.6
 - Updated jquery tablesorter, old version was vulnerable to XSS 
 - Removed all unused versions of CSS 
 - Smalls validation checks when searching the database page. (searching now requires min 3 chars)
 - Small changes to index.html (home for arm ui) to warn before abandoning jobs
 - Jquery ui now fully removed. Now uses only bootstrap for theming
 - ARM ui database no longer needs logfiles in url (potentially dangerous), it checks the database instead for the logfile matching the job.
 - Some progress on converting all string types to fstrings where possible
 - ARM will now break out of wait if the user inputs/searches for movie/series.

## v2.3.4 - v2.4.5
 - Adding bypass for db.session.commit() error for movies (WIP only MakeMKV and part of handbrake is coded)
 - Abandon job option added to main ARM ui page (for now this only sets job to failed no processes are cancelled)
 - Typo fixes (ARM ui images has/had some typos these have been updated and corrected)
 - ARM ui now shows CPU temps
 - ARM ui now uses percentage bars to more clearly display storage and RAM usage 
 - ARM ui database page is now fully functional with updated ui that looks clearer and with more details
 - ARM ui database is now searchable
 - ARM ui settings page now fully works and saves your settings to the arm.yaml
 - ARM ui now prevents logfiles that contain "../"
 - ARM ui login page updated to look smoother look
 - Bugfix (ARM will no longer log failures when opening sdx or hdx devices)
 - Bugfix (ARM will no longer crash when dealing with non utf-8 chars)
 - Bugfix (ARM database_updater() was setting incorrect values into the database)
 - Bugfix (ARM ui will no longer crash when trying to read logs with non utf-8 chars)
 - Bugfix (ARM ui will now get the latest % of encode, this was buggy as it was getting the very first % it could find)
 - Bugfix (ARM ui will now correctly display ram usage)
 - Bugfix (ARM ui now correctly deals with setup (it should now create all necessary folders and do so without errors) )
 - Bugfix (ARM ui update title no longer shows html on update)

## v2.3.4
 - Travisci/flake8 code fixes
 - github actions added
 - Bugfix(small bugfix for datadiscs)
 - Bugfix (old versions of yaml would cause Exceptions)
 - Bugfix (db connections are now closed properly for CD's)
 - added bypass for music CD's erroring when trying to commit to the db at the same time

## v2.3.3

 - A smaller more manageable update this time 
 - Early changes for cleaner looking log output
  - Security (HandBrake.py outputs the new prettytable format)
  - Bugfix (Transcode limit is now respected) 
  - Bugfix (Bluray disc with no titles will now be handled correctly and will not throw an exception )
  - Bugfix (abcde.config now correctly uses musicbrainz)

## v2.3.2
 - Added prettytables for logging
 - Remove api/keys from the Config class string printout 
  - Security (HandBrake.py was still outputting all api key and secrets to log file. This has now been fixed)
  - Bugfix (Transcode limit is now respected) 
  - Bugfix (Bluray disc with no titles will now be handled correctly and will not throw an exception ) 

## v2.2.0
 - Added Apprise notifications
  - Added more to the Basic web framework (flask_login)
    - Added login/admin account
    - Added dynamic websever ip to notifications
    - Allow Deleting entries from the db (also warning for both the page and every delete)
    - Added music CD covers (provied by musicbrainz & coverartarchive.org)
    - Added CPU/RAM info on index page
    - Added some clearer display for the listlogs page 
    - Bugfix (Mainfeature now works when updating in the ui) 
    - Bugfix (Job is no longer added twice when updated in ui) 
    - ALPHA: Added ARM settings page (This only shows settings for the moment, no editing)
  - Added Intel QuickSync Video support
  - Added AMD VCE support
  - Added desktop notifications
  - Added user table to the sqlite db
  - Added Debian Installer Script
  - Added Ubuntu Installer Script
  - Added Auto Identfy of music CD's
  - Made changes to the setup logging to allow music CD's to use the their artist name and album name as the log file 
  - Added abcde config file overide (This lets you give a custom config file to abcde from anywhere)
  - Added log cleaner function to strip out secret keys (This isnt complete yet)
  - Bugfix (datadiscs with no label no longer fail) 
  - Bugfix (NONE_(timestamp).log will no longer be generated ) 

## v2.1.0
 - Added new package (armui) for web user interface
  - Basic web framework (Flask, Bootstrap)
    - Retitle functionality
    - View or download logs of active and past rips
  - sqlite db

## v2.0.1
 - Fixed crash inserting bluray when bdmt_eng.xml file is not present
 - Fixed error when deleting non-existent raw files
 - Fixed file extension config parameter not being honored when RIPMETHOD='mkv'
 - Fixed media not being moved when skip_transcode=True
 - Added logic for when skip_trancode=True to make it consistant with standard processing
 - Removed systemd and reimplemented arm_wrapper.sh (see Readme for upgrade instructions)

## v2.0.0
 - Rewritten completely in Python
 - Run as non-root
 - Seperate HandBrake arguments and profiles for DVD's and Bluray's
 - Set video type or automatically identify
 - Better logging
-  Auto download latest keys_hashed.txt and KEYDB.cfg

## v1.3.0
 - Get Title for DVD and Blu-Rays so that media servesr can identify them easily.
 - Determine if video is Movie or TV-Show from OMDB API query so that different actions can be taken (TV shows usually require manual episode identification)
 - Option for MakeMKV to rip using backup method.
 - Option to rip only main feature if so desired.

## v1.2.0
- Distinguish UDF data from UDF video discs

## v1.1.1

- Added devname to abcde command
- Added logging stats (timers). "grep STAT" to see parse them out.

## v1.1.0

- Added ability to rip from multiple drives at the same time
- Added a config file for parameters
- Changed logging
  - Log name is based on ID_FS_LABEL (dvd name) variable set by udev in order to isolate logging from multiple process running simultaneously
  - Log file name and path set in config file
  - Log file cleanup based on parameter set in config file
- Added phone notification options for Pushbullet and IFTTT
- Remove MakeMKV destination directory after HandBrake finishes transcoding
- Misc stuff

## v1.0.1

- Fix ripping "Audio CDs" in ISO9660 format like LOTR.

## v1.0.0

- Initial Release

# The native macOS app. See README.md. Needs macOS 26 and Swift 6.3 or later (Xcode 26).
#
#   make build                build the debug executable
#   make test                 run the unit tests, the release scripts' checks, and the
#                             WebKit gate's build and Node tests
#   make app                  assemble and sign build/dev/Metabrowser.app
#   make run FOLDER=path      build the app and open a folder with it; what it opens
#                             stays out of the recent targets (METABROWSER_RECORD_RECENT=0)
#   make dmg                  build/Metabrowser-Dev-VERSION-arm64.dmg, checked, not notarized
#   make release              the official build: build/Metabrowser-VERSION-arm64.dmg,
#                             Developer ID signed, notarized, and stapled
#   make release NOTARIZE=0   rehearse the release with an ad hoc signature
#   make notarize [FILE=path] notarize and staple the release DMG, or FILE
#   make signing-check        the signing doctor: can this Mac sign and notarize a release?
#                             Read-only; ONLINE=1 also asks the notary service
#   make check-release TAG=macos-vX.Y.Z BUILT=local|ci EXPECTED_TEAM_ID=TEAMID [LAUNCH=1]
#                             check a draft or published release as a downloader gets it;
#                             LAUNCH=1 also launches it, translocated, at the Mac
#   make webkit-gate          the WebKit measurement gate against Chrome (webkit-gate/run.mjs);
#                             PAIRS=n and CASES=a,b pass through
#   make clean                remove .build and build
#
# Every build is the dev variant (build/dev/Metabrowser.app, the canary icon) except
# `release` and `notarize`, the official path, which build the release variant
# (build/release/Metabrowser.app, the published icon). VARIANT=release or VARIANT=dev on
# the command line overrides that; a VARIANT in the environment is ignored, so a leftover
# export cannot turn a
# development build into a release build. SIGN_IDENTITY, SIGN_KEYCHAIN, the notary
# credentials, NOTARIZE, ONLINE, EXPECTED_TEAM_ID, TAG, BUILT, LAUNCH, and ARCHES reach the
# scripts, which document them.

SHELL := /bin/bash
SWIFT ?= swift
FOLDER ?=
FILE ?=
ifneq ($(origin VARIANT),command line)
VARIANT :=
endif
dev_variant = $(or $(VARIANT),dev)
release_variant = $(or $(VARIANT),release)

.PHONY: build test app run dmg release notarize signing-check check-release clean webkit-gate

build:
	$(SWIFT) build

# Four test processes, so no suite shares the main actor with WebKit's startup, the
# Settings window's, or the stress suite's spawns, which each stall it for seconds on a
# loaded runner: see ignoreSIGPIPELikeTheApp and runAppKitEventLoop in
# Tests/ShellCoreTests/Support.swift, and ExitObservationStressTests.swift. The patterns
# also match StagedDownloadTests.
webkit_suites := DownloadTests WebConfigurationTests PagePrintTests PagePrintAuthorizationTests PageRevealWebKitTests \
	WebViewWebKitTests PageFindWebKitTests OpenFileWebKitTests
#
# The WebKit suites run with --no-parallel. Every suite runs on the main actor, and a
# test's WKWebView(frame:configuration:) blocks the main thread inside WebKit: a new
# configuration creates a WebProcessPool, whose setup makes a synchronous call to notifyd
# (notify_get_state), seconds long when the machine is loaded. In parallel, the other
# tests' constructions block the main thread while a test waits for a click's window or
# its delegate callback, so `eventually`'s wall-clock 10 s passes without that test's own
# events running (the page saw its Command-click's mousedown 20 s late). Measured on a
# 10-core machine with 12 busy loops: parallel failed theUsersClickOnTheButtonReachesTheAppAlone
# in about one full-suite run in four, and the test took 3 to 40 s; serial passed 18 of 18,
# in 0.3 to 1.2 s. The whole serial run takes about 7 s.
#
# SettingsWindowTests opens the app's Settings window on screen and runs AppKit's event
# loop for the rest of its process. Measured on 2026-11-24 with the machine's load
# average near 400, back to back: the unit process without it passed once and once missed
# StartupDeadlineTests' 10 s bound, in 12 and 14 s; with it, it failed two and four
# wall-clock bounds, HealthCheckTests' 2 s one by 6 to 8 s both times, in 37 and 35 s.
# FolderWindowTests puts folder windows on screen in the same event loop, and each of its
# pages builds a web view, so it runs in that process too.
window_suites := SettingsWindowTests FolderWindowTests
#
# Each test process runs through scripts/swift-test.sh, which fails one that exits 0 without
# swift-testing's summary of a passed run of at least one test: a window-server event once
# ended a process that way with its tests unrun, and a process whose filters match no test
# at all exits 0 too. It checks only that count, so a process that runs some tests passes
# even when one of its filters names no suite. SWIFT is quoted so that a value of several
# words, such as "xcrun swift", reaches it whole, as it reaches $(SWIFT) build.
swift_test = SWIFT='$(SWIFT)' scripts/swift-test.sh
#
# The WebKit gate's driver ships in no product, so nothing else would notice a change to
# the app's views or configuration that broke its build; the gate itself needs Chrome and
# a logged-in session, so only its build and its Node tests, which need neither, run here.
test:
	$(SWIFT) build --product WebKitDriver
	$(swift_test) --skip ExitObservationStressTests $(webkit_suites:%=--skip %) $(window_suites:%=--skip %)
	$(swift_test) --no-parallel $(webkit_suites:%=--filter %)
	$(swift_test) --no-parallel $(window_suites:%=--filter %)
	$(swift_test) --filter ExitObservationStressTests
	scripts/test-scripts.sh
	node --test 'webkit-gate/*.test.mjs'

app:
	VARIANT=$(dev_variant) scripts/build-app.sh

# A development run records nothing in the recent targets, the one list it shares with the
# installed app: agents launch the app this way for hand checks, and the folders they open
# are not the user's (mb-1q02). The app passes the variable on to every `metab` it runs
# (`ChildEnvironment.passedThrough`), so whatever the run opens later stays out too; open
# your own folders in the installed app.
run: app
	set -e; source scripts/common.sh; variant_settings $(dev_variant); \
	open --env METABROWSER_RECORD_RECENT=0 -a "$(CURDIR)/$$app" $(if $(FOLDER),"$(FOLDER)")

dmg:
	VARIANT=$(dev_variant) NOTARIZE=0 scripts/release.sh

release:
	VARIANT=$(release_variant) scripts/release.sh

notarize:
	set -e; source scripts/common.sh; variant_settings $(release_variant); \
	scripts/notarize.sh $(if $(FILE),"$(FILE)","$$dmg")

signing-check:
	scripts/check-signing.sh

check-release:
	scripts/check-release.sh

webkit-gate:
	node webkit-gate/run.mjs $(if $(PAIRS),--pairs $(PAIRS)) $(if $(CASES),--cases $(CASES))

# A launch check that ended before restoring the release identity's state left the only
# copy of it in build/launch-check-*/backup (scripts/launch-release.sh), so clean keeps
# build/ until that is restored.
clean:
	@set -e; source scripts/common.sh; source scripts/check-release-lib.sh; \
	leftover="$$(leftover_launch_checks "$(CURDIR)/build")"; \
	if [[ -n "$$leftover" ]]; then \
	  echo "error: $$leftover holds a launch check's backup, the only copy of the release identity's state; quit Metabrowser, then restore it: scripts/launch-release.sh --restore $$leftover" >&2; \
	  exit 1; \
	fi
	rm -rf .build build

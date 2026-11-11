# The native macOS app. See README.md. Needs macOS and Swift 6.2 or later (Xcode 26).
#
#   make build                build the debug executable
#   make test                 run the unit tests and the release scripts' checks
#   make app                  assemble and sign build/Metabrowser Dev.app
#   make run FOLDER=path      build the app and open a folder with it
#   make dmg                  build/Metabrowser-Dev-VERSION-arm64.dmg, checked, not notarized
#   make release              the official build: build/Metabrowser-VERSION-arm64.dmg,
#                             Developer ID signed, notarized, and stapled
#   make release NOTARIZE=0   rehearse the release with an ad hoc signature
#   make notarize [FILE=path] notarize and staple the release DMG, or FILE
#   make clean                remove .build and build
#
# Every build is the dev variant (Metabrowser Dev, the canary icon) except `release`
# and `notarize`, the official path, which build the release variant (Metabrowser, the
# published icon). VARIANT=release or VARIANT=dev on the command line overrides that;
# a VARIANT in the environment is ignored, so a leftover export cannot turn a
# development build into a release build. SIGN_IDENTITY, the notary credentials,
# NOTARIZE, and ARCHES reach the scripts, which document them.

SHELL := /bin/bash
SWIFT ?= swift
FOLDER ?=
FILE ?=
ifneq ($(origin VARIANT),command line)
VARIANT :=
endif
dev_variant = $(or $(VARIANT),dev)
release_variant = $(or $(VARIANT),release)

.PHONY: build test app run dmg release notarize clean

build:
	$(SWIFT) build

test:
	$(SWIFT) test
	scripts/test-scripts.sh

app:
	VARIANT=$(dev_variant) scripts/build-app.sh

run: app
	set -e; source scripts/common.sh; variant_settings $(dev_variant); \
	open -a "$(CURDIR)/$$app" $(if $(FOLDER),"$(FOLDER)")

dmg:
	VARIANT=$(dev_variant) NOTARIZE=0 scripts/release.sh

release:
	VARIANT=$(release_variant) scripts/release.sh

notarize:
	set -e; source scripts/common.sh; variant_settings $(release_variant); \
	scripts/notarize.sh $(if $(FILE),"$(FILE)","$$dmg")

clean:
	rm -rf .build build

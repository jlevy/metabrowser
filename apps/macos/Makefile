# The native macOS app. See README.md. Needs macOS and Swift 6.2 or later (Xcode 26).
#
#   make build                build the debug executable
#   make test                 run the unit tests
#   make app                  assemble and sign build/Metabrowser.app
#   make run FOLDER=path      build the app and open a folder with it
#   make clean                remove .build and build

SWIFT ?= swift
APP := build/Metabrowser.app
FOLDER ?=

.PHONY: build test app run clean

build:
	$(SWIFT) build

test:
	$(SWIFT) test

app:
	scripts/build-app.sh

run: app
	open -a "$(CURDIR)/$(APP)" $(if $(FOLDER),"$(FOLDER)")

clean:
	rm -rf .build build

# Minimal Sphinx Makefile — run via `uv run` so the docs extras are picked up.

SPHINXBUILD   ?= uv run sphinx-build
SOURCEDIR     = .
BUILDDIR      = _build

.PHONY: help html clean livehtml

help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)"

html:
	@$(SPHINXBUILD) -b html "$(SOURCEDIR)" "$(BUILDDIR)/html"

clean:
	rm -rf "$(BUILDDIR)"

livehtml:
	uv run sphinx-autobuild "$(SOURCEDIR)" "$(BUILDDIR)/html"

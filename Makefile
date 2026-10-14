PROJECTS := $(sort $(patsubst %/Makefile,%,$(shell grep -l '^help:' */Makefile */*/Makefile 2>/dev/null)))

.PHONY: help setup run test

help:
	@echo "setup - make setup in every project"
	@echo "run   - show this help (a collection of projects, no single pipeline)"
	@echo "test  - make test in every project, then list the failures"
	@echo ""
	@echo "Projects (cd <project> && make help):"
	@for p in $(PROJECTS); do echo "  $$p"; done

setup:
	@for p in $(PROJECTS); do $(MAKE) --no-print-directory -C $$p setup || exit 1; done

run: help

test:
	@failed=""; \
	for p in $(PROJECTS); do \
		echo "== $$p"; \
		$(MAKE) --no-print-directory -C $$p test || failed="$$failed $$p"; \
	done; \
	if [ -n "$$failed" ]; then echo "failed:$$failed" >&2; exit 1; fi

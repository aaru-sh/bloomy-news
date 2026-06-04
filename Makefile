# Bloomy News - cross-platform Makefile
# Works with GNU make (Linux/macOS) and via Git Bash / WSL on Windows.
# Override the Python interpreter with:  make PYTHON=python run

PYTHON ?= python3
PIP    ?= $(PYTHON) -m pip

# Detect Windows (Git Bash / MSYS) so we can switch extensions.
ifeq ($(OS),Windows_NT)
    EXE := .exe
    RM  := del /Q
    LAUNCHER := LAUNCH_DAILY.bat
else
    EXE :=
    RM  := rm -f
    LAUNCHER := ./launch_daily.sh
endif

.PHONY: help install test test-all smoke run pipeline server scheduler-install scheduler-uninstall scheduler-status scheduler-run clean clean-data

help:
	@echo "Bloomy News - common tasks"
	@echo "  make install              Install Python dependencies"
	@echo "  make test                 Run the test suite"
	@echo "  make smoke                Run the fresh-install smoke test (10 checks)"
	@echo "  make pipeline             Run the news pipeline once"
	@echo "  make server               Start the dashboard server (foreground)"
	@echo "  make run                  Launch the full daily flow ($(LAUNCHER))"
	@echo "  make scheduler-install    Install scheduler as Windows autostart"
	@echo "  make scheduler-uninstall  Remove scheduler autostart"
	@echo "  make scheduler-status     Print scheduler state"
	@echo "  make scheduler-run        Run scheduler pipeline once and exit"
	@echo "  make clean                Delete generated artifacts (news.db, dashboard data)"
	@echo "  make clean-data           Same as clean, plus logs"

install:
	$(PIP) install -r requirements.txt

test:
	$(PYTHON) -m unittest discover -s tests -v

test-all: test

smoke:
	$(PYTHON) scripts/smoke_test.py

pipeline:
	$(PYTHON) news_tool.py

server:
	$(PYTHON) dashboard/serve.py

run:
	@if [ -f "$(LAUNCHER)" ]; then $(LAUNCHER); else echo "Launcher not found: $(LAUNCHER)"; exit 1; fi

scheduler-install:
	$(PYTHON) scripts/scheduler.py --install

scheduler-uninstall:
	$(PYTHON) scripts/scheduler.py --uninstall

scheduler-status:
	$(PYTHON) scripts/scheduler.py --status

scheduler-run:
	$(PYTHON) scripts/scheduler.py --run-now

clean:
	-$(RM) news.db
	-$(RM) dashboard/data/dashboard_data.json
	-$(RM) dashboard/data/bookmarks.json
	-$(RM) .last_run

clean-data: clean
	-$(RM) logs/*.log
	-$(RM) raw

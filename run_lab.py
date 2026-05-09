#!/usr/bin/env python3
"""Compatibility wrapper for the isolated external agent lab launcher."""

from external_agent_lab.cli import main


if __name__ == "__main__":
    raise SystemExit(main(default_command="run"))

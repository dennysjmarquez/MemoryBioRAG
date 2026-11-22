"""Presentation-only argparse adapter for consistent public help sections."""
import argparse

from core.cli_notes import NOTES, help_intro, help_end


class HelpParser(argparse.ArgumentParser):
    """Keep argparse parsing and options authoritative; only compose help text."""

    def format_help(self):
        command = self.prog.removeprefix('biorag ')
        if command not in NOTES:
            return super().format_help()
        description, epilog = self.description, self.epilog
        try:
            self.description = self.epilog = None
            raw = super().format_help()
        finally:
            self.description, self.epilog = description, epilog
        usage, _, options = raw.partition('\n\n')
        summary = NOTES[command].split('. ')[0].rstrip('.') + '.'
        return (usage + '\n\n' + help_intro(command, summary) + '\n\n'
                + options.rstrip() + '\n\n' + help_end(command) + '\n')

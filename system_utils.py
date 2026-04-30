#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess

from config import SUDO_REBOOT_COMMANDS, SUDOERS_REBOOT_HINT


def request_reboot():
    """Try to reboot with non-interactive sudo and return (success, message)."""
    errors = []

    for command in SUDO_REBOOT_COMMANDS:
        try:
            result = subprocess.run(
                ["sudo", "-n", *command],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            continue

        if result.returncode == 0:
            return True, f"accepted: sudo -n {' '.join(command)}"

        details = (result.stderr or result.stdout or "").strip()
        if not details:
            details = f"exit code {result.returncode}"
        errors.append(f"{' '.join(command)} -> {details}")

        lowered = details.lower()
        if (
            "password is required" in lowered
            or "a terminal is required" in lowered
            or "not in the sudoers" in lowered
        ):
            return False, f"{details}. {SUDOERS_REBOOT_HINT}"

    if errors:
        return False, f"{'; '.join(errors)}. {SUDOERS_REBOOT_HINT}"

    return False, f"No reboot command was found. {SUDOERS_REBOOT_HINT}"
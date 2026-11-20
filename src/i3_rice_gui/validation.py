"""Validate staged i3 configurations without changing the desktop."""

from dataclasses import dataclass
from enum import Enum
import os
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory


class ValidationStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class ValidationResult:
    status: ValidationStatus
    summary: str
    details: str = ""


def validate_i3(text: str, timeout: float = 10.0) -> ValidationResult:
    try:
        encoded = text.encode("utf-8")
    except UnicodeError as exc:
        return ValidationResult(ValidationStatus.UNAVAILABLE, f"Could not encode the draft: {exc}")
    if len(encoded) > 1024 * 1024:
        return ValidationResult(
            ValidationStatus.UNAVAILABLE, "The draft exceeds the 1 MiB validation limit."
        )
    for line in text.splitlines():
        stripped = line.lstrip()
        if not stripped.startswith("#") and (
            stripped.startswith("$")
            or re.search(r"(?<!\w)include(?!\w)", line, re.IGNORECASE)
        ):
            return ValidationResult(
                ValidationStatus.UNAVAILABLE,
                "Validation is unavailable for configurations that may include other files "
                "or contain dynamically generated directives.",
                "Included files and dynamically generated directives cannot yet be validated "
                "as part of the staged draft.",
            )
    executable = shutil.which("i3")
    if not executable:
        return ValidationResult(
            ValidationStatus.UNAVAILABLE, "The i3 validator is not available in PATH."
        )
    try:
        with TemporaryDirectory(prefix="i3-rice-validation-") as directory:
            config = Path(directory) / "config"
            config.write_bytes(encoded)
            environment = os.environ.copy()
            environment["LC_ALL"] = "C"
            process = subprocess.run(
                [executable, "-C", "-c", str(config)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                env=environment,
                check=False,
            )
    except subprocess.TimeoutExpired:
        return ValidationResult(ValidationStatus.UNAVAILABLE, "i3 validation timed out.")
    except (OSError, UnicodeError) as exc:
        return ValidationResult(ValidationStatus.UNAVAILABLE, f"Could not run i3 validation: {exc}")

    details = "\n".join(part.strip() for part in (process.stdout, process.stderr) if part.strip())
    if len(details) > 16000:
        details = details[:16000] + "\n[Output truncated]"
    if process.returncode == 0:
        return ValidationResult(ValidationStatus.VALID, "i3 accepted this draft.", details)
    if "ERROR: CONFIG:" in details:
        return ValidationResult(ValidationStatus.INVALID, "i3 reported configuration errors.", details)
    return ValidationResult(
        ValidationStatus.UNAVAILABLE,
        f"i3 validation failed without a configuration diagnosis (exit {process.returncode}).",
        details,
    )

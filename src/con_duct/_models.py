"""Data models and enums for con-duct."""

from __future__ import annotations
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
import logging
import os
import string
from con_duct._constants import SUFFIXES

lgr = logging.getLogger("con-duct")


class Outputs(str, Enum):
    ALL = "all"
    NONE = "none"
    STDOUT = "stdout"
    STDERR = "stderr"

    def __str__(self) -> str:
        return self.value

    def has_stdout(self) -> bool:
        return self is Outputs.ALL or self is Outputs.STDOUT

    def has_stderr(self) -> bool:
        return self is Outputs.ALL or self is Outputs.STDERR


class RecordTypes(str, Enum):
    ALL = "all"
    SYSTEM_SUMMARY = "system-summary"
    PROCESSES_SAMPLES = "processes-samples"

    def __str__(self) -> str:
        return self.value

    def has_system_summary(self) -> bool:
        return self is RecordTypes.ALL or self is RecordTypes.SYSTEM_SUMMARY

    def has_processes_samples(self) -> bool:
        return self is RecordTypes.ALL or self is RecordTypes.PROCESSES_SAMPLES


class SessionMode(str, Enum):
    NEW_SESSION = "new-session"
    CURRENT_SESSION = "current-session"

    def __str__(self) -> str:
        return self.value


@dataclass
class SystemInfo:
    cpu_total: int
    memory_total: int
    hostname: str | None
    uid: int
    user: str | None


@dataclass
class LogPaths:
    stdout: str
    stderr: str
    usage: str
    info: str
    prefix: str

    def __iter__(self) -> Iterator[tuple[str, str]]:
        for name, path in asdict(self).items():
            if name != "prefix":
                yield name, path

    @classmethod
    def create(cls, output_prefix: str, pid: None | int = None) -> LogPaths:
        if any(
            field_name == "datetime_filesafe"
            for _, field_name, _, _ in string.Formatter().parse(output_prefix)
        ):
            lgr.warning(
                "{datetime_filesafe} in --output-prefix is deprecated; use {datetime} instead"
            )
        datetime_filesafe = datetime.now().strftime("%Y.%m.%dT%H.%M.%S")
        formatted_prefix = output_prefix.format(
            pid=pid,
            datetime=datetime_filesafe,
            # Use of the `datetime_filesafe` format field is deprecated.
            # The setting of it here is to provide for backwards compatibility
            # It should be removed eventually
            datetime_filesafe=datetime_filesafe,
        )
        return cls(
            stdout=f"{formatted_prefix}{SUFFIXES['stdout']}",
            stderr=f"{formatted_prefix}{SUFFIXES['stderr']}",
            usage=f"{formatted_prefix}{SUFFIXES['usage']}",
            info=f"{formatted_prefix}{SUFFIXES['info']}",
            prefix=formatted_prefix,
        )

    def prepare_paths(self, clobber: bool, capture_outputs: Outputs) -> None:
        conflicts = [path for _name, path in self if os.path.exists(path)]
        if conflicts and not clobber:
            raise FileExistsError(
                "Conflicting files:\n"
                + "\n".join(f"- {path}" for path in conflicts)
                + "\nUse --clobber to overwrite conflicting files."
            )

        if self.prefix.endswith(os.sep):  # If it ends in "/" (for linux) treat as a dir
            os.makedirs(self.prefix, exist_ok=True)
        else:
            # Path does not end with a separator, treat the last part as a filename
            directory = os.path.dirname(self.prefix)
            if directory:
                os.makedirs(directory, exist_ok=True)
        for name, path in self:
            if name == SUFFIXES["stdout"] and not capture_outputs.has_stdout():
                continue
            elif name == SUFFIXES["stderr"] and not capture_outputs.has_stderr():
                continue
            # TODO: AVOID PRECREATION -- would interfere e.g. with git-annex
            # assistant monitoring new files to be created and committing
            # as soon as they are closed
            open(path, "w").close()

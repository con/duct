"""Data models and enums for con-duct."""

from __future__ import annotations
from collections import Counter
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
import logging
import os
import re
from typing import Any, Optional
from con_duct._constants import SUFFIXES
from con_duct._utils import assert_num

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
class ProcessStats:
    pcpu: float  # %CPU
    pmem: float  # %MEM
    rss: int  # Memory Resident Set Size in Bytes
    vsz: int  # Virtual Memory size in Bytes
    timestamp: str
    etime: str
    stat: Counter
    cmd: str

    def aggregate(self, other: ProcessStats) -> ProcessStats:
        cmd = self.cmd
        if self.cmd != other.cmd:
            lgr.debug(
                f"cmd has changed. Previous measurement was {self.cmd}, now {other.cmd}."
            )
            # Brackets indicate that the kernel has substituted an abbreviation.
            surrounded_by_brackets = r"^\[.+\]"
            if re.search(surrounded_by_brackets, self.cmd):
                lgr.debug(f"using {other.cmd}.")
                cmd = other.cmd
            lgr.debug(f"using {self.cmd}.")

        new_counter: Counter = Counter()
        new_counter.update(self.stat)
        new_counter.update(other.stat)
        return ProcessStats(
            pcpu=max(self.pcpu, other.pcpu),
            pmem=max(self.pmem, other.pmem),
            rss=max(self.rss, other.rss),
            vsz=max(self.vsz, other.vsz),
            timestamp=max(self.timestamp, other.timestamp),
            etime=other.etime,  # For the aggregate always take the latest
            stat=new_counter,
            cmd=cmd,
        )

    def for_json(self) -> dict:
        ret = asdict(self)
        ret["stat"] = dict(self.stat)
        return ret

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        assert_num(self.pcpu, self.pmem, self.rss, self.vsz)


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


@dataclass
class Averages:
    rss: Optional[float] = None
    vsz: Optional[float] = None
    pmem: Optional[float] = None
    pcpu: Optional[float] = None
    num_samples: int = 0

    def update(self: Averages, other: Sample) -> None:
        assert_num(other.total_rss, other.total_vsz, other.total_pmem, other.total_pcpu)
        if not self.num_samples:
            self.num_samples += 1
            self.rss = other.total_rss
            self.vsz = other.total_vsz
            self.pmem = other.total_pmem
            self.pcpu = other.total_pcpu
        else:
            assert self.rss is not None
            assert self.vsz is not None
            assert self.pmem is not None
            assert self.pcpu is not None
            assert other.total_rss is not None
            assert other.total_vsz is not None
            assert other.total_pmem is not None
            assert other.total_pcpu is not None
            self.num_samples += 1
            self.rss += (other.total_rss - self.rss) / self.num_samples
            self.vsz += (other.total_vsz - self.vsz) / self.num_samples
            self.pmem += (other.total_pmem - self.pmem) / self.num_samples
            self.pcpu += (other.total_pcpu - self.pcpu) / self.num_samples

    @classmethod
    def from_sample(cls, sample: Sample) -> Averages:
        assert_num(
            sample.total_rss, sample.total_vsz, sample.total_pmem, sample.total_pcpu
        )
        return cls(
            rss=sample.total_rss,
            vsz=sample.total_vsz,
            pmem=sample.total_pmem,
            pcpu=sample.total_pcpu,
            num_samples=1,
        )


@dataclass
class Sample:
    stats: dict[int, ProcessStats] = field(default_factory=dict)
    averages: Averages = field(default_factory=Averages)
    total_rss: Optional[int] = None
    total_vsz: Optional[int] = None
    total_pmem: Optional[float] = None
    total_pcpu: Optional[float] = None
    timestamp: str = ""  # TS of last sample collected

    def add_pid(self, pid: int, stats: ProcessStats) -> None:
        # We do not calculate averages when we add a pid because we require all pids first
        assert (
            self.stats.get(pid) is None
        )  # add_pid should only be called when pid not in Sample
        self.total_rss = (self.total_rss or 0) + stats.rss
        self.total_vsz = (self.total_vsz or 0) + stats.vsz
        self.total_pmem = (self.total_pmem or 0.0) + stats.pmem
        self.total_pcpu = (self.total_pcpu or 0.0) + stats.pcpu
        self.stats[pid] = stats
        self.timestamp = max(self.timestamp, stats.timestamp)

    def aggregate(self: Sample, other: Sample) -> Sample:
        output = Sample()
        for pid in self.stats.keys() | other.stats.keys():
            if (mine := self.stats.get(pid)) is not None:
                if (theirs := other.stats.get(pid)) is not None:
                    output.add_pid(pid, mine.aggregate(theirs))
                else:
                    output.add_pid(pid, mine)
            else:
                output.add_pid(pid, other.stats[pid])
        assert other.total_pmem is not None
        assert other.total_pcpu is not None
        assert other.total_rss is not None
        assert other.total_vsz is not None
        output.total_pmem = max(self.total_pmem or 0.0, other.total_pmem)
        output.total_pcpu = max(self.total_pcpu or 0.0, other.total_pcpu)
        output.total_rss = max(self.total_rss or 0, other.total_rss)
        output.total_vsz = max(self.total_vsz or 0, other.total_vsz)
        output.averages = self.averages
        output.averages.update(other)
        return output

    def for_json(self) -> dict[str, Any]:
        d = {
            "timestamp": self.timestamp,
            "num_samples": self.averages.num_samples,
            "processes": {
                str(pid): stats.for_json() for pid, stats in self.stats.items()
            },
            "totals": {  # total of all processes during this sample
                "pmem": self.total_pmem,
                "pcpu": self.total_pcpu,
                "rss": self.total_rss,
                "vsz": self.total_vsz,
            },
            "averages": asdict(self.averages) if self.averages.num_samples >= 1 else {},
        }
        return d

"""Tests for Instruments enum and parsing."""

from __future__ import annotations
import pytest
from con_duct.duct_main import Instruments, instruments_from_str


class TestInstruments:
    @pytest.mark.ai_generated
    def test_parse_single_cpu(self) -> None:
        result = instruments_from_str("cpu")
        assert result == {Instruments.CPU}

    @pytest.mark.ai_generated
    def test_parse_single_mem(self) -> None:
        result = instruments_from_str("mem")
        assert result == {Instruments.MEM}

    @pytest.mark.ai_generated
    def test_parse_single_gpu(self) -> None:
        result = instruments_from_str("gpu")
        assert result == {Instruments.GPU}

    @pytest.mark.ai_generated
    def test_parse_multiple(self) -> None:
        result = instruments_from_str("cpu,mem,gpu")
        assert result == {Instruments.CPU, Instruments.MEM, Instruments.GPU}

    @pytest.mark.ai_generated
    def test_parse_cpu_mem(self) -> None:
        result = instruments_from_str("cpu,mem")
        assert result == {Instruments.CPU, Instruments.MEM}

    @pytest.mark.ai_generated
    def test_parse_all(self) -> None:
        result = instruments_from_str("all")
        assert result == {Instruments.CPU, Instruments.MEM, Instruments.GPU}

    @pytest.mark.ai_generated
    def test_parse_all_uppercase(self) -> None:
        result = instruments_from_str("ALL")
        assert result == {Instruments.CPU, Instruments.MEM, Instruments.GPU}

    @pytest.mark.ai_generated
    def test_parse_with_spaces(self) -> None:
        result = instruments_from_str("cpu, mem, gpu")
        assert result == {Instruments.CPU, Instruments.MEM, Instruments.GPU}

    @pytest.mark.ai_generated
    def test_parse_case_insensitive(self) -> None:
        result = instruments_from_str("CPU,MEM,GPU")
        assert result == {Instruments.CPU, Instruments.MEM, Instruments.GPU}

    @pytest.mark.ai_generated
    def test_parse_mixed_case(self) -> None:
        result = instruments_from_str("Cpu,Mem,Gpu")
        assert result == {Instruments.CPU, Instruments.MEM, Instruments.GPU}

    @pytest.mark.ai_generated
    def test_parse_invalid_raises_error(self) -> None:
        with pytest.raises(ValueError, match="Invalid instrument"):
            instruments_from_str("invalid")

    @pytest.mark.ai_generated
    def test_parse_partially_invalid_raises_error(self) -> None:
        with pytest.raises(ValueError, match="Invalid instrument"):
            instruments_from_str("cpu,invalid,mem")

    @pytest.mark.ai_generated
    def test_parse_empty_items_ignored(self) -> None:
        result = instruments_from_str("cpu,,mem")
        assert result == {Instruments.CPU, Instruments.MEM}

    @pytest.mark.ai_generated
    def test_str_method(self) -> None:
        assert str(Instruments.CPU) == "cpu"
        assert str(Instruments.MEM) == "mem"
        assert str(Instruments.GPU) == "gpu"

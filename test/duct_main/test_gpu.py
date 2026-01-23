"""Tests for GPU monitoring functionality."""

from __future__ import annotations
from copy import deepcopy
import subprocess
from unittest import mock
import pytest
from con_duct.duct_main import (
    GPU_SAMPLE_TIMEOUT,
    GpuAverages,
    GpuSample,
    GpuStats,
    _get_gpu_sample,
)

# Sample GPU stats for testing
gpu_stat0 = GpuStats(
    index=0,
    utilization_gpu=45.0,
    utilization_memory=23.0,
    memory_used=4096 * 1024 * 1024,  # 4GB
    memory_total=16384 * 1024 * 1024,  # 16GB
    timestamp="2024-06-11T10:09:37-04:00",
)

gpu_stat1 = GpuStats(
    index=0,
    utilization_gpu=80.0,
    utilization_memory=45.0,
    memory_used=8192 * 1024 * 1024,  # 8GB
    memory_total=16384 * 1024 * 1024,
    timestamp="2024-06-11T10:13:23-04:00",
)


class TestGpuStats:
    @pytest.mark.ai_generated
    def test_aggregate_keeps_peak_values(self) -> None:
        result = gpu_stat0.aggregate(gpu_stat1)
        assert result.utilization_gpu == 80.0
        assert result.utilization_memory == 45.0
        assert result.memory_used == 8192 * 1024 * 1024
        assert result.timestamp == "2024-06-11T10:13:23-04:00"

    @pytest.mark.ai_generated
    def test_for_json(self) -> None:
        json_dict = gpu_stat0.for_json()
        assert json_dict["index"] == 0
        assert json_dict["utilization_gpu"] == 45.0
        assert json_dict["memory_used"] == 4096 * 1024 * 1024


class TestGpuSample:
    @pytest.mark.ai_generated
    def test_add_gpu(self) -> None:
        sample = GpuSample()
        sample.add_gpu(0, deepcopy(gpu_stat0))
        assert 0 in sample.stats
        assert sample.total_utilization_gpu == 45.0
        assert sample.total_memory_used == 4096 * 1024 * 1024

    @pytest.mark.ai_generated
    def test_multi_gpu_totals(self) -> None:
        sample = GpuSample()
        sample.add_gpu(0, deepcopy(gpu_stat0))
        gpu1 = deepcopy(gpu_stat0)
        gpu1.index = 1
        sample.add_gpu(1, gpu1)
        # Utilization is summed across GPUs
        assert sample.total_utilization_gpu == 90.0
        # Memory is summed across GPUs
        assert sample.total_memory_used == 2 * 4096 * 1024 * 1024

    @pytest.mark.ai_generated
    def test_aggregate(self) -> None:
        sample1 = GpuSample()
        sample1.add_gpu(0, deepcopy(gpu_stat0))
        sample1.averages = GpuAverages(
            utilization_gpu=sample1.total_utilization_gpu,
            utilization_memory=sample1.total_utilization_memory,
            memory_used=float(sample1.total_memory_used or 0),
            num_samples=1,
        )

        sample2 = GpuSample()
        sample2.add_gpu(0, deepcopy(gpu_stat1))

        result = sample1.aggregate(sample2)
        # Peak values should be kept
        assert result.total_utilization_gpu == 80.0
        assert result.total_memory_used == 8192 * 1024 * 1024
        # Averages should be updated
        assert result.averages.num_samples == 2

    @pytest.mark.ai_generated
    def test_from_stats(self) -> None:
        stats = {0: deepcopy(gpu_stat0)}
        sample = GpuSample.from_stats(stats)
        assert sample.total_utilization_gpu == 45.0
        assert sample.averages.num_samples == 1

    @pytest.mark.ai_generated
    def test_for_json(self) -> None:
        sample = GpuSample.from_stats({0: deepcopy(gpu_stat0)})
        json_dict = sample.for_json()
        assert "gpus" in json_dict
        assert "0" in json_dict["gpus"]
        assert "totals" in json_dict
        assert json_dict["totals"]["utilization_gpu"] == 45.0


class TestGpuAverages:
    @pytest.mark.ai_generated
    def test_update(self) -> None:
        sample1 = GpuSample.from_stats({0: deepcopy(gpu_stat0)})
        averages = GpuAverages(
            utilization_gpu=sample1.total_utilization_gpu,
            utilization_memory=sample1.total_utilization_memory,
            memory_used=float(sample1.total_memory_used or 0),
            num_samples=1,
        )

        sample2 = GpuSample.from_stats({0: deepcopy(gpu_stat1)})
        averages.update(sample2)

        assert averages.num_samples == 2
        # Average of 45.0 and 80.0
        assert averages.utilization_gpu == pytest.approx(62.5)


class TestGetGpuSample:
    @pytest.mark.ai_generated
    @mock.patch("con_duct.duct_main.shutil.which")
    def test_returns_none_when_nvidia_smi_not_found(
        self, mock_which: mock.MagicMock
    ) -> None:
        mock_which.return_value = None
        result = _get_gpu_sample()
        assert result is None

    @pytest.mark.ai_generated
    @mock.patch("con_duct.duct_main.shutil.which")
    @mock.patch("con_duct.duct_main.subprocess.check_output")
    def test_parses_nvidia_smi_output(
        self,
        mock_check_output: mock.MagicMock,
        mock_which: mock.MagicMock,
    ) -> None:
        mock_which.return_value = "/usr/bin/nvidia-smi"
        mock_check_output.return_value = "0, 45, 23, 4096, 16384\n"

        result = _get_gpu_sample()

        assert result is not None
        assert 0 in result.stats
        assert result.stats[0].utilization_gpu == 45.0
        assert result.stats[0].memory_used == 4096 * 1024 * 1024

    @pytest.mark.ai_generated
    @mock.patch("con_duct.duct_main.shutil.which")
    @mock.patch("con_duct.duct_main.subprocess.check_output")
    def test_handles_timeout(
        self,
        mock_check_output: mock.MagicMock,
        mock_which: mock.MagicMock,
    ) -> None:
        mock_which.return_value = "/usr/bin/nvidia-smi"
        mock_check_output.side_effect = subprocess.TimeoutExpired(
            cmd="nvidia-smi", timeout=GPU_SAMPLE_TIMEOUT
        )

        result = _get_gpu_sample()
        assert result is None

    @pytest.mark.ai_generated
    @mock.patch("con_duct.duct_main.shutil.which")
    @mock.patch("con_duct.duct_main.subprocess.check_output")
    def test_handles_called_process_error(
        self,
        mock_check_output: mock.MagicMock,
        mock_which: mock.MagicMock,
    ) -> None:
        mock_which.return_value = "/usr/bin/nvidia-smi"
        mock_check_output.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd="nvidia-smi"
        )

        result = _get_gpu_sample()
        assert result is None

    @pytest.mark.ai_generated
    @mock.patch("con_duct.duct_main.shutil.which")
    @mock.patch("con_duct.duct_main.subprocess.check_output")
    def test_multi_gpu_parsing(
        self,
        mock_check_output: mock.MagicMock,
        mock_which: mock.MagicMock,
    ) -> None:
        mock_which.return_value = "/usr/bin/nvidia-smi"
        mock_check_output.return_value = (
            "0, 45, 23, 4096, 16384\n" "1, 30, 15, 2048, 16384\n"
        )

        result = _get_gpu_sample()

        assert result is not None
        assert len(result.stats) == 2
        assert result.total_utilization_gpu == 75.0  # 45 + 30
        assert result.total_memory_used == (4096 + 2048) * 1024 * 1024

    @pytest.mark.ai_generated
    @mock.patch("con_duct.duct_main.shutil.which")
    @mock.patch("con_duct.duct_main.subprocess.check_output")
    def test_handles_malformed_output(
        self,
        mock_check_output: mock.MagicMock,
        mock_which: mock.MagicMock,
    ) -> None:
        mock_which.return_value = "/usr/bin/nvidia-smi"
        mock_check_output.return_value = "malformed output\n"

        result = _get_gpu_sample()
        assert result is None

    @pytest.mark.ai_generated
    @mock.patch("con_duct.duct_main.shutil.which")
    @mock.patch("con_duct.duct_main.subprocess.check_output")
    def test_custom_timeout(
        self,
        mock_check_output: mock.MagicMock,
        mock_which: mock.MagicMock,
    ) -> None:
        mock_which.return_value = "/usr/bin/nvidia-smi"
        mock_check_output.return_value = "0, 45, 23, 4096, 16384\n"

        _get_gpu_sample(timeout=10.0)

        mock_check_output.assert_called_once()
        call_kwargs = mock_check_output.call_args[1]
        assert call_kwargs["timeout"] == 10.0

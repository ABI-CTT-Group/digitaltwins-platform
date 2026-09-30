"""Tests for ``digitaltwins.tools.validation.find_tool_cwl``."""
import pytest

from digitaltwins.tools.validation import find_tool_cwl


def _tool(root, *cwl_names):
    (root / "primary").mkdir(parents=True)
    (root / "code").mkdir()
    for name in cwl_names:
        (root / "primary" / name).write_text("cwlVersion: v1.2\nclass: CommandLineTool\n")
    return root


def test_single_tool_cwl_is_found(tmp_path):
    _tool(tmp_path, "tool_convert.cwl")
    assert find_tool_cwl(tmp_path) == tmp_path / "primary" / "tool_convert.cwl"


def test_wrapper_folder_is_unwrapped(tmp_path):
    _tool(tmp_path / "my_tool", "tool_convert.cwl")
    assert find_tool_cwl(tmp_path) == tmp_path / "my_tool" / "primary" / "tool_convert.cwl"


def test_missing_primary_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="primary/"):
        find_tool_cwl(tmp_path)


def test_no_cwl_is_rejected(tmp_path):
    _tool(tmp_path)
    with pytest.raises(ValueError, match="tool_"):
        find_tool_cwl(tmp_path)


def test_two_cwls_are_rejected(tmp_path):
    _tool(tmp_path, "tool_a.cwl", "tool_b.cwl")
    with pytest.raises(ValueError, match="exactly one"):
        find_tool_cwl(tmp_path)


def test_cwl_without_tool_prefix_is_rejected(tmp_path):
    _tool(tmp_path, "convert.cwl")
    with pytest.raises(ValueError, match="tool_"):
        find_tool_cwl(tmp_path)


def test_cwl_in_a_subfolder_is_not_counted(tmp_path):
    _tool(tmp_path)
    (tmp_path / "primary" / "sub-1").mkdir()
    (tmp_path / "primary" / "sub-1" / "tool_convert.cwl").write_text("")
    with pytest.raises(ValueError, match="tool_"):
        find_tool_cwl(tmp_path)

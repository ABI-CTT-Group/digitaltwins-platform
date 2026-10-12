"""Tests for ``digitaltwins.models.validation.validate_model_structure``."""
import tempfile
import unittest
from pathlib import Path

from digitaltwins.models.validation import validate_model_structure


class ValidateModelStructureTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _model(self, root: Path) -> None:
        (root / "dataset_description.xlsx").write_bytes(b"")
        trainer = root / "primary" / "nnUNetTrainer__nnUNetPlans__3d_fullres" / "fold_0"
        trainer.mkdir(parents=True)
        (trainer / "checkpoint_final.pth").write_bytes(b"weights")

    def test_valid_model_with_nested_files(self) -> None:
        self._model(self.root)
        ok, msg = validate_model_structure(self.root)
        self.assertTrue(ok, msg)
        self.assertEqual(msg, "")

    def test_valid_model_with_json_description_and_top_level_file(self) -> None:
        (self.root / "dataset_description.json").write_text("{}")
        (self.root / "primary").mkdir()
        (self.root / "primary" / "model.onnx").write_bytes(b"x")
        ok, msg = validate_model_structure(self.root)
        self.assertTrue(ok, msg)

    def test_missing_dataset_description_fails(self) -> None:
        (self.root / "primary").mkdir()
        (self.root / "primary" / "model.onnx").write_bytes(b"x")
        ok, msg = validate_model_structure(self.root)
        self.assertFalse(ok)
        self.assertIn("dataset_description", msg)

    def test_missing_primary_fails(self) -> None:
        (self.root / "dataset_description.xlsx").write_bytes(b"")
        ok, msg = validate_model_structure(self.root)
        self.assertFalse(ok)
        self.assertIn("primary/", msg)

    def test_primary_with_only_empty_folders_fails(self) -> None:
        (self.root / "dataset_description.xlsx").write_bytes(b"")
        (self.root / "primary" / "fold_0").mkdir(parents=True)
        ok, msg = validate_model_structure(self.root)
        self.assertFalse(ok)
        self.assertIn("no model files", msg)

    def test_wrapper_directory_is_unwrapped(self) -> None:
        wrapper = self.root / "model_skin_test"
        wrapper.mkdir()
        self._model(wrapper)
        ok, msg = validate_model_structure(self.root)
        self.assertTrue(ok, msg)

    def test_missing_staging_dir_fails(self) -> None:
        ok, msg = validate_model_structure(self.root / "nope")
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()

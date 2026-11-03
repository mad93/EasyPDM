"""Macro regression tests without a FreeCAD installation.

Run: python3 -m unittest discover -s EasyPDM.FreeCad/tests -v
Only the functions under test are loaded; GUI/network dependencies are mocked.
"""
import ast
import ntpath
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


MACRO = Path(__file__).resolve().parents[1] / "EasyPDMUpload.FCMacro"


def load_function(name, namespace):
    tree = ast.parse(MACRO.read_text(encoding="utf-8"))
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(MACRO), "exec"), namespace)
    return namespace[name]


class UploadTests(unittest.TestCase):
    def upload_namespace(self):
        doc = SimpleNamespace(FileName=r"C:\CAD\EngineBlock.FCStd", Label="EngineBlock")

        def save_as(document, path):
            document.FileName = path
            return True

        ns = {
            "os": SimpleNamespace(path=ntpath),
            "sanitize_filename": lambda name: name,
            "revision_label": lambda revision: "A",
            "_ensure_fully_loaded": lambda document: document,
            "_save_local_as_pdm_name": Mock(side_effect=save_as),
            "_refresh_links_to": Mock(),
            "api_get": Mock(return_value=[]),
            "api_delete": Mock(),
            "api_upload_file": Mock(),
            "_upload_step_attachment": Mock(),
            "_upload_pdf_attachment": Mock(),
            "_push_mass_and_material": Mock(),
            # A remote Linux storage path must never be requested or created locally.
            "get_storage_root": Mock(side_effect=AssertionError("server path used locally")),
            "api_register_attachment": Mock(side_effect=AssertionError("register used")),
        }
        return doc, ns

    def test_windows_client_uses_http_and_keeps_local_names_and_links(self):
        doc, ns = self.upload_namespace()
        upload = load_function("_rename_and_upload", ns)
        result = upload(doc, "item-id", "5(EngineBlock)", "EngineBlock", 1,
                        target_folder=r"C:\CAD\PDM", export_step=True, export_pdf=True)
        expected = r"C:\CAD\PDM\5(EngineBlock).A.FCStd"
        self.assertEqual(doc.FileName, expected)
        self.assertEqual(doc.Label, "5(EngineBlock).A")
        self.assertTrue(result["localRenamed"])
        ns["_refresh_links_to"].assert_called_once_with(doc)
        ns["api_upload_file"].assert_called_once_with(
            "/items/item-id/attachments", expected,
            override_filename="5(EngineBlock).A.FCStd", extra_fields={"role": "cad"})
        ns["get_storage_root"].assert_not_called()
        ns["api_register_attachment"].assert_not_called()
        ns["_upload_step_attachment"].assert_called_once_with(doc, "item-id")
        ns["_upload_pdf_attachment"].assert_called_once_with(doc, "item-id")

    def test_reupload_replaces_only_same_filename(self):
        doc, ns = self.upload_namespace()
        ns["api_get"].return_value = [
            {"id": "same", "fileName": "5(EngineBlock).A.FCStd"},
            {"id": "previous", "fileName": "5(EngineBlock).B.FCStd"},
        ]
        upload = load_function("_rename_and_upload", ns)
        upload(doc, "item-id", "5(EngineBlock)", "EngineBlock", 1, export_step=False)
        ns["api_delete"].assert_called_once_with("/attachments/same")
        ns["api_upload_file"].assert_called_once()
        ns["_upload_step_attachment"].assert_not_called()

    def test_http_failure_is_not_reported_as_success(self):
        doc, ns = self.upload_namespace()
        ns["api_upload_file"].side_effect = RuntimeError("HTTP upload failed")
        upload = load_function("_rename_and_upload", ns)
        with self.assertRaisesRegex(RuntimeError, "HTTP upload failed"):
            upload(doc, "item-id", "5(EngineBlock)", "EngineBlock", 1)
        ns["_upload_step_attachment"].assert_not_called()
        ns["_push_mass_and_material"].assert_not_called()

    def test_failure_closes_progress_and_still_saves_documents(self):
        doc = SimpleNamespace(FileName=r"C:\CAD\EngineBlock.FCStd",
                              recompute=Mock(), save=Mock())
        dialog = SimpleNamespace(exec=Mock(return_value=1), result_folder=r"C:\CAD")
        ns = {
            "os": SimpleNamespace(path=ntpath),
            "App": SimpleNamespace(ActiveDocument=doc, Console=SimpleNamespace(PrintError=Mock())),
            "QtWidgets": SimpleNamespace(QDialog=SimpleNamespace(Accepted=1),
                                          QMessageBox=Mock()),
            "ensure_logged_in": Mock(return_value=True),
            "TargetFolderDialog": Mock(return_value=dialog),
            "_send_and_link": Mock(side_effect=RuntimeError("upload rejected")),
            "_save_open_documents": Mock(),
            "progress_mark": Mock(),
            "progress_finish": Mock(),
            "TOP_DOCUMENT_PROGRESS_KEY": "__top__",
            "_main_window": Mock(return_value=None),
            "t": lambda key, **kwargs: str(kwargs),
        }
        load_function("run", ns)()
        ns["progress_mark"].assert_called_once_with("__top__", "failed")
        ns["progress_finish"].assert_called_once()
        ns["_save_open_documents"].assert_called_once()
        ns["QtWidgets"].QMessageBox.critical.assert_called_once()
        self.assertIn("upload rejected", ns["App"].Console.PrintError.call_args.args[0])


if __name__ == "__main__":
    unittest.main()

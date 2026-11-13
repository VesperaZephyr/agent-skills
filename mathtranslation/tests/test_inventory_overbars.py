import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "inventory_overbars.py"
spec = importlib.util.spec_from_file_location("inventory_overbars", MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class InventoryTest(unittest.TestCase):
    def test_nested_comments_escaped_percent_and_unbraced(self):
        text = (r"$\overline{A+\overline{B}}$ % \bar{ignored}" "\n"
                r"\% $\bar\alpha + \bar u + \bar{a\{b\}}$" "\n"
                r"\overline{broken" "\n")
        with patch.object(Path, "read_bytes", return_value=text.encode("utf-8")):
            rows = list(mod.inventory(Path("sample.tex")))
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[0]["argument"], r"{A+\overline{B}}")
        self.assertEqual(rows[2]["argument"], r"\alpha")
        self.assertEqual(rows[3]["argument"], "u")
        self.assertEqual(rows[4]["argument"], r"{a\{b\}}")
        self.assertEqual(rows[5]["parse_status"], "unclosed_group")
        self.assertEqual(rows[2]["line"], 2)


if __name__ == "__main__":
    unittest.main()

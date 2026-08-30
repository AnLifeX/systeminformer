import json
import re
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
FINDOBJ_SOURCE = REPOSITORY_ROOT / "SystemInformer" / "findobj.c"
CATALOG_PATH = REPOSITORY_ROOT / "tools" / "localization" / "zh-CN.json"


class FindObjectLocalizationTests(unittest.TestCase):
    def test_object_type_display_names_preserve_internal_search_keys(self):
        source = FINDOBJ_SOURCE.read_text(encoding="utf-8")
        table_start = source.index(
            "static const PHP_OBJECT_TYPE_DISPLAY_NAME PhpObjectTypeDisplayNames[]"
        )
        table_end = source.index("};", table_start)
        table_source = source[table_start:table_end]
        table_rows = re.findall(
            r'\{ L"(?P<type>[^"]+)", L"(?P<display>[^"]+)" \}',
            table_source,
        )

        self.assertTrue(table_rows)
        self.assertEqual(len(table_rows), len({type_name for type_name, _ in table_rows}))
        self.assertTrue(
            all(type_name == display_name for type_name, display_name in table_rows)
        )

        catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        display_group = next(
            group
            for group in catalog["groups"]
            if group["id"] == "find-objects-object-type-display-names"
        )
        translations = {
            item["source"]: item["translation"] for item in display_group["items"]
        }

        self.assertEqual({type_name for type_name, _ in table_rows}, set(translations))
        self.assertTrue(all(translations.values()))
        self.assertEqual(display_group["context"], ', L"{text}" }')

        for type_name, display_name in table_rows:
            source_row = f'{{ L"{type_name}", L"{display_name}" }}'
            translated_row = source_row.replace(
                display_group["context"].replace("{text}", type_name),
                display_group["context"].replace("{text}", translations[type_name]),
            )
            self.assertEqual(
                translated_row,
                f'{{ L"{type_name}", L"{translations[type_name]}" }}',
            )

        self.assertIn("ComboBox_SetItemData", source)
        self.assertIn("ComboBox_GetItemData", source)
        self.assertNotIn(
            "PhGetWindowText(context->TypeWindowHandle)",
            source,
        )
        self.assertIn(
            "PhMoveReference(&context->SearchTypeString, PhReferenceObject(typeName));",
            source,
        )


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""
Tests for marketplace validator (mp_validator).

Validates:
- get_marketplaces_registered_from_payload
- extract_mentioned_marketplaces
- validate_marketplace_access
- validate_from_context

Run from project root:
  python -m pytest scripts/test_mp_validator.py -v
  # or
  python scripts/test_mp_validator.py
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import unittest

# Import mp_validator directly to avoid pulling in agent_service (langchain_aws, etc.)
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "mp_validator",
    project_root / "src" / "services" / "mp_validator.py",
)
_mp = importlib.util.module_from_spec(_spec)
# Load utils.logger_config for get_logger used inside mp_validator
sys.path.insert(0, str(project_root))
import utils.logger_config  # noqa: E402
_spec.loader.exec_module(_mp)

get_marketplaces_registered_from_payload = _mp.get_marketplaces_registered_from_payload
extract_mentioned_marketplaces = _mp.extract_mentioned_marketplaces
validate_marketplace_access = _mp.validate_marketplace_access
validate_from_context = _mp.validate_from_context

# Use the same names from the loaded module (already assigned above)
get_marketplaces_registered_from_payload = _mp.get_marketplaces_registered_from_payload
extract_mentioned_marketplaces = _mp.extract_mentioned_marketplaces
validate_marketplace_access = _mp.validate_marketplace_access
validate_from_context = _mp.validate_from_context


class TestGetMarketplacesRegisteredFromPayload(unittest.TestCase):
    def test_empty_or_none_returns_empty_list(self):
        self.assertEqual(get_marketplaces_registered_from_payload(None), [])
        self.assertEqual(get_marketplaces_registered_from_payload({}), [])

    def test_missing_key_returns_empty_list(self):
        self.assertEqual(get_marketplaces_registered_from_payload({"userId": "1"}), [])

    def test_non_list_returns_empty_list(self):
        self.assertEqual(get_marketplaces_registered_from_payload({"marketplaces_registered": "Amazon"}), [])
        self.assertEqual(get_marketplaces_registered_from_payload({"marketplaces_registered": None}), [])

    def test_returns_list_as_provided(self):
        self.assertEqual(
            get_marketplaces_registered_from_payload({"marketplaces_registered": ["Amazon", "Flipkart"]}),
            ["Amazon", "Flipkart"],
        )
        self.assertEqual(
            get_marketplaces_registered_from_payload({"marketplaces_registered": ["Amazon.in", "ONDC"]}),
            ["Amazon.in", "ONDC"],
        )
        self.assertEqual(
            get_marketplaces_registered_from_payload({"marketplaces_registered": []}),
            [],
        )


class TestExtractMentionedMarketplaces(unittest.TestCase):
    def test_empty_or_none_returns_empty_set(self):
        self.assertEqual(extract_mentioned_marketplaces(""), set())
        self.assertEqual(extract_mentioned_marketplaces(None), set())

    def test_single_mention(self):
        self.assertEqual(extract_mentioned_marketplaces("What is my Walmart sales?"), {"walmart"})
        self.assertEqual(extract_mentioned_marketplaces("Show my Amazon orders"), {"amazon"})
        self.assertEqual(extract_mentioned_marketplaces("Flipkart returns"), {"flipkart"})
        self.assertEqual(extract_mentioned_marketplaces("ONDC inventory"), {"ondc"})

    def test_multiple_mentions(self):
        self.assertEqual(
            extract_mentioned_marketplaces("sales across Amazon, ONDC and Flipkart"),
            {"amazon", "ondc", "flipkart"},
        )
        self.assertEqual(
            extract_mentioned_marketplaces("What is my sales on Walmart and Shopify?"),
            {"walmart", "shopify"},
        )

    def test_case_insensitive(self):
        self.assertEqual(extract_mentioned_marketplaces("AMAZON sales"), {"amazon"})
        self.assertEqual(extract_mentioned_marketplaces("my amazon and Walmart data"), {"amazon", "walmart"})

    def test_aliases(self):
        self.assertEqual(extract_mentioned_marketplaces("Amazon.in dashboard"), {"amazon"})
        self.assertEqual(extract_mentioned_marketplaces("Amazon.com reports"), {"amazon"})

    def test_no_false_positives_inside_words(self):
        self.assertEqual(extract_mentioned_marketplaces("myamazon or amazonian"), set())
        self.assertEqual(extract_mentioned_marketplaces("random text about products"), set())


class TestValidateMarketplaceAccess(unittest.TestCase):
    def test_no_mention_always_valid(self):
        ok, err = validate_marketplace_access("What is the weather?", "What is the weather?", ["Amazon"])
        self.assertTrue(ok)
        self.assertIsNone(err)

    def test_mentioned_and_registered_valid(self):
        ok, err = validate_marketplace_access("My Amazon sales", "My Amazon sales", ["Amazon"])
        self.assertTrue(ok)
        self.assertIsNone(err)

        ok, err = validate_marketplace_access(
            "What is my sales?",
            "What is my sales across Amazon, ONDC and Flipkart?",
            ["Amazon", "ONDC", "Flipkart"],
        )
        self.assertTrue(ok)
        self.assertIsNone(err)

    def test_mentioned_not_registered_invalid(self):
        ok, err = validate_marketplace_access("My Walmart sales", "My Walmart sales", ["Amazon"])
        self.assertFalse(ok)
        self.assertIsNotNone(err)
        self.assertEqual(err["reply"], "")
        self.assertEqual(err["work_status"], "You have not registered this marketplace")
        self.assertEqual(err["intent"], "marketplace_validation_failed")
        self.assertEqual(err["unregistered_marketplaces"], ["walmart"])

    def test_enriched_adds_unregistered_invalid(self):
        # User said "What is my sales?"; enriched added "Amazon, ONDC, Flipkart" but user only has Amazon
        ok, err = validate_marketplace_access(
            "What is my sales?",
            "What is my sales across Amazon, ONDC and Flipkart?",
            ["Amazon"],
        )
        self.assertFalse(ok)
        self.assertIsNotNone(err)
        self.assertEqual(err["reply"], "")
        self.assertIn("You have not registered", err["work_status"])
        self.assertIn("ondc", err["unregistered_marketplaces"])
        self.assertIn("flipkart", err["unregistered_marketplaces"])

    def test_multiple_unregistered_message(self):
        ok, err = validate_marketplace_access(
            "Sales on Walmart and Shopify",
            "Sales on Walmart and Shopify",
            ["Amazon"],
        )
        self.assertFalse(ok)
        self.assertEqual(err["reply"], "")
        self.assertIn("these marketplaces", err["work_status"])
        self.assertIn("Walmart", err["work_status"])
        self.assertIn("Shopify", err["work_status"])

    def test_registered_alias_matches(self):
        ok, err = validate_marketplace_access("Amazon.in reports", "Amazon.in reports", ["Amazon.in"])
        self.assertTrue(ok)
        self.assertIsNone(err)


class TestValidateFromContext(unittest.TestCase):
    def test_valid_from_context(self):
        context = {"marketplaces_registered": ["Amazon", "Flipkart"], "userId": "1"}
        ok, err = validate_from_context("My Amazon sales", "My Amazon sales", context)
        self.assertTrue(ok)
        self.assertIsNone(err)

    def test_invalid_from_context(self):
        context = {"marketplaces_registered": ["Amazon"], "userId": "1"}
        ok, err = validate_from_context("My Walmart orders", "My Walmart orders", context)
        self.assertFalse(ok)
        self.assertIsNotNone(err)
        self.assertEqual(err["reply"], "")
        self.assertEqual(err["work_status"], "You have not registered this marketplace")

    def test_empty_context_treated_as_no_registered(self):
        context = {}
        ok, err = validate_from_context("My Amazon sales", "My Amazon sales", context)
        # Mentioned Amazon but registered is empty -> invalid
        self.assertFalse(ok)
        self.assertIsNotNone(err)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python


# ==============================================================================
# Imports and constants
# ==============================================================================

import json
import os

from validators.validators import Draft4Validator, BASEDIR


TEST_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "data")

SCHEMA_TO_TESTS = {
    "delta": "delta",
    "discovery": "discovery",
    "signalk": "full",
    "hello": "hello",
    "messages/subscribe": "subscribe",
    "messages/unsubscribe": "unsubscribe",
    "vessel": "vessel",
}


# ==============================================================================
# Utilities
# ==============================================================================

def assert_schema_file_valid(validator, filepath):
    with open(filepath, "r") as f:
        instance = json.load(f)
        try:
            validator.assert_is_valid(instance)
        except AssertionError as e:
            print "error validating " + filepath
            raise e


def assert_schema_file_invalid(validator, filepath):
    with open(filepath, "r") as f:
        instance = json.load(f)
        try:
            validator.assert_is_valid(instance)
        except AssertionError:
            pass
        else:
            raise AssertionError(filepath + " is valid but should be invalid")


def do_schema_validation(schema_name):
    schema_uri = "file://{}/schemas/{}.json".format(BASEDIR, schema_name)
    validator = Draft4Validator.from_schema_uri(schema_uri)
    folder_prefix = SCHEMA_TO_TESTS[schema_name]
    valid_folder = "{}/{}-valid".format(TEST_DATA_DIR, folder_prefix)
    for root, dirs, files in os.walk(valid_folder):
        for fname in files:
            if not fname.endswith(".json"):
                continue
            assert_schema_file_valid(validator, os.path.join(root, fname))
    invalid_folder = "{}/{}-invalid".format(TEST_DATA_DIR, folder_prefix)
    for root, dirs, files in os.walk(invalid_folder):
        for fname in files:
            if not fname.endswith(".json"):
                continue
            assert_schema_file_invalid(validator, os.path.join(root, fname))


# ==============================================================================
# Test cases
# ==============================================================================

def test_delta():
    # FIXME
    # Tests failing:
    # - data/vessel-invalid/environment-inside_invalid_property.json is valid
    # but should be invalid
    # - data/vessel-invalid/
    # environment-inside_humidity_rather_than_relativeHumidity.json is valid
    # but should be invalid
    do_schema_validation("delta")


def test_discovery():
    do_schema_validation("discovery")


def test_signalk():
    # FIXME
    do_schema_validation("signalk")


def test_hello():
    do_schema_validation("hello")


def test_subscribe():
    do_schema_validation("messages/subscribe")


def test_unsubscribe():
    do_schema_validation("messages/unsubscribe")


def test_vessel():
    # FIXME
    # Tests failing:
    # - data/full-invalid/alarms-must_use_alarmStateEnum.json is valid but
    # should be invalid
    # - data/full-invalid/sar-sails.json is valid but should be invalid
    # - data/full-invalid/alarms-must_use_alarmStateEnum.json is valid but
    # should be invalid
    # - data/full-invalid/alarms-must_use_array_of_states_not_string.json is
    # valid but should be invalid
    # - data/full-invalid/alarms-must_use_alarmMethod_array_with_enum.json is
    # valid but should be invalid
    # - data/full-invalid/aton-has_sails.json is valid but should be invalid
    # - data/full-invalid/
    # sources-valid_sources_with_no_0183_n2k_or_ais_and_other_items.json is
    # valid but should be invalid
    # - data/full-valid/electrical-full_tree.json is invalid but should be
    # valid
    do_schema_validation("vessel")

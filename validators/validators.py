#!/usr/bin/env python
"""
This module add utilities to jsonschema and allows to:
- use local jsonschema definition files (via a new RefResolver subclass that
  removes the "id" schema property to avoid the reference lookup scope reset)
- utility methods (monkey-patched) to jsonschema validator classes

Usage example:
```
from validators import Draft4Validator

validator = Draft4Validator.from_schema_uri(FULL_STATE_SCHEMA_URI)

validator.assert_is_valid(full_state)
```
"""


# ==============================================================================
# Imports and constants
# ==============================================================================

import os
import re
import json
import jsonschema
from jsonschema import (Draft3Validator, Draft4Validator)


BASEDIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FULL_STATE_SCHEMA_URI = "file://{}/schemas/signalk.json".format(BASEDIR)
DELTA_SCHEMA_URI = "file://{}/schemas/delta.json".format(BASEDIR)


# ==============================================================================
# Utilities
# ==============================================================================

def monkey_patch(cls, **kwargs):
    def wrapper(function):
        try:
            func_name = kwargs.get("func_name", function.__name__)
        except AttributeError:
            # For classmethod and staticmethod
            func_name = kwargs.get("func_name", function.__func__.__name__)
        setattr(cls, func_name, function)
        return function
    return wrapper


# ==============================================================================
# JsonSchema utilities
# ==============================================================================

class RefResolverNoReset(jsonschema.RefResolver):
    """
    A subclass of jsonschema.RefResolver that allow to NOT reset the current
    scope (url at key "id") where the references are looked up.
    """

    def __init__(self, *args, **kwargs):
        self.reset_uri = kwargs.pop("reset_uri", False)
        super(RefResolverNoReset, self).__init__(*args, **kwargs)

    def resolve_remote(self, uri):
        result = super(RefResolverNoReset, self).resolve_remote(uri)
        if not self.reset_uri:
            try:
                result.pop("id")
            except KeyError:
                pass
        return result


def find_additional_properties_in_children(instance, schema):
    """
    #TODO Update docstring
    Return the set of additional properties for the given ``instance``.

    Weeds out properties that should have been validated by ``properties`` and
    / or ``patternProperties``.

    Assumes ``instance`` is list-like already.

    """
    props = set()
    pattern_props = set()
    for i, subschema in enumerate(schema):
        props = props.union(set(subschema.get("properties", {})))
        pattern_props = pattern_props.union(
            set(subschema.get("patternProperties", {})))
    patterns = "|".join(pattern_props)
    properties = []
    for prop in instance:
        if isinstance(prop, basestring) and prop not in props:
            if patterns and re.search(patterns, prop):
                continue
            properties.append(prop)
    return set(properties), pattern_props


def ban_unknown_properties(validator, bup, instance, schema,
                           collect_children_properties=False):
    """
    #TODO Update docstring
    """
    if not bup:
        return
    if collect_children_properties:
        if not validator.is_type(instance, "array"):
            return
        extras, patterns = find_additional_properties_in_children(instance,
                                                                  schema)
    else:
        if (
            not validator.is_type(instance, "object")
            or not ("properties" in schema or "patternProperties" in schema)
        ):
            return
        extras = set(jsonschema._utils.find_additional_properties(
            instance, schema))
        patterns = sorted(schema.get("patternProperties", {}))
    if extras:
        if patterns:
            if len(extras) == 1:
                verb = "does"
            else:
                verb = "do"
            error = "%s: %s %s not match any of the regexes: %s" % (
                "banUnknownProperties",
                ", ".join(map(repr, sorted(extras))),
                verb,
                ", ".join(map(repr, patterns)),
            )
            yield jsonschema.exceptions.ValidationError(error)
        else:
            error = "banUnknownProperties (%s %s unexpected)"
            yield jsonschema.exceptions.ValidationError(
                error % jsonschema._utils.extras_msg(extras) +
                "\nschema: " + str(schema))


def validator_error_gen(validator_name, validator_function, validator,
                        value, instance, schema, **kwargs):
    errors = validator_function(validator, value, instance, schema,
                                **kwargs) or ()
    for error in errors:
        # set details if not already set by the called fn
        error._set(
            validator=validator_name,
            validator_value=value,
            instance=instance,
            schema=schema,
        )
        if validator_name != u"$ref":
            error.schema_path.appendleft(validator_name)
        yield error


@monkey_patch(Draft3Validator)
@monkey_patch(Draft4Validator)
def iter_errors(self, instance, _schema=None, banUnknownProperties=True):
    if _schema is None:
        _schema = self.schema
    scope = _schema.get(u"id")
    if scope:
        self.resolver.push_scope(scope)
    try:
        found_key = False
        if banUnknownProperties:
            for key in ["allOf", "anyOf"]:
                prop = _schema.get(key)
                bup = _schema.get("banUnknownProperties", banUnknownProperties)
                if prop:
                    found_key = True
                    errors = validator_error_gen(
                        "banUnknownProperties", ban_unknown_properties, self,
                        bup, instance, prop, collect_children_properties=True)
                    for error in errors:
                        yield error
                    for item in prop:
                        ref = item.get(u"$ref")
                        if ref is not None:
                            _, resolved = self.resolver.resolve(ref)
                            resolved.setdefault("banUnknownProperties", False)
                        else:
                            item.setdefault("banUnknownProperties", False)
        ref = _schema.get(u"$ref")
        if ref is not None:
            validators = [(u"$ref", ref)]
        else:
            validators = jsonschema.compat.iteritems(_schema)
            if banUnknownProperties and not found_key:
                bup = _schema.get("banUnknownProperties", banUnknownProperties)
                errors = validator_error_gen(
                        "banUnknownProperties", ban_unknown_properties, self,
                        bup, instance, _schema)
                for error in errors:
                    yield error
        for k, v in validators:
            validator = self.VALIDATORS.get(k)
            if validator is None:
                continue
            errors = validator_error_gen(k, validator, self, v, instance,
                                         _schema)
            for error in errors:
                yield error
    finally:
        if scope:
            self.resolver.pop_scope()


@monkey_patch(Draft3Validator, func_name="from_schema_uri")
@monkey_patch(Draft4Validator, func_name="from_schema_uri")
@classmethod
def get_validator_from_schema_uri(validator_cls, base_uri,
                                  resolver_cls=RefResolverNoReset,
                                  reset_uri=False):
    """
    Return a validator instance with a resolver of the given class and the
    schema loaded from given URI.
    """
    schema_dump = jsonschema.compat.urlopen(base_uri).read()
    schema = json.loads(schema_dump.decode("utf-8"))
    if not reset_uri:
        try:
            schema.pop("id")
        except KeyError:
            pass
    resolver = RefResolverNoReset(base_uri, schema, reset_uri=reset_uri)
    return validator_cls(schema, resolver=resolver)


@monkey_patch(Draft3Validator)
@monkey_patch(Draft4Validator)
def assert_is_valid(self, instance, banUnknownProperties=True):
    """
    Validate a schema instance and raise assertion error if not valid.

    Unlike the "validate" method, this method prints all the validation errors
    in the AssertionError.
    """
    error_count = 0
    error_msg = ""
    err_line = "\n-----\n{}\n at path \n{}\n in instance \n{}"
    err_gen = self.iter_errors(instance,
                               banUnknownProperties=banUnknownProperties)
    for error in sorted(err_gen, key=str):
        error_count += 1
        error_msg += err_line.format(
            error.message, ", ".join([str(p) for p in error.absolute_path]),
            error.instance)
    msg = "jsonchema validation failed with {} errors:{}"
    assert error_count == 0, msg.format(error_count, error_msg)

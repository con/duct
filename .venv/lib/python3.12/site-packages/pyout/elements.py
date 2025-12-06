"""Style elements and schema validation.
"""

from collections.abc import Mapping
import functools
import jsonschema
import hashlib


schema = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "definitions": {
        # Plain style elements
        "align": {
            "description": "Alignment of text",
            "type": "string",
            "enum": ["left", "right", "center"],
            "default": "left",
            "scope": "column"},
        "bold": {
            "description": "Whether text is bold",
            "oneOf": [{"type": "boolean"},
                      {"$ref": "#/definitions/lookup"},
                      {"$ref": "#/definitions/re_lookup"},
                      {"$ref": "#/definitions/interval"}],
            "default": False,
            "scope": "field"},
        "color": {
            "description": "Foreground color of text",
            "oneOf": [{"type": "string",
                       "enum": ["black", "red", "green", "yellow",
                                "blue", "magenta", "cyan", "white"]},
                      {"$ref": "#/definitions/lookup"},
                      {"$ref": "#/definitions/re_lookup"},
                      {"$ref": "#/definitions/interval"}],
            "default": "black",
            "scope": "field"},
        "hide": {
            "description": """Whether to hide column.  A value of True
            unconditionally hides the column.  'if_missing' hides the column
            until the first non-missing value is encountered.""",
            "oneOf": [{"type": "boolean"},
                      {"type": "string", "enum": ["if_missing"]}],
            "default": False,
            "scope": "column"},
        "underline": {
            "description": "Whether text is underlined",
            "oneOf": [{"type": "boolean"},
                      {"$ref": "#/definitions/lookup"},
                      {"$ref": "#/definitions/re_lookup"},
                      {"$ref": "#/definitions/interval"}],
            "default": False,
            "scope": "field"},
        "width_type": {
            "description": "Type for numeric values in 'width'",
            "oneOf": [{"type": "integer", "minimum": 1},
                      {"type": "number",
                       "exclusiveMinimum": 0,
                       "exclusiveMaximum": 1}]},
        "width": {
            "description": """Width of field.  With the default value, 'auto',
            the column width is automatically adjusted to fit the content and
            may be truncated to ensure that the entire row fits within the
            available output width.  An integer value forces all fields in a
            column to have a width of the specified value.

            In addition, an object can be specified.  Its 'min' and 'max' keys
            specify the minimum and maximum widths allowed, whereas the 'width'
            key specifies a fixed width.  The values can be given as an integer
            (representing the number of characters) or as a fraction, which
            indicates the proportion of the total table width (typically the
            width of your terminal).

            The 'marker' key specifies the marker used for truncation ('...' by
            default).  Where the field is truncated can be configured with
            'truncate': 'right' (default), 'left', or 'center'.

            The object can also include a 'weight' key.  Conceptually,
            assigning widths to each column can be (roughly) viewed as each
            column claiming _one_ character of available width at a time until
            a column is at its maximum width or there is no available width
            left.  Setting a column's weight to an integer N makes it claim N
            characters each iteration.""",
            "oneOf": [{"$ref": "#/definitions/width_type"},
                      {"type": "string",
                       "enum": ["auto"]},
                      {"type": "object",
                       "properties": {
                           "max": {"$ref": "#/definitions/width_type"},
                           "min": {"$ref": "#/definitions/width_type"},
                           "width": {"$ref": "#/definitions/width_type"},
                           "weight": {"type": "integer", "minimum": 1},
                           "marker": {"type": ["string", "boolean"]},
                           "truncate": {"type": "string",
                                        "enum": ["left",
                                                 "right",
                                                 "center"]}},
                       "additionalProperties": False}],
            "default": "auto",
            "scope": "column"},
        # Other style elements
        "aggregate": {
            "description": """A function that produces a summary value.  This
            function will be called with all of the column's (unprocessed)
            field values and should return a single value to be displayed.""",
            "scope": "column"},
        "delayed": {
            "description": """Don't wait for this column's value.
            The accessor will be wrapped in a function and called
            asynchronously.  This can be set to a string to mark columns as
            part of a "group".  All columns within a group will be accessed
            within the same callable.  True means to access the column's value
            in its own callable (i.e. independently of other columns).""",
            "type": ["boolean", "string"],
            "scope": "field"},
        "missing": {
            "description": "Text to display for missing values",
            "type": "string",
            "default": "",
            "scope": "column"
        },
        "re_flags": {
            "description": """Flags passed to re.search when using re_lookup.
            See the documentation of the re module for a description of
            possible values.  'I' (ignore case) is the most likely value of
            interest.""",
            "type": "array",
            "items": [{"type": "string",
                       "enum": ["A", "I", "L", "M", "S", "U", "X"]}],
            "scope": "field"},
        "transform": {
            "description": """An arbitrary function.
            This function will be called with the (unprocessed) field value as
            the single argument and should return a transformed value.  Note:
            This function should not have side-effects because it may be called
            multiple times.""",
            "scope": "field"},
        # Complete list of column style elements
        "styles": {
            "type": "object",
            "properties": {"aggregate": {"$ref": "#/definitions/aggregate"},
                           "align": {"$ref": "#/definitions/align"},
                           "bold": {"$ref": "#/definitions/bold"},
                           "color": {"$ref": "#/definitions/color"},
                           "delayed": {"$ref": "#/definitions/delayed"},
                           "hide": {"$ref": "#/definitions/hide"},
                           "missing": {"$ref": "#/definitions/missing"},
                           "re_flags": {"$ref": "#/definitions/re_flags"},
                           "transform": {"$ref": "#/definitions/transform"},
                           "underline": {"$ref": "#/definitions/underline"},
                           "width": {"$ref": "#/definitions/width"}},
            "additionalProperties": False},
        # Mapping elements
        "interval": {
            "description": "Map a value within an interval to a style",
            "type": "object",
            "properties": {"interval":
                           {"type": "array",
                            "items": [
                                {"type": "array",
                                 "items": [{"type": ["number", "null"]},
                                           {"type": ["number", "null"]},
                                           {"type": ["string", "boolean"]}],
                                 "additionalItems": False}]}},
            "additionalProperties": False},
        "lookup": {
            "description": "Map a value to a style",
            "type": "object",
            "properties": {"lookup": {"type": "object"}},
            "additionalProperties": False},
        "re_lookup": {
            "description": """Apply a style to values that match a regular
            expression.  The regular expressions are matched with re.search and
            tried in order, stopping after the first match.  Flags for
            re.search can be specified via the re_flags style attribute.""",
            "type": "object",
            "properties": {"re_lookup":
                           {"type": "array",
                            "items": [
                                {"type": "array",
                                 "items": [{"type": "string"},
                                           {"type": ["string", "boolean"]}],
                                 "additionalItems": False}]}},
            "additionalProperties": False},
    },
    "type": "object",
    "properties": {
        "aggregate_": {
            "description": "Shared attributes for the summary rows",
            "oneOf": [{"type": "object",
                       "properties":
                       {"color": {"$ref": "#/definitions/color"},
                        "bold": {"$ref": "#/definitions/bold"},
                        "underline": {"$ref": "#/definitions/underline"}}},
                      {"type": "null"}],
            "default": {},
            "scope": "table"},
        "default_": {
            "description": "Default style of columns",
            "oneOf": [{"$ref": "#/definitions/styles"},
                      {"type": "null"}],
            "default": {"align": "left",
                        "hide": False,
                        "width": "auto"},
            "scope": "table"},
        "header_": {
            "description": "Attributes for the header row",
            "oneOf": [{"type": "object",
                       "properties":
                       {"color": {"$ref": "#/definitions/color"},
                        "bold": {"$ref": "#/definitions/bold"},
                        "underline": {"$ref": "#/definitions/underline"}}},
                      {"type": "null"}],
            "default": None,
            "scope": "table"},
        "separator_": {
            "description": "Separator used between fields",
            "type": "string",
            "default": " ",
            "scope": "table"},
        "width_": {
            "description": """Total width of table.
            This is typically not set directly by the user.  With the default
            null value, the width is set to the stream's width for interactive
            streams and as wide as needed to fit the content for
            non-interactive streams.""",
            "default": None,
            "oneOf": [{"type": "integer"},
                      {"type": "null"}],
            "scope": "table"}
    },
    # All other keys are column names.
    "additionalProperties": {"$ref": "#/definitions/styles"}
}


def default(prop):
    """Return the default value schema property.

    Parameters
    ----------
    prop : str
        A key for schema["properties"]
    """
    return schema["properties"][prop]["default"]


def adopt(style, new_style):
    if new_style is None:
        return style

    combined = {}
    for key, value in style.items():
        if isinstance(value, Mapping):
            combined[key] = dict(value, **new_style.get(key, {}))
        else:
            combined[key] = new_style.get(key, value)
    return combined


class StyleError(Exception):
    """Style is invalid or mispecified in some way.
    """
    pass


class StyleValidationError(StyleError):
    """Exception raised if the style schema does not validate.
    """
    def __init__(self, original_exception):
        msg = ("Invalid style\n\n{}\n\n\n"
               "See pyout.schema for style definition."
               .format(original_exception))
        super(StyleValidationError, self).__init__(msg)


class StrHasher():
    """A wrapper for objects that hashes based on the string representation.

    Primarily its purpose to provide a customized @StrHasher.lru_cache
    decorator which allows to cache based on the string representation of the
    argument of unhashable objects.
    """
    def __init__(self, obj):
        self.value = obj
        self.hash = hashlib.md5(str(obj).encode()).hexdigest()

    def __hash__(self):
        return hash(self.hash)

    def __eq__(self, other):
        return self.hash == other.hash

    @staticmethod
    def _to(func):
        def cached_func(*args, **kwargs):
            wrapper = StrHasher((args, kwargs))
            return func(wrapper)
        return cached_func

    @staticmethod
    def _from(func):
        def cached_func(wrapper):
            return func(*wrapper.value[0], **wrapper.value[1])
        return cached_func

    @classmethod
    def lru_cache(cls, maxsize=128):
        """
        Custom LRU cache decorator that allows for a custom hasher function.
        """
        def decorator(func):
            @functools.lru_cache(maxsize=maxsize)
            @cls._from
            def lru_cached_func(*args, **kwargs):
                return func(*args, **kwargs)

            # Interface cache operations
            cached_func = functools.wraps(func)(
                cls._to(
                    lru_cached_func
                )
            )
            for op in dir(lru_cached_func):
                if op.startswith('cache_'):
                   setattr(cached_func, op,
                    getattr(lru_cached_func, op))
            return cached_func
        return decorator


@StrHasher.lru_cache()  # the same styles could be checked over again
def validate(style):
    """Check `style` against pyout.styling.schema.

    Parameters
    ----------
    style : dict
        Style object to validate.

    Raises
    ------
    StyleValidationError if `style` is not valid.
    """
    try:
        jsonschema.validate(style, schema)
    except jsonschema.ValidationError as exc:
        new_exc = StyleValidationError(exc)
        # Don't dump the original jsonschema exception because it is already
        # included in the StyleValidationError's message.
        new_exc.__cause__ = None
        raise new_exc


def value_type(value):
    """Classify `value` of bold, color, and underline keys.

    Parameters
    ----------
    value : style value

    Returns
    -------
    str, {"simple", "lookup", "re_lookup", "interval"}
    """
    try:
        keys = list(value.keys())
    except AttributeError:
        return "simple"
    if keys in [["lookup"], ["re_lookup"], ["interval"]]:
        return keys[0]
    raise ValueError("Type of `value` could not be determined")

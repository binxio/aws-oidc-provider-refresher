import click
from typing import Optional, Tuple


class Tag(object):
    """
    a key value pair.
    >>> Tag("Name")
    Name
    >>> Tag("Name", "Value")
    Name=Value
    """

    def __init__(self, key: str, value: Optional[str] = None):
        super(Tag, self).__init__()
        self.key = key
        self.value = value

    @staticmethod
    def from_string(s: str):
        """
        Creates a tag from a string representation.
        >>> Tag.from_string("Name=Value")
        Name=Value
        >>> Tag.from_string("Name")
        Name
        >>> Tag.from_string("Name=ab=c").value
        'ab=c'
        """
        splits = s.split("=", 1)
        return Tag(key=splits[0], value=None if len(splits) == 1 else splits[1])

    def __repr__(self) -> str:
        return f"{self.key}={self.value}" if self.value else self.key


class TagFilter(object):
    """
    A boto3 tag filter
    >>> TagFilter((Tag("Name"),))
    [{'Key': 'Name', 'Values': []}]
    >>> TagFilter((Tag("Name", "Value"),))
    [{'Key': 'Name', 'Values': ['Value']}]
    >>> TagFilter((Tag("Name", "Value"), Tag("Name", "Value2")))
    [{'Key': 'Name', 'Values': ['Value', 'Value2']}]
    >>> TagFilter((Tag("Name", "Value"), Tag("Name", "Value")))
    [{'Key': 'Name', 'Values': ['Value']}]
    >>> TagFilter((Tag("Name", "Value"), Tag("Name", "Value2"), Tag("Region", "eu-west-1a"), Tag("Region", "eu-west-1b")))
    [{'Key': 'Name', 'Values': ['Value', 'Value2']}, {'Key': 'Region', 'Values': ['eu-west-1a', 'eu-west-1b']}]
    """

    def __init__(self, tags: Tuple[Tag]):
        self.filter = {}
        for tag in tags:
            key = tag.key
            if not self.filter.get(key):
                self.filter[key] = []
            if tag.value:
                if tag.value not in self.filter[key]:
                    self.filter[key].append(tag.value)

    def to_api(self):
        """
        returns an array of dictionaries with `Name` and `Values` set as expected by the boto3 api.
        >>> TagFilter([Tag("Name", "Value"), Tag("Name", "Value2")]).to_api()
        [{'Key': 'Name', 'Values': ['Value', 'Value2']}]
        """
        return [{"Key": k, "Values": self.filter[k]} for k in self.filter.keys()]

    def __repr__(self):
        return str(self.to_api())


class TagType(click.ParamType):
    """
    an AWS tag in the form <key>=<value> or <key>.
    """

    name = "tag"

    def convert(self, value, param, ctx):
        splits = value.split("=", 1)
        return Tag(key=splits[0], value=None if len(splits) == 1 else splits[1])

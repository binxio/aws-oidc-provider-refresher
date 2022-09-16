import unittest
import doctest
from aws_oidc_provider_refresher import schema, tag, command


def load_tests(loader, tests, ignore):
    tests.addTests(doctest.DocTestSuite(schema))
    tests.addTests(doctest.DocTestSuite(tag))
    tests.addTests(doctest.DocTestSuite(command))
    return tests


if __name__ == "__main__":
    unittest.main()

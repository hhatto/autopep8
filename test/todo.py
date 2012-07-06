"""Incomplete fixes."""


# E501: This should be wrapped similar to how pprint does it
{'2323k2323': 24232323, '2323323232323': 3434343434343434, '34434343434535535': 3434343434343434, '4334343434343': 3434343434}
# See below
{'2323323232323': 3434343434343434,
 '2323k2323': 24232323,
 '34434343434535535': 3434343434343434,
 '4334343434343': 3434343434}

# W601: Handle complicated cases
x = {1: 2}
y = {}
y.has_key(0) + x.has_key(x.has_key(0) + x.has_key(x.has_key(0) + x.has_key(1)))

# E123
if True:
    foo = (
        )

# E127
for k, v in sys.modules.items():
    if k in ('setuptools', 'pkg_resources') or (
        not os.path.exists(os.path.join(v.__path__[0], '__init__.py'))):
        sys.modules.pop(k)
parser = OptionParser(usage=usage)
parser.add_option("-v", "--version", dest="version",
                          help="use a specific zc.buildout version")

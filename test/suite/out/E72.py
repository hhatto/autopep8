#: E721
if isinstance(res, type(42)):
    pass
#: E721
if not isinstance(res, type("")):
    pass
#: E721
import types

if res == types.IntType:
    pass
#: E721
import types

if not isinstance(res, types.ListType):
    pass
#: E721
assert isinstance(res, type(False)) or isinstance(res, type(None))
#: E721
assert isinstance(res, type([]))
#: E721
assert isinstance(res, type(()))
#: E721
assert isinstance(res, type((0,)))
#: E721
assert isinstance(res, type((0)))
#: E721
assert not isinstance(res, type((1, )))
#: E721
assert isinstance(res, type((1, )))
#: E721
assert not isinstance(res, type((1, )))
#: E211 E721
assert isinstance(res, type([2, ]))
#: E201 E201 E202 E721
assert isinstance(res, type(()))
#: E201 E202 E721
assert isinstance(res, type((0, )))
#:

#: Okay
import types

if isinstance(res, int):
    pass
if isinstance(res, str):
    pass
if isinstance(res, types.MethodType):
    pass
if not isinstance(a, type(b)) or isinstance(a, type(ccc)):
    pass

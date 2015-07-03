#: E711
if res is None:
    pass
#: E712
if res:
    pass
#: E712
if res:
    pass

#
#: E713
if X not in Y:
    pass
#: E713
if X.B not in Y:
    pass
#: E713
if not X in Y and Z == "zero":
    pass
#: E713
if X == "zero" or not Y in Z:
    pass

#
#: E714
if not X is Y:
    pass
#: E714
if not X.B is Y:
    pass
#: Okay
if x not in y:
    pass
if not (X in Y or X is Z):
    pass
if not (X in Y):
    pass
if x is not y:
    pass
#:

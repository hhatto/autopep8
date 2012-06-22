"""Incomplete fixes."""


# E501: We should put parentheses around this and wrap it
1234567 + 343243423 + 23423429340234 + 324234234 + 2423424 + 32423423432 + 234234234 + 324234234

# E501: We should wrap after comman instead of before. From
#       Intellect-1.4.8.4/intellect/grammar/PolicyParser.py
def dummy():
    if True:
        if True:
            if True:
                object = ModifyAction( [MODIFY70.text, OBJECTBINDING71.text, COLON72.text], MODIFY70.getLine(), MODIFY70.getCharPositionInLine() )

# E501: This should be wrapped similar to how pprint does it
{'2323k2323': 24232323, '2323323232323': 3434343434343434, '34434343434535535': 3434343434343434, '4334343434343': 3434343434}
# See below
{'2323323232323': 3434343434343434,
 '2323k2323': 24232323,
 '34434343434535535': 3434343434343434,
 '4334343434343': 3434343434}

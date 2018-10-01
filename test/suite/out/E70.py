#: E701
if a:
    a = False
#: E701
if not header or header[:6] != 'bytes=':
    return
#: E702
a = False
b = True
#: E702
print(1)
bdist_egg.write_safety_flag(cmd.egg_info, safe)
#: E703
print(1)
#: E702 E703
del a[:]
a.append(42)
#:

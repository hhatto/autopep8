import sys, os


print 1 
print 2 # e261
print 2  ## e262
print 2  #### e262


def func1():
    print "A"
    
    return 0



def func11():
    a = (1,2, 3,"a")
    b = [1, 2, 3,"b"]
    return 1





def func2():
    pass
def func22():
    pass;


def func_oneline():if True: print 1

def func_last():
    if True: print 1
    pass


if __name__ == '__main__': func_last()


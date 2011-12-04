import sys, os

def foo():
    import subprocess, argparse


print 1 
print 2 # e261
print 2  ## e262
print 2  #### e262
1 /1
1 *2
1 +1
1 -1
1 **2


def dummy1 ( a ):
    print a 
    print a


def dummy2(a) :
    if 1 in a:
        print "a"
        print 1+1   # e225
        print 1 +1  # e225
        print 1+ 1  # e225
        print 1  +1  # e221+e225
        print 1  + 1  # e221
        print 1  * 1  # e221
        print 1 +  1  # e222
        print 1 *    1  # e222
    print a


def func1():
    print "A"
    
    return 0



def func11():
    a = (1,2, 3,"a")
    b = [1, 2, 3,"b"]
    c = 0,11/2
    return 1





def func2():
    pass
def func22():
    pass;


def func_oneline(): print 1

def func_last():
    if True: print 1
    pass


def func_e251(a, b=1, c = 3):
    pass


def func_e251_t(a, b=1, c = 3, d = 4):
    pass


# e201
( 1)
[ 1]
{ 1: 2}

# e202
(1 )
[1 ]
{1: 2 }

# e203
{4 : 2}
[4 , 2]


def func_e702():
    4; 1
    print 2; print 4
    if True:
        1; 2; 3
0; 1


if __name__ == '__main__': func_last()


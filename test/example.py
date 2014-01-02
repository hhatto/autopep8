import sys, os

def foo():
    import subprocess, argparse
    import copy; import math, email


print(1) 
print(2) # e261
d = {1: 2,# e261
     3: 4}
print(2)  ## e262
print(2)  #### e262
print(2)  #e262
print(2)  #     e262
1 /1
1 *2
1 +1
1 -1
1 **2


def dummy1 ( a ):
    print(a) 
    print(a)


def dummy2(a) :
    if 1 in a:
        print("a")
        print(1+1)   # e225
        print(1 +1)  # e225
        print(1+ 1)  # e225


        print(1  +1)  # e221+e225
        print(1  + 1)  # e221
        print(1  * 1)  # e221
        print(1 +  1)  # e222
        print(1 *    1)  # e222
    print(a)


def func1():
    print("A")
    
    return 0



def func11():
    a = (1,2, 3,"a")
    b = [1, 2, 3,"b"]
    c = 0,11/2
    return 1




# comment after too empty lines
def func2():
    pass
def func22():
    pass;


def func_oneline(): print(1)

def func_last():
    if True: print(1)
    pass


def func_e251(a, b=1, c = 3):
    pass


def func_e251_t(a, b=1, c = 3, d = 4):
    pass


# e201
(         1)
[         1]
{         1: 2}

# e202
(1        )
[1        ]
{1: 2     }

# e203
{4           : 2}
[4           , 2]

# e211
d = [1]
d  	 [0]
dummy1  	  (0)


def func_e702():
    4; 1;
    4; 1;	  
    4; 1;

    4; 1;
    print(2); print(4);          6;8
    if True:
        1; 2; 3
0; 1
2;3
4;     5;


def func_w602():
    raise ValueError, "w602 test"
    raise ValueError, "w602 test"  # my comment

    raise ValueError
    raise ValueError  # comment

    raise ValueError, 'arg'   ; print(1)
    raise ValueError, 'arg'   ; print(2) # my comment

    raise ValueError, \
        'arg no comment'
    raise ValueError, \
        'arg'  # my comment
    raise ValueError, \
        """arg"""  # my comment
    raise ValueError, \
        """arg

  """  # my comment
    raise ValueError, \
        '''multiline

'''  # my comment

    a = 'a'
    raise ValueError, "%s" % (a,)

    raise 'string'


def func_w603():
    if 1 <> 2:
        if 2 <> 2:
            print(True)
        else:
            print(False)


def func_w604():
    a = 1.1
    b = ```a```

def func_e101():
	print('abc')
	if True:
	    print('hello')

if __name__ == '__main__': func_last()
  

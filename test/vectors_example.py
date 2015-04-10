# vectors - a simple vector, complex, quaternion, and 4d matrix math module

'''
http://www.halley.cc/code/python/vectors.py

A simple vector, complex, quaternion, and 4d matrix math module.

ABSTRACT

This module gives a simple way of doing lightweight 2D, 3D or other
vector math tasks without the heavy clutter of doing tuple/list/vector
conversions yourself, or the burden of installing some high-performance
native math routine module.

Included are:
    V(...) - mathematical real vector
    C(...) - mathematical complex number (same as python "complex" type)
    Q(...) - hypercomplex number, also known as a quaternion
    M(...) - a fixed 4x4 matrix commonly used in graphics

SYNOPSIS

    >>> import vectors ; from vectors import *

    Vectors:

    >>> v = V(1,2,3) ; w = V(4,5,6)

    >>> v+w,               (v+w == w+v),  v*2
        V(5.0, 7.0, 9.0),  True,          V(2.0, 4.0, 6.0)

    >>> v.dot(w),  v.cross(w),          v.normalize().magnitude()
        32.0,      V(-3.0, 6.0, -3.0),  1.0

    Quaternions:

    >>> q = Q.rotate('X', vectors.radians(30))
        Q(0.7071067811, 0.0, 0.0, 0.7071067811)

    >>> q*q*q*q*q*q == Q.rotate('X', math.pi) == Q(1,0,0,0)
        True

AUTHOR

    Ed Halley (ed@halley.cc) 12 February 2005

REFERENCES

    Many libraries implement a host of 4x4 matrix math and vector
    routines, usually related to the historical SGI GL implementation.
    A common problem is whether matrix element formulas are transposed.
    One useful FAQ on matrix math can be found at this address:
    http://www.j3d.org/matrix_faq/matrfaq_latest.html

'''

__all__ = [ 'V', 'C', 'Q', 'M',
            'zero', 'equal',
	    'radians', 'degrees',
	    'angle', 'track',
            'distance', 'nearest', 'farthest' ]

#----------------------------------------------------------------------------

import math
import random

EPSILON = 0.00000001

__deg2rad = math.pi / 180.0
__rad2deg = 180.0 / math.pi

def zero(a): return abs(a) < EPSILON
def equal(a, b): return abs(a - b) < EPSILON
def degrees(rad): return rad * __rad2deg
def radians(deg): return deg * __deg2rad

def sign(a):
    if a < 0: return -1
    if a > 0: return +1
    return 0

def isseq(x):
    return isinstance(x, (list, tuple))

def collapse(*args):
    it = []
    for i in range(len(args)):
        if isinstance(args[i], V):
            it.extend(args[i]._v)
        else:
            it.extend(args[i])
    return it

#----------------------------------------------------------------------------

class V:

    '''A mathematical vector of arbitrary number of scalar number elements.
    '''

    O = None
    X = None
    Y = None
    Z = None

    __slots__ = [ '_v', '_l' ]

    @classmethod
    def __constants__(cls):
        if V.O: return
        V.O = V() ; V.O._v = (0.,0.,0.) ; V.O._l = 0.
        V.X = V() ; V.X._v = (1.,0.,0.) ; V.X._l = 1.
        V.Y = V() ; V.Y._v = (0.,1.,0.) ; V.Y._l = 1.
        V.Z = V() ; V.Z._v = (0.,0.,1.) ; V.Z._l = 1.
   
    def __init__(self, *args):
	l = len(args)
        if not l:
            self._v = [0.,0.,0.]
	    self._l = 0.
	    return
	if l > 1:
            self._v = map(float, args)
	    self._l = None
	    return
        arg = args[0]
        if isinstance(arg, (list, tuple)):
            self._v = map(float, arg)
	    self._l = None
        elif isinstance(arg, V):
            self._v = list(arg._v[:])
            self._l = arg._l
        else:
	    arg = float(arg)
            self._v = [ arg ]
	    self._l = arg

    def __len__(self):
        '''The len of a vector is the dimensionality.'''
        return len(self._v)

    def __list__(self):
        '''Accessing the list() will return all elements as a list.'''
        if isinstance(self._v, tuple): return list(self._v[:])
        return self._v[:]

    list = __list__

    def __getitem__(self, key):
        '''Vector elements can be accessed directly.'''
        return self._v[key]

    def __setitem__(self, key, value):
        '''Vector elements can be accessed directly.'''
        self._v[key] = value

    def __str__(self): return self.__repr__()
    def __repr__(self): 
        return self.__class__.__name__ + repr(tuple(self._v))

    def __eq__(self, other):
        '''Vectors can be checked for equality.
        Uses epsilon floating comparison; tiny differences are still equal.
        '''
        for i in range(len(self._v)):
            if not equal(self._v[i], other._v[i]):
                return False
        return True
    def __cmp__(self, other):
        '''Vectors can be compared, returning -1,0,+1.
        Elements are compared in order, using epsilon floating comparison.
        '''
        for i in range(len(self._v)):
            if not equal(self._v[i], other._v[i]):
                if self._v[i] > other._v[i]: return 1
                return -1
        return 0

    def __pos__(self): return V(self)
    def __neg__(self):
        '''The inverse of a vector is a negative in all elements.'''
        v = V(self)
        for i in range(len(v._v)):
            v[i] = -v[i]
        v._l = self._l
        return v

    def __nonzero__(self):
        '''A vector is nonzero if any of its elements are nonzero.'''
        for i in range(len(self._v)):
            if self._v[i]: return True
        return False

    def zero(self):
        '''A vector is zero if none of its elements are nonzero.'''
        return not self.__nonzero__()

    @classmethod
    def random(cls, order=3):
        '''Returns a unit vector in a random direction.'''
        # distribution is not without bias, need to use polar coords?
        v = V(range(order))
        v._l = None
        short = True
        while short:
            for i in range(order):
                v._v[i] = 2.0*random.random() - 1.0
                if not zero(v._v[i]): short = False
        return v.normalize()

    # Vector or scalar addition.
    def __add__(self, other): return self.__class__(self).__iadd__(other)
    def __radd__(self, other): return self.__class__(self).__iadd__(other)
    def __iadd__(self, other):
        '''Vectors can be added to each other, or a scalar added to them.'''
        if isinstance(other, V):
            if len(other._v) != len(self._v):
                raise ValueError, 'mismatched dimensions'
            for i in range(len(self._v)):
                self._v[i] += other._v[i]
        else:
            for i in range(len(self._v)):
                self._v[i] += other
        self._l = None
        return self

    # Vector or scalar subtraction.
    def __sub__(self, other): return self.__class__(self).__isub__(other)
    def __rsub__(self, other): return (-self.__class__(self)).__iadd__(other)
    def __isub__(self, other):
        '''Vectors can be subtracted, or a scalar subtracted from them.'''
        if isinstance(other, V):
            if len(other._v) != len(self._v):
                raise ValueError, 'mismatched dimensions'
            for i in range(len(self._v)):
                self._v[i] -= other._v[i]
        else:
            for i in range(len(self._v)):
                self._v[i] -= other
        self._l = None
        return self

    # Cross product or magnification.  See dot() for dot product.
    def __mul__(self, other):
        if isinstance(other, M): return other.__rmul__(self)
        return self.__class__(self).__imul__(other)
    def __rmul__(self, other):
        # The __rmul__ is called in scalar * vector case; it's commutative.
        return self.__class__(self).__imul__(other)
    def __imul__(self, other):
        '''Vectors can be multipled by a scalar. Two 3d vectors can cross.'''
        if isinstance(other, V):
            self._v = self.cross(other)._v
        else:
            for i in range(len(self._v)):
                self._v[i] *= other
        self._l = None
        return self

    def __div__(self, other): return self.__class__(self).__idiv__(other)
    def __rdiv__(self, other):
        raise TypeError, 'cannot divide scalar by non-scalar value'
    def __idiv__(self, other):
        '''Vectors can be divided by scalars; each element is divided.'''
        other = 1.0 / other
        for i in range(len(self._v)):
            self._v[i] *= other
        self._l = None
        return self

    def cross(self, other):
        '''Find the vector cross product between two 3d vectors.'''
        if len(self._v) != 3 or len(other._v) != 3:
            raise ValueError, 'cross multiplication only for 3d vectors'
        p, q = self._v, other._v
        r = [ p[1] * q[2] - p[2] * q[1],
              p[2] * q[0] - p[0] * q[2],
              p[0] * q[1] - p[1] * q[0] ]
        return V(r)

    def dot(self, other):
        '''Find the scalar dot product between this vector and another.'''
        s = 0
        for i in range(len(self._v)):
            s += self._v[i] * other._v[i]
        return s

    def __mag(self):
        if self._l is not None:
            return self._l
        m = 0
        for i in range(len(self._v)):
            m += self._v[i] * self._v[i]
        self._l = math.sqrt(m)
        return self._l

    def magnitude(self, value=None):
        '''Find the magnitude (spatial length) of this vector.
        With a value, return a vector with same direction but of given length.
        '''
        mag = self.__mag()
        if value is None: return mag
        if zero(mag):
            raise ValueError, 'Zero-magnitude vector cannot be scaled.'
        v = self.__class__(self)
        v.__imul__(value / mag)
        v._l = value
        return v

    def dsquared(self, other):
        m = 0
        for i in range(len(self._v)):
            d = self._v[i] - other._v[i]
            m += d * d
        return m

    def distance(self, other):
        '''Compare this vector with another, for distance.'''
        return math.sqrt(self.dsquared(other))

    def normalize(self):
        '''Return a vector with the same direction but of unit length.'''
        return self.magnitude(1.0)

    def order(self, order):
        '''Remove elements from the end, or extend with new elements.'''
        order = int(order)
        if order < 1:
            raise ValueError, 'cannot reduce a vector to zero elements'
        v = V(self)
        while order < len(v._v):
            v._v.pop()
        while order > len(v._v):
            v._v.append(1.0)
        v._l = None
        return v

#----------------------------------------------------------------------------

class C (V):

    # python has a built-in complex() type which is pretty good,
    # but we provide this class for completeness and consistency

    O = None
    j = None

    __slots__ = [ '_v', '_l' ]

    @classmethod
    def __constants__(cls):
        if C.O: return
        C.O = C(0+0j) ; C.O._v = tuple(C.O._v)
        C.j = C(0+1j) ; C.j._v = tuple(C.j._v)

    def __init__(self, *args):
        if not args:
            args = (0, 0)
        a = args[0]
        if isinstance(a, complex):
            a = (a.real, a.imag)
        if isinstance(a, V):
            if len(a) != 2: raise TypeError, 'C() takes exactly 2 elements'
            self._v = list(a._v[:])
        elif isseq(a):
            if len(a) != 2: raise TypeError, 'C() takes exactly 2 elements'
            self._v = map(float, a)
        else:
            if len(args) != 2: raise TypeError, 'C() takes exactly 2 elements'
            self._v = map(float, args)

    #def __repr__(self):
    #    return 'C(%s+%sj)' % (repr(self._v[0]), repr(self._v[1]))

    # addition and subtraction of C() work the same as V()

    def dot(self): raise AttributeError, "C instance has no attribute 'dot'"

    def __imul__(self, other):
        if isinstance(other, C):
            sx,sj = self._v
            ox,oj = other._v
            self._v = [ sx*ox - sj*oj, sx*oj + ox*sj ]
        else:
            V.__imul__(self, other)
        return self

    def conjugate(self):
        twin = C(self)
        twin._v[0] = -twin._v[0]
        return twin

#----------------------------------------------------------------------------

class Q (V):

    I = None

    __slots__ = [ '_v', '_l' ]

    @classmethod
    def __constants__(cls):
        if Q.O: return
        Q.I = Q() ; Q.I._v = tuple(Q.I._v)

    def __init__(self, *args):
        # x, y, z, w
        if not args:
            args = (0, 0, 0, 1)
        a = args[0]
        if isinstance(a, V):
            if len(a) != 4: raise TypeError, 'Q() takes exactly 4 elements'
            self._v = list(a._v[:])
        elif isseq(a):
            if len(a) != 4: raise TypeError, 'Q() takes exactly 4 elements'
            self._v = map(float, a)
        else:
            if len(args) != 4: raise TypeError, 'Q() takes exactly 4 elements'
            self._v = map(float, args)
        self._l = None

    # addition and subtraction of Q() work the same as V()

    def dot(self): raise AttributeError, "Q instance has no attribute 'dot'"

    #TODO: extra methods to convert euler vectors and quaternions

    def conjugate(self):
        '''The conjugate of a quaternion has its X, Y and Z negated.'''
        twin = Q(self)
        for i in range(3):
            twin._v[i] = -twin._v[i]
        twin._l = twin._l
        return twin

    def inverse(self):
        '''The quaternion inverse is the conjugate with reciprocal W.'''
        twin = self.conjugate()
        if twin._v[3] != 1.0:
            twin._v[3] = 1.0 / twin._v[3]
            twin._l = None
        return twin

    @classmethod
    def rotate(cls, axis, theta):
        '''Prepare a quaternion that represents a rotation on a given axis.'''
        if isinstance(axis, str):
            if axis in ('x','X'): axis = V.X
            elif axis in ('y','Y'): axis = V.Y
            elif axis in ('z','Z'): axis = V.Z
        axis = axis.normalize()
        s = math.sin(theta / 2.)
        c = math.cos(theta / 2.)
        return Q( axis._v[0] * s, axis._v[1] * s, axis._v[2] * s, c )

    def __imul__(self, other):
        if isinstance(other, Q):
            sx,sy,sz,sw = self._v
            ox,oy,oz,ow = other._v
            self._v = [ sw*ox + sx*ow + sy*oz - sz*oy,
                        sw*oy + sy*ow + sz*ox - sx*oz,
                        sw*oz + sz*ow + sx*oy - sy*ox,
                        sw*ow - sx*ox - sy*oy - sz*oz ]
        else:
            V.__imul__(self, other)
        return self

#----------------------------------------------------------------------------

class M (V):

    I = None
    Z = None

    __slots__ = [ '_v' ]

    @classmethod
    def __constants__(cls):
        if M.I: return
        M.I = M() ; M.I._v = tuple(M.I._v)
        M.Z = M() ; M.Z._v = (0,)*16

    def __init__(self, *args):
        '''Constructs a new 4x4 matrix.
        If no arguments are given, an identity matrix is constructed.
        Any combination of V vectors, tuples, lists or scalars may be given,
        but taken together in order, they must have 16 number values total.
        '''
        # no args gives identity matrix
        # 16 scalars collapsed from any combination of lists, tuples, vectors
        if not args:
            args = (1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1)
        if len(args) == 4: args = collapse(*args)
        a = args[0]
        if isinstance(a, V):
            if len(a) != 16: raise TypeError, 'M() takes exactly 16 elements'
            self._v = list(a._v[:])
        elif isseq(a):
            if len(a) != 16: raise TypeError, 'M() takes exactly 16 elements'
            self._v = map(float, a)
        else:
            if len(args) != 16: raise TypeError, 'M() takes exactly 16 elements'
            self._v = map(float, args)

    @classmethod
    def rotate(cls, axis, theta=0.0):
        if isinstance(axis, str):
            if axis in ('x','X'):
                c = math.cos(theta) ; s = math.sin(theta)
                return cls( [  1,  0,  0,  0,
                               0,  c, -s,  0,
                               0,  s,  c,  0,
                               0,  0,  0,  1 ] )
            if axis in ('y','Y'):
                c = math.cos(theta) ; s = math.sin(theta)
                return cls( [  c,  0,  s,  0,
                               0,  1,  0,  0,
                              -s,  0,  c,  0,
                               0,  0,  0,  1 ] )
            if axis in ('z','Z'):
                c = math.cos(theta) ; s = math.sin(theta)
                return cls( [  c, -s,  0,  0,
                               s,  c,  0,  0,
                               0,  0,  1,  0,
                               0,  0,  0,  1 ] )
        if isinstance(axis, V):
            axis = Q.rotate(axis, theta)
        if isinstance(axis, Q):
            return cls.twist(axis)
        raise ValueError, 'unknown rotation axis'

    @classmethod
    def twist(cls, torsion):
        # quaternion to matrix
        torsion = torsion.normalize()
        (X,Y,Z,W) = torsion._v
        xx = X * X ; xy = X * Y ; xz = X * Z ; xw = X * W
        yy = Y * Y ; yz = Y * Z ; yw = Y * W ; zz = Z * Z ; zw = Z * W
        a = 1 - 2*(yy + zz) ; b =     2*(xy - zw) ; c =     2*(xz + yw)
        e =     2*(xy + zw) ; f = 1 - 2*(xx + zz) ; g =     2*(yz - xw)
        i =     2*(xz - yw) ; j =     2*(yz + xw) ; k = 1 - 2*(xx + yy)
        return cls( [ a, b, c, 0,
                      e, f, g, 0,
                      i, j, k, 0,
                      0, 0, 0, 1 ] )

    @classmethod
    def scale(cls, factor):
        m = cls()
        if isinstance(factor, (V, list, tuple)):
            for i in (0,1,2):
                m[(i,i)] = factor[i]
        else:
            for i in (0,1,2):
                m[(i,i)] = factor
        return m

    @classmethod
    def translate(cls, offset):
        m = cls()
        for i in (0,1,2):
            m[(3,i)] = offset[i]
        return m

    @classmethod
    def reflect(cls, normal, dist=0.0):
        (x,y,z,w) = normal.normalize()._v
        (n2x,n2y,n2z) = (-2*x, -2*y, -2*z)
        return cls( [ 1+n2x*x,   n2x*y,   n2x*z, 0,
                        n2y*x, 1+n2y*y,   n2y*z, 0,
                        n2z*x,   n2z*y, 1+n2z*z, 0,
                          d*x,     d*y,     d*y, 1  ] )

    @classmethod
    def shear(cls, amount):
        #   | 1. yx zx 0. |
        #   | xy 1. zy 0. |
        #   | xz yz 1. 0. |
        #   | 0. 0. 0. 1. |
        pass

    @classmethod
    def frustrum(cls, l, r, b, t, n, f):
        rl = 1/(r-l) ; tb = 1/(t-b) ; fn = 1/(f-n)
        return cls( [  2*n*rl,  0,       (r+l)*rl,  0,
                       0,       2*n*tb,  0,         0,
                       0,       0,      -(f+n)*fn, -2*f*n*fn,
                       0,       0,      -1,         0         ] )

    @classmethod
    def perspective(cls, yfov, aspect, n, f):
        t = math.tan(yfov/2)*n
        b = -t
        r = aspect * t
        l = -r
        return cls.frustrum(l, r, b, t, n, f)

    def __str__(self):
        '''Returns a multiple-line string representation of the matrix.'''
        # prettier on multiple lines
        n = self.__class__.__name__
        ns = ' '*len(n)
        t = n+'('+', '.join([ repr(self._v[i]) for i in 0,1,2,3 ])+',\n'
        t += ns+' '+', '.join([ repr(self._v[i]) for i in 4,5,6,7 ])+',\n'
        t += ns+' '+', '.join([ repr(self._v[i]) for i in 8,9,10,11 ])+',\n'
        t += ns+' '+', '.join([ repr(self._v[i]) for i in 12,13,14,15 ])+')'
        return t

    def __getitem__(self, rc):
        '''Returns a single element of the matrix.
        May index 0-15, or with tuples of (row,column) 0-3 each.
        Indexing goes across first, so m[3] is m[0,3] and m[7] is m[1,3].
        '''
        if not isinstance(rc, tuple): return V.__getitem__(self, rc)
        return self._v[rc[0]*4+rc[1]]

    def __setitem__(self, rc, value):
        '''Injects a single element into the matrix.
        May index 0-15, or with tuples of (row,column) 0-3 each.
        Indexing goes across first, so m[3] is m[0,3] and m[7] is m[1,3].
        '''
        if not isinstance(rc, tuple): return V.__getitem__(self, rc)
        self._v[rc[0]*4+rc[1]] = float(value)

    def dot(self): raise AttributeError, "M instance has no attribute 'dot'"
    def magnitude(self): raise AttributeError, "M instance has no attribute 'magnitude'"

    def row(self, r, v=None):
        '''Returns or replaces a vector representing a row of the matrix.
        Rows are counted 0-3. If given, new vector must be four numbers.
        '''
        if r < 0 or r > 3: raise IndexError, 'row index out of range'
        if v is None: return V(self._v[r*4:(r+1)*4])
        e = v
        if isinstance(v, V): e = v._v
        if len(e) != 4: raise ValueError, 'new row must include 4 values'
        self._v[r*4:(r+1)*4] = e
        return v

    def col(self, c, v=None):
        '''Returns or replaces a vector representing a column of the matrix.
        Columns are counted 0-3. If given, new vector must be four numbers.
        '''
        if c < 0 or c > 3: raise IndexError, 'column index out of range'
        if v is None: return V([ self._v[c+4*i] for i in range(4) ])
        e = v
        if isinstance(v, V): e = v._v
        if len(e) != 4: raise ValueError, 'new row must include 4 values'
        for i in range(4): self._v[c+4*i] = e[i]
        return v

    def translation(self):
        '''Extracts the translation component from this matrix.'''
        (a,b,c,d,
         e,f,g,h,
         i,j,k,l,
         m,n,o,p) = self._v
        return V(m,n,o)

    def rotation(self):
        '''Extracts Euler angles of rotation from this matrix.
        This attempts to find alternate rotations in case of gimbal lock,
        but all of the usual problems with Euler angles apply here.
        All Euler angles are in radians.
        '''
        (a,b,c,d,e,f,g,h,i,j,k,l,m,n,o,p) = self._v
        rotY = D = math.asin(c)
        C = math.cos(rotY)
        if (abs(C) > 0.005):
            trX = k/C ; trY = -g/C ; rotX = math.atan2(trY, trX)
            trX = a/C ; trY = -b/C ; rotZ = math.atan2(trY, trX)
        else:
            rotX = 0
            trX = f ; trY = e ; rotZ = math.atan2(trY, trX)
        return V(rotX,rotY,rotZ)

    def scaling(self):
        '''Extracts the scaling component from this matrix.'''
        (a,b,c,d,e,f,g,h,i,j,k,l,m,n,o,p) = self._v
        return V(a,f,k)

    def determinant(self):
        (a,b,c,d,e,f,g,h,i,j,k,l,m,n,o,p) = self._v
        # determinants of 2x2 submatrices
        kplo = k*p-l*o ; jpln = j*p-l*n ; jokn = j*o-k*n
        iplm = i*p-l*m ; iokm = i*o-k*m ; injm = i*n-j*m
        # determinants of 3x3 submatrices
        d00 = (f*kplo - g*jpln + h*jokn)
        d01 = (e*kplo - g*iplm + h*iokm)
        d02 = (e*jpln - f*iplm + h*injm)
        d03 = (e*jokn - f*iokm + g*injm)
        # reciprocal of the determinant of the 4x4
        dr = a*d00 - b*d01 + c*d02 - d*d03
        return dr

    def inverse(self):
        (a,b,c,d,e,f,g,h,i,j,k,l,m,n,o,p) = self._v
        # determinants of 2x2 submatrices
        kplo = k*p-l*o ; jpln = j*p-l*n ; jokn = j*o-k*n
        iplm = i*p-l*m ; iokm = i*o-k*m ; injm = i*n-j*m
        gpho = g*p-h*o ; ifhn = f*p-h*n ; fogn = f*o-g*n
        ephm = e*p-h*m ; eogm = e*o-g*m ; enfm = e*n-f*m
        glhk = g*l-h*k ; flhj = f*l-h*j ; fkgj = f*k-g*j
        elhi = e*l-h*i ; ekgi = e*k-g*i ; ejfi = e*j-f*i
        # determinants of 3x3 submatrices
        d00 = (f*kplo - g*jpln + h*jokn)
        d01 = (e*kplo - g*iplm + h*iokm)
        d02 = (e*jpln - f*iplm + h*injm)
        d03 = (e*jokn - f*iokm + g*injm)
        d10 = (b*kplo - c*jpln + d*jokn)
        d11 = (a*kplo - c*iplm + d*iokm)
        d12 = (a*jpln - b*iplm + d*injm)
        d13 = (a*jokn - b*iokm + c*injm)
        d20 = (b*gpho - c*ifhn + d*fogn)
        d21 = (a*gpho - c*ephm + d*eogm)
        d22 = (a*ifhn - b*ephm + d*enfm)
        d23 = (a*fogn - b*eogm + c*enfm)
        d30 = (b*glhk - c*flhj + d*fkgj)
        d31 = (a*glhk - c*elhi + d*ekgi)
        d32 = (a*flhj - b*elhi + d*ejfi)
        d33 = (a*fkgj - b*ekgi + c*ejfi)
        # reciprocal of the determinant of the 4x4
        dr = 1.0 / (a*d00 - b*d01 + c*d02 - d*d03)
        # inverse
        return self.__class__( [  d00*dr, -d10*dr,  d20*dr, -d30*dr,
                                 -d01*dr,  d11*dr, -d21*dr,  d31*dr,
                                  d02*dr, -d12*dr,  d22*dr, -d32*dr,
                                 -d03*dr,  d13*dr, -d23*dr,  d33*dr ] )

    def transpose(self):
        return M( [ self._v[i] for i in [ 0, 4,  8, 12,
                                          1, 5,  9, 13,
                                          2, 6, 10, 14,
                                          3, 7, 11, 15 ] ] )

    def __mul__(self, other):
        # called in case of m *m, m * v, m * s
        # support 3d m * v by extending to 4d v
        if isinstance(other, V):
            if len(other._v) == 3:
                other = V(other._v[0], other._v[1], other._v[2], 1)
            if len(other._v) == 4:
                a,b,c,d,e,f,g,h,i,j,k,l,m,n,o,p = self._v
                X,Y,Z,W = other._v
                return V( a*X + b*Y + c*Z + d*W,
                          e*X + f*Y + g*Z + h*W,
                          i*X + j*Y + k*Z + l*W,
                          m*X + n*Y + o*Z + p*W )
        return self.__class__(self).__imul__(other)

    def __rmul__(self, other):
        # called in case of s * m or v * m
        # support 3d v * m by extending to 4d v
        if isinstance(other, V):
            if len(other._v) == 3:
                other = V(other._v[0], other._v[1], other._v[2], 1)
            if len(other._v) == 4:
                A,B,C,D,E,F,G,H,I,J,K,L,M,N,O,P = self._v
                x,y,z,w = other._v
                return V( x*A + y*E + z*I + w*M,
                          x*B + y*F + z*J + w*N,
                          x*C + y*G + z*K + w*O,
                          x*D + y*H + z*L + w*P )
        return self.__class__(self).__imul__(other)

    def __imul__(self, other):
        # can m *= s
        # can't m *= v since answer is vector
        if not isinstance(other, V):
            other = float(other)
            self._v = [ self._v[i]*other for i in range(len(self._v)) ]
        elif len(other._v) == 16:
            s0,s1,s2,s3,s4,s5,s6,s7,s8,s9,sA,sB,sC,sD,sE,sF = self._v
            o0,o1,o2,o3,o4,o5,o6,o7,o8,o9,oA,oB,oC,oD,oE,oF = other._v
            self._v = [ o0*s0 + o1*s4 + o2*s8 + o3*sC, #
                        o0*s1 + o1*s5 + o2*s9 + o3*sD,
                        o0*s2 + o1*s6 + o2*sA + o3*sE,
                        o0*s3 + o1*s7 + o2*sB + o3*sF,
                        o4*s0 + o5*s4 + o6*s8 + o7*sC, #
                        o4*s1 + o5*s5 + o6*s9 + o7*sD,
                        o4*s2 + o5*s6 + o6*sA + o7*sE,
                        o4*s3 + o5*s7 + o6*sB + o7*sF,
                        o8*s0 + o9*s4 + oA*s8 + oB*sC, #
                        o8*s1 + o9*s5 + oA*s9 + oB*sD,
                        o8*s2 + o9*s6 + oA*sA + oB*sE,
                        o8*s3 + o9*s7 + oA*sB + oB*sF,
                        oC*s0 + oD*s4 + oE*s8 + oF*sC, #
                        oC*s1 + oD*s5 + oE*s9 + oF*sD,
                        oC*s2 + oD*s6 + oE*sA + oF*sE,
                        oC*s3 + oD*s7 + oE*sB + oF*sF ]
        else:
            raise ValueError, 'multiply by 4d matrix or 4d vector or scalar'
        return self

#----------------------------------------------------------------------------

V.__constants__()
C.__constants__()
Q.__constants__()
M.__constants__()

def angle(a, b):
    '''Find the angle (scalar value in radians) between two 3d vectors.'''
    a = a.normalize()
    b = b.normalize()
    if a == b: return 0.0
    return math.acos(a.dot(b))

def track(v):
    '''Find the track (direction in positive radians) of a 2d vector.
    E.g., track(V(1,0)) == 0 radians; track(V(0,1) == math.pi/2 radians;
    track(V(-1,0)) == math.pi radians; and track(V(0,-1) is math.pi*3/2.
    '''
    t = math.atan2(v[1], v[0])
    if t < 0:
	return t + 2.*math.pi
    return t

def quangle(a, b):
    '''Find a quaternion that rotates one 3d vector to parallel another.'''
    x = a.cross(b)
    w = a.magnitude() * b.magnitude() + a.dot(b)
    return Q(x[0], x[1], x[2], w)

def dsquared(one, two):
    '''Find the square of the distance between two points.'''
    # working with squared distances is common to avoid slow sqrt() calls
    m = 0
    for i in range(len(one._v)):
        d = one._v[i] - two._v[i]
        m += d * d
    return m

def distance(one, two):
    '''Find the distance between two points.
    Equivalent to (one-two).magnitude().
    '''
    return math.sqrt(dsquared(one, two))

def nearest(point, neighbors):
    '''Find the nearest neighbor point to a given point.'''
    best = None
    for other in neighbors:
        d = dsquared(point, other)
        if best is None or d < best[1]:
            best = (other, d)
    return best[0]

def farthest(point, neighbors):
    '''Find the farthest neighbor point to a given point.'''
    best = None
    for other in neighbors:
        d = dsquared(point, other)
        if best is None or d > best[1]:
            best = (other, d)
    return best[0]

#----------------------------------------------------------------------------

def __test__():
    from testing import __ok__, __report__

    print 'Testing basic math...'

    __ok__(equal(1.0, 1.0), True)
    __ok__(equal(1.0, 1.01), False)
    __ok__(equal(1.0, 1.0001), False)
    __ok__(equal(1.0, 0.9999), False)
    __ok__(equal(1.0, 1.0000001), False)
    __ok__(equal(1.0, 0.9999999), False)
    __ok__(equal(1.0, 1.0000000001), True)
    __ok__(equal(1.0, 0.9999999999), True)

    __ok__(equal(degrees(0), 0.0))
    __ok__(equal(degrees(math.pi/2), 90.0))
    __ok__(equal(degrees(math.pi), 180.0))
    __ok__(equal(radians(0.0), 0.0))
    __ok__(equal(radians(90.0), math.pi/2))
    __ok__(equal(radians(180.0), math.pi))

    print 'Testing V vector class...'

    # structural construction
    __ok__(V.O is not None, True)
    __ok__(V.O._v is not None, True)
    __ok__(V.O._v, (0., 0., 0.)) ; __ok__(V.O._l, 0.)
    __ok__(V.X._v, (1., 0., 0.)) ; __ok__(V.X._l, 1.)
    __ok__(V.Y._v, (0., 1., 0.)) ; __ok__(V.Y._l, 1.)
    __ok__(V.Z._v, (0., 0., 1.)) ; __ok__(V.Z._l, 1.)
    a = V(3., 2., 1.) ; __ok__(a._v, [3., 2., 1.])
    a = V((1., 2., 3.)) ; __ok__(a._v, [1., 2., 3.])
    a = V([1., 1., 1.]) ; __ok__(a._v, [1., 1., 1.])
    a = V(0.) ; __ok__(a._v, [0.]) ; __ok__(a._l, 0.)
    a = V(3.) ; __ok__(a._v, [3.]) ; __ok__(a._l, 3.)

    # constants and direct comparisons
    __ok__(V.O, V(0.,0.,0.))
    __ok__(V.X, V(1.,0.,0.))
    __ok__(V.Y, V(0.,1.,0.))
    __ok__(V.Z, V(0.,0.,1.))

    # formatting and elements
    __ok__(repr(V.X), 'V(1.0, 0.0, 0.0)')
    __ok__(V.X[0], 1.)
    __ok__(V.X[1], 0.)
    __ok__(V.X[2], 0.)

    # simple addition
    __ok__(V.X + V.Y, V(1.,1.,0.))
    __ok__(V.Y + V.Z, V(0.,1.,1.))
    __ok__(V.X + V.Z, V(1.,0.,1.))

    # didn't overwrite our constants, did we?
    __ok__(V.X, V(1.,0.,0.))
    __ok__(V.Y, V(0.,1.,0.))
    __ok__(V.Z, V(0.,0.,1.))

    a = V(3.,2.,1.)
    b = a.normalize()
    __ok__(a != b)
    __ok__(a == V(3.,2.,1.))
    __ok__(b.magnitude(), 1)
    b = a.magnitude(5)
    __ok__(a == V(3.,2.,1.))
    __ok__(b.magnitude(), 5)
    __ok__(equal(b.dsquared(V.O), 25))

    a = V(3.,2.,1.).normalize()
    __ok__(equal(a[0], 0.80178372573727319))
    b = V(1.,3.,2.).normalize()
    __ok__(equal(b[2], 0.53452248382484879))
    d = a.dot(b)
    __ok__(equal(d, 0.785714285714), True)

    __ok__(V(2., 2., 1.) * 3, V(6, 6, 3))
    __ok__(3 * V(2., 2., 1.), V(6, 6, 3))
    __ok__(V(2., 2., 1.) / 2, V(1, 1, 0.5))

    v = V(1,2,3)
    w = V(4,5,6)
    __ok__(v.cross(w), V(-3,6,-3))
    __ok__(v.cross(w), v*w)
    __ok__(v*w, -(w*v))
    __ok__(v.dot(w), 32)
    __ok__(v.dot(w), w.dot(v))

    __ok__(zero(angle(V(1,1,1), V(2,2,2))), True)
    __ok__(equal(90.0, degrees(angle(V(1,0,0), V(0,1,0)))), True)
    __ok__(equal(180.0, degrees(angle(V(1,0,0), V(-1,0,0)))), True)

    __ok__(equal(  0.0, degrees(track(V( 1, 0)))), True)
    __ok__(equal( 90.0, degrees(track(V( 0, 1)))), True)
    __ok__(equal(180.0, degrees(track(V(-1, 0)))), True)
    __ok__(equal(270.0, degrees(track(V( 0,-1)))), True)

    __ok__(equal( 45.0, degrees(track(V( 1, 1)))), True)
    __ok__(equal(135.0, degrees(track(V(-1, 1)))), True)
    __ok__(equal(225.0, degrees(track(V(-1,-1)))), True)
    __ok__(equal(315.0, degrees(track(V( 1,-1)))), True)

    print 'Testing C complex number class...'

    __ok__(C(1,2) is not None, True)
    __ok__(C(1,2)[0], 1.0)
    __ok__(C(1+2j)[0], 1.0)
    __ok__(C((1,2))[1], 2.0)
    __ok__(C(V([1,2]))[1], 2.0)

    __ok__(C(3+2j) * C(1+4j), C(-5+14j))

    try:
        __ok__(C(1,2,3) is not None, True)
    except TypeError: # takes exactly 2 elements
        __ok__(True, True)

    try:
        __ok__(C([1,2,3]) is not None, True)
    except TypeError: # takes exactly 2 elements
        __ok__(True, True)

    except TypeError: # takes exactly 2 elements
        __ok__(True, True)

    print 'Testing Q quaternion class...'

    __ok__(Q(1,2,3,4) is not None, True)
    __ok__(Q(1,2,3,4)[1], 2.0)
    __ok__(Q((1,2,3,4))[2], 3.0)
    __ok__(Q(V(1,2,3,4))[3], 4.0)

    __ok__(Q(), Q(0,0,0,1))
    __ok__(Q(1,2,3,4).conjugate(), Q(-1,-2,-3,4))

    print 'Testing M matrix class...'

    m = M()
    __ok__(V(1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1), m)
    __ok__(m.row(0), V(1,0,0,0))
    __ok__(m.row(2), V(0,0,1,0))
    __ok__(m.col(1), V(0,1,0,0))
    __ok__(m.col(3), V(0,0,0,1))
    __ok__(m[5], 1.0)
    __ok__(m[1,1], 1.0)
    __ok__(m[6], 0.0)
    __ok__(m[1,2], 0.0)
    __ok__(m * V(1,2,3,4), V(1,2,3,4))
    __ok__(V(1,2,3,4) * m, V(1,2,3,4))
    mm = m * m
    __ok__(mm.__class__, M)
    __ok__(mm, M.I)
    mm = m * 2
    __ok__(mm.__class__, M)
    __ok__(mm, 2.0 * m)
    __ok__(mm[3,3], 2)
    __ok__(mm[3,2], 0)

    __ok__(M.rotate('X',radians(90)),
           M.twist(Q.rotate('X',radians(90))))
    __ok__(M.twist(Q(0,0,0,1)), M.I)
    __ok__(M.twist(Q(.5,0,0,1)),
           M.twist(Q(.5,0,0,1).normalize()))
    __ok__(V.O * M.translate(V(1,2,3)),
           V(1,2,3,1))
    __ok__((V.X+V.Y+V.Z) * M.translate(V(1,2,3)),
           V(2,3,4,1))

    # need some tests on m.determinant()

    m = M()
    m = m.translate(V(1,2,3))
    __ok__(m.inverse(), M().translate(-V(1,2,3)))
    m = m.rotate('Y', radians(30))
    __ok__(m * m.inverse(), M.I)

    __report__()

def __time__():
    from testing import __time__
    __time__("(V.X+V.Y).magnitude() memo",
             "import vectors; x=(vectors.V.X+vectors.V.Y)",
             "x._l = x._l ; x.magnitude()")
    __time__("(V.X+V.Y).magnitude() unmemo",
             "import vectors; x=(vectors.V.X+vectors.V.Y)",
             "x._l = None ; x.magnitude()")
    import psyco
    psyco.full()
    __time__("(V.X+V.Y).magnitude() memo [psyco]",
             "import vectors; x=(vectors.V.X+vectors.V.Y)",
             "x._l = x._l ; x.magnitude()")
    __time__("(V.X+V.Y).magnitude() unmemo [psyco]",
             "import vectors; x=(vectors.V.X+vectors.V.Y)",
             "x._l = None ; x.magnitude()")

if __name__ == '__main__':
    import sys
    if 'test' in sys.argv:
        __test__()
    elif 'time' in sys.argv:
        __time__()
    else:
        raise Exception, \
            'This module is not a stand-alone script.  Import it in a program.'

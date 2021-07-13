import numpy as np

def _from_zs_matrix(radius, height):
    h = height
    R = radius
    mat = np.array([[-h*np.sqrt(3), 0, h*np.sqrt(3)],
                    [h, -2*h, h],
                    [R, R, R],
                    [-1, 2, -1],
                    [-np.sqrt(3), 0, np.sqrt(3)],
                    [0, 0, 0]])
    return np.array(mat)

def _to_zs_matrix(radius, height):
    h = height
    R = radius
    t1 = R*np.sqrt(3) / (2 * h)
    mat = np.array([[-t1, R/(2*h), 1],
                    [0, -R/h, 1],
                    [t1, R/(2*h), 1]])
    return np.array(mat)

class JPECoord():

    def __init__(self, radius, height, zmin, zmax):
        self.R = radius
        self.h = height
        self.zmin = zmin
        self.zmax = zmax
        self.mat_from_zs = _from_zs_matrix(radius, height)
        self.mat_to_zs = _to_zs_matrix(radius, height)

    def cart_from_zs(self, zs):
        return self.from_zs(zs)[:3]
    
    def rot_from_zs(self, zs):
        return self.from_zs(zs)[3:]
    
    def from_zs(self, zs):
        return self.mat_from_zs @ zs
    
    def zs_from_cart(self, cart):
        return self.mat_to_zs @ cart

    def bounds(self, const_axis='z', const_value=0):
        norm = np.zeros(3)
        if const_axis == 'z':
            norm[2] = const_value
        elif const_axis == 'x':
            norm[1] = const_value
        elif const_axis == 'y':
            norm[0] = const_value
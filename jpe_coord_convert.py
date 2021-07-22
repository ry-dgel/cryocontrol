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
        func_dic = {'x' : _xlims, 'y' : _ylims, 'z' : _zlims}
        if const_axis not in func_dic.keys():
            raise ValueError(f"Invalid constant axis: {const_axis}")
        # Generate the bounding vertices
        pts = func_dic[const_axis](const_value, self.zmin, self.zmax, self.R, self.h)
        pts = np.array(pts)
        # Ordering the points by angle relative to their central position.
        mid = np.mean(pts,axis=0)
        sortfunc = lambda x: np.arctan2(x[1]-mid[1],x[0]-mid[0])
        order = np.apply_along_axis(sortfunc, 1, pts).argsort()
        return pts[order]
    
    def inbounds(self,point,poly_points):
        subbed_points = poly_points - points
        angle_signs = []
        n = poly_points.shape[0]
        for i, point in enumerate(subbed_points):
            ip1 = (i+1) % n
            sign = subbed_points[ip1][0]*point[1] > point[0]*subbed_points[ip1][1]
            angle_signs.append(sign)
        angle_signs = np.array([angle_signs])
        return not np.any(np.diff(angle_signs))


def _zlims(z,zmin,zmax,R,h):
    zmid = (zmin + zmax)/2
    zd = (zmax - zmin)/2
    z = z - zmid
    lims = []
    s3 = np.sqrt(3) 
    hr = h/R
    if 3*z <= -zd and -zd <= z:
        print("First Yes")
        x = s3*hr * (z + zd)
        y = hr * (z + zd)
        lims.append([x,y])
        lims.append([-x,y])
        lims.append([0, -2*y])
    if 3*z > -zd and 3*z < zd:
        print("Second Yes")
        x = hr/s3 * (zd - 3*z)
        y = hr * (z + zd)
        lims.append([x,y])
        lims.append([-x,y])
        x = hr/s3 * (zd + 3*z)
        y = hr * (z - zd)
        lims.append([-x,y])
        lims.append([x,y])
        x = 2*hr/s3 * zd
        y = -2 * hr * z
        lims.append([x,y])
        lims.append([-x,y])
    if 3*z >= zd and z <= zd:
        print("Third Yes")
        y = 2*hr*(-z + zd)
        lims.append([0,y])
        x = s3*hr*(z - zd)
        y = hr*(z-zd)
        lims.append([x,y])
        lims.append([-x,y])
    if lims:
        return lims
    else:
        return [[0,0]]
    
def _xlims(x,zmin,zmax,R,h):
    zmid = (zmin + zmax)/2
    zd = (zmax - zmin)/2
    lims = []
    s3 = np.sqrt(3) 
    hr = h/R
    if x >= 0:
        if x <= 2/3*s3*hr*zd:
            y = x/s3
            z = x/(s3 * hr) - zd
            lims.append([y,z])
            lims.append([-y,-z])
            y = -x / s3 + 4/3*hr*zd
            z = 1/3 * (-s3 * x /hr + zd)
            lims.append([y,z])
            lims.append([-y,-z])
    if x < 0:
        if x >= -2*hr*zd/s3:
            y = - x/s3
            z = - x/(s3 * hr) - zd
            lims.append([y,z])
            lims.append([-y,-z])
            y = x / s3 + 4/3*hr*zd
            z = 1/3 * (s3 * x /hr + zd)
            lims.append([y,z])
            lims.append([-y,-z])
    for lim in lims:
        lim[1] -= zd
    if lims:
        return lims
    else:
        return [[0,0]]

def _ylims(y, zmin,zmax,R,h):
    zmid = (zmin + zmax)/2
    zd = (zmax - zmin)/2
    lims = []
    s3 = np.sqrt(3) 
    hr = h/R

    if 0 <= y <= 4/3*hr*zd:
        z = - y/(2*hr) + zd
        lims.append([z,-0])
    if  -2/3*hr*zd <= y <= 0:
        x = s3 * y
        z = y/hr + zd
        lims.append([z,x])
        lims.append([z,-x])
    if  0 <= y <= 2/3*hr*zd:
        z = y/hr - zd
        x = s3*y
        lims.append([z,x])
        lims.append([z,-x])
    if  -4/3 * hr * zd <= y <= 0:
        z = -y/(2*hr) - zd
        lims.append([z,-0])
    if 2/3 * hr * zd <= y <= 4/3 * hr * zd:
        x = -y*s3 + 4*hr*zd/s3
        z = y/hr - zd
        lims.append([z,x])
        lims.append([z,-x])
    if -2/3 * hr * zd <= y <= 2/3 * hr * zd:
        x = 2*hr*zd/s3
        z = -y/(2*hr)
        lims.append([z,x])
        lims.append([z,-x])
    if -4/3 * hr * zd <= y <= -2/3 * hr * zd:
        x = -(y*s3 + 4*hr*zd/s3)
        z = y/hr + zd
        lims.append([z,x])
        lims.append([z,-x])

    for lim in lims:
        lim[0] -= zd
        
    if lims:
        return lims
    else:
        return [[0,0]]
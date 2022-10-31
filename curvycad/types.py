
##########
# Types used to define paths
##########
class PathElement(object):
    pass

class Start(PathElement):
    def __init__(self, location, theta):
        self.location = location
        self.theta = theta

    @property
    def length(self):
        return 0.0

    def __repr__(self):
        return f"Start(location={self.location}, theta={self.theta})"

class Straight(PathElement):
    def __init__(self, length):
        self.length = length

    @property
    def length(self):
        return self._length

    @length.setter
    def length(self, val):
        self._length = val

    def __repr__(self):
        return f"Straight(length={self._length})"

class Curve(PathElement):
    def __init__(self, angle, radius):
        self.angle = angle
        self.radius = radius
    
    @property
    def length(self):
        return abs(self.angle) * self.radius

    def __repr__(self):
        return f"Curve(angle={self.angle}, radius={self.radius})"

##########
# Types used to define patterns
##########
class PatternElement(object):
    pass

class ParallelLine(PatternElement):
    def __init__(self, start, end, offset, width, layer):
        """Defines a line which runs parallel to the direction of the path
        
        start: The distance along the path at which to start the line (dimensionless, 0 to 1)
        end: The distance along the path at which to end the line (dimensionless, 0 to 1)
        offset: The transverse offset from the line (mm, positive right)
        width: The width of the line (mm)
        layer: The kicad layer it is to be drawn in (e.g. pcbnew.F_Cu, or pcbnew.B_Cu)
        """
        self.start = float(start)
        self.end = float(end)
        self.offset = float(offset)
        self.width = float(width)
        self.layer = layer

class TransverseLine(PatternElement):
    def __init__(self, start, end, offset, width, layer):
        """Defines a line which runs perpendicular to the direction of the path
        
        start: The transversal position at which the line starts (mm)
        end: The transversal position at which the line ends (mm)
        offset: The position of the line along the path (dimensionless, 0 to 1)
        width: The width of the line (mm)
        layer: The kicad layer it is to be drawn in (e.g. pcbnew.F_Cu, or pcbnew.B_Cu)
        """
        self.start = float(start)
        self.end = float(end)
        self.offset = float(offset)
        self.width = float(width)
        self.layer = layer

class Via(PatternElement):
    def __init__(self, distance: float, transverse: float, drill: float=0.3, pad: float=0.6):
        """Defines a via located at a certain spot in the pattern

        distance: Define the position of the via along the path (dimensionless, 0 to 1)
        transverse: Defines the position of the via parallel to the path (mm, positive right)
        drill: Defines the size of the hole in the via (mm)
        pad: Defines the size of the copper pad around the via (mm)
        """
        self.distance = float(distance)
        self.transverse = float(transverse)
        self.drill = float(drill)
        self.pad = float(pad)
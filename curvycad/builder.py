import numpy as np
from .types import *

def rotate(x, theta):
    x = np.asarray(x)
    R = np.array([
        [np.cos(theta), np.sin(theta)],
        [-np.sin(theta), np.cos(theta)]
    ])
    return np.dot(R, x.T).T

def warp_point_on_arc(p, radius):
    """Warp point (u, v) to cartesian x y
    u is distance along path
    v is transverse displacement, perpendicular to track.
    radius is the curvature of the arc.
    """
    u, v = p
    # Compute the angle
    theta = u / radius
    p = (0.0, radius + v)
    return rotate(p, theta) - (0.0, radius)


class TrackBuilder(object):
    def __init__(self, pitch, pattern):
        """The TrackBuilder class contains all of the logic for transforming 
        a pattern to follow a path. It is abstract, so it cannot be used
        directly. An implementation must implement `emit_line`, `emit_arc`, and
        `emit_via` to be used. The default implementation is KicadTrackBuilder.

        Arguments: 
            - pitch: The default distance-along-path which will be
            occupied by one pattern cycle, in mm.
            - pattern: A list of PathElements (Start, Straight, Curve)
            which define the path to be followed.
        """
        self.pitch = pitch
        self.pattern = pattern
        self.pos = np.array((0.0, 0.0))
        self.theta = 0.0
        self.cycle_pos = 0.0

    def set_location(self, p, theta):
        self.pos = np.array(p, dtype=np.float64)
        self.theta = float(theta)

    def draw_path(self, path):
        """Draw the pattern along the provided path
        
        Note that the configured pitch will be adjusted so that the full track
        length is a multiple of the pitch, so that all patterns are completed.
        """
        total_length = sum([el.length for el in path])

        # Adjust the pitch to match the length
        # So that we end up with an integer number of cycles
        cycles = np.round(total_length / self.pitch)
        pitch = total_length / cycles

        for el in path:
            if isinstance(el, Start):
                self.pos = el.location
                self.theta = el.theta
            elif isinstance(el, Straight):
                self.__laydown_straight_distance(el.length, pitch)
            elif isinstance(el, Curve):
                self.__laydown_curve_distance(el.radius, el.angle, pitch)

    def __laydown_straight_distance(self, distance, pitch):
        distance_remaining = distance
        while distance_remaining > 1e-12:
            if self.cycle_pos > 0.0:
                # Start mid cycle
                seg_start = self.cycle_pos
                if distance_remaining / pitch < 1.0 - seg_start - 1e-12:
                    # End mid cycle too
                    seg_end = distance_remaining / pitch + seg_start
                    self.cycle_pos = seg_end + 1e-14
                else:
                    # Room to finish the cycle
                    seg_end = 1.0
                    self.cycle_pos = 0.0
            else:
                seg_start = 0.0
                if distance_remaining / pitch < 1.0 - 1e-12:
                    # End mid cycle
                    seg_end = distance_remaining / pitch 
                    self.cycle_pos = seg_end + 1e-14
                else:
                    # Room to finish the cycle
                    seg_end = 1.0
                    self.cycle_pos = 0.0

            self.__laydown_straight_cycle(seg_start, seg_end, pitch)
            distance_added = (seg_end - seg_start) * pitch
            self.pos += rotate((distance_added, 0), self.theta)
            distance_remaining -= distance_added


    def __laydown_curve_distance(self, radius, angle, pitch):
        distance_remaining = radius * np.abs(angle)
        while distance_remaining > 1e-12:
            if self.cycle_pos > 0.0:
                # Start mid cycle
                seg_start = self.cycle_pos
                if distance_remaining / pitch < 1.0 - seg_start - 1e-12:
                    # End mid cycle too
                    seg_end = distance_remaining / pitch + seg_start
                    self.cycle_pos = seg_end + 1e-14
                else:
                    # Room to finish the cycle
                    seg_end = 1.0
                    self.cycle_pos = 0.0
            else:
                seg_start = 0.0
                if distance_remaining / pitch < 1.0 - 1e-12:
                    # End mid cycle
                    seg_end = distance_remaining / pitch 
                    self.cycle_pos = seg_end + 1e-14
                else:
                    # Room to finish the cycle
                    seg_end = 1.0
                    self.cycle_pos = 0.0

            self.__laydown_curve_cycle(seg_start, seg_end, pitch, radius, angle)
            distance_added = (seg_end - seg_start) * pitch
            self.pos += rotate(warp_point_on_arc((distance_added, 0.0), radius * np.sign(angle)), self.theta)
            self.theta += np.sign(angle) * distance_added / radius
            distance_remaining -= distance_added
        
    def __laydown_straight_cycle(self, seg_start, seg_end, pitch):
        for el in self.pattern:
            if isinstance(el, ParallelLine):
                start = (
                    (max(seg_start, el.start) - seg_start) * pitch,
                    el.offset
                )
                end = (
                    (min(seg_end, el.end) - seg_start) * pitch,
                    el.offset
                )
                if start[0] > end[0]:
                    continue
                start = rotate(start, self.theta) + self.pos
                end = rotate(end, self.theta) + self.pos
                self.emit_line(start, end, el.width, el.layer)
            elif isinstance(el, TransverseLine):
                if el.offset >= seg_start and el.offset <= seg_end:
                    start = ((el.offset - seg_start) * self.pitch, el.start)
                    end = ((el.offset - seg_start) * self.pitch, el.end)
                    start = rotate(start, self.theta) + self.pos
                    end = rotate(end, self.theta) + self.pos
                    self.emit_line(start, end, el.width, el.layer)
            elif isinstance(el, Via):
                if el.distance >= seg_start and el.distance <= seg_end:
                    p = ((el.distance - seg_start) * self.pitch, el.transverse)
                    p = rotate(p, self.theta) + self.pos
                    self.emit_via(p, el.drill, el.pad)
    
    def __laydown_curve_cycle(self, seg_start, seg_end, pitch, radius, angle):
        for el in self.pattern:
            if isinstance(el, ParallelLine):
                start = (
                    (max(seg_start, el.start) - seg_start) * pitch,
                    el.offset
                )
                end = (
                    (min(seg_end, el.end) - seg_start) * pitch,
                    el.offset
                )
                if start[0] > end[0]:
                    continue
                # Curve the points onto the arc
                start = warp_point_on_arc(start, radius * np.sign(angle))
                end = warp_point_on_arc(end, radius * np.sign(angle))
                mid = warp_point_on_arc(((start[0] + end[0])/2, el.offset), radius * np.sign(angle))
                
                # Transform into current board coordinates
                start = rotate(start, self.theta) + self.pos
                end = rotate(end, self.theta) + self.pos
                mid = rotate(mid, self.theta) + self.pos

                self.emit_arc(start, mid, end, el.width, el.layer)
            elif isinstance(el, TransverseLine):
                if el.offset >= seg_start and el.offset <= seg_end:
                    # Line in local coordinates on arc
                    p0 = warp_point_on_arc(((el.offset - seg_start) * self.pitch, el.start), radius * np.sign(angle))
                    p1 = warp_point_on_arc(((el.offset - seg_start) * self.pitch, el.end), radius * np.sign(angle))
                    
                    # Transform into board coordinates
                    p0 = rotate(p0, self.theta) + self.pos
                    p1 = rotate(p1, self.theta) + self.pos
                    
                    self.emit_line(p0, p1, el.width, el.layer)
            elif isinstance(el, Via):
                if el.distance >= seg_start and el.distance <= seg_end:
                    p = warp_point_on_arc(((el.distance - seg_start) * self.pitch, el.transverse), radius * np.sign(angle))
                    p = rotate(p, self.theta) + self.pos
                    self.emit_via(p, el.drill, el.pad)

    def draw_straight(self, cycles, pitch):
        n_cycles = int(cycles)
        for _ in range(n_cycles):
            for el in self.pattern:
                if isinstance(el, ParallelLine):
                    start = (el.start * self.pitch, el.offset)
                    end = (el.end * self.pitch, el.offset)
                    start = rotate(start, self.theta) + self.pos
                    end = rotate(end, self.theta) + self.pos
                    self.emit_line(start, end, el.width, el.layer)
                elif isinstance(el, TransverseLine):
                    start = (el.offset * self.pitch, el.start)
                    end = (el.offset * self.pitch, el.end)
                    start = rotate(start, self.theta) + self.pos
                    end = rotate(end, self.theta) + self.pos
                    self.emit_line(start, end, el.width, el.layer)
                elif isinstance(el, Via):
                    p = (el.distance * self.pitch, el.transverse)
                    p = rotate(p, self.theta) + self.pos
                    self.emit_via(p, el.drill, el.pad)
            self.pos += rotate(np.array((1.0, 0)) * self.pitch, self.theta)
        
    def draw_arc(self, radius, angle):
        """Draw a curved section
        
        Sections must always be drawn with complete phase cycles, so radius
        may be rounded to achieve this. 
        To get exact radius, angle*radius must be equal to n * pitch, where n
        is an integer.
        """
        radius = float(radius)
        angle = float(angle)
        if np.abs(angle) > 2 * np.pi:
            raise RuntimeError("Angle should be in radians, in range (-2pi, 2pi). Got {angle}")
        n_cycles = int(np.round(radius * np.abs(angle) / self.pitch))
        # Compute new radius to achieve complete cycles
        radius = self.pitch * n_cycles / np.abs(angle)

        for _ in range(n_cycles):
            for el in self.pattern:
                if isinstance(el, ParallelLine):
                    # Compute three arc points in local coordinates
                    start = warp_point_on_arc((el.start*self.pitch, el.offset), radius * np.sign(angle))
                    end = warp_point_on_arc((el.end*self.pitch, el.offset), radius * np.sign(angle))
                    mid = warp_point_on_arc(((el.start + el.end)/2 * self.pitch, el.offset), radius * np.sign(angle))
                    
                    # Transform into current board coordinates
                    start = rotate(start, self.theta) + self.pos
                    end = rotate(end, self.theta) + self.pos
                    mid = rotate(mid, self.theta) + self.pos

                    self.emit_arc(start, mid, end, el.width, el.layer)
                elif isinstance(el, TransverseLine):
                    # Line in local coordinates on arc
                    p0 = warp_point_on_arc((el.offset * self.pitch, el.start), radius * np.sign(angle))
                    p1 = warp_point_on_arc((el.offset * self.pitch, el.end), radius * np.sign(angle))
                    
                    # Transform into board coordinates
                    p0 = rotate(p0, self.theta) + self.pos
                    p1 = rotate(p1, self.theta) + self.pos
                    
                    self.emit_line(p0, p1, el.width, el.layer)
                elif isinstance(el, Via):
                    p = warp_point_on_arc((el.distance * self.pitch, el.transverse), radius * np.sign(angle))
                    p = rotate(p, self.theta) + self.pos
                    self.emit_via(p, el.drill, el.pad)

            self.pos += rotate(warp_point_on_arc((self.pitch, 0.0), radius * np.sign(angle)), self.theta)
            self.theta += angle / n_cycles

        def emit_line(self, p0, p1, width, layer):
            raise RuntimeError("TrackBuilder is abstract. Use KicadTrackBuilder, or implement your own emit methods.")

        def emit_arc(self, start, mid, end, width, layer):
            raise RuntimeError("TrackBuilder is abstract. Use KicadTrackBuilder, or implement your own emit methods.")

        def emit_via(self, p, drill, pad):
            raise RuntimeError("TrackBuilder is abstract. Use KicadTrackBuilder, or implement your own emit methods.")

class KicadTrackBuilder(TrackBuilder):
    def __init__(self, pitch, pattern, board):
        """Implements emit methods for writing to a kicad board"""
        # Globally import pcbnew, only when a KicadTrackBuilder is created to
        # avoid the dependency if another type of builder is used
        global pcbnew
        pcbnew = __import__('pcbnew', globals(), locals())
        super().__init__(pitch, pattern)
        self.board = board
        self.group = pcbnew.PCB_GROUP(self.board)
        self.board.Add(self.group)
    
    def emit_line(self, p0, p1, width, layer):
        track = pcbnew.PCB_TRACK(self.board)
        track.SetStart(self.__pcbpoint(p0))
        track.SetEnd(self.__pcbpoint(p1))
        track.SetWidth(int(width * 1e6))
        track.SetLayer(layer)
        self.board.Add(track)
        self.group.AddItem(track)

    def emit_arc(self, start, mid, end, width, layer):
        track = pcbnew.PCB_ARC(self.board)
        track.SetStart(self.__pcbpoint(start))
        track.SetMid(self.__pcbpoint(mid))
        track.SetEnd(self.__pcbpoint(end))
        track.SetWidth(int(width * 1e6))
        track.SetLayer(layer)
        self.board.Add(track)
        self.group.AddItem(track)

    def emit_via(self, p, drill, pad):
        via = pcbnew.PCB_VIA(self.board)
        via.SetPosition(self.__pcbpoint(p))
        via.SetDrill(int(drill * 1e6))
        via.SetWidth(int(pad * 1e6))
        self.board.Add(via)
        self.group.AddItem(via)

    @staticmethod
    def __pcbpoint(p):
        return pcbnew.wxPointMM(float(p[0]), float(p[1]))

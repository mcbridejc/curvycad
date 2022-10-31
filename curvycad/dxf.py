"""Utilities for reading a path from a DXF"""

import ezdxf
from ezdxf.entities import Arc, Line, LWPolyline
import math
import numpy as np
from typing import AnyStr, List, Tuple, Union

from .types import PathElement, Curve, Straight, Start


class PolyArc(object):
    """A local arc designed to look like a exdxf Arc"""
    def __init__(self, start_pos, end_pos, start_angle, end_angle, radius):
        self.start_pos = start_pos
        self.end_pos = end_pos
        self.start_angle = start_angle
        self.end_angle = end_angle
        self.radius = radius

def arc_from_lwpolyline_points(
        p0: Tuple[float, float, float, float, float],
        p1: Tuple[float, float, float, float, float]) -> PolyArc:
    """Get an Arc from two vertices of an LWPolyline
    The first point (p0) provides a starting point, and a "bulge" value. The second point (p1)
    provides the end point.

    The format is the same 5-tuple returned from the iter of an exdxf LWPolyline.

    """
    start_pos = [p0[0], p0[1]]
    bulge = p0[4]
    end_pos = [p1[0], p1[1]]
    dx = end_pos[0] - start_pos[0]
    dy = end_pos[1] - start_pos[1]
    d = math.sqrt(dx*dx + dy*dy)
    if (bulge == 0):
        raise ValueError("Cannot make arc from segment with bulge==0.0")
    bulge_sign = -1 if bulge < 0 else 1
    # Bulge is given as a proportion of line size
    bulge = abs(bulge) * d / 2
    # Apply some geometry to determine the radius of the arc segment from bulge and the distance between the two points on the arc
    arc_radius = (bulge*bulge + d * d / 4) / (2 * bulge)
    # Get the angle or arc between the start and end points
    arc_angle = 2 * math.atan(d / (2 * (arc_radius - bulge)))
    # Get the angle of the line from start to end
    line_angle = math.atan2(dy, dx)
    start_angle = line_angle + bulge_sign * (math.pi / 2 - arc_angle / 2) + math.pi
    end_angle = start_angle - bulge_sign * arc_angle
    return PolyArc(start_pos, end_pos, start_angle, end_angle, arc_radius)

def get_start(element):
    if isinstance(element, Line):
        return element.dxf.start
    elif isinstance(element, Arc):
        return element.start_point
    elif isinstance(element, LWPolyline):
        p = element[0]
        return [p[0], p[1], 0.0]
    else:
        raise ValueError(f"Bad input to get_start {element}")

def get_end(element):
    if isinstance(element, Line):
        return element.dxf.end
    elif isinstance(element, Arc):
        return element.end_point
    elif isinstance(element, LWPolyline):
        p = element[-1]
        return [p[0], p[1], 0.0]
    else:
        raise ValueError(f"Bad input to get_start {element}")

def get_start_angle(element):
    if isinstance(element, Line):
        dx = element.dxf.end[0] - element.dxf.start[0]
        dy = element.dxf.end[1] - element.dxf.start[1]
        return math.atan2(dy, dx)
    elif isinstance(element, Arc):
        if hasattr(element, 'reversed'):
            return np.deg2rad(Arc.dxf.start_angle) + math.pi / 2
        else:
            return np.deg2rad(Arc.dxf.start_angle) - math.pi / 2
    elif isinstance(element, LWPolyline):
        p0 = element[0]
        p1 = element[1]
        arc = arc_from_lwpolyline_points(p0, p1)
        bulge = p0[4]
        if bulge > 0:
            return arc.start_angle + math.pi / 2
        else:
            return arc.start_angle - math.pi / 2


def reverse_element(element):
    if isinstance(element, Line):
        tmp = element.dxf.start
        element.dxf.start = element.dxf.end
        element.dxf.end = tmp
    elif isinstance(element, Arc):
        tmp = element.dxf.start_angle
        element.dxf.start_angle = element.dxf.end_angle
        element.dxf.end_angle = tmp
        # Extremely hacky; but we need to know later if this element is
        # reversed
        element.reversed = True
    elif isinstance(element, LWPolyline):
        element.reversed = True
    else:
        raise ValueError(f"Bad input to get_start {element}")

    return element

def dxf_entity_string(entity):
    if isinstance(entity, ezdxf.entities.Line):
        dxf_attrs = ['start', 'end']
        props = ','.join([f"{name}={getattr(entity.dxf, name)}" for name in dxf_attrs])
        return f"Line({props})"
    elif isinstance(entity, ezdxf.entities.Arc):
        dxf_attrs = ['center', 'radius', 'start_angle', 'end_angle']
        el_attrs = ['start_point', 'end_point']
        props = ','.join([f"{name}={getattr(entity.dxf, name)}" for name in dxf_attrs])
        subprops = ','.join([f"{name}={getattr(entity, name)}" for name in el_attrs])
        return f"Arc({props}) ({subprops})"
    elif isinstance(entity, LWPolyline):
        points = list(entity)
        return f"LWPoly({points})"
    else:
        return str(entity)

def reduce_lw_polyline(pl: LWPolyline) -> List[Union[Curve, Straight]]:
    """Convert the LW polyline to series of Straights and Curves"""
    reversed = hasattr(pl, 'reversed')

    if pl.is_closed:
        indices = range(len(pl))
    else:
        indices = range(len(pl) - 1)
    result = []
    if reversed:
        indices = reversed(indices)
    for i in indices:
        start = pl[i]
        end = pl[(i+1) % len(pl)]
        bulge = start[4]
        if bulge == 0.0:
            # It's a line
            dx = start[0] - end[0]
            dy = start[1] - end[1]
            d = math.sqrt(dx*dx + dy*dy)
            result.append(Straight(d))
        else:
            # It's an arc
            arc = arc_from_lwpolyline_points(start, end)
            angle = arc.start_angle - arc.end_angle
            if reversed:
                angle *= -1
            result.append(Curve(angle, arc.radius))

    return result

def __read_dxf_elements(filepath: AnyStr):
    """Read elements"""
    elements = []

    dxf = ezdxf.readfile(filepath)
    msp = dxf.modelspace()

    for el in msp.query():
        if isinstance(el, (Line, Arc, LWPolyline)):
            elements.append(el)
        else:
            raise ValueError(f"Encountered an unsupported element type {el} in DXF")

    # Now, do some validation to make sure that the elements form a complete path,
    # and order them in the process.

    # Outline of the process is:
    # - Pick the first element, abitrarily
    # - Search for other elements which share an endpoint
    #   - If they share start, insert at the front of list, if they share end
    #     append them. If they are not in the same direction (i.e. end == end or
    #     start == start) reverse the direction of the new element
    # - Get new start and end points from the new ordered_list, and repeat
    #
    # If the file is not a single connected path, not all of the elements will
    # be connected, and we will fail.

    ordered_elements = [elements[0]]
    elements.remove(elements[0])

    while len(elements) > 0:
        start = get_start(ordered_elements[0])
        end = get_end(ordered_elements[-1])
        found = False
        for el in elements:
            if np.allclose(get_start(el), end):
                ordered_elements.append(el)
                elements.remove(el)
                found = True
            elif np.allclose(get_end(el), start):
                ordered_elements.insert(0, el)
                elements.remove(el)
                found = True
            elif np.allclose(get_end(el), end):
                reverse_element(el)
                ordered_elements.append(el)
                elements.remove(el)
                found = True
            elif np.allclose(get_start(el), start):
                reverse_element(el)
                ordered_elements.insert(0, el)
                ordered_elements.remove(el)
                found = True
            if found:
                break

        if not found:
            error = "Failed to make sequence from shapes.\n"
            error += "Ordered: \n"
            for e in ordered_elements:
                error += dxf_entity_string(e) + "\n"
            error += "Remaining: \n"
            for e in elements:
                error += dxf_entity_string(e) + "\n"
            raise ValueError(error)

    return ordered_elements

def read_dxf(filename) -> List[PathElement]:
    """Reads a DXF file, and returns it as a list of PathElements.

    The first element is a Start, giving the starting position of the curve.
    This is followed by a collection of Straight and Curve elements.

    There are some requirements on the DXF:
        - It can only have Arcs and Lines
        - They must all be connected (i.e. Each endpoint -- except perhaps
          two for an open path -- must be shared by exactly two features.)
        - All connected arcs/lines MUST be tangent. A corollary to his is that
          the sequence must be alternating arcs and lines (an exception is that
          it's acceptable though redundant for two co-linear, connected lines to be
          consecutive.)
    """

    # Get elements, re-ordered/reversed as necessary
    elements = __read_dxf_elements(filename)

    path = [Start(get_start(elements[0])[0:2], get_start_angle(elements[0]))]
    for el in elements:
        if isinstance(el, Line):
            dx = el.dxf.end[0] - el.dxf.start[0]
            dy = el.dxf.end[1] - el.dxf.start[1]
            d = math.sqrt(dx*dx + dy*dy)
            path.append(Straight(d))
        elif isinstance(el, Arc):
            if hasattr(el, 'reversed'):
                s = el.dxf.end_angle
                e = el.dxf.start_angle
            else:
                s = el.dxf.start_angle
                e = el.dxf.end_angle
            # DXF arc always go counterclockwise; but we may have reversed them
            angle = np.deg2rad(e - s)
            if angle < 0:
                angle = math.pi * 2 - angle
            if hasattr(el, 'reversed'):
                angle *= -1
            path.append(Curve(angle, el.dxf.radius))
        elif isinstance(el, LWPolyline):
            path += reduce_lw_polyline(el)
        else:
            raise ValueError(f"Unknown element {el}")
    return path
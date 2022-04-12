curvycad
========

A (hacked together) tool for PCB racetracks. Actually, it's a bit more general: it takes a repeating
pattern defined by a set of parallel lines, transverse lines, and points (e.g. vias)
and it repeats this pattern along a path defined by lines and arcs, so that the
pattern is bent to follow the path. But I used it to make PCB racetracks, and it
is designed with the idea that it is run as part of a kicad plugin.

It's setup to modify a KiCad board; but you can use the same geometry code to
output to other formats by creating a class which derives from `TrackBuilder`,
and implementing new `emit_line`, `emit_arc`, and `emit_via` methods.

## DXF Path Import

The path can be created in a CAD tool like Fusion 360 or LibreCAD, and exported as a
DXF, then imported to a path via the `curvycad.read_dxf` function. However, there are
some constraints on what can go in the DXF.

For one thing, no extra lines. All lines must be connected to form a continuous path.
It can be closed, or open.

All segments have to be tangent to the previous segment. This means that lines must
be connected via an arc, and you must constrain the arc to be tangent to the line
on both sides in your sketch.

Only arcs and lines are supported; splines, polylines, etc are not. I don't know
how robust this will be to different DXF files created by different tools. I used
it successfully on a DXF exported from Fusion 360, and that's all I can say.

## Path Elements

Of course, you can also create a path manually, or from some other source. A
path consists of a list containing a series of the three objects below.

### Start

`Start(location, theta)`

Should be placed at the beginning of the list of elements. It initializes the
current draw position to the given location -- (x, y) in mm -- and angle (radians).

### Straight

`Straight(length)`

Moves ahead in the current direction the provided distance (in mm).

### Curve

`Curve(angle, radius)`

Inserts a turn through the given angle (radians) with the given radius.

## An example

This is a simple example which defines a pattern, and lays it out along a path provided
in `track.dxf`. This is setup to run as a KiCad action plugin. It can be adapted to
run in the pcbnew python console, or to be run on the command line and modify a .kicad_pcb
file directly.

```python
import pcbnew
import curvycad as cc
import os

PITCH=4.0
LINE_WIDTH = 0.2
RAIL_WIDTH = 1.0
VIA_DRILL = 0.3
VIA_PAD = 0.6

# This list defines the periodically repeated pattern of objects. 
# All distances along the path are normalized to the range (0 to 1), and
# they will be scaled by the provided `pitch` value later. Distances
# orthogonal to the path are given in absolute terms.
segment = [
    # Draw two parallel lines 5mm on either side of the path in top layer
    # They cover the entire length of the segment (0 to 1)
    cc.ParallelLine(start=0.0, end=1.0, offset=-5, width=RAIL_WIDTH, layer=pcbnew.F_Cu),
    cc.ParallelLine(start=0.0, end=1.0, offset=5, width=RAIL_WIDTH, layer=pcbnew.F_Cu),

    # Create one line across the track from the two rails at the middle (0.5) of
    # each pattern segment
    cc.TransverseLine(start=-5, end=5, offset=0.5, width=LINE_WIDTH, layer=pcbnew.F_Cu),

    # Add a via in the middle of the cross line. Why? I don't know. It's just
    # an example of a via.
    cc.Via(distance=0.5, transverse=0, drill=VIA_DRILL, pad=VIA_PAD),
]

class TrackLayout(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "Layout example pattern"
        self.category = "Modify PCB"
        self.description = "Layout example pattern"
        self.show_toolbar_button = True

    def Run(self):
        board = pcbnew.GetBoard()
        projdir = os.path.dirname(os.path.abspath(board.GetFileName()))
        guide = cc.read_dxf(os.path.join(projdir, 'track.dxf'))
        # Print the path elements for our own edification
        for el in guide:
            print(el)
        # Create the builder
        track = cc.KicadTrackBuilder(PITCH, segment, board)
        # Layout the path defined in `guide`
        # The pitch will be adjusted slightly as necessary to ensure that the
        # last pattern ends at the end of the path. This ensures that in a closed
        # path there is no discontinuity.
        track.draw_path(guide)
        


TrackLayout().register()
```

And the result looks something like this, depending on the path you apply it to:


![Example Result](/docs/track_example_kicad.png?raw=true "Example rendered in kicad")

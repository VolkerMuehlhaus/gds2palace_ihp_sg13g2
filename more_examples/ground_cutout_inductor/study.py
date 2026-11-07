"""Inductor to ground frame margin study: layouts and Palace models.

The layout code is the one of more_examples/inductor_synthesis_no_external_library (taken from that file when this
runs, so there is one copy), with two changes for this study:
 - the frame margin is a parameter instead of D/2,
 - below a margin of about 30 um the ring lies between coil and ports. The ground strip under the feed then goes from
   the ring out to the ports, so the ports stay 30 um from the coil at every margin.

Frame "floating": Metal1 only, as in the synthesis example, couples to the silicon through the oxide.
Frame "tied": the same outline also on Cont and Activ and on the SUBGND sheet, like a substrate tie ring.
No cutout, "plane_M1" or "plane_M3": one solid plane on that layer instead of the frame, with the outer size of the frame
at this margin. It reaches under the coil, so the ports go from the plane to the feed.

The simulation box is the same for all margins of a coil (settings['margin'] per side), so that only the frame changes.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__)).replace(os.sep, "/")
REPO = os.path.abspath(os.path.join(HERE, "..", "..")).replace(os.sep, "/")
GENERATOR = f"{REPO}/more_examples/inductor_synthesis_no_external_library/synthesize_ihp_inductor_v4.py"
XML = f"{REPO}/XML_stackup/latest/IHP/SG13G2_FEM_200um.xml"

W = 5.0
S = 2.0
FEED_LENGTH = 30
FRAME_WIDTH = 20        # generator's min(20, 5*w) at w = 5
MAX_GAP = 150           # largest frame margin of the study: the simulation box is sized for this one
BOX_BEYOND_FRAME = 200  # dielectric beyond the frame at the largest margin
AIR = 50

COILS = {"L0n5": dict(N=2, f_stop=80e9), "L2n0": dict(N=3, f_stop=40e9)}
PLANES = {"plane_M1": (8, "Metal1"), "plane_M3": (30, "Metal3")}   # no cutout: GDS layer and stackup name of the plane


def _load_generator():
    """symmetric_octa_IHP() of the synthesis example, with the frame margin as a parameter."""
    import gdspy   # noqa: F401, used by the generator code
    text = open(GENERATOR, encoding="utf-8").read()
    start = text.index("# ==================================== INDUCTOR LAYOUT CODE")
    end = text.index("# ==================================== SIMULATION FLOW CODE")
    code = text[start:end].replace("\r\n", "\n")

    def replace(old, new):
        nonlocal code
        assert code.count(old) == 1, old
        code = code.replace(old, new)

    replace('forEM=False, filename="inductor.gds", textlabel=""):',
            'forEM=False, filename="inductor.gds", textlabel="", frame_gap=None):')
    replace("frame_margin = gridsnap(D/2)", "frame_margin = gridsnap(frame_gap)")
    replace("p1=(x0-feedline_spacing/2-w, y0-D/2-feed_length + 2), \n",
            "p1=(x0-feedline_spacing/2-w, y0-D/2-feed_length + (2 if frame_margin > feed_length - 2 else -2)), \n")
    namespace = {"math": math, "gdspy": gdspy}
    exec(compile(code, GENERATOR, "exec"), namespace)
    return namespace


def layout_file(coil, D, gap, tie):
    return f"{HERE}/layouts/{coil}_D{D:g}_gap{gap:g}_{ {False: 'floating', True: 'tied'}.get(tie, tie)}.gds"


def make_layout(coil, D, gap, tie):
    """Writes the layout, returns its file name."""
    import gdspy
    generator = _load_generator()
    filename = layout_file(coil, D, gap, tie)
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    generator["symmetric_octa_IHP"](N=COILS[coil]["N"], D=D, w=W, s=S, includeCenterTap=False, LBE=False, forEM=True,
                                    filename=filename, frame_gap=gap)
    # the frame as one Metal1 shape: ring and feed strip overlap at small margins
    lib = gdspy.GdsLibrary(infile=filename)
    cell = lib.top_level()[0]
    if tie in PLANES:
        half = D / 2 + gap + FRAME_WIDTH
        cell.remove_polygons(lambda points, layer, datatype: layer == 8 and datatype == 0)
        cell.add(gdspy.Rectangle((-half, -half), (half, half), layer=PLANES[tie][0]))
        lib.write_gds(filename)
        return filename
    frame = gdspy.boolean(cell.get_polygons(by_spec=True)[(8, 0)], None, "or", precision=1e-3, layer=8)
    cell.remove_polygons(lambda points, layer, datatype: layer == 8 and datatype == 0)
    if tie == "slot":   # diagnostic: ring cut on the side away from the ports, so that it is no shorted turn
        slot = gdspy.Rectangle((-1, D / 2 + gap - 1), (1, D / 2 + gap + FRAME_WIDTH + 1))
        frame = gdspy.boolean(frame, slot, "not", precision=1e-3, layer=8)
    # tie_noPEC: diagnostic, tie ring through Cont and Activ into the silicon, without the ideal SUBGND sheet
    layers = {True: (8, 1, 6, 250), "tie_noPEC": (8, 1, 6)}.get(tie, (8,))
    for layer in layers:
        for polygon in frame.polygons:
            cell.add(gdspy.Polygon(polygon, layer=layer))
    lib.write_gds(filename)
    return filename


def box_half_width(D):
    return D / 2 + MAX_GAP + FRAME_WIDTH + BOX_BEYOND_FRAME


def make_model(name, coil, D, gap, tie, fpoint=None, order=2, conductor_model="solve_inside", box_beyond=None,
               refined_cellsize=2.0, frame_cellsize=5.0, amr_passes=0):
    """Writes one Palace model into palace_model/<name>_data."""
    from gds2palace import gds_reader, simulation_setup, stackup_reader, utilities

    filename = make_layout(coil, D, gap, tie)
    materials_list, dielectrics_list, metals_list = stackup_reader.read_substrate(XML)
    ports = simulation_setup.all_simulation_ports()
    port_ground = PLANES[tie][1] if tie in PLANES else "Metal1"
    for number, layer in ((1, 201), (2, 202)):
        ports.add_port(simulation_setup.simulation_port(portnumber=number, voltage=1, port_Z0=50, source_layernum=layer,
                                                        from_layername=port_ground, to_layername="TopMetal1", direction="z"))
    layers = metals_list.getlayernumbers()
    layers.extend(ports.portlayers)
    allpolygons = gds_reader.read_gds(filename, layers, purposelist=[0], metals_list=metals_list, merge_polygon_size=0,
                                      gds_boundary_layers=dielectrics_list.get_boundary_layers())

    # the same box for every margin: per-side margin from the bounding box of this layout
    half = D / 2 + MAX_GAP + FRAME_WIDTH + (BOX_BEYOND_FRAME if box_beyond is None else box_beyond)
    xmin, xmax, ymin, ymax = allpolygons.get_bounding_box()
    margin = [float(xmin + half), float(half - xmax), float(ymin + half), float(half - ymax)]

    settings = {
        "unit": 1e-6, "margin": margin, "air_around": AIR, "boundary": ["ABC"] * 6,
        "refined_cellsize": refined_cellsize,
        "refined_cellsize_override": [[layer, frame_cellsize] for layer in ("Metal1", "Metal3", "Activ", "SUBGND")],
        "cells_per_wavelength": 10, "meshsize_max": 70, "order": order, "conductor_model": conductor_model,
        "adaptive_mesh_iterations": amr_passes, "amr_tol": 1e-3, "amr_max_dof": 4e6, "no_gui": True, "no_preview": True,
    }
    if fpoint is not None:
        settings["fpoint"] = fpoint
    else:
        settings.update(fstart=0.1e9, fstop=COILS[coil]["f_stop"], fstep=0.1e9)

    sim_path = utilities.create_sim_path(HERE, name)
    settings.update(simulation_ports=ports, materials_list=materials_list, dielectrics_list=dielectrics_list,
                    metals_list=metals_list, layernumbers=layers, allpolygons=allpolygons, sim_path=sim_path,
                    model_basename=name)
    simulation_setup.create_palace(ports.all_active_excitations(), settings)
    print("MODEL DONE", name, "margin", margin)


if __name__ == "__main__":
    # study.py <name> <coil> <D> <gap> <0 floating|1 tied|slot|tie_noPEC|plane_M1|plane_M3> [fpoint in Hz, comma separated]
    #          [box_beyond] [refined_cellsize] [frame_cellsize] [amr_passes]
    name, coil, D, gap = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4])
    tie = {"0": False, "1": True}.get(sys.argv[5], sys.argv[5])
    fpoint = [float(f) for f in sys.argv[6].split(",")] if len(sys.argv) > 6 and sys.argv[6] else None
    box_beyond = float(sys.argv[7]) if len(sys.argv) > 7 and sys.argv[7] else None
    refined = float(sys.argv[8]) if len(sys.argv) > 8 and sys.argv[8] else 2.0
    frame_cell = float(sys.argv[9]) if len(sys.argv) > 9 and sys.argv[9] else 5.0
    amr_passes = int(sys.argv[10]) if len(sys.argv) > 10 and sys.argv[10] else 0
    make_model(name, coil, D, gap, tie, fpoint=fpoint, box_beyond=box_beyond, refined_cellsize=refined,
               frame_cellsize=frame_cell, amr_passes=amr_passes)

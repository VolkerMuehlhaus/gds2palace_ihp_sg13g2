# Inductor synthesis for SG13G2 technology with IHP inductor2/3 shapes, EM simulated using gds2palace workflow

# Changes:
# 07-April-2026: New version with built-in geometry code, does not require external pclab library
# This new version is not limited in number of turns
# 13-June-2026: Fixed bug in output name of final model 

# Specify the target frequency, target value and geometry limits in the parameters below.
# Settings for gds2palace FEM simulation are defined in the script below.


import os, math, sys, time, shutil
import subprocess
import gdspy
from gds2palace import *
import skrf as rf
from matplotlib import pyplot as plt


# RUN CONTROLS
start_simulation = True # start solver after creating the model?
cleanup_old_data = True # cleanup existing GDSII and S-parameters when starting a new run?

initial_sweep_FEM_order = 1  # many candicates are simulated here, order=1 is faster but less accurate
finetune_FEM_order = 2  # user oder=2 for accurate results from finetune step

how_many_top_results = 2  # number of best inductors from initial sweep that are evaluated more closely and re-tuned to target
how_many_finetune_steps = 2 # how many iteration of tune-to-target before selecting the final candidate for full frequency sweep

# CREATE INDUCTOR WITH TARGET VALUE
Ltarget = 0.5e-9 # target inductance in H
ftarget = 30e9  # design frequency in Hz
faked_dc = 0.1e9  # do not change, this is the "DC-like" low frequency for data extraction

w_range = [2.01,3,4,6,8,10,12,15] # sweep over these width values 
s_range = [2.01,3,4,6]
nturns_range = [2,3]
dout_max = 300 # maximum outer diameter in microns

layout_with_centertap = False # layout with or without center tap

# TECHNOLOGY
XML_filename = "SG13G2_200um.xml"   #  EM simulation stackup data       

materials_list, dielectrics_list, metals_list = stackup_reader.read_substrate (XML_filename)


# ----------------------------------------------------------------

settings = {}

settings['unit']   = 1e-6  # geometry is in microns
settings['margin'] = 50    # distance in microns from GDSII geometry boundary to simulation boundary 

settings['fstart']  = ftarget
settings['fstop']   = ftarget
settings['fstep']   = 1e9
settings['fpoint']  = faked_dc

settings['preprocess_gds'] = True
settings['merge_polygon_size'] = 1.5

settings['refined_cellsize'] = 5  # mesh cell size in conductor region
settings['adaptive_mesh_iterations'] = 0  # Palace adative mesh iterations

settings['cells_per_wavelength'] = 10   # how many mesh cells per wavelength, must be 10 or more
settings['meshsize_max'] = 70  # microns, override cells_per_wavelength 

settings['no_gui'] = True  # create files without showing 3D model
settings['no_preview'] = True
settings['order'] = initial_sweep_FEM_order

script_path = utilities.get_script_path(__file__)  # get path for this simulation file

# ==================================== INDUCTOR LAYOUT CODE ============================



# ------ constants ----------
SCALE_FACTOR  = 1  # input parameters are micron, drawing unit is micron

SPIRAL_LAYER_NUM = 134  # TopMetal2 for drawing main inductor turns
CROSSOVER_LAYER_NUM = 126 # TopMetal1 for crossover and feedline
VIA_LAYER_NUM = 133 # TopVia2
LBE_LAYER_NUM = 157 # LBE = localized backside etching
FRAME_LAYER_NUM = 8 # Metal1 layer for ground frame, used when forEM==True

PURPOSE_DRAWING = 0 
PURPOSE_PIN = 2  # data type for pin shapes on metal layers

EXTRA_LAYER_PURPOSE_PAIRS = [
    (1,23), # Activ.nofill
    (5,23), # Gatpoly nofill
    (8,23), # Metal1.nofill
    (10,23), # Metal2.nofill
    (30,23), # Metal3.nofill
    (50,23), # Metal4.nofill
    (67,23), # Metal5.nofill
    (126,23), # TopMetal1.nofill
    (134,23), # TopMetal2.nofill
    (46,21), # Pwell.block
    (148,0), # NoRCX.drawing
    (27,0)  # IND.drawing
]

IND_PIN = (27,2)    # layer and purpose used for inductor pins in SG13G2 OPDK
IND_TEXT = (27,25)  # layer and purpose used for inductor pin labels in SG13G2 OPDK

TEXT_DRAWING = (63,0)  # layer to show additional text information

VIA_SIZE = 0.9          # IHP TopVia2 rule TV2.a
VIA_GAP = 1.06          # IHP TopVia2 rule TV2.b
VIA_MARGIN = 0.5        # IHP TopVia2 rule TV2.c, TV2.d

DELTA = 0.1             # size of EM port perpendicular to width

MU0 = 4*math.pi*1e-7

# --- utility functions ---

def gridsnap(x):
    grid = 0.01   # grid in micron
    return round(x/grid)*grid
    
def is_even(x):
    return x % 2 == 0

# --- GDSII drawing functions ---

def add_path (all_geometries_list, layer, purpose, points, width):
    p = gdspy.FlexPath(points, width, corners='miter',ends='flush', layer=layer, datatype=purpose)
    all_geometries_list.append(p)
    return p

def add_box (all_geometries_list, layer, purpose, p1, p2):
    b = gdspy.Rectangle(p1, p2, layer=layer, datatype=purpose)
    all_geometries_list.append(b)
    return b

def add_poly (all_geometries_list, layer, purpose, points):
    p = gdspy.Polygon(points, layer=layer, datatype=purpose)
    all_geometries_list.append(p)
    return p

def add_via (all_geometries_list, layer, purpose, p1, p2, forEM):
    # if forEM:
    #     add_box (all_geometries_list, layer, purpose, p1, p2)
    # else:
        draw_via_array (all_geometries_list, layer, purpose, p1, p2)

def draw_via_array (all_geometries_list, layer, purpose, p1, p2):
    # draw a via array with all detail
    x1 = min(p1[0],p2[0])
    x2 = max(p1[0],p2[0])
    y1 = min(p1[1],p2[1])
    y2 = max(p1[1],p2[1])

    # maximum net size available for vias
    max_size_x = gridsnap((x2-x1) - 2*VIA_MARGIN)
    num_vias_x = 1 + math.floor((max_size_x - VIA_SIZE)/(VIA_SIZE + VIA_GAP))
    effective_margin_x = gridsnap(((x2-x1) - VIA_SIZE - (num_vias_x-1)*(VIA_SIZE + VIA_GAP))/2)

    max_size_y = gridsnap((y2-y1) - 2*VIA_MARGIN)
    num_vias_y = 1 + int( (max_size_y - VIA_SIZE)/(VIA_SIZE + VIA_GAP))
    effective_margin_y = gridsnap(((y2-y1) - VIA_SIZE - (num_vias_y-1)*(VIA_SIZE + VIA_GAP))/2)

    x = gridsnap(x1 + effective_margin_x)
    for n in range (1, num_vias_x+1): 
        y = gridsnap(y1 + effective_margin_y)
        for m in range (1, num_vias_y+1):
            add_box (all_geometries_list, layer, purpose, (x,y), (x+VIA_SIZE, y+VIA_SIZE))
            y = gridsnap(y + VIA_SIZE + VIA_GAP)
        x = gridsnap(x + VIA_SIZE + VIA_GAP)


# ========================
#   Inductor calculations
# ========================

def get_min_outer_diameter (N,w,s):

    crossover_size = 3*w + 2*s

    # make sure we don't create a single via 
    size_for_two_vias =  2*VIA_SIZE + VIA_GAP + 2*VIA_MARGIN
    overlap_size = w
    if w < size_for_two_vias:
        overlap_size = 1.1*size_for_two_vias

    min_crossover_size = (2*s+w)*(math.sqrt(2)-1) + (s+w) +  2*overlap_size

    if crossover_size < min_crossover_size:
        crossover_size = min_crossover_size

    if N < 3:   
        inner_segment_size = crossover_size
    else:    
        
        feedline_spacing = crossover_size + w + 2 * s
        inner_segment_size = feedline_spacing



    if N>1:
        Di_min = inner_segment_size * (1 + math.sqrt(2))
    else:
        Di_min = 2*(w + s) *(1 + math.sqrt(2))  # for single turn inductor     

    Do_min = (Di_min + 2*N*w + 2*(N-1)*s)
    # round to 2 decimal digits
    Do_min = math.ceil(100*Do_min)/100
    return Do_min




def calculate_octa_diameter (N, w, s, Ltarget, K1=2.15522, K2=3.61868, L0=0):
    # Calculate diameter for given target inductance

    # Calculation uses Wheeler's equation, based on N,w,s and target L
    # This calculation is for DC, no high frequency effects
    # Valid for normal spiral and overlay transformer

    # input data is required in MKS units

    # K1, K2 vary by shape and can also vary by technology (metal layer thickness etc.)
    # L0 is an offset that accounts for feedline inductance, on top of the "core" inductor shape

    # calculation must be done in MKS units
    um = 1E-6

    Lsyn = Ltarget - L0
    b = 2*N*w*um + 2*(N-1)*s*um # difference between outer and inner diameter
    c = K1*MU0*N*N 	      # constant in Wheeler's equation

    p = -(b + Lsyn/c)
    q = b*b/4 - Lsyn*b*(K2-1)/(2*c)
    Dout = (-p/2 + math.sqrt(p*p/4-q))/um # output is in micron
    Dout = math.ceil(Dout*100)/100
    return Dout

# ====================
#   Inductor layout
# ====================

def symmetric_octa_IHP(N, D, w, s, includeCenterTap=False, LBE=False, forEM=False, filename="inductor.gds", textlabel=""):
    # Drawing unit and parameter unit is micron

    # GDSII setup
    lib = gdspy.GdsLibrary()

    if includeCenterTap:
        cellname = f'inductor3_N{N}_Do{D}_w{w}_s{s}'
    else:
        cellname = f'inductor2_N{N}_Do{D}_w{w}_s{s}'    


    try:
        cell =lib.new_cell(cellname, overwrite_duplicate=True)
    except:
        cell =lib.new_cell('final_'+cellname, overwrite_duplicate=True)


    # list with all goemtries that we created
    all_geometries_list = []


    # Convert to user units
    D = 2*gridsnap(D/2 * SCALE_FACTOR)
    w = 2*gridsnap(w/2 * SCALE_FACTOR)
    s = 2*gridsnap(s/2 * SCALE_FACTOR)

    # Reference center
    x0 = 0
    y0 = 0

    # --- Geometry calculations ---
    via_size = w
    crossover_size = (2 * s + w) * (math.sqrt(2) - 1) + (s + w)
    crossover_size = gridsnap(2 * via_size + crossover_size)

    # Feedline spacing
    if N < 3:
        feedline_spacing = w + s
        if N == 2 and includeCenterTap:
            feedline_spacing = 2 * (w + s)
    else:
        feedline_spacing = crossover_size + w + 2 * s

    # Inner diameter
    Di = gridsnap(D - 2 * N * w - 2 * (N - 1) * s)

    # Feed length
    feed_length = 30



    # --- Feedline drawing  ---
    if N == 1:
        # for single turn, we draw everything on single layer TopMetal2
        feed_layer = SPIRAL_LAYER_NUM
    else:
        # for multi turn, we draw trace on TopMetal2 and feedline on TopMetal1
        feed_layer = CROSSOVER_LAYER_NUM

    add_box (all_geometries_list, layer=feed_layer, purpose=PURPOSE_DRAWING, 
                        p1=(x0-w/2-feedline_spacing/2, y0-Di/2),
                        p2=(x0+w/2-feedline_spacing/2, y0-D/2-feed_length)
                        )
    
    add_box (all_geometries_list, layer=feed_layer, purpose=PURPOSE_DRAWING, 
                        p1=(x0-w/2+feedline_spacing/2, y0-Di/2),
                        p2=(x0+w/2+feedline_spacing/2, y0-D/2-feed_length)
                        )

 
    if N > 1:
        # for all N except single turn, we need via from TopMetal1 feedline to TopMetal2 trace

        add_via (all_geometries_list, layer=VIA_LAYER_NUM, purpose=PURPOSE_DRAWING, 
                 p1=(x0-w/2-feedline_spacing/2, y0-Di/2),
                 p2=(x0+w/2-feedline_spacing/2, y0-Di/2-w),
                 forEM=forEM)

        add_via (all_geometries_list, layer=VIA_LAYER_NUM, purpose=PURPOSE_DRAWING, 
                 p1=(x0-w/2+feedline_spacing/2, y0-Di/2),
                 p2=(x0+w/2+feedline_spacing/2, y0-Di/2-w),
                 forEM=forEM)


    # create pin label in IHP PDK-style on layer IND.text
    cell.add(gdspy.Label("LA", (x0-feedline_spacing/2, y0-D/2-feed_length+w/4), layer=IND_TEXT[0], texttype=IND_TEXT[1]))
    cell.add(gdspy.Label("LB", (x0+feedline_spacing/2, y0-D/2-feed_length+w/4), layer=IND_TEXT[0], texttype=IND_TEXT[1]))
    
    # create pin shape on the metal layer where that pin is
    add_box (all_geometries_list, layer=feed_layer, purpose=PURPOSE_PIN, 
                            p1=(x0-w/2-feedline_spacing/2, y0-D/2-feed_length+w/2),
                            p2=(x0+w/2-feedline_spacing/2, y0-D/2-feed_length)
                            )   
    add_box (all_geometries_list, layer=feed_layer, purpose=PURPOSE_PIN, 
                            p1=(x0-w/2+feedline_spacing/2, y0-D/2-feed_length+w/2),
                            p2=(x0+w/2+feedline_spacing/2, y0-D/2-feed_length)
                            )   

    if forEM:
        # create ports for gds2palace design flow
        add_box (all_geometries_list, layer=201, purpose=0, 
                                p1=(x0-w/2-feedline_spacing/2, y0-D/2-feed_length+DELTA),
                                p2=(x0+w/2-feedline_spacing/2, y0-D/2-feed_length)
                                )   
        add_box (all_geometries_list, layer=202, purpose=0, 
                                p1=(x0-w/2+feedline_spacing/2, y0-D/2-feed_length+DELTA),
                                p2=(x0+w/2+feedline_spacing/2, y0-D/2-feed_length)
                                )   



    if includeCenterTap:
        if is_even(N):
            cell.add(gdspy.Label("LC", (x0, y0 - D/2 - feed_length + w/4),  layer=IND_TEXT[0], texttype=IND_TEXT[1]))
            add_box (all_geometries_list, layer=SPIRAL_LAYER_NUM, purpose=PURPOSE_PIN, 
                                    p1=(x0-w/2, y0-D/2-feed_length+w/2),
                                    p2=(x0+w/2, y0-D/2-feed_length)
                                    )   
            if forEM:
                add_box (all_geometries_list, layer=203, purpose=0, 
                                        p1=(x0-w/2, y0-D/2-feed_length+DELTA),
                                        p2=(x0+w/2, y0-D/2-feed_length)
                                        )   

        else:
            cell.add(gdspy.Label("LC", (x0, y0 + D/2 + feed_length - w/4),  layer=IND_TEXT[0], texttype=IND_TEXT[1]))
            add_box (all_geometries_list, layer=SPIRAL_LAYER_NUM, purpose=PURPOSE_PIN, 
                                    p1=(x0-w/2, y0+D/2+feed_length-w/2),
                                    p2=(x0+w/2, y0+D/2+feed_length)
                                    )   
            if forEM:
                add_box (all_geometries_list, layer=203, purpose=0, 
                                        p1=(x0-w/2, y0+D/2+feed_length-DELTA),
                                        p2=(x0+w/2, y0+D/2+feed_length)
                                        )   

    
    if textlabel=="":
        # descriptive label with inductor parameters
        textlabel =   f"  number of turns: {N}\n" + \
                    f"  width: {w:.2f}\n" + \
                    f"  spacing: {s:.2f}\n" + \
                    f"  outer diameter: {D:.2f}\n" + \
                    f"  inner diameter: {Di:.2f}\n"
    cell.add(gdspy.Label(textlabel, (x0,y0), layer=TEXT_DRAWING[0], texttype=TEXT_DRAWING[1]))



    # --- Spiral segments ---
    segment_length = (D - w) / (1 + math.sqrt(2))

    for i in range(1, N + 1):

        # left side

        # lower left quadrant
        points =[]
        #  shorter innermost turn at feed side
        if (i==N):
            x1 = gridsnap(x0-feedline_spacing/2+w/2)
        else:    
            x1 = gridsnap(x0-crossover_size/2+w)
        y1 = gridsnap(y0 + (-D/2 + w/2 + (i-1)*(w+s)))
        points.append((x1,y1))
        x1 = x0 - gridsnap(segment_length/2)
        points.append((x1,y1))
        x1 = x1 - gridsnap(segment_length/math.sqrt(2))
        y1 = y1 + gridsnap(segment_length/math.sqrt(2))
        points.append((x1,y1))
        #  half segment and a little bit
        y1 = y1 + gridsnap(segment_length/2+w) 
        points.append((x1,y1))
        add_path(all_geometries_list, layer=SPIRAL_LAYER_NUM, purpose=PURPOSE_DRAWING, points=points, width=w)


        # upper left quadrant
        points =[]
        x1 = gridsnap(x0-crossover_size/2+w)
        y1 = gridsnap(y0 + D/2 - w/2 - (i-1)*(w+s))
        points.append((x1,y1))
        x1 = x0 - gridsnap(segment_length/2)
        points.append((x1,y1))
        x1 = x1 - gridsnap(segment_length/math.sqrt(2))
        y1 = y1 - gridsnap(segment_length/math.sqrt(2))
        points.append((x1,y1))
        # half segment and a little bit
        y1 = y1 - gridsnap(segment_length/2+w) 
        points.append((x1,y1))
        add_path(all_geometries_list, layer=SPIRAL_LAYER_NUM, purpose=PURPOSE_DRAWING, points=points, width=w)

        # right side
        # lower right quadrant
        points =[]
        # shorter innermost turn at feed side
        if (i==N):
            x1 = gridsnap(x0+feedline_spacing/2-w/2)
        else:    
            x1 = gridsnap(x0+crossover_size/2-w)
        y1 = gridsnap(y0 + (-D/2 + w/2 + (i-1)*(w+s)))
        points.append((x1,y1))
        x1 = x0 + gridsnap(segment_length/2)
        points.append((x1,y1))
        x1 = x1 + gridsnap(segment_length/math.sqrt(2))
        y1 = y1 + gridsnap(segment_length/math.sqrt(2))
        points.append((x1,y1))
        # half segment and a little bit
        y1 = y1 + gridsnap(segment_length/2 + w)
        points.append((x1,y1))
        add_path(all_geometries_list, layer=SPIRAL_LAYER_NUM, purpose=PURPOSE_DRAWING, points=points, width=w)

        # upper right quadrant
        points =[]
        x1 = gridsnap(x0+crossover_size/2-w)
        y1 = gridsnap(y0 + D/2 - w/2 - (i-1)*(w+s))
        points.append((x1,y1))
        x1 = x0 + gridsnap(segment_length/2)
        points.append((x1,y1))
        x1 = x1 + gridsnap(segment_length/math.sqrt(2))
        y1 = y1 - gridsnap(segment_length/math.sqrt(2))
        points.append((x1,y1))
        # half segment and a little bit
        y1 = y1 - gridsnap(segment_length/2+w)
        points.append((x1,y1))
        add_path(all_geometries_list, layer=SPIRAL_LAYER_NUM, purpose=PURPOSE_DRAWING, points=points, width=w)

        # decrease segment length for next turn
        segment_length = segment_length - 2*(w+s)/(1+math.sqrt(2))
    
    # --- Crossovers ---
    num_top = math.floor((N-1)/2)
    num_bot = num_top
    if is_even(N):
        num_top += 1


    # bottom side
    for i in range(1, num_bot + 1):

        points =[]
        x1 = gridsnap(x0 - crossover_size / 2)
        y1 = gridsnap(y0 - D/2 + 2 * i * (w + s) + 0.5 * w)
        if not is_even(N):
            y1 = y1-w-s
        points.append((x1,y1))    
        x1 = x0 - gridsnap((w+s)/2)
        points.append((x1,y1))    
        x1 = x1 + gridsnap(w+s)
        y1 = y1 - gridsnap(w+s)
        points.append((x1,y1))    
        x1 = gridsnap(x0 + crossover_size/2)
        points.append((x1,y1))    
        add_path(all_geometries_list, layer=SPIRAL_LAYER_NUM, purpose=PURPOSE_DRAWING, points=points, width=w)


        points = []
        x1 = gridsnap(x0 - crossover_size/2 )
        y1 = gridsnap(y0 - D/2 + 2*i*(w+s) - 0.5*w-s)
        if not is_even(N):
            y1 = y1-w-s
        points.append((x1,y1))    
        x1 = x0 - gridsnap((w+s)/2)
        points.append((x1,y1))    
        x1 = x1 + gridsnap(w+s)
        y1 = y1 + gridsnap(w+s)
        points.append((x1,y1))    
        x1 = gridsnap(x0 + crossover_size/2)
        points.append((x1,y1))    
        add_path(all_geometries_list, layer=CROSSOVER_LAYER_NUM, purpose=PURPOSE_DRAWING, points=points, width=w)

        if is_even(N):  # N! not i!
            # add vias also
            add_via (all_geometries_list, layer=VIA_LAYER_NUM, purpose=PURPOSE_DRAWING, 
                     p1=(x0-crossover_size/2,  y0 - D/2 + 2*i*(w+s) -s),
                     p2=(x0-crossover_size/2+via_size, y0 - D/2 + 2*i*(w+s) - w-s),
                     forEM=forEM)
            add_via (all_geometries_list, layer=VIA_LAYER_NUM, purpose=PURPOSE_DRAWING, 
                     p1=(x0+crossover_size/2,  y0 - D/2 + (2*i+1)*(w+s) -s),
                     p2=(x0+crossover_size/2-via_size, y0 - D/2 + (2*i+1)*(w+s) - w-s),
                     forEM=forEM)
        else:
            # add vias also
            add_via (all_geometries_list, layer=VIA_LAYER_NUM, purpose=PURPOSE_DRAWING, 
                     p1=(x0-crossover_size/2,  y0 - D/2 -w-s + (2*i-1)*(w+s)),
                     p2=(x0-crossover_size/2+via_size, y0 - D/2 + (2*i-1)*(w+s) -s),
                     forEM=forEM)
            add_via (all_geometries_list, layer=VIA_LAYER_NUM, purpose=PURPOSE_DRAWING, 
                     p1=(x0+crossover_size/2,  y0 - D/2 -w-s + (2*i)*(w+s)),
                     p2=(x0+crossover_size/2-via_size,   y0 - D/2 + (2*i)*(w+s) -s),
                     forEM=forEM)


   # top side
    for i in range(1, num_top + 1):

        points =[]
        x1 = gridsnap(x0 - crossover_size/2)
        y1 = gridsnap(y0 + D/2 - (2*i-1)*(w+s) - 0.5*w)
        if not is_even(N):
            y1 = y1-w-s
        points.append((x1,y1))    
        x1 = x0 - gridsnap((w+s)/2);
        points.append((x1,y1))    
        x1 = x1 + gridsnap(w+s);
        y1 = y1 + gridsnap(w+s);
        points.append((x1,y1))    
        x1 = gridsnap(x0 + crossover_size/2);
        points.append((x1,y1))    
        add_path(all_geometries_list, layer=SPIRAL_LAYER_NUM, purpose=PURPOSE_DRAWING, points=points, width=w)


        points =[]
        x1 = gridsnap(x0 - crossover_size/2)
        y1 = gridsnap(y0 + D/2 - (2*i-1)*(w+s) + 0.5*w+s)
        if not is_even(N):
            y1 = y1-w-s
        points.append((x1,y1))    
        x1 = x0 - gridsnap((w+s)/2)
        points.append((x1,y1))    
        x1 = x1 + gridsnap(w+s)
        y1 = y1 - gridsnap(w+s)
        points.append((x1,y1))    
        x1 = gridsnap(x0 + crossover_size/2)
        points.append((x1,y1))    
        add_path(all_geometries_list, layer=CROSSOVER_LAYER_NUM, purpose=PURPOSE_DRAWING, points=points, width=w)

        if (is_even(N)):  # N! not i!
            # add via also
            add_via (all_geometries_list, layer=VIA_LAYER_NUM, purpose=PURPOSE_DRAWING, 
                     p1=(x0-crossover_size/2, y0 + D/2 - (2*i-1)*(w+s) + w+s),
                     p2=(x0-crossover_size/2+via_size, y0 + D/2 - (2*i-1)*(w+s) + s),
                     forEM=forEM)
            add_via (all_geometries_list, layer=VIA_LAYER_NUM, purpose=PURPOSE_DRAWING,
                     p1=(x0+crossover_size/2, y0 + D/2 - (2*i)*(w+s) + w+s),
                     p2=(x0+crossover_size/2-via_size,y0 + D/2 - (2*i)*(w+s) + s),
                     forEM=forEM)

        else:
            # add via also
            add_via (all_geometries_list, layer=VIA_LAYER_NUM, purpose=PURPOSE_DRAWING, 
                     p1=(x0-crossover_size/2, y0 + D/2 -w-s - (2*i-1)*(w+s) + w+s),
                     p2=(x0-crossover_size/2+via_size, y0 + D/2 -w-s - (2*i-1)*(w+s) + s),
                     forEM=forEM)
            add_via (all_geometries_list, layer=VIA_LAYER_NUM, purpose=PURPOSE_DRAWING, 
                     p1=(x0+crossover_size/2, y0 + D/2 -w-s - (2*i)*(w+s) + w+s),
                     p2=(x0+crossover_size/2-via_size,y0 + D/2 -w-s - (2*i)*(w+s) + s),
                     forEM=forEM)


    # one straight segment at outer turn
    if is_even(N):
        # even number of turns, N=2,4,6,..
        points =[]
        points.append((x0-crossover_size/2, y0 -D/2 +w/2))
        points.append((x0+crossover_size/2, y0 -D/2 +w/2))
        add_path(all_geometries_list, layer=SPIRAL_LAYER_NUM, purpose=PURPOSE_DRAWING, points=points, width=w)
    else:
        # odd number of turns, N=1,3,5,..
        points =[]
        if N>1:
            points.append((x0-crossover_size/2, y0 + D/2 -w/2))
            points.append((x0+crossover_size/2, y0 + D/2 -w/2))
        else:
            # we can go to small diameters, so we must keep this short
            points.append((x0-(w+s), y0 + D/2 -w/2))
            points.append((x0+(w+s), y0 + D/2 -w/2))
        add_path(all_geometries_list, layer=SPIRAL_LAYER_NUM, purpose=PURPOSE_DRAWING, points=points, width=w)



    # --- Center tap ---
    if includeCenterTap:
        if is_even(N):
            add_box (all_geometries_list, layer=SPIRAL_LAYER_NUM, purpose=PURPOSE_DRAWING, 
                        p1=(x0 - w/2, y0 - D/2 + w),
                        p2=(x0 + w/2, y0 - D/2 - feed_length))
        else:
            add_box (all_geometries_list, layer=SPIRAL_LAYER_NUM, purpose=PURPOSE_DRAWING,
                        p1=(x0 - w/2, y0 + D/2 - w),
                        p2=(x0 + w/2, y0 + D/2 + feed_length))


    # IHP extra layers for inductors
    D1 = gridsnap(D / 2 + feed_length)
    D2 = gridsnap(D1 / (1 + math.sqrt(2)))
    points =[]
    points.append(( x0 + D2, y0 - D1))
    points.append(( x0 + D1, y0 - D2))
    points.append(( x0 + D1, y0 + D2))
    points.append(( x0 + D2, y0 + D1))
    points.append(( x0 - D2, y0 + D1))
    points.append(( x0 - D1, y0 + D2))
    points.append(( x0 - D1, y0 - D2))
    points.append(( x0 - D2, y0 - D1))

    # iterate over the EXTRA_LAYER_PURPOSE_PAIRS and add an octagon on each of them
    if not forEM:
        for LPP in EXTRA_LAYER_PURPOSE_PAIRS:
            layer, datatype = LPP
            add_poly(all_geometries_list, layer=layer, purpose=datatype, points=points)

    # --- localized backside etching option ---
    if LBE:
        add_poly(all_geometries_list, layerLBE_LAYER_NUM, purpose=PURPOSE_DRAWING, points=points)
       
    
    # --- ground frame for EM simulation using gds2palace -------
    if forEM:
        frame_width = min(20, gridsnap(5*w))
        frame_margin = gridsnap(D/2)

        xmin_frame_inner = gridsnap(x0 - D/2 - frame_margin)
        xmax_frame_inner = gridsnap(x0 + D/2 + frame_margin)
        ymin_frame_inner = gridsnap(y0 - D/2 - frame_margin)
        ymax_frame_inner = gridsnap(y0 + D/2 + frame_margin)

        xmin_frame_outer = xmin_frame_inner - frame_width
        xmax_frame_outer = xmax_frame_inner + frame_width
        ymin_frame_outer = ymin_frame_inner - frame_width
        ymax_frame_outer = ymax_frame_inner + frame_width    

        add_box (all_geometries_list, layer=FRAME_LAYER_NUM, purpose=PURPOSE_DRAWING, 
                p1=(xmin_frame_outer,ymin_frame_outer), 
                p2=(xmin_frame_inner,ymax_frame_outer))
        add_box (all_geometries_list, layer=FRAME_LAYER_NUM, purpose=PURPOSE_DRAWING, 
                p1=(xmax_frame_inner,ymin_frame_outer), 
                p2=(xmax_frame_outer,ymax_frame_outer))
        add_box (all_geometries_list, layer=FRAME_LAYER_NUM, purpose=PURPOSE_DRAWING,
                p1=(xmin_frame_inner,ymin_frame_inner), 
                p2=(xmax_frame_inner, ymin_frame_outer))
        add_box (all_geometries_list, layer=FRAME_LAYER_NUM, purpose=PURPOSE_DRAWING, 
                p1=(xmin_frame_inner,ymax_frame_inner), 
                p2=(xmax_frame_inner, ymax_frame_outer))


        # ground under feedline at pin LA,LB
        add_box (all_geometries_list, layer=FRAME_LAYER_NUM, purpose=PURPOSE_DRAWING, 
                p1=(x0-feedline_spacing/2-w, y0-D/2-feed_length + 2), 
                p2=(x0+feedline_spacing/2+w, ymin_frame_inner))


        if includeCenterTap and not is_even(N):
            # ground under feedline at top side pin LC
            add_box (all_geometries_list, layer=FRAME_LAYER_NUM, purpose=PURPOSE_DRAWING, 
                    p1=(x0-feedline_spacing/2-w, y0+D/2+feed_length - 2),
                    p2=(x0+feedline_spacing/2+w, ymax_frame_inner))


    # add all created shapes to cell now
    for geometry in all_geometries_list:
        cell.add(geometry)

    lib.write_gds(filename)






# ==================================== SIMULATION FLOW CODE ============================

def get_num_ports():
    if layout_with_centertap:
        num_ports = 3
    else:
        num_ports = 2    
    return num_ports    



def create_simulation_model (gds_filename, settings, geometry_name, port_layer_name, ground_layer_name, force2port):
    """Creates a Palace FEM simulation model from GDSII file using gds2palace

    Args:
        gds_filename (string): GDSII input file that also includes port geometries
        settings (dict): settings for gds2palace
        geometry_name (string): name for the Palace model
        port_layer (string): Layer name where upper end of port is connected

    Returns:
        config_name, data_dir: filename of Palace config.json file and output directory
    """

    # ======================== simulation settings ================================

    # create model basename from balun name and settings
    model_basename = geometry_name
    sim_path = utilities.create_sim_path (script_path,model_basename) # set and create directory for simulation output

    simulation_ports = simulation_setup.all_simulation_ports()

    # for EM, we never connect the center tap -> always just connect ports 1 and 2
    portcount = get_num_ports()

    if force2port:
        # in initial sweep, we don't place port at center tap, that is only for final model
        portcount = 2

    for portnumber in range(1,portcount+1):
        port_source_layer = 200+portnumber # port 1 is layer 201
        simulation_ports.add_port(simulation_setup.simulation_port(portnumber=portnumber, 
                                                                voltage=1, 
                                                                port_Z0=50, 
                                                                source_layernum=port_source_layer, 
                                                                from_layername=ground_layer_name,
                                                                to_layername=port_layer_name, 
                                                                direction='z'))

    # ======================== read material stackup and geometry ================================

    # get list of layers from technology
    layernumbers = metals_list.getlayernumbers()
    layernumbers.extend(simulation_ports.portlayers)

    # read geometries from GDSII, only purpose 0
    allpolygons = gds_reader.read_gds(gds_filename, layernumbers, purposelist=[0], metals_list=metals_list, preprocess=settings['preprocess_gds'], merge_polygon_size=settings['merge_polygon_size'])


    ########### create model ###########

    settings['simulation_ports'] = simulation_ports
    settings['materials_list'] = materials_list
    settings['dielectrics_list'] = dielectrics_list
    settings['metals_list'] = metals_list
    settings['layernumbers'] = layernumbers
    settings['allpolygons'] = allpolygons
    settings['sim_path'] = sim_path
    settings['model_basename'] = model_basename


    # list of ports that are excited (set voltage to zero in port excitation to skip an excitation!)
    excite_ports = simulation_ports.all_active_excitations()
    config_name, data_dir = simulation_setup.create_palace (excite_ports, settings)

    # add palace config to list, we will simulate later in one action
    return config_name, data_dir

# -----------------------------------------------------------------

def run_models_from_list (script_path, config_files_list):
    """Create and run batch file that simulates all Plaace models from the given list

    Args:
        script_path (string): Target directory where to store batch script
        config_files_list (list of strings): list with filepath of Palace config.json for models to be simulated
    """
    # Create ONE script file in script_path to simulate ALL models
    # This is to avoid asynchronous finish of simulation jobs
    simulate_script_filename = os.path.join(script_path, 'simulate_all')
    output_file = open(simulate_script_filename, "w") 
    output_file.write('#!/bin/bash\n')
    output_file.write('START_DIR="$PWD"\n')
    for config_name in config_files_list:
        path, basename = os.path.split(config_name)
        output_file.write(f'cd {path}\n')
        output_file.write(f'run_palace {basename}\n')
    output_file.write('cd "$START_DIR"\n')
    # next step is to create Touchstone data
    output_file.write('combine_snp\n')
    # move *.snp to directory where Python model is 
    output_file.write(r'find . -type f -name "*.s*p" -exec cp {} . \;' + '\n')
    output_file.close() 

    if sys.platform.startswith("linux"):
        os.chmod(simulate_script_filename, 0o755)        
        if start_simulation:
            subprocess.run(simulate_script_filename, shell=True)


# -----------------------------------------------------------------


def create_gds_and_model (nturns, w, s, d_outer, layout_with_centertap, force2port):
    """Create GDSII file and Palace model from given parameters

    Args:
        nturns (integer): number of turns
        w (float): width in micron
        s (float): spacing in micron
        d_outer (float): outer diameter in micron
        layout_with_centertap (Boolean): Centertap True/False
        remove_centertap_for_EM (Boolean): If True, no EM port is created for a center tap 

    Returns:
        If layout is possible: config_name, data_dir, port_dict, geometry_name, do_min: Palace config file, Palace output dir, port dict, model name, minimum possible diameter
        If layout is not possible: None, None, None, None, do_min
    """
    # create layout file, convert to layout file with ports, then run gds2palace to create simulation model

    geometry_name = f"{ind_geom}_N{nturns}_do{d_outer}_w{w}_s{s}"
    gds_filename = geometry_name + '.gds'

    includeCenterTap = layout_with_centertap
    symmetric_octa_IHP(N=nturns, D=d_outer, w=s, s=s, includeCenterTap=includeCenterTap, LBE=False, forEM=True, filename=gds_filename)
    print(f"Created output file {gds_filename}")

    # create Palace model and add to list of models, but don't start simulation immediately
    if nturns == 1:
        port_layer_name = metals_list.getbylayernumber(SPIRAL_LAYER_NUM).name
    else:    
        port_layer_name = metals_list.getbylayernumber(CROSSOVER_LAYER_NUM).name
    ground_layer_name = metals_list.getbylayernumber(FRAME_LAYER_NUM).name

    config_name, data_dir = create_simulation_model (gds_filename, settings, geometry_name, port_layer_name, ground_layer_name, force2port)
    return config_name, data_dir, geometry_name



def create_models_from_list (geometry_candidates_list, layout_with_centertap, force2port):
    """Create GDSII files and Palace models from a list of geometry parameters

    Args:
        geometry_candidates_list (list): List of geometry parameters
        layout_with_centertap (Boolean): Inductor layout has centertap

    Returns:
        palace_config_files, all_models_dict, data_dir
    """
    # create GDSII and Palace model from list of geometry candidates

    palace_config_files = []  # the created config.json with full path
    all_models_dict = {} # name and data of models, used so that we can find "our" results later
    data_dir = None

    for geometry in geometry_candidates_list:
        nturns = geometry['nturns']
        w = geometry['w']
        s = geometry['s']
        d_outer = geometry['d_outer']

        config_name, a_data_dir, geometry_name = create_gds_and_model (nturns, w, s, d_outer, layout_with_centertap, force2port)
        if config_name is not None:
            palace_config_files.append(config_name)  
            model_data_dict = {'nturns':nturns, 'w':w, 's':s, 'd_outer':d_outer} 
            all_models_dict[geometry_name] = model_data_dict
            data_dir = a_data_dir

    return palace_config_files, all_models_dict, data_dir


def get_best_results (palace_config_files, requested_result_count, all_models_dict, rescale_diameter=True):
    """after simulation, read results and calculate new rescaled diameter for next iteration
    then, sort results by Q factor and return the requested_result_count best geometries

    Args:
        palace_config_files (list): list of Palace config.json files
        requested_result_count (Integer): How many toop results are returned
        all_models_dict (dict): geometry parameters for inductors from list
        rescale_diameter (bool, optional): Re-calculate outer diameter for next iteration? Defaults to True.

    Returns:
        _type_: _description_
    """
    # after simulation, read results and calculate new rescaled diameter for next iteration
    # then, sort results by Q factor and return the requested_result_count best geometries

    num_ports = get_num_ports() # we need port count to set correct Touchstone suffix
    expected_snp_results = []
    for model_name in all_models_dict.keys():
        snp_name = f"{model_name}.s2p"  # for running these sweeps, we always do 2-port simulation, possible center tap is floating
        # only append files that actually exist
        if os.path.isfile(snp_name):
            expected_snp_results.append(snp_name)

    # now read all these files
    networks = []
    for snp_file in expected_snp_results:
        network = rf.Network(snp_file)
        networks.append(network)

    results_dict = {}
    

    for network in networks:
        nturns = all_models_dict[network.name]['nturns']
        w = all_models_dict[network.name]['w']
        s = all_models_dict[network.name]['s']
        d_outer = all_models_dict[network.name]['d_outer']

        freq, Rdiff, Ldiff, Qdiff = get_diff_model(network)
        # get data at target frequency
        ftarget_index = rf.util.find_nearest_index(freq, ftarget)
        L_at_ftarget = Ldiff[ftarget_index]
        Q_at_ftarget = Qdiff[ftarget_index]

        # get data at faked DC point
        DC_index = rf.util.find_nearest_index(freq, faked_dc)
        L_at_DC = Ldiff[DC_index]
        # calculate tweaked new diameter to reach target value
        resize_factor = calc_resize_factor (Ltarget, L_at_ftarget, L_at_DC)
        d_outer_new = math.ceil(d_outer*resize_factor*100)/100  # 2 decimal digits only

        if rescale_diameter:
            d_outer = d_outer_new

        # add to dictionary of results, not sorted at this moment
        results_dict[Q_at_ftarget] = {'nturns':nturns,'w':w,'s':s,'d_outer':d_outer}
        # write to log
        log.append(f"  {network.name}: L={L_at_ftarget*1e9:.2f}nH Q={Q_at_ftarget:.1f}, parameters N={nturns} w={w} s={s} do={d_outer} -> {d_outer_new}")

    # sort results by Q factor, get best 
    sorted_results = dict(sorted(results_dict.items(), key=lambda item: int(item[0]), reverse=True))

    # write to top list
    geometries =[]
    for geometry in sorted_results.values():
            geometries.append(geometry)
    if requested_result_count > len(geometries):        
        best_list = geometries[:requested_result_count] 
    else:
        best_list = geometries            
    return best_list
    

# -----------------------------------------------------------------

# function to get differential Zin from 1,2 or 3-port data (port 3 = center tap)

def get_diff_model (sub):
    """Get differential inductor parameters from 2-port data

    Args:
        sub (network): network to evaluate

    Returns:
        freq, Rdiff, Ldiff, Qdiff
    """

    if sub.number_of_ports == 1:
        Zdiff=sub.z[0::,0,0]
    elif sub.number_of_ports == 2:
        z11=sub.z[0::,0,0]
        z21=sub.z[0::,1,0]
        z12=sub.z[0::,0,1]
        z22=sub.z[0::,1,1]
        Zdiff = z11-z12-z21+z22
    elif sub.number_of_ports == 3:
        y11=sub.y[0::,0,0]
        y21=sub.y[0::,1,0]
        y12=sub.y[0::,0,1]
        y22=sub.y[0::,1,1]
        Zdiff = (y11+y12+y21+y22)/(y11*y22-y12*y21)
    else:
        print('S-parameter files with ', sub.number_of_ports, ' ports not supported')
        exit(1)    
    
    freq = sub.frequency.f
    omega = freq*2*math.pi
    Ldiff = Zdiff.imag/omega
    Rdiff = Zdiff.real
    Qdiff = Zdiff.imag/Zdiff.real
    
    return freq, Rdiff, Ldiff, Qdiff


def calc_resize_factor (L_target, L_is_ftarget, L_is_DC):
    """finetune step: rescale diameter after initial simulation that was based on predicted DC inductance
    make sure L_is_ftarget is positive, it might be negative if we are above SRF -> drop this geometry

    Args:
        L_target (float): target inductance that we want to reach
        L_is_ftarget (float): simulated inductance at target frequency
        L_is_DC (float): simulated inductance at DC-like low frequency

    Returns:
        float: scaling factor for diameter resize 
    """
    # finetune step: rescale diameter after initial simulation that was based on predicted DC inductance
    # make sure L_is_ftarget is positive, it might be negative if we are above SRF -> drop this geometry
    if L_is_ftarget>0:
        factor = math.pow(L_target/L_is_ftarget, 0.5)
    else:
        factor = 1000 # will result in dropping geometry    

    return factor

# -----------------------------------------------------------------
#    MAIN
# -----------------------------------------------------------------

# CLEANUP OLD DATA BEFORE WE CREATE NEW INDUCTOR

if cleanup_old_data:
    # cleanup old models
    if sys.platform.startswith("linux"):
        os.system('rm -rf palace_model')
        os.system('rm -f *.s?p *.gds')

time.sleep(1)

if layout_with_centertap:
    ind_geom = "inductor3"
else:    
    ind_geom = "inductor2"


global log
log = []
log.append(f'Design goal: {ind_geom} L={Ltarget*1e9} nH @ {ftarget/1e9} GHz ')


# CREATE MODELS FOR INITIAL SWEEP ACROSS ALL CANDIDATES

geometry_candidates_list = []
for nturns in nturns_range:  # number of turns
    for w in w_range:  # trace width
        
        # for special case N=1, we don't need to sweep over multiple spacing values
        if nturns>1:
            s_sweep = s_range
        else:
            s_sweep = [0]
                
        for s in s_sweep:  # spacing between turns
            # calculate diameter from target inductance
            d_outer = calculate_octa_diameter (nturns, w, s, Ltarget)  # technology specific
            # calculate minimum possible diameter without breaking layout
            do_min = get_min_outer_diameter (nturns, w, s)

            # leave some reserve to shrink diameter, check against maximim diameter limit
            if (d_outer >= 1.1 * do_min) and (d_outer <= dout_max):            
                model_data_dict = {'nturns':nturns, 'w':w, 's':s, 'd_outer':d_outer} 
                geometry_candidates_list.append(model_data_dict)


# create GDSII and Palace model from list of geometry candidates
# If we have a centertap, draw that but don't simulate port 3 there for this initial sweep
palace_config_files, all_models_dict, data_dir = create_models_from_list (geometry_candidates_list, layout_with_centertap, force2port=True)

# Give some feedback to user on the number of geometry candidates
wait_time_seconds = 10
print(f'\n\nThere are {len(geometry_candidates_list)} geometries that meet your specified parameters.\n')
print(f'Simulation will start in {wait_time_seconds} seconds.')
print(f'You can press Ctrl+C now to quit and review your specification, or wait for simulation starting in {wait_time_seconds} seconds.')
time.sleep(wait_time_seconds)

# Run all simulation models for initial sweep over parameter range
# Start measuring EM simulation 
start = time.perf_counter()
run_models_from_list (script_path, palace_config_files)
# evaluate simulation time
end = time.perf_counter()
log.append (f"INITIAL RESULTS (simulation time  {end - start:.1f} seconds):")

if len(palace_config_files) > 0:

    settings['order'] = finetune_FEM_order # switch to higher accuracy

    # get best results from initial sweep over all candidates
    best_list = get_best_results (palace_config_files, how_many_top_results, all_models_dict)
 
    finetune_list = []
    for n in range(how_many_top_results):
      if len(best_list)>n:
        finetune_list.append(best_list[n]) 

    # now do finetune steps over the best candidates, that list is sorted by Q factor, top down
    for repeat in range(how_many_finetune_steps):
        palace_config_files, all_models_dict, data_dir = create_models_from_list (finetune_list, layout_with_centertap, force2port=True)
        if len(palace_config_files)>0:
            start = time.perf_counter()
            run_models_from_list (script_path, palace_config_files)
            end = time.perf_counter()
            log.append(f'Finetune step {repeat+1} results sorted by Q factor (simulation time  {end - start:.1f} seconds):')
            finetune_list = get_best_results (palace_config_files, how_many_top_results, all_models_dict)

    # Now we have done multiple finetune steps for multiple candidates, get the best one
    print('Now we have done multiple finetune steps for multiple candidates, get the best one')

    settings['fstart']  = 0
    settings['fstop']   = 2*ftarget
    settings['fstep']   = ftarget/40
    settings['fpoint']  = [ftarget]

    if len(finetune_list)>0:

        geometry_data = [finetune_list[0]]
        # now run wideband sweep on final result
        log.append(f'Running final wideband sweep for {geometry_data}')

        # Create final model
        force_2port_for_final_model = False 
        palace_config_files, all_models_dict, data_dir = create_models_from_list (geometry_data, layout_with_centertap, force2port=force_2port_for_final_model)
        start = time.perf_counter()
        run_models_from_list (script_path, palace_config_files)
        end = time.perf_counter()
        
        nturns = geometry_data[0]['nturns']
        w = geometry_data[0]['w']
        s = geometry_data[0]['s']
        d_outer = geometry_data[0]['d_outer']
        
        # Use same name here as defined when creating GDSII files!
        if layout_with_centertap:
            geometry_name = f'inductor3_N{nturns}_do{d_outer}_w{w}_s{s}'
        else:
            geometry_name = f'inductor2_N{nturns}_do{d_outer}_w{w}_s{s}'  

        log.append(f'Finished running wideband sweep for {geometry_name} (simulation time  {end - start:.1f} seconds)\n')

        # evaluate results again, because we might have used other simulation settings now
        if palace_config_files != []:
            num_ports = get_num_ports()
            snp_file = f"{geometry_name}.s{num_ports}p"
            network = rf.Network(snp_file)
            freq, Rdiff, Ldiff, Qdiff = get_diff_model(network)
            # get data at target frequency
            ftarget_index = rf.util.find_nearest_index(freq, ftarget)
            L_at_ftarget = Ldiff[ftarget_index]
            Q_at_ftarget = Qdiff[ftarget_index]

            # summary of inductor data
            summary = f"L={L_at_ftarget*1e9:.2f}nH Q={Q_at_ftarget:.1f} at {ftarget/1e9} GHz\n" + \
            f"  number of turns: {nturns}\n" + \
            f"  width: {w:.2f}\n" + \
            f"  spacing: {s:.2f}\n" + \
            f"  outer diameter: {d_outer:.2f}\n" + \
            f"  inner diameter: {d_outer-2*(nturns*w+(nturns-1)*s):.2f}\n"

            log.append(f"FINAL RESULT:\n  {network.name}: {summary}")
            
            # Finalize GDSII with IHP SG13G2 layout features and save with prefix "final", so that we can identify the result more easily
            gds_filename = geometry_name + '.gds'
            final_gds_filename = 'final_' + gds_filename

            symmetric_octa_IHP(N=nturns, D=d_outer, w=w, s=s, includeCenterTap=layout_with_centertap, LBE=False, forEM=False, filename=final_gds_filename, textlabel=summary)
            log.append(f"Final GDSII file with SG13G2 OPDK options created as {final_gds_filename}")

            final_snp_filename = 'final_' + snp_file
            shutil.copy(snp_file, final_snp_filename)
            log.append(f"S-parameter file copied to {final_snp_filename}")


            print('===============================================================================')
            for line in log:
                print(line)      

            # Do the plotting for differential parameters
            fig, axes = plt.subplots(1, 2, figsize=(12,6))  # NxN grid
            fig.suptitle("Differential Inductor Parameters")        

            # Inductance
            ax = axes[0]
            ax.set_ylim (0, 2*L_at_ftarget*1e9)
            ax.plot(freq / 1e9, Ldiff*1e9, label=network.name)
            ax.plot(ftarget/1e9, L_at_ftarget*1e9, 'ro', label = f"L={L_at_ftarget*1e9:.2f}nH @ {ftarget/1e9} GHz")
            ax.set_xlabel("Frequency (GHz)")
            ax.set_ylabel("Diff. Inductance (nH)")
            ax.set_xmargin(0)
            ax.legend(loc='lower left')
            ax.grid()

            # Q factor
            ax = axes[1]
            ax.set_ylim (0, 1.2*Q_at_ftarget)
            ax.plot(freq/1e9, Qdiff,label=network.name)
            ax.plot(ftarget/1e9, Q_at_ftarget,'ro', label = f"Q={Q_at_ftarget:.1f} @ {ftarget/1e9} GHz")
            ax.set_xlabel("Frequency (GHz)")
            ax.set_ylabel("Diff. Q factor")
            ax.set_xmargin(0)
            ax.legend(loc='lower left')
            ax.grid()

            plt.tight_layout()
            plt.show()

        else:
            log.append(f"FINAL RESULT:\n  Could not find geometries that match requirements (check number of turns)")        
            
            print('===============================================================================')
            for line in log:
                print(line)                         

    else:
        log.append("NO DATA: No results from initial sweep, no candidates for fine tune step, abort. One reason can be that simulation did not run.")        
  
        
        print('===============================================================================')
        for line in log:
            print(line)                        


else:
    # no results at all
    print('There are no inductor geometries that match your target value and parameter range!')
    exit(1)

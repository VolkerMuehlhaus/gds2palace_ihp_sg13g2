########################################################################
#
# Copyright 2025 Volker Muehlhaus and IHP PDK Authors
#
# Licensed under the GNU General Public License, Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    https://www.gnu.org/licenses/gpl-3.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
########################################################################

# Extract objects on *all* IHP SG13G2 layers in GDSII file
# Find polygons with holes (cutouts) that are used to increase density, replace by bounding box
# Find circles and replace by octagon

# Usage: gds_simplify <input.gds> 


# File history: 
# Initial version 29 June 2025 Volker Muehlhaus 
# Circle detection 01 Dec 2025 Volker Muehlhaus

import gdspy
from pathlib import Path
import sys
import math
import numpy as np
from collections import Counter


# ==================== settings =========================


# ============= technology specific stuff ===============

# list of layers to evaluate, we only check  metal layers

metal_layers_list = [
  1,
  8,
  9,
  10,
  30,
  41, 
  50,
  67,
  126,
  134,
  6,
  19,
  29,
  49,
  66,
  129,
  125,
  133
]


# list of purpose to evaluate
required_purpose_list = [
  0,  # drawing
  35, # pillar
  70  # copper
]

# list of layers to delete, to reduce file size
delete_layers_list = [
  148,
  160
]

# list of purpose to delete, with no replacement
delete_purpose_list = [
  22,
  23,
  29,
  2 # pin
]



# ============= utilities ==========

def float2string (value):
  return "{:.3f}".format(value)    # fixed 3 decimal digits



def is_circle_like(points, radius_variation_threshold=0.2, min_points=12):
    """
    Detects whether a polygon is circle-like using:
    - Enough points
    - Uniform radii from centroid
    """
    pts = np.asarray(points)

    # Must have enough vertices
    if len(pts) < min_points:
        return False

    # Compute centroid
    center = pts.mean(axis=0)
    
    # Compute radii
    radii = np.linalg.norm(pts - center, axis=1)

    # Radii uniformity (coefficient of variation)
    cv = radii.std() / radii.mean()

    if cv < radius_variation_threshold:
      # Compute distances between consecutive points
      edge_lengths = np.sqrt(np.sum(np.diff(np.vstack([pts, pts[0]]), axis=0)**2, axis=1))
      avg_edge = np.average(edge_lengths)
      max_edge = np.max(edge_lengths)    
      # print(f'edgelength avg {avg_edge} max {max_edge} factor {max_edge/avg_edge}')
      # Check if any edge length differs by more than factor 2
      if (max_edge > 10 * avg_edge) or max_edge > 100:
          return False    

    return cv < radius_variation_threshold



def simplify_round_polygon_to_octagon(points):
    pts = np.asarray(points)

    # --- 1. Estimate circle center ---
    center = pts.mean(axis=0)

    # --- 2. Estimate radius ---
    radii = np.linalg.norm(pts - center, axis=1)
    radius = radii.mean()

    # --- 3. Fixed angles (rotated by 22.5°) ---
    angles = np.deg2rad(np.arange(0, 360, 45) + 22.5)  # 0,45,90,.. +22.5

    # --- 4. Generate octagon points ---
    octagon = np.column_stack([
        center[0] + radius * np.cos(angles),
        center[1] + radius * np.sin(angles)
    ])

    return octagon


# ============= main ===============

if len(sys.argv) >= 2:
  input_name = sys.argv[1]
  
  print ("Input file: ", input_name)
  # get basename of input file, append suffix to identify output polygons
  # output_name = Path(input_name).stem + "_forEM.gds"
  output_name = input_name.replace(".gds","_forEM.gds")
    
  # Read GDSII library
  output_library = gdspy.GdsLibrary(infile=input_name)
  
  # iterate over cells
  for cell in output_library:
    print('cellname = ' + str(cell.name))
  
    # iterate over polygons
    for n,poly in enumerate(cell.polygons):
      # points of this polygon
      polypoints = poly.polygons[0]

      poly_layer = poly.layers[0]
      poly_purpose = poly.datatypes[0]


      # -------- Check for dummy rectagles with hole inside ---------
      if ((poly_layer in metal_layers_list or poly_layer>200) and (poly_purpose in required_purpose_list)):
        # Polygon of interest, check if we need to process this

        # get number of vertices
        numvertices = len(polypoints)

        # criteria for dummy rectangle with cutout:
        # number of vertices = 10 
        # when sorting vertices by distance to center, we have 4 identcal values for outer distance and 4 identical values for inner distance


        # we are interested in polygons with 10 vertices
        if numvertices == 10:
          # get bounding box
          bb = poly.get_bounding_box()

          xmin = bb[0,0]
          ymin = bb[0,1]
          xmax = bb[1,0]
          ymax = bb[1,1]

          xcenter = (xmax+xmin)/2
          ycenter = (ymax+ymin)/2

          # print('      Bounding box xmin=', xmin, ' ymin=', ymin,' xmax=', xmax, ' ymax=', ymax)

          radius_list = []
          for i_vertex in range(numvertices):
            
            # print('polypoints  = ' + str(polypoints))
            x = polypoints[i_vertex][0]
            y = polypoints[i_vertex][1]

            # calculate distance from center
            r = math.sqrt((x-xcenter)**2 + (y-ycenter)**2)
            radius_list.append(r)

          # get count for radius values
          counter = Counter(radius_list)
          sorted_by_count = sorted(counter.items(), key=lambda x: x[1], reverse=True)
          
          r1,n1 = sorted_by_count[0]   
          r2,n2 = sorted_by_count[1]   

          if n1==4 and n2==4:
            # We can be sure we have a dummy square with cutout.
            print('   Replacing cutout polygon #', str(n), ' layer ', str(poly_layer))      
         
            # invalidate original polygon
            poly.layers=[0]
            # remove original polygon
            cell.remove_polygons(lambda pts, layer, datatype:layer == 0)

            # Replace it with a solid square   
            basepoly_points=[(xmin,ymin),(xmin,ymax),(xmax,ymax),(xmax,ymin),(xmin,ymin)]    
            basepoly = gdspy.Polygon(basepoly_points, layer=poly_layer, datatype=poly_purpose)
            cell.add(basepoly)     

        # now do the check for circle-like structures
        if numvertices > 11:
          if is_circle_like(polypoints):
              new_points = simplify_round_polygon_to_octagon(polypoints)

              # invalidate original polygon
              poly.layers=[0]
              # remove original polygon
              cell.remove_polygons(lambda pts, layer, datatype:layer == 0)
              basepoly = gdspy.Polygon(new_points, layer=poly_layer, datatype=poly_purpose)
              cell.add(basepoly)     


      # -------- Check for layer or purpose on delete list ---------
      if ((poly_layer in delete_layers_list) or (poly_purpose in delete_purpose_list)):
        # invalidate original polygon
        # mark by assigning layer 0 
        poly.layers=[0] 
        # remove original polygon that is now on layer 0
        cell.remove_polygons(lambda pts, layer, datatype:layer == 0)

  # write to output file
  output_library.write_gds(output_name)
  
  print('\n\nFINISHED: Created output file ', output_name)

  
else:
  print ("Usage: gds_simplify <input.gds> ")
  

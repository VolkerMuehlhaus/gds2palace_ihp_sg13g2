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


# Via array merging for IHP SG13 technology

import gdspy
import os, sys
import math
from collections import defaultdict

# only metals from this layer list are included in output file
metal_layers_list = [
  1,
  8,
  9,
  10,
  30,
  36,
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

# layers in this purpose list are EXCLUDED from output file
exclude_purpose_list = [
  20, # noqrc
  22, # filler
  23, # nofill   
  32 # block
]



# Via spacings to be merged, use large values to TopVia1,TopVia2 to get Pad vias also
via_layers_dict = {
  6:  0.5,   # Cont
  19: 1, # Via1
  29: 2, # Via2
  49: 3, # Via3
  66: 3, # Via4 
  129: 2.0,# Vmim
  125: 10.0,# TopVia1, large distance for pads
  133: 10.0 # TopVia2, large distance for pads
}


# Layers above the via layer
layer_above_dict = {
  6:  8,  # Cont
  19: 10, # Via1
  29: 30, # Via2
  49: 50, # Via3
  66: 67, # Via4 
  129: 126,# Vmim
  125: 126,# TopVia1
  133: 134 # TopVia2
}

# Layers below the via layer
layer_below_dict = {
  6:  1, # Cont
  19: 8, # Via1
  29: 10, # Via2
  49: 30, # Via3
  66: 50, # Via4 
  129: 36,# Vmim
  125: 67,# TopVia1
  133: 126 # TopVia2
}


def merge_via_array (polygons, maxspacing):
  """Used internally in processing data from gdspy, does not work on our own all_polygons_list class!

  Args:
      polygons (_type_): LPPpolylist data
      maxspacing (float): offset for oversize/undersize of polygons during via array merge

  Returns:
      _type_: LPPpolylist data
  """

  # Via array merging consists of 3 steps: oversize, merge, undersize
  # Value for oversize depends on via layer
  # Oversized vias touch if each via is oversized by half spacing
  
  offset = maxspacing/2 + 0.01

  offsetpolygonset=gdspy.offset(polygons, offset, join='miter', tolerance=2, precision=0.001, join_first=True, max_points=1999)
  mergedpolygonset=gdspy.boolean(offsetpolygonset, None,"or", max_points=1999)
  mergedpolygonset=gdspy.offset(mergedpolygonset, -offset, join='miter', tolerance=2, precision=0.001, join_first=False, max_points=1999)

  # offset and boolean return PolygonSet, we only need the list of polygons from that
  return mergedpolygonset.polygons 


# ---------------- main ------------------

# ============= main ===============

if len(sys.argv) >= 2:
  input_name = sys.argv[1]

  if os.path.isfile(input_name):
      # Read GDSII library
      print('Reading GDSII input file:', input_name)

    # get basename of input file, append suffix to identify output polygons
    # output_name = Path(input_name).stem + "_forEM.gds"
      input_library = gdspy.GdsLibrary(infile=input_name)

      output_name = input_name.replace(".gds","_viamerge.gds")
      output_library = gdspy.GdsLibrary()
      
      # evaluate only first top level cell
      toplevel_cell_list = input_library.top_level()
      input_cell = toplevel_cell_list[0]
      
      # create new cell in output library with the same name as the top level cell in input library that we work on
      cellname = input_cell.name
      output_cell = output_library.new_cell(cellname)


      # flatten hierarchy below this cell
      input_cell.flatten(single_layer=None, single_datatype=None, single_texttype=None)

      # in addition to IHP layers, also keep layers above 200 that we use for ports etc.
      for layer in range(201,250):
        metal_layers_list.append(layer)

      for layer_to_extract_gds in metal_layers_list:
          
          # print ("Evaluating layer ", str(layer_to_extract))

          # get layers used in cell
          used_layers = input_cell.get_layers()

          if (layer_to_extract_gds in used_layers):  # use base layer number here to match GDSII
                      
                  # iterate over layer-purpose pairs (by_spec=true)
                  # do not descend into cell references (depth=0)
                  LPPpolylist = input_cell.get_polygons(by_spec=True, depth=0)

                  # go through cells of this layer, to find our target layer
                  for LPP in LPPpolylist:
                      layer = LPP[0]   
                      purpose = LPP[1]
                      
                      # now get polygons for this one layer-purpose-pair
                      if (layer==layer_to_extract_gds) and (purpose not in exclude_purpose_list):
                          layerpolygons = LPPpolylist[(layer, purpose)]
                          numpoly = len(layerpolygons)
                          print(f"Number of polygons on layer {layer}: {numpoly}")

                          if layer in via_layers_dict.keys():
                            # merge via arrays, all other layers skip this step
                            merge_polygon_size = via_layers_dict.get(layer, 0)
                            layerpolygons = merge_via_array (layerpolygons, merge_polygon_size)

                            # offset = -1
                            # layerpolygons=gdspy.offset(layerpolygons, offset, join='miter', tolerance=2*offset, precision=0.001, join_first=True, max_points=1499)

                            # now get polygons on layer above and do boolean and with via
                            layer_num_above = layer_above_dict[layer]
                            layer_above_polygons = LPPpolylist[(layer_num_above, 0)] # drawing

                            # Perform boolean AND with layer above
                            layerpolygons = gdspy.boolean(layerpolygons, layer_above_polygons, operation='and', layer=layer, datatype=purpose)

                            # now get polygons on layer below and do boolean and
                            layer_num_below = layer_below_dict[layer]
                            layer_below_polygons = LPPpolylist[(layer_num_below, 0)] # drawing
                            layerpolygons = gdspy.boolean(layerpolygons, layer_below_polygons, operation='and', layer=layer, datatype=purpose)
                            
                            output_cell.add(layerpolygons)

                          else:
                            for poly in layerpolygons:
                              newpoly = gdspy.Polygon(poly,  layer=layer, datatype=purpose)
                              output_cell.add(newpoly)


      output_library.write_gds(output_name)                    
  else:
    print ('No valid input file specified')  

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

# -*- coding: utf-8 -*-

__version__ = "1.0.1"

import os
import sys
import gmsh
import math

import numpy as np

import json

def get_tag_after_fragment (tag_to_find_list, geom_dimtags, mapping, dimension=2):
    '''    
    Tags usually change after gmsh fragmenting, but fragmenting returns a table with mappings.
    This function returns the new tags, if we know the original tags before fragmenting.
      - tag_to_find_list: list of tags obtained when creating the geometry
      - geom_dimtags: list of all original dimtags before fragmenting
      - mapping: list of mapping between old and new tags, obtained as return value from fragment() function
      - dimension: dimension for tags that we are looking for
    '''

    # make this algorithm safe for single tags also
    if isinstance(tag_to_find_list, int):
        tag_to_find_list = [tag_to_find_list]

    indices = [
        i for i, x in enumerate(geom_dimtags) 
        if x[0] == dimension and (x[1] in tag_to_find_list)
    ]
    raw = [mapping[i] for i in indices]
    flat = [item for sublist in raw for item in sublist]
    newtags = [s[-1] for s in flat]

    return newtags



class simulation_port:
  """
    port object
    for in-plane port, parameter target_layername is specified
    for via port, parameters from_layername and to_layername are specified for the metals above and below   
  """
  
  def __init__ (self, portnumber, voltage, port_Z0, source_layernum, target_layername=None, from_layername=None, to_layername=None, direction='x'):
    self.portnumber = portnumber
    self.source_layernum = source_layernum        # source for port geometry is a GDSII layer, just one port per layer
    self.target_layername = target_layername      # target layer where we create the port, if specified we create in-plane port
    self.from_layername  = from_layername         # layer on one end of via port, used if target_layername is None
    self.to_layername    = to_layername           # layer on other  end of via port
    self.direction  = direction
    
    self.port_Z0 = port_Z0
    self.voltage = voltage
    self.CSXport = None

  def set_CSXport (self, CSXport):
    self.CSXport = CSXport  

  def __str__ (self):
    # string representation 
    mystr = 'Port ' + str(self.portnumber) + ' voltage = ' + str(self.voltage) + ' GDS source layer = ' + str(self.source_layernum) + ' target layer = ' + str(self.target_layername) + ' direction = ' + str(self.direction)
    return mystr
  

class all_simulation_ports:
  """
  all simulation ports object
  """
  
  def __init__ (self):
      self.ports = []
      self.portcount = 0
      self.portlayers = []

  def add_port (self, port):
      self.ports.append(port)
      self.portcount = len(self.ports)
      self.portlayers.append(port.source_layernum)

  def get_port_by_layernumber (self, layernum):  # special GDSII layer for ports only, one port per layer, so we have 1:1 mapping
      found = None
      for port in self.ports:
          if port.source_layernum == layernum:
              found = port
              break
      return found       
  
  def get_port_by_number (self, portnum):
      return self.ports[portnum-1] 

  def apply_layernumber_offset (self, offset):
      newportlayers = []    
      for port in self.ports:
          port.source_layernum = port.source_layernum + offset
          newportlayers.append(port.source_layernum)
      self.portlayers = newportlayers      

  def all_active_excitations (self):
    numbers = []
    for port in self.ports:
        if abs(port.voltage) > 1E-6:
            # skip zero voltage ports for excitation
            # append as list, we need that for create_palace() function
            numbers.append([port.portnumber])
    return numbers



def add_metals (allpolygons, metals_list, meshseed=0):
    '''
    Add drawn geometries from layout layers to gmsh
    '''

    def get_layer_volumes (metals_list, layername):
        # return all volume tags for a given  layer name
        this_metal = metals_list.getbylayername(layername)
        
        # get volumes on this layer
        delta = 0.001
        layer_zmin = this_metal.zmin - delta/2
        layer_zmax = this_metal.zmax + delta/2
            
        # This returns the list of volumes inside
        # But unfortunately, it will trigger also for thinner layers enclosed inside that volume
        volumes_in_bounding_box = gmsh.model.getEntitiesInBoundingBox(-math.inf,-math.inf,layer_zmin,math.inf,math.inf,layer_zmax,3)
        # not iterate over return values and check exact height
        volume_on_layer_list = []
        for volume in volumes_in_bounding_box:
            volume_tag = volume[1]
            xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(3, volume_tag)
            if (abs(zmin-layer_zmin) < delta) and (abs(zmax-layer_zmax) < delta):
                volume_on_layer_list.append(volume)
            
        return  volume_on_layer_list


    def get_sheet_surfaces (metals_list, layername):
        # return all surface tags for a given  layer name
        # NOTE: This is specialized for thin sheet and only evaluates at zmin, ignoring zmax value
        this_metal = metals_list.getbylayername(layername)
        
        # get volumes on this layer
        delta = 0.001
        sheet_zmin = this_metal.zmin - delta/2
        sheet_zmax = this_metal.zmin + delta/2  # evaluate zmin, ignore zmax, because we look at thin sheet layers
            
        # This returns the list of volumes inside
        # But unfortunately, it will trigger also for thinner layers enclosed inside that volume
        surfaces_in_bounding_box = gmsh.model.getEntitiesInBoundingBox(-math.inf,-math.inf,sheet_zmin,math.inf,math.inf,sheet_zmax,2)
        # not iterate over return values and check exact height
        surfaces_on_layer_list = []
        for surface in surfaces_in_bounding_box:
            surfaces_on_layer_list.append(surface)
            
        return  surfaces_on_layer_list



    kernel = gmsh.model.occ

    # add geometries on metal and via layers
    for poly in allpolygons.polygons:
        # each poly knows its layer number

        # We might have one layout polygon mapped to multiple layers in stackup, for special use cases in MIM etc
        # We then  have multiple entries in the XML that share the same layer number
        # For that special case, get ALL metals from technology file for that same polygon
        all_assigned = metals_list.getallbylayernumber (poly.layernum) 
        if all_assigned is not None:
            for metal in all_assigned:

                # add Polygon to gmsh using poly.pts
                linetaglist = []
                vertextaglist = []
                numvertices = len(poly.pts_x)

                for v in range(numvertices):
                    # addPoint parameters: x (double), y (double), z (double), meshSize = 0. (double), tag = -1 (integer)
                    vertextag = kernel.addPoint(poly.pts_x[v], poly.pts_y[v], metal.zmin, meshseed, -1)
                    vertextaglist.append(vertextag)

                # after writing the vertices, we combine them to boundary lines
                for v in range(numvertices):
                    pt_start = vertextaglist[v]
                    if v==(numvertices-1):
                        pt_end = vertextaglist[0]
                    else:
                        pt_end = vertextaglist[v+1]

                    # addLine parameters: startTag (integer), endTag (integer), tag = -1 (integer)
                    linetag = kernel.addLine(pt_start, pt_end, -1)
                    linetaglist.append(linetag)

                # after creating the lines, we can create a curve loop and a surface 
                # to do so, we need the line segment numbers again
                curvetag   = kernel.addCurveLoop(linetaglist, tag=-1)
                surfacetag = kernel.addPlaneSurface([curvetag], tag=-1)

                if not (metal.is_sheet):
                    if metal.thickness > 0:
                        kernel.extrude([(2,surfacetag)],0,0,metal.thickness)

    kernel.synchronize()


    # We have created initial 3D volumes from GDSII, now iterate over 3D entities to merge them
    volumelist = gmsh.model.getEntities(3)
    volumecount = len(volumelist)
    if volumecount>0:
        # try to merge volumes on each layer
        for metal in metals_list.metals:
            if not (metal.is_via or metal.is_sheet):            
                # try to merge planar metal volumes
                layername = metal.name
                volume_on_layer_list = get_layer_volumes(metals_list, layername)

                # try boolean union of volumes on this layer
                if len(volume_on_layer_list)>1:
                    # get first element and delete from list
                    first = volume_on_layer_list.pop(0)
                    # print('  Layer = ' + layername)
                    # print('  FUSE, object = ' + str(first)) 
                    # print('  FUSE, tool   = ' + str(volume_on_layer_list)) 
                    
                    gmsh.model.occ.fuse([first],volume_on_layer_list, -1)
                    gmsh.model.occ.synchronize()


    tags_created_3D = {} # each layer has a flat list
    taglist_created_2D = {} # each layer has nested list, one list per polygon, these are surfaces of 3D volumes
    tags_created_sheet2D = {} # each layer has a flat list of tags for thin sheet surfaces

    # Remove volume of planar metals, keep surface only
    # Store tags of created geometries, one list per layer, key is layer name

    volumelist = gmsh.model.getEntities(3)
    volumecount = len(volumelist)
    if volumecount>0:
        # print('Number of volumes after merging = ' + str(volumecount)) 

        for metal in metals_list.metals:
            layername = metal.name

            # prepare the lists that hold the tags
            if layername in taglist_created_2D.keys():
                layer_perpolytags_2D = taglist_created_2D[layername]
            else:
                layer_perpolytags_2D = []
                taglist_created_2D[layername] = layer_perpolytags_2D


            if layername in tags_created_3D.keys():
                layer_tags_3D = tags_created_3D[layername]                   
            else:
                layer_tags_3D = []
                tags_created_3D[layername] = layer_tags_3D 


            if layername in tags_created_sheet2D.keys():
                layer_tags_sheets = tags_created_sheet2D[layername]                   
            else:
                layer_tags_sheets = []
                tags_created_sheet2D[layername] = layer_tags_sheets 



            # get layer volumes, all metals and vias are volumes at this processing step
            # the only exception are sheet layers, handled below
            volume_on_layer_list = get_layer_volumes(metals_list, layername)

            # check if we have planar metal or via, process differently
            if metal.is_via or metal.is_dielectric:
                # vias and dielectric bricks are kept as 3D volumes
                for dimtag in volume_on_layer_list:
                    volumetag = dimtag[1]
                    tags_created_3D[layername].append(volumetag)

            elif metal.is_metal:
                # planar metal is shelved, we keep the surfaces and remove the volume  
                for dimtag in volume_on_layer_list:
                    volumetag = dimtag[1]
                   
                    # get all surfaces of 3d body
                    _, surfaceloops = kernel.getSurfaceLoops(volumetag)
                    layer_perpolytags_2D.append(surfaceloops)

                    # remove volume, for simulation we only keep surfaces
                    kernel.remove([(3,volumetag)])

            elif metal.is_sheet:
                surfaces_on_layer_list = get_sheet_surfaces (metals_list, layername)
                tags_created_sheet2D[layername] = surfaces_on_layer_list 

            else:
                print('Unknown "Type" assigned to layer ', metal.name)
                exit(1)


        kernel.synchronize()
    return tags_created_3D, taglist_created_2D, tags_created_sheet2D            


def create_box_with_meshseed (kernel, xmin,ymin,zmin,xmax,ymax,zmax, meshseed):
    pt1 = kernel.addPoint(xmin, ymin, zmin, meshseed, -1)
    pt2 = kernel.addPoint(xmin, ymax, zmin, meshseed, -1)
    pt3 = kernel.addPoint(xmax, ymax, zmin, meshseed, -1)
    pt4 = kernel.addPoint(xmax, ymin, zmin, meshseed, -1)
    
    line1 = kernel.addLine(pt1,pt2,-1) 
    line2 = kernel.addLine(pt2,pt3,-1) 
    line3 = kernel.addLine(pt3,pt4,-1) 
    line4 = kernel.addLine(pt4,pt1,-1) 
    linetaglist = [line1, line2, line3, line4]

    # after creating the lines, we can create a curve loop and a surface 
    # to do so, we need the line segment numbers again
    curvetag   = kernel.addCurveLoop(linetaglist, tag=-1)
    surfacetag = kernel.addPlaneSurface([curvetag], tag=-1)    
    returnval  = kernel.extrude([(2,surfacetag)],0,0,zmax-zmin)
    volumetag = returnval[1][1]

    return volumetag


def add_dielectrics (kernel, materials_list, dielectrics_list, gds_layers_list, allpolygons, margin, air_around, refined_cellsize):
# Add dielectric layers (these extend through simulation area and have no polygons in GDSII)

    # Store tags of created geometries, key is layer name
    tags_created_3D = {}

    # meshseed is not relevant because we create a mesh later from distance to metal edges
    meshseed = 0

    # largest dimensions of dielectrics, across all stackups in multi-chip models
    overall_xmin = math.inf
    overall_ymin = math.inf
    overall_xmax = -math.inf
    overall_ymax = -math.inf

    # margin can be specified as single value only 
    if isinstance(margin, list):
        print('Error: expected margin to be a single value for dielectric layer oversize in xy plane,')
        print('but instead we have this: ', str(margin))    
        exit(1)

    # air_around can be specified as single value or array, check what we have header
    if isinstance(air_around, list):
        if len(air_around)==6:
            air_xmin = air_around[0]
            air_xmax = air_around[1]
            air_ymin = air_around[2]
            air_ymax = air_around[3]
            air_zmin = air_around[4]
            air_zmax = air_around[5]
        else:
            print('Error: expected air_around to be a single value or a list of 6 values:')
            print('[air_xmin, air_xmax, air_ymin, air_ymax, air_zmin, air_zmax]')
            print('but instead we have this: ', str(air_around))    
            exit(1)
    else:
        # all the same
        air_xmin = air_xmax = air_ymin = air_ymax = air_zmin = air_zmax = air_around



    # dielectrics from stackup
    offset = 0 
    offset_delta = margin/20 # some relevant offset for alternating dielectric dimensions (workaround for mesh error)

    for dielectric in dielectrics_list.dielectrics:
        # get CSX material object for this dielectric layers material name
        materialname = dielectric.material
        
        # tag managment: get list of tags for this materialname
        if materialname in tags_created_3D.keys():
            layer_tags_3D = tags_created_3D[materialname]                   
        else:
            layer_tags_3D = []
            tags_created_3D[materialname] = layer_tags_3D 


        # xy dimensions of dielectric boxes from stackup
        if dielectric.gdsboundary is None:
            bound_layernum = None
        else:
            bound_layernum = int(dielectric.gdsboundary) 

        bbox_xmin, bbox_xmax, bbox_ymin, bbox_ymax = allpolygons.bounding_box.get_layer_bounding_box(bound_layernum)
        
        x1 = bbox_xmin - margin
        y1 = bbox_ymin - margin
        x2 = bbox_xmax + margin
        y2 = bbox_ymax + margin

        overall_xmin = min(overall_xmin, x1)
        overall_ymin = min(overall_ymin, y1)
        overall_xmax = max(overall_xmax, x2)
        overall_ymax = max(overall_ymax, y2)

        # now that we have a material, add the dielectric body (substrate, oxide etc)
        z1 = dielectric.zmin
        z2 = dielectric.zmax
       
        box_tag = create_box_with_meshseed (kernel, x1-offset, y1-offset, z1, x2+offset, y2+offset, z2, meshseed)
        tags_created_3D[materialname].append(box_tag)

        # workaround to avoid gsmh meshing error: alternating size of stacked dielectric blocks
        if offset == 0:
            offset = offset_delta
        else:
            offset = 0    

    # add surrounding air box

    x1 = overall_xmin - air_xmin
    y1 = overall_ymin - air_ymin
    x2 = overall_xmax + air_xmax
    y2 = overall_ymax + air_ymax
    if len(dielectrics_list.dielectrics)>0:
        # we have at least one dielectric
        z1 = dielectrics_list.dielectrics[-1].zmin - air_zmin
        z2 = dielectrics_list.dielectrics[0].zmax  + air_zmax
    else:
        # we have no dielectrics, get zmin/zmax from gds layers
        z1 = math.inf
        z2 = -math.inf
        for gds_layer in gds_layers_list.metals:
            z1 = min(z1, gds_layer.zmin)
            z2 = max(z2, gds_layer.zmin)
        z1 = z1 - air_zmin  
        z2 = z2 + air_zmax

        # we have no dielectrics, but we need to get get xy size of g
        x1 = allpolygons.get_xmin() - air_xmin
        y1 = allpolygons.get_ymin() - air_ymin
        x2 = allpolygons.get_xmax() + air_xmax
        y2 = allpolygons.get_ymax() + air_ymax


    box_tag = kernel.addBox(x1,y1,z1,x2-x1,y2-y1,z2-z1)
    tags_created_3D['airbox'] = [box_tag]

    kernel.synchronize()

    return tags_created_3D  



def add_ports (kernel, allpolygons, metals_list, simulation_ports, meshseed = 0):
    '''
    Add ports from special port layers  to gmsh
    '''
    tags_created_2D = {}

    # data structure that we write to Palace output directory with information about port Z0 and port dimensions
    all_port_information = []

    # add geometries on metal and via layers
    for poly in allpolygons.polygons:
        # each poly knows its layer number
        # get material name for poly, by using metal information from stackup
        metal = metals_list.getbylayernumber (poly.layernum)
        if metal is None: # this layer does not exist in XML stackup
            # found a layer that is not defined in stackup from XML, check if used for ports
            if poly.layernum in simulation_ports.portlayers:
                # mark polygon for special handling in meshing
                poly.is_port = True 

                port_dimtag = []
                # find port definition for this GDSII source layer number
                port = simulation_ports.get_port_by_layernumber(poly.layernum)
                if port is not None:

                    port_information_data = {}
                    port_information_data['portnumber'] = port.portnumber
                    port_information_data['Z0'] = port.port_Z0
                    port_information_data['direction'] = port.direction.upper()

                    portnum = port.portnumber
                    xmin = poly.xmin
                    xmax = poly.xmax
                    ymin = poly.ymin
                    ymax = poly.ymax
                    
                    # port z coordinates are different between in-plane ports and via ports
                    if port.target_layername is not None:
                        # in-plane port   
                        port_metal = metals_list.getbylayername(port.target_layername)
                        zmin = port_metal.zmin
                        zmax = port_metal.zmin # port has zero thickness

                        # rectangle in xy plane
                        pt1 = kernel.addPoint(xmin, ymin, zmin, meshseed, -1)
                        pt2 = kernel.addPoint(xmin, ymax, zmin, meshseed, -1)
                        pt3 = kernel.addPoint(xmax, ymax, zmin, meshseed, -1)
                        pt4 = kernel.addPoint(xmax, ymin, zmin, meshseed, -1)

                        # port information that we write to Palace output directory
                        if 'X' in port.direction:
                            length = xmax-xmin
                            width  = ymax-ymin
                        else:    
                            length = ymax-ymin
                            width  = xmax-xmin
                        port_information_data['length'] = length                           
                        port_information_data['width']  = width      

                    else:
                       # via port 
                       from_metal = metals_list.getbylayername(port.from_layername)
                       to_metal   = metals_list.getbylayername(port.to_layername)

                       if to_metal is None:
                          print('[ERROR] Invalid layer ' , port.to_layername, ' in port definition, not found in XML stackup file!')
                          sys.exit(1)                             
                       if from_metal is None:
                          print('[ERROR] Invalid layer ' , port.from_layername, ' in port definition, not found in XML stackup file!')
                          sys.exit(1)                             

                       if from_metal.zmin < to_metal.zmin:
                           lower = from_metal
                           upper = to_metal
                       else:  
                           lower = to_metal
                           upper = from_metal

                       zmin = lower.zmax
                       zmax = upper.zmin
                       length = zmax-zmin

                       # port is expected to be a line only (no area), we now create surface in z direction
                       # to make sure that we have a line only, we check size in x and y direction
                       size_x = xmax - xmin
                       size_y = ymax - ymin 
                       
                       if size_y > size_x:
                            # ports are line in y direction
                            pt1 = kernel.addPoint(xmin, ymin, zmin, meshseed, -1)
                            pt2 = kernel.addPoint(xmin, ymax, zmin, meshseed, -1)
                            pt3 = kernel.addPoint(xmin, ymax, zmax, meshseed, -1)
                            pt4 = kernel.addPoint(xmin, ymin, zmax, meshseed, -1)
                            width = size_y
                       else: 
                            # ports are line in x direction
                            pt1 = kernel.addPoint(xmin, ymin, zmin, meshseed, -1)
                            pt2 = kernel.addPoint(xmin, ymin, zmax, meshseed, -1)
                            pt3 = kernel.addPoint(xmax, ymin, zmax, meshseed, -1)
                            pt4 = kernel.addPoint(xmax, ymin, zmin, meshseed, -1)
                            width = size_x

                       port_information_data['length'] = length                            
                       port_information_data['width']  = width      

                    port_information_data['xmin'] = xmin                           
                    port_information_data['xmax'] = xmax      
                    port_information_data['ymin'] = ymin                           
                    port_information_data['ymax'] = ymax      
                    port_information_data['zmin'] = zmin                           
                    port_information_data['zmax'] = zmax      

                    all_port_information.append(port_information_data)

                    # for both in-plane and vertical
                    line1 = kernel.addLine(pt1,pt2,-1) 
                    line2 = kernel.addLine(pt2,pt3,-1) 
                    line3 = kernel.addLine(pt3,pt4,-1) 
                    line4 = kernel.addLine(pt4,pt1,-1) 
                    linetaglist = [line1, line2, line3, line4]

                    # after creating the lines, we can create a curve loop and a surface 
                    # to do so, we need the line segment numbers again
                    curvetag   = kernel.addCurveLoop(linetaglist, tag=-1)
                    surfacetag = kernel.addPlaneSurface([curvetag], tag=-1)

                    port_dimtag.append(surfacetag)
                    tags_created_2D['P'+str(portnum)]=port_dimtag

    kernel.synchronize()

    all_port_information_struct = {}
    all_port_information_struct['ports'] = all_port_information

    return tags_created_2D, all_port_information_struct                    




######### end of function createSimulation ()  ##########


def create_palace (excite_ports, settings):

    def get_optional_setting (settings, key, default):
        # get setting that might exist, but is not required
        value = default
        if key in settings.keys():
            value = settings[key]
        return value    

    def get_surface_orientation (s):
        # get the normal of a surface, we use that to get surface orientation (x, y or z)

        # Get the boundary of the surface
        boundary_lines  = gmsh.model.getBoundary([(2, s)], oriented=True)

        # Get points from these lines
        points = []
        seen_points = set()

        for dim, line_tag in boundary_lines:
            line_points = gmsh.model.getBoundary([(1, line_tag)], oriented=True)
            for pdim, ptag in line_points:
                if ptag not in seen_points:
                    coord = gmsh.model.getValue(0, ptag, [])
                    points.append(np.array(coord))
                    seen_points.add(ptag)
                if len(points) == 3:
                    break
            if len(points) == 3:
                break

        # Compute surface normal using cross product
        v1 = points[1] - points[0]
        v2 = points[2] - points[0]
        normal = np.cross(v1, v2)
        normal = normal / np.linalg.norm(normal)
        return normal
    
    def is_vertical_surface (s):
        # check if surface is not in xy plane
        normal = get_surface_orientation(s)   
        n = normal[2]
        if not np.isnan(n):
            is_vertical = int(abs(n)) == 0
        else:    
            is_vertical = False    
        return is_vertical
    
   
    
    # get settings from simulation model
    unit = settings['unit']
    margin = settings['margin']   # oversize of dielectric layers relative to drawing
    air_around = get_optional_setting (settings, "air_around", margin)  # airbox size to simulation boundary

    fstart = get_optional_setting (settings, 'fstart', None)
    fstop  = get_optional_setting (settings, 'fstop', None)
    if (fstart is not None) and (fstop is not None):
        fstep  = get_optional_setting (settings, "fstep", (fstop-fstart)/100)

    # we might have additional discrete frequencies specified, which can be number or list of numbers
    f_discrete_list =  get_optional_setting (settings, "fpoint", []) # extra frequencies in GHz in addition to sweep
    # make it a list always
    if isinstance(f_discrete_list,float) or isinstance(f_discrete_list, int):
        f_discrete_list = [f_discrete_list]

    # we might have additional discrete frequencies specified for field dump, which can be number or list of numbers
    f_dump_list =  get_optional_setting (settings, "fdump", []) # extra dump frequencies in GHz in addition to sweep
    # make it a list always
    if isinstance(f_dump_list, float) or isinstance(f_dump_list, int):
        f_dump_list = [f_dump_list]


    if fstart is None and len(f_discrete_list)==0 and len(f_dump_list)==0: 
        print('No frequencies defined, you must define fstart+fstop or fpoint!')
        exit(1)

    # Discrete frequencies list values must be in GHz, divide by 1e9
    if len(f_discrete_list) > 0:
        GHz = [f / 1e9 for f in f_discrete_list]
        f_discrete_list = GHz

    # Discrete frequencies list values must be in GHz, divide by 1e9
    if len(f_dump_list) > 0:
        GHz = [f / 1e9 for f in f_dump_list]
        f_dump_list = GHz


    adaptive_sweep = get_optional_setting (settings, "adaptive_sweep", True)
    
    order = int(get_optional_setting (settings, "order", 2))  # order of FEM basis functions, default 2
    if (order < 1) or (order > 3):
        print('WARNING: Order of basis function must 1, 2 or 3.\nValue changed to default value order=2.')
        order = 2
   
    simulation_ports = settings['simulation_ports'] 
    materials_list = settings['materials_list']
    dielectrics_list = settings['dielectrics_list'] 
    metals_list = settings['metals_list'] 
    allpolygons = settings['allpolygons'] 

    sim_path = settings['sim_path'] 
    model_basename = settings['model_basename'] 
    config_suffix = get_optional_setting (settings, "config_suffix", '')  # suffix to configuration file name


    # mesh control
    cells_per_wavelength = get_optional_setting (settings, "cells_per_wavelength", 10) # how many mesh cells per wavelength, must be 10 or more
    if cells_per_wavelength < 10:
        print('WARNING: Cells per wavelength must be >= 10\nValue changed to default value cells_per_wavelength=10.')
        cells_per_wavelength=10

    refined_cellsize = settings['refined_cellsize']  # mesh cell size in conductor region
    meshsize_max = get_optional_setting (settings, "meshsize_max", 70)
    adaptive_mesh_iterations = get_optional_setting (settings, "adaptive_mesh_iterations", 0)
    save_adaptive_mesh = get_optional_setting (settings, "save_adaptive_mesh", False)
    save_gmsh_geometry =  get_optional_setting (settings, "save_gmsh_unrolled", False)
    substrate_refinement = get_optional_setting (settings, "substrate_refinement", False)

    # separate_z_group_for_metals setting 
    z_thickness_factor = get_optional_setting (settings, "z_thickness_factor", 1)

    # boundary conditions default to absorbing
    boundary_condition = get_optional_setting (settings,'boundary',['ABC','ABC','ABC','ABC','ABC','ABC'])
    print ('Using boundary condition ', str(boundary_condition))
    if len(boundary_condition) != 6:
        print('If specified, the boundary condition parameter must be a list with 6 string values, "PML", "ABC", "PEC" or "PMC')
        exit(1)

    # script control
    no_gui = get_optional_setting (settings,'no_gui', False)

    geo_name = os.path.join(sim_path, model_basename + '.geo_unrolled')
    msh_name = os.path.join(sim_path, model_basename + '.msh')
    config_name = os.path.join(sim_path, 'config' + config_suffix + '.json')
    data_dir = 'output/' + model_basename 

    # parameter check
    # DC simulation gives errors for now, so replace that
    if fstart is not None:
        if fstart < 0.1e8:
            fstart = fstep # start sweep from next step
            # add low frequency to list of discrete frequencies, to replace 0 Hz from user input
            f_DC = 0.1
            f_discrete_list.append (f_DC)
            print('WARNING: Start frequency changed from DC to ', f_DC, ' GHz!')


    # AdaptiveTol value enables adaptive frequency sweep, 0 means regular sweep (not adaptive)
    if adaptive_sweep:
        AdaptiveTol = 2e-2
    else:    
        AdaptiveTol = 0

    # refinement value controls adaptive mesh refinement
    # always write this control block, even when 0 iterations specified, because user can then edit json himself
    Refinement = {
        "UniformLevels": 0,
        "Tol": 1e-2,
        "MaxIts": adaptive_mesh_iterations,
        "MaxSize": 2e6,
        "Nonconformal": True,
        "UpdateFraction": 0.7,
        "SaveAdaptMesh": save_adaptive_mesh        	
    }



    # --------- config header ----------------
    config_data = {}    # data structure to hold the config file data
 
    problem =  {
            "Type": "Driven",
            "Verbose": 3,
            "Output": data_dir
        }
    config_data['Problem'] = problem


    model =  {
            "Mesh": model_basename + '.msh',
            "L0": unit,
            "Refinement": Refinement
        }
    config_data['Model'] = model

    # user defined sweep
    sweep = []
    
    if (fstart is not None) and (fstop is not None):
        linear = {
                "Type": "Linear",
                "MinFreq": fstart/1e9,
                "MaxFreq": fstop/1e9,
                "FreqStep": fstep/1e9,
                "SaveStep": 0                        
            }

        sweep.append(linear)    

    # add f_discrete_list, this might have the value that replaces user input 0 GHz
    if len(f_discrete_list) > 0:

        discrete = {
                    "Type": "Point",
                    "Freq": f_discrete_list,
                    "SaveStep": 0,
        }

        sweep.append(discrete)


    # add f_dump_list for frequencies where we request dump file at every sample
    if len(f_dump_list) > 0:

        dump = {
                    "Type": "Point",
                    "Freq": f_dump_list,
                    "SaveStep": 1,
        }

        sweep.append(dump)



    allsamples = {
                  "Samples":sweep,
                  "AdaptiveTol": AdaptiveTol
                  }



    solver = {
            "Linear": {
                "Type": "Default",
                "KSPType": "GMRES",
                "Tol": 1e-06,
                "MaxIts": 400
            },
            "Order": order,
            "Device": "CPU"
            }

    solver['Driven'] = allsamples


    config_data['Solver'] = solver


    print('Creating mesh file and config file')

    fmax = 0
    if fstop is not None: 
        fmax = max(fmax, fstop)
    if len(f_discrete_list) > 0: 
        discrete_max_GHz = max(f_discrete_list) 
        fmax = max(fmax, discrete_max_GHz*1e9)

    wavelength_air = 3e8/fmax / unit
    # max_cellsize = min((wavelength_air)/(math.sqrt(materials_list.eps_max)*cells_per_wavelength), meshsize_max)
    max_cellsize_air = wavelength_air/cells_per_wavelength

    print('Wavelength in air : ', wavelength_air, ' units')
    print('  meshsize_max    : ', meshsize_max, ' units')
    print('  max_cellsize_air: ', max_cellsize_air, ' units')

    kernel = gmsh.model.occ
    gmsh.initialize()
    gmsh.option.setNumber("General.Verbosity", 4)


    # Add model, initialize
    if "from_gds" in gmsh.model.list():
        gmsh.model.setCurrent("from_gds")
        gmsh.model.remove()
    gmsh.model.add("from_gds")

       
    # add drawn geometries to gmsh model
    # store metal tags for surfaces and volumes per layer 
    print('Adding metal tags ...')
    metal_tags_created_3D, metal_perpolytags_2D, sheet_tags_created_2D = add_metals (allpolygons, metals_list)

    # add ports
    print('Adding ports ...')
    port_tags_created_2D, all_port_information_struct = add_ports (kernel, allpolygons, metals_list, simulation_ports)

    # add units to port information
    all_port_information_struct['unit'] = settings['unit']


    # add dielectric boxes (oxide, substrate, air etc) to gmsh model
    print('Adding dielectrics ...')
    dielectric_tags_created_3D = add_dielectrics (kernel, materials_list, dielectrics_list, metals_list, allpolygons, margin, air_around, refined_cellsize=refined_cellsize)

    # Prepare for embedding/fragmenting, where tags will change
    # get all surfaces and volumes and store their original dimtags, we will fragment them to  align mesh where they touch or intersect
    geom_dimtags = [x for x in kernel.getEntities() if x[0] in (2, 3)]

    # Now embed/fragment them, return value geom_map keeps mapping between original tags and new tags after fragmenting
    _, geom_map = kernel.fragment(geom_dimtags, [])   
    kernel.synchronize()


    # ---------------- VOLUMES -----------------

    # for config file 
    Palace_materials = []

    # Next, we use our mapping between original tags and new tags, and assign physical names
    # Outer iteration is over the layer names
    for layername in metal_tags_created_3D.keys():   # drawn volumes, for GDS metals that is vias and dielectric bricks only
        # gmsh
        volumes_of_layer = metal_tags_created_3D[layername]
        new_tags = get_tag_after_fragment (volumes_of_layer, geom_dimtags, geom_map, dimension=3)
        phys_group = gmsh.model.addPhysicalGroup(3, new_tags, tag=-1)
        gmsh.model.setPhysicalName(3, phys_group, layername)

        # config file
        if len(new_tags) > 0:
            Palace_material = {}
            metal = metals_list.getbylayername(layername)
            if metal is not None:
                stackup_material = materials_list.get_by_name(metal.material)
                if stackup_material is not None:
                    Palace_material['Attributes']=[phys_group]
                    Palace_material['Permittivity']=stackup_material.eps
                    if metal.is_via:
                        # anisotropic conductivity so that merged via array don't carry (much) xy current
                        xy_sigma = stackup_material.sigma/10
                        Palace_material['Conductivity']=[xy_sigma, xy_sigma, stackup_material.sigma]
                    else:    
                        Palace_material['Conductivity']=stackup_material.sigma

                    Palace_materials.append(Palace_material)

    kernel.synchronize()

    for dielectricname in dielectric_tags_created_3D.keys():
        print('Dielectric = ', dielectricname)
        volumes_of_layer = dielectric_tags_created_3D[dielectricname]
        new_tags = get_tag_after_fragment (volumes_of_layer, geom_dimtags, geom_map, dimension=3)
        max_index = len(volumes_of_layer)
        phys_group = gmsh.model.addPhysicalGroup(3, new_tags[0:max_index], tag=-1)  
        gmsh.model.setPhysicalName(3, phys_group, dielectricname)


        # config file
        if len(new_tags) > 0:
            Palace_material = {}
            dielectric = dielectrics_list.get_by_name(dielectricname)
            if dielectric is not None:
                stackup_material = materials_list.get_by_name(dielectric.material)
                if stackup_material is not None:
                    Palace_material['Attributes']=[phys_group]
                    Palace_material['Permittivity']=stackup_material.eps
                    if stackup_material.sigma>0:
                        Palace_material['Conductivity']=stackup_material.sigma  # for conducting silicon
                    else:
                        Palace_material['LossTan']=stackup_material.tand  # for regular substrate 
                    Palace_materials.append(Palace_material)
            else:
                # special case airbox
                if dielectricname=='airbox':
                    Palace_material['Attributes']=[phys_group]
                    Palace_material['Permittivity']=1.0
                    Palace_material['LossTan']=0.0
                    Palace_materials.append(Palace_material)
    

    kernel.synchronize()



    postprocessing =  {
                "Energy": [],
                "Probe": []
            }

    domains={}
    domains['Materials']=Palace_materials
    domains['Postprocessing']=postprocessing
    config_data['Domains'] = domains


    # ---------------- SURFACES -----------------

    # MESHING: Get list of boundary line tags of all metals, used to refine mesh along the edges
    boundary_line_tags = []    

    # CONFIG: config_data for surfaces in Palace config file
    boundaries = {}
    Palace_conductors = []
    Palace_lumpedports = []
    Palace_impedances = []

    # 2D surfaces from shell of hollow conductors (top, bottom and side walls)
    # one physical group per polygon (shared by all polygon surfaces)
    for layername in metal_perpolytags_2D.keys():
        if len(metal_perpolytags_2D[layername]) > 0:
            # surfaces used for planar metal 

            # gmsh
            all_phys_surfacetags_for_layer_xy = []
            all_phys_surfacetags_for_layer_z = []

            i = 0
            for polysurface in metal_perpolytags_2D[layername]:
                if len(polysurface)>0:
                    i = i+1

                    new_tags = get_tag_after_fragment (polysurface[0], geom_dimtags, geom_map, dimension=2)

                    # new_tags includes ALL surfaces of this one polygon
                    # we now loop over all surfaces to check normal (get surface orientation)

                    new_tags_planar = []
                    new_tags_vertical = []
                    
                    for tag in new_tags:
                        if is_vertical_surface(tag):
                            new_tags_vertical.append(tag)
                        else:
                            new_tags_planar.append(tag)     

                    # xy in-plane
                    phys_group_xy = gmsh.model.addPhysicalGroup(2, new_tags_planar, tag=-1)
                    gmsh.model.setPhysicalName(2, phys_group_xy, layername + '_' + str(i) +'_xy')
                    all_phys_surfacetags_for_layer_xy.append(phys_group_xy)

                    # vertical
                    phys_group_z = gmsh.model.addPhysicalGroup(2, new_tags_vertical, tag=-1)
                    gmsh.model.setPhysicalName(2, phys_group_z, layername + '_' + str(i) + '_z')
                    all_phys_surfacetags_for_layer_z.append(phys_group_z)


            # Palace config file

            if len(all_phys_surfacetags_for_layer_xy) > 0:
                Palace_conductor = {}
                metal = metals_list.getbylayername(layername)
                if metal is not None:
                    stackup_material = materials_list.get_by_name(metal.material)
                    # check that use of conductor or sheet matches material definition
                    if stackup_material.type == "CONDUCTOR" and metal.is_sheet:
                        print('Invalid material assignment: sheet layer ', metal.name, ' must use a resistor material!')
                        exit(1)

                    if stackup_material.type == "RESISTOR" and not metal.is_sheet:
                        print('Invalid material assignment: resistor material mapping only valid for sheet layers, not for ', metal.name)
                        exit(1)


                    if stackup_material is not None:
                        Palace_conductor['Attributes']=all_phys_surfacetags_for_layer_xy
                        Palace_conductor['Conductivity']=stackup_material.sigma
                        Palace_conductor['Thickness']=metal.thickness
                        Palace_conductors.append(Palace_conductor)

            if len(all_phys_surfacetags_for_layer_z) > 0:
                Palace_conductor = {}
                metal = metals_list.getbylayername(layername)
                if metal is not None:
                    stackup_material = materials_list.get_by_name(metal.material)
                    if stackup_material is not None:
                        Palace_conductor['Attributes']=all_phys_surfacetags_for_layer_z
                        Palace_conductor['Conductivity']=stackup_material.sigma
                        Palace_conductor['Thickness']=metal.thickness * z_thickness_factor
                        Palace_conductors.append(Palace_conductor)


            # Meshing: get all boundary lines of metals, store the tags for local refinement
            for polysurface in metal_perpolytags_2D[layername]:
                if len(polysurface)>0:
                    new_tags = get_tag_after_fragment (polysurface[0], geom_dimtags, geom_map, dimension=2)

                    for tag in new_tags:
                        clt, ct = kernel.getCurveLoops(tag)
                        for curvetag in ct:
                            boundary_line_tags.extend(curvetag)             


    kernel.synchronize()

    
    # 2D surfaces from lumped port
    # One physical group for each port
    port_surface_tags = []  # flat list of all port surfaces
    for porttag in port_tags_created_2D.keys():

        # gmsh
        port_surface = port_tags_created_2D[porttag]
        new_tag = get_tag_after_fragment (port_surface, geom_dimtags, geom_map, dimension=2)
        phys_group = gmsh.model.addPhysicalGroup(2, new_tag, tag=-1)
        gmsh.model.setPhysicalName(2, phys_group, porttag)
        port_surface_tags.extend(new_tag)

        # add ports to boundary for fine meshing also 
        for tag in new_tag:
            clt, ct = kernel.getCurveLoops(tag)
            for curvetag in ct:
                boundary_line_tags.extend(curvetag)     

        # config file
        if len(new_tag) > 0:
            Palace_lumpedport = {}
            portnum = int(porttag.replace('P',''))
            port = simulation_ports.get_port_by_number(portnum)

            # find in which excitation group the port is, defaults to boolean false
            excite_group = False
            for idx, group in enumerate(excite_ports):
                if portnum in group:
                    excite_group = idx + 1

            Palace_lumpedport['Index'] = portnum
            Palace_lumpedport['R'] = port.port_Z0
            Palace_lumpedport['Direction'] = port.direction.upper()
            Palace_lumpedport['Excitation'] = excite_group
            Palace_lumpedport['Attributes']=[phys_group]
            Palace_lumpedports.append(Palace_lumpedport)


    # 2D surfaces from 2D thin sheets in metals section 
    # One physical group for each sheet (resistor) polygon
    all_sheet_surface_tags = [] # global list across all sheet layer surfaces
    for layername in sheet_tags_created_2D.keys():
        sheet_surface_tags_for_layer = []  # list for this layer only
        sheettag_list = sheet_tags_created_2D[layername]
        if len(sheettag_list) > 0:
            i = 0
            for surface in sheettag_list:
                i = i +1
                surfacetag = surface[1]
                new_tags = get_tag_after_fragment (surfacetag, geom_dimtags, geom_map, dimension=2)

                # add sheet tags for boundary meshing also
                for tag in new_tags:
                    clt, ct = kernel.getCurveLoops(tag)
                    for curvetag in ct:
                        boundary_line_tags.extend(curvetag)     

                phys_group = gmsh.model.addPhysicalGroup(2, new_tags, tag=-1)
                gmsh.model.setPhysicalName(2, phys_group, layername + '_' + str(i))
                sheet_surface_tags_for_layer.append(phys_group)

            all_sheet_surface_tags.extend(sheet_surface_tags_for_layer)

        # Palace config file

        if len(sheet_surface_tags_for_layer) > 0:
            Palace_impedance = {}
            metal = metals_list.getbylayername(layername)
            if metal is not None:
                stackup_material = materials_list.get_by_name(metal.material)
                if stackup_material is not None:
                    Palace_impedance['Attributes']=sheet_surface_tags_for_layer
                    Palace_impedance['Rs']=stackup_material.Rs
                    Palace_impedances.append(Palace_impedance) # append to global list



    kernel.synchronize()



    # get surface tags of airbox 
    airbox_volume_tag = dielectric_tags_created_3D['airbox'] 
    airbox_volume_tag = get_tag_after_fragment (airbox_volume_tag, geom_dimtags, geom_map, dimension=3)
    airbox_volume_tag = airbox_volume_tag[0]

    _, simulation_boundary = kernel.getSurfaceLoops(airbox_volume_tag)
    simulation_boundary = next(iter(simulation_boundary))

    PEC_boundaries = []
    PML_boundaries = []
    PMC_boundaries = []
    # re-order boundary condition after fragmenting

    if len(simulation_boundary)==6:
        bc = [boundary_condition[0],boundary_condition[2],boundary_condition[5],boundary_condition[3],boundary_condition[4],boundary_condition[1]]
        for idx, boundary in enumerate (simulation_boundary):
            if bc[idx] == 'PEC':
                PEC_boundaries.append(boundary)
            elif bc[idx] == 'PML' or bc[idx] == 'ABC':    
                PML_boundaries.append(boundary)
            elif bc[idx] == 'PMC':    
                PMC_boundaries.append(boundary)
            else:
                print('Error: Boundary condition ', boundary_condition[idx],' is not supported. Use ABC, PML, PEC or PMC only.')    
                exit(1)
    else:
        print('Invalid simulation boundary, the surrounding air margin must be > 0 on all six sides!')
        exit(0)


    phys_group_PML = gmsh.model.addPhysicalGroup(2, PML_boundaries, tag=-1)
    gmsh.model.setPhysicalName(2, phys_group_PML, 'Absorbing boundary')

    phys_group_PEC = gmsh.model.addPhysicalGroup(2, PEC_boundaries, tag=-1)
    gmsh.model.setPhysicalName(2, phys_group_PEC, 'PEC boundary')

    phys_group_PMC = gmsh.model.addPhysicalGroup(2, PMC_boundaries, tag=-1)
    gmsh.model.setPhysicalName(2, phys_group_PMC, 'PMC boundary')


    # config file entry for absorbing simulation boundary (we have no real PML yet, use 2nd order absorbing)
    Palace_absorbing_boundaries = {}
    Palace_absorbing_boundaries['Attributes']=[phys_group_PML] # absorbing simulation_boundary
    Palace_absorbing_boundaries['Order']=2 

    # config file entry for PEC simulation boundary
    Palace_PEC_boundaries = {}
    Palace_PEC_boundaries['Attributes']=[phys_group_PEC] # PEC simulation_boundary

    # config file entry for PEC simulation boundary
    Palace_PMC_boundaries = {}
    Palace_PMC_boundaries['Attributes']=[phys_group_PMC] # PMC simulation_boundary


    boundaries['Conductivity']= Palace_conductors
    boundaries['LumpedPort'] = Palace_lumpedports
    if len(Palace_impedances) > 0:
        boundaries['Impedance']   = Palace_impedances
    if len(PML_boundaries) > 0:
        boundaries['Absorbing']   = Palace_absorbing_boundaries
    if len(PEC_boundaries) > 0:
        boundaries['PEC']   = Palace_PEC_boundaries
    if len(PMC_boundaries) > 0:
        boundaries['PMC']   = Palace_PMC_boundaries


    config_data['Boundaries'] = boundaries



    # write JSON simulation config file now, so that we can verify it while geometry is open in gmsh GUI
    with open(config_name, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, ensure_ascii=False, indent=4)
    f.close()

    # write JSON with port information to Palace outputmodel directory
    port_information_file = os.path.join(sim_path, 'port_information' + config_suffix + '.json')
    with open(port_information_file, 'w', encoding='utf-8') as f:
        json.dump(all_port_information_struct, f, ensure_ascii=False, indent=4)
    f.close()

    
    if save_gmsh_geometry:
        # write "raw" geometry with no mesh, so that we can open in gmsh
        gmsh.write(geo_name)

    # open gmsh GUI with unmeshed geometry
    if not no_gui:
        gmsh.fltk.run()



    # -------------- MESH ------------------

    # MESH IN SILICON
    # 
    # We want to add some higher mesh density at the upper end of silicon
    # To do so, we need to get the z position of the topmost semiconductor

    z_semi = -math.inf  # maximum z position for semiconductors in stackup, default at minus infinity

    # dielectrics from stackup
    for dielectric in dielectrics_list.dielectrics:
        # get CSX material object for this dielectric layers material name
        materialname = dielectric.material
        material = materials_list.get_by_name(materialname)
        
        if material.sigma > 0:
            z_semi = max(z_semi, dielectric.zmax)


    # MESH AT CONDUCTORS (SURFACES)
    # 
    # Say we would like to obtain mesh elements with size lc/30 near curve 2 and
    # point 5, and size lc elsewhere. To achieve this, we can use two fields:
    # "Distance", and "Threshold". We first define a Distance field (`Field[1]') on
    # points 5 and on curve 2. This field returns the distance to point 5 and to
    # (100 equidistant points on) curve 2.
    gmsh.model.mesh.field.add("Distance", 1)
    gmsh.model.mesh.field.setNumbers(1, "CurvesList", boundary_line_tags) 
    gmsh.model.mesh.field.setNumber(1, "Sampling", 200)

    fields_list = []

    # We then define a `Threshold' field, which uses the return value of the
    # `Distance' field 1 in order to define a simple change in element size
    # depending on the computed distances
    #
    # SizeMax -                     /------------------
    #                              /
    #                             /
    #                            /
    # SizeMin -o----------------/
    #          |                |    |
    #        Point         DistMin  DistMax
    gmsh.model.mesh.field.add("Threshold", 2)
    gmsh.model.mesh.field.setNumber(2, "InField", 1)  # number of this field definition
    gmsh.model.mesh.field.setNumber(2, "SizeMin", refined_cellsize)
    gmsh.model.mesh.field.setNumber(2, "SizeMax", max_cellsize_air)
    gmsh.model.mesh.field.setNumber(2, "DistMin", 0)
    gmsh.model.mesh.field.setNumber(2, "DistMax", max_cellsize_air)

    fields_list.append(2)

   
    # Optional refinement of mesh at the upper end of the semiconductor

    if z_semi>0 and substrate_refinement:
        # xy dimensions of dielectric boxes from stackup
        x1 = allpolygons.get_xmin() 
        y1 = allpolygons.get_ymin()
        x2 = allpolygons.get_xmax()
        y2 = allpolygons.get_ymax()

        refine_layer_thickness = max(30*refined_cellsize,z_semi/2)
        refine_value = min(10*refined_cellsize, 20)

        # semiconductor with eps_r = 11.9
        max_cellsize_local = min(max_cellsize_air/math.sqrt(11.9), meshsize_max)

        gmsh.model.mesh.field.add("Box", 6)
        gmsh.model.mesh.field.setNumber(6, "VIn",  refine_value)
        gmsh.model.mesh.field.setNumber(6, "VOut", max_cellsize_local)
        gmsh.model.mesh.field.setNumber(6, "XMin", x1)
        gmsh.model.mesh.field.setNumber(6, "XMax", x2)
        gmsh.model.mesh.field.setNumber(6, "YMin", y1)
        gmsh.model.mesh.field.setNumber(6, "YMax", y2)
        gmsh.model.mesh.field.setNumber(6, "ZMin", z_semi-refine_layer_thickness)
        gmsh.model.mesh.field.setNumber(6, "ZMax", z_semi)

        fields_list.append(6)


    # Iterate over dielectric and set max_cellsize in medium according to permittivity
    i = 10
    for dielectric in dielectrics_list.dielectrics:
        # get CSX material object for this dielectric layers material name
        materialname = dielectric.material
        material = materials_list.get_by_name(materialname)
        permittivity = material.eps

        max_cellsize_local = min(max_cellsize_air/math.sqrt(permittivity), meshsize_max)
        print('Dielectric ',materialname, ' with max_cellsize_local = ', max_cellsize_local, 'units' )

        if dielectric.gdsboundary is None:
            # size of dielectric is global size, no boundary defined for this layer
            x1 = allpolygons.get_xmin() - margin
            y1 = allpolygons.get_ymin() - margin
            x2 = allpolygons.get_xmax() + margin
            y2 = allpolygons.get_ymax() + margin
        else:
            # size of dielectric is defined for this layer by polygon from gds
            bound_layernum = int(dielectric.gdsboundary) 
            bbox_xmin, bbox_xmax, bbox_ymin, bbox_ymax = allpolygons.bounding_box.get_layer_bounding_box(bound_layernum)
       
            x1 = bbox_xmin - margin
            y1 = bbox_ymin - margin
            x2 = bbox_xmax + margin
            y2 = bbox_ymax + margin

        # add local mesh size according to permittivity
        gmsh.model.mesh.field.add("Box", i)
        gmsh.model.mesh.field.setNumber(i, "VIn",  max_cellsize_local) # inside
        gmsh.model.mesh.field.setNumber(i, "VOut", max_cellsize_air) # outside
        gmsh.model.mesh.field.setNumber(i, "XMin", x1)
        gmsh.model.mesh.field.setNumber(i, "XMax", x2)
        gmsh.model.mesh.field.setNumber(i, "YMin", y1)
        gmsh.model.mesh.field.setNumber(i, "YMax", y2)
        gmsh.model.mesh.field.setNumber(i, "ZMin", dielectric.zmin)
        gmsh.model.mesh.field.setNumber(i, "ZMax", dielectric.zmax)

        fields_list.append(i)
        i = i + 1


    # Let's use the minimum of all the fields as the mesh size field:
    gmsh.model.mesh.field.add("Min", i)
    gmsh.model.mesh.field.setNumbers(i, "FieldsList", fields_list)

    gmsh.model.mesh.field.setAsBackgroundMesh(i)



    # The API also allows to set a global mesh size callback, which is called each
    # time the mesh size is queried
    def meshSizeCallback(dim, tag, x, y, z, lc):
        return min(max(lc/refined_cellsize, (lc/refined_cellsize)**1.5), max_cellsize)

    # gmsh.model.mesh.setSizeCallback(meshSizeCallback)

    # When the element size is fully specified by a mesh size field (as it is in
    # this example), it is thus often desirable to set

    gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
    gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 0)
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)

    # This will prevent over-refinement due to small mesh sizes on the boundary.

    # Finally, while the default "Frontal-Delaunay" 2D meshing algorithm
    # (Mesh.Algorithm = 6) usually leads to the highest quality meshes, the
    # "Delaunay" algorithm (Mesh.Algorithm = 5) will handle complex mesh size fields
    # better - in particular size fields with large element size gradients:


    gmsh.option.setNumber("Mesh.Algorithm", 5)


    gmsh.model.mesh.generate(3)

    # Save mesh
    gmsh.option.setNumber("Mesh.Binary", 0)
    gmsh.option.setNumber("Mesh.SaveAll", 0)  # value 1 means: save everything, no matter if in physical group or not - DON'T USE WITH V2.2
    gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)  # Palace requires mesh version 2.2!

    # write meshed geometry
    gmsh.write(msh_name)
    # show meshed model in gmsh GUI
    if not no_gui:
        gmsh.fltk.run()
    
    gmsh.clear()
    gmsh.finalize()

    return config_name, data_dir



# Utility functions for hash file.
# Not used by gds2palace yet

def calculate_sha256_of_file(filename):
    import hashlib
    sha256_hash = hashlib.sha256()
    with open(filename, 'rb') as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    return sha256_hash.hexdigest()

def write_hash_to_data_folder (excitation_path, hash_value):
    filename = os.path.join(excitation_path, 'simulation_model.hash')
    hashfile = open(filename, 'w')
    hashfile.write(str(hash_value))
    hashfile.close() 

def get_hash_from_data_folder (excitation_path):
    filename = os.path.join(excitation_path, 'simulation_model.hash')
    hashvalue = ''
    if os.path.isfile(filename):
        hashfile = open(filename, "r")
        hashvalue = hashfile.read()
        hashfile.close()
    return hashvalue


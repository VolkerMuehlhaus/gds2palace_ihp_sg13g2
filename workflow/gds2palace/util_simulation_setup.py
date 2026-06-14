########################################################################
#
# Copyright 2025-2026 Volker Muehlhaus and IHP PDK Authors
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

__version__ = "1.4.0"

import os
import sys
import gmsh
import math
import numpy as np
import json

from . import util_elmer 


class simulation_port:
  """
    port object
    for in-plane port, parameter target_layername is specified
    for via port, parameters from_layername and to_layername are specified for the metals above and below   
  """
  
  def __init__ (self, portnumber, voltage, port_Z0, source_layernum, target_layername=None, from_layername=None, to_layername=None, direction='x'):
    """create new simulation port

    Args:
        portnumber (int): port number
        voltage (float): port voltage, 0 if not excited
        port_Z0 (float): port impedance
        source_layernum (int): layer number in layout with port shape
        target_layername (string, optional): Target layer name for in-plane port. Defaults to None.
        from_layername (string, optional): Start layer name for via port. Defaults to None.
        to_layername (string, optional): End layer name for via port. Defaults to None.
        direction (str, optional): port direction. Defaults to 'x'.
    """
    self.portnumber = portnumber
    self.source_layernum = source_layernum        # source for port geometry is a GDSII layer, just one port per layer
    self.target_layername = target_layername      # target layer where we create the port, if specified we create in-plane port
    self.from_layername  = from_layername         # layer on one end of via port, used if target_layername is None
    self.to_layername    = to_layername           # layer on other  end of via port
    self.direction  = direction

    # check if layer assignment matches specified direction
    via_port = ("Z" in direction.upper()) and (from_layername is not None) and (to_layername is not None)
    in_plane_port = ("X" in direction.upper() or "Y" in direction.upper()) and (target_layername is not None)
    if not (via_port or in_plane_port):
        print(f'ERROR: Port {portnumber} definition is invalid, port direction does not match from/to/target layer!')
        print('        Valid port configurations:')
        print('        direction x, -x- y, -y with target_layername')
        print('        direction z, -z with from_layername and to_layername')
        exit(1)
        
    
    self.port_Z0 = port_Z0
    self.voltage = voltage
    self.CSXport = None

  def set_CSXport (self, CSXport):
    """Not used for Palace
    """
    self.CSXport = CSXport  

  def __str__ (self):
    """Create string representation of port, useful for debugging
    Returns:
        string: string representation of polygon data
    """
    mystr = 'Port ' + str(self.portnumber) + ' voltage = ' + str(self.voltage) + ' GDS source layer = ' + str(self.source_layernum) + ' target layer = ' + str(self.target_layername) + ' direction = ' + str(self.direction)
    return mystr
  

class all_simulation_ports:
  """
  all simulation ports object, provides .ports (list), .portcount (int) and portlayers (list)
  """
  
  def __init__ (self):
      """Initialize new data structure that holds all port data
      """
      self.ports = []
      self.portcount = 0
      self.portlayers = []


  def add_port (self, port):
      """Add ports
      Args:
          port (simulation_port): simulation_port instance to be added
      """
      # check if we already have that port number in list
      existing = self.get_port_by_number(port.portnumber)
      if existing is not None:
        print(f'ERROR: Port {port.portnumber} already exists, check for duplicate port definitions!')
        exit(1)

      self.ports.append(port)
      self.portcount = len(self.ports)
      self.portlayers.append(port.source_layernum)


  def get_port_by_layernumber (self, layernum):   
      """Get port from layer number. Numbers are unique, one port per layer, so we have 1:1 mapping
      Args:
          layernum (int): layer number in layout
      Returns:
          simulation_port: port defined with that layer number
      """
      found = None
      for port in self.ports:
          if port.source_layernum == layernum:
              found = port
              break
      return found       
  

  def get_port_by_number (self, portnum):
      """Get simulation_port instance by port number
      Args:
          portnum (integer): port number used when creating port definition
      Returns:
          simulation_port: port to be found
      """
      found = None
      for port in self.ports:
          if port.portnumber == portnum:
              found = port
              break
      return found       


  def apply_layernumber_offset (self, offset):
      """Apply layer number offset to all ports
      Args:
          offset (int): offset
      """
      newportlayers = []    
      for port in self.ports:
          port.source_layernum = port.source_layernum + offset
          newportlayers.append(port.source_layernum)
      self.portlayers = newportlayers      


  def all_active_excitations (self):
    """Get all active port excitations, i.e. ports with voltage other than zero
    Returns:
        list of simulation_port: active port instances
    """

    numbers = []
    for port in self.ports:
        if abs(port.voltage) > 1E-6:
            # skip zero voltage ports for excitation
            # append as list, we need that for create_palace() function
            numbers.append([port.portnumber])
    return numbers



def get_layer_volumes (metals_list, layername):
    """return all volume dimtags for a given  layer name, preselect by z position and z height, then check name of gmsh entity

    Args:
        metals_list: metals list from stackup reader
        layername (string): layer name as used in XML stackup file

    Returns:
        list of dimtags: volumes for that layer name
    """
    # return all volume tags for a given  layer name, 
    # preselect by z position and z height, then check name of gmsh entity

    this_metal = metals_list.getbylayername(layername)
    
    # get volumes on this layer
    delta = 0.001
    layer_zmin = this_metal.zmin - delta/2
    layer_zmax = this_metal.zmax + delta/2
        
    # This returns the list of volumes inside
    volumes_in_bounding_box = gmsh.model.getEntitiesInBoundingBox(-math.inf,-math.inf,layer_zmin,math.inf,math.inf,layer_zmax,3)
    volume_on_layer_list = []
    for volume in volumes_in_bounding_box:
        name_assigned = gmsh.model.getEntityName(dim=3,tag=volume[1])
        if name_assigned == layername:
            volume_on_layer_list.append(volume)
    return  volume_on_layer_list



def get_layer_sheets (metals_list, layername):
    """return all 2D dimtags for a given  layer name, preselect by z position and z height, then check name of gmsh entity

    Args:
        metals_list: metals list from stackup reader
        layername (string): layer name as used in XML stackup file

    Returns:
        list of dimtags: surfaces for that layer name
    """

    this_metal = metals_list.getbylayername(layername)
    
    # get volumes on this layer
    delta = 0.001
    layer_zmin = this_metal.zmin - delta/2
    layer_zmax = this_metal.zmin + delta/2  # expect sheet resistors at zmin!
        
    # This returns the list of sheets inside
    sheets_in_bounding_box = gmsh.model.getEntitiesInBoundingBox(-math.inf,-math.inf,layer_zmin,math.inf,math.inf,layer_zmax,2)
    sheets_on_layer_list = []
    for sheet in sheets_in_bounding_box:
        name_assigned = gmsh.model.getEntityName(dim=2,tag=sheet[1])
        if name_assigned == layername:
            sheets_on_layer_list.append(sheet)
    return  sheets_on_layer_list


def create_surface_from_polygon (poly, zposition, meshseed):

    """create surface from single polygon at the given z position

    Returns:
        dimtag of created surface
    """

    # add Polygon to gmsh using poly.pts
    linetaglist = []
    vertextaglist = []
    numvertices = len(poly.pts_x)

    # store vertex info for debugging
    debug_vertices = False
    if debug_vertices: 
        vertex_info = {}
    
    for v in range(numvertices):
        # addPoint parameters: x (double), y (double), z (double), meshSize = 0. (double), tag = -1 (integer)
        vertextag = gmsh.model.occ.addPoint(poly.pts_x[v], poly.pts_y[v], zposition, meshseed, -1)
        vertextaglist.append(vertextag)
        if debug_vertices: 
            vertex_info[vertextag] = f"x={poly.pts_x[v]} y={poly.pts_y[v]}"

    # after writing the vertices, we combine them to boundary lines
    for v in range(numvertices):
        pt_start = vertextaglist[v]
        if v==(numvertices-1):
            pt_end = vertextaglist[0]
        else:
            pt_end = vertextaglist[v+1]

        # addLine parameters: startTag (integer), endTag (integer), tag = -1 (integer)
        try:
            linetag = gmsh.model.occ.addLine(pt_start, pt_end, -1)
            linetaglist.append(linetag)
        except:
            if debug_vertices: 
                print(f"skipping invalid line on layer {poly.layernum} ")
                print("  pt_start: ", str(pt_start), " -> ", vertex_info[pt_start])
                print("  pt_end: ", str(pt_end), " -> ", vertex_info[pt_end])


    # after creating the lines, we can create a curve loop and a surface 
    # to do so, we need the line segment numbers again
    curvetag   = gmsh.model.occ.addCurveLoop(linetaglist, tag=-1)
    surfacetag = gmsh.model.occ.addPlaneSurface([curvetag], tag=-1)

    return surfacetag


def add_metal_volumes (allpolygons, metals_list, meshseed=0):
    """Add drawn geometries from layout layers to gmsh as 3D volumes

    Args:
        allpolygons (all_polygons_list): instance of all_polygons_list from reading GDSII
        metals_list (_type_): instance of metals_list from reading stackup XML file
        meshseed (float, optional): Mesh seed to apply at polygon vertices. Defaults to 0.

    Returns:
        list of created tags
    """

    metal_dimtags_created_3D = []
    metal_dimtags_created_sheetlayer = []

    # add geometries on metal and via layers (volume only, excluding thin sheets)
    for poly in allpolygons.polygons:
        # each poly knows its layer number

        # We might have one layout polygon mapped to multiple layers in stackup, for special use cases in MIM etc
        # We then  have multiple entries in the XML that share the same layer number
        # For that special case, get ALL metals from technology file for that same polygon
        all_assigned = metals_list.getallbylayernumber (poly.layernum) 
        if all_assigned is not None:
            for metal_layer in all_assigned:  
                layername = metal_layer.name

                surfacetag = create_surface_from_polygon (poly, metal_layer.zmin, meshseed)
                
                if not (metal_layer.is_sheet):
                    if metal_layer.thickness > 0:
                        out = gmsh.model.occ.extrude([(2,surfacetag)],0,0,metal_layer.thickness)
                        tag = out[1][1]
                        # set name of metal layer to extruded volume
                        # we also use that to identify the volumes later
                        gmsh.model.setEntityName(dim=3,tag=tag, name=layername)
                else:
                    # sheet metal
                    gmsh.model.setEntityName(dim=2,tag=surfacetag, name=layername)
    

    # Try removing duplicates at this stage
    # gmsh.model.occ.removeAllDuplicates()  # <<<<<< This also splits overlapping polygons into separare items that loose their EntityName, don't do this!!!!
    gmsh.model.occ.synchronize()
        

    # We have created initial 3D volumes from GDSII, now iterate over 3D entities to merge them
    volumelist = gmsh.model.getEntities(3)
    volumecount = len(volumelist)
    if volumecount>0:
        # try to merge volumes on each layer
        for metal_layer in metals_list.metals:
            if not metal_layer.is_sheet:            
                # try to merge planar metal volumes
                layername = metal_layer.name
                volume_on_layer_list = get_layer_volumes(metals_list, layername)

                if metal_layer.is_via:
                    # no merge 
                    metal_dimtags_created_3D.extend(volume_on_layer_list)
                else:

                    # try boolean union of volumes on this layer
                    if len(volume_on_layer_list)>1:
                        # get first element and delete from list
                        first = volume_on_layer_list.pop(0)
                        # print('  Layer = ' + layername)
                        # print('  FUSE, object = ' + str(first)) 
                        # print('  FUSE, tool   = ' + str(volume_on_layer_list)) 

                        out = gmsh.model.occ.fuse(volume_on_layer_list,[first], -1)
                        gmsh.model.occ.synchronize()

                        # set name for fused volumes
                        volume_dimtags = out[0] # TODO: check for complex cases

                        for volume_dimtag in volume_dimtags:
                            gmsh.model.setEntityName(dim=3,tag=volume_dimtag[1], name=layername)
                        metal_dimtags_created_3D.extend(volume_dimtags)
                        gmsh.model.occ.synchronize()

                    elif len(volume_on_layer_list)==1:
                        # single volume on layer
                        dim, tag = volume_on_layer_list[0]
                        gmsh.model.setEntityName(dim=3,tag=tag, name=layername)
                        metal_dimtags_created_3D.extend(volume_on_layer_list)
                        gmsh.model.occ.synchronize()
                   

    # Get tags of sheet metals (resistors)
    for metal_layer in metals_list.metals:
        if metal_layer.is_sheet:            
            layername = metal_layer.name
            sheet_on_layer_list = get_layer_sheets(metals_list, layername)
            metal_dimtags_created_sheetlayer.extend(sheet_on_layer_list)


    
    return metal_dimtags_created_3D, metal_dimtags_created_sheetlayer
    


def create_box_with_meshseed (xmin,ymin,zmin,xmax,ymax,zmax, meshseed):
    """Create a box with given value for mesh seed
    Returns:
        tag of created volume (integer)
    """
    pt1 = gmsh.model.occ.addPoint(xmin, ymin, zmin, meshseed, -1)
    pt2 = gmsh.model.occ.addPoint(xmin, ymax, zmin, meshseed, -1)
    pt3 = gmsh.model.occ.addPoint(xmax, ymax, zmin, meshseed, -1)
    pt4 = gmsh.model.occ.addPoint(xmax, ymin, zmin, meshseed, -1)
    
    line1 = gmsh.model.occ.addLine(pt1,pt2,-1) 
    line2 = gmsh.model.occ.addLine(pt2,pt3,-1) 
    line3 = gmsh.model.occ.addLine(pt3,pt4,-1) 
    line4 = gmsh.model.occ.addLine(pt4,pt1,-1) 
    linetaglist = [line1, line2, line3, line4]

    # after creating the lines, we can create a curve loop and a surface 
    # to do so, we need the line segment numbers again
    curvetag   = gmsh.model.occ.addCurveLoop(linetaglist, tag=-1)
    surfacetag = gmsh.model.occ.addPlaneSurface([curvetag], tag=-1)    
    returnval  = gmsh.model.occ.extrude([(2,surfacetag)],0,0,zmax-zmin)
    volumetag = returnval[1][1]

    return volumetag


def add_dielectrics (materials_list, dielectrics_list, gds_layers_list, allpolygons, margin, air_around, refined_cellsize):
    """
    Add dielectric layers (these extend through simulation area and have no polygons in GDSII)
    
    :param materials_list: from stackup reader
    :param dielectrics_list: from stackup reader
    :param gds_layers_list: from gds reader
    :param allpolygons: from gds reader
    :param margin: spacing to add from metal bounding box to dielectric boundary
    :param air_around: air margin between dielectric and simulation boundary. Can be float or a list of 6 float values.
    :param refined_cellsize: refined_cellsize parameter set by user
    """    
# 

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

    # air_around can be specified as single value or array, check what we have here
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


    # check if we have at least one dielectric layer in stackup
    if len(dielectrics_list.dielectrics) == 0:
        print('ERROR: There are no dielectric layers defined in "ELayers > Dielectrics" section of XML stackup file. Aborting now.')
        exit(1)


    # dielectrics from stackup
    for dielectric in dielectrics_list.dielectrics:

        # get CSX material object for this dielectric layer
        dielectricname = dielectric.name
        
        # tag managment: get list of tags for this materialname
        if dielectricname in tags_created_3D.keys():
            layer_tags_3D = tags_created_3D[dielectricname]                   
        else:
            layer_tags_3D = []
            tags_created_3D[dielectricname] = layer_tags_3D 


        # xy dimensions of dielectric boxes from stackup
        if dielectric.gdsboundary is None:
            # dielectric with bounding box from all polygons
            bbox_xmin, bbox_xmax, bbox_ymin, bbox_ymax = allpolygons.get_bounding_box()
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
    
        box_tag = create_box_with_meshseed (x1, y1, dielectric.zmin, x2, y2, dielectric.zmax, meshseed)
        gmsh.model.setEntityName(dim=3,tag=box_tag, name= dielectricname)
        tags_created_3D[dielectricname].append(box_tag)



    # identify airbox
    tool_tags = []
    for key in tags_created_3D.keys():
        if key != 'airbox':
            tags = tags_created_3D[key]
            for tag in tags:
                tool_tags.append((3,tag))
    

    # Fragment dielectrics to clean up touching surfaces, tags will not change here
    _, geom_map = gmsh.model.occ.fragment(tool_tags, [])   
    gmsh.model.occ.synchronize()

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

        # we have no dielectrics, but we need to get get xy size of drawing
        x1 = allpolygons.get_xmin() - air_xmin
        y1 = allpolygons.get_ymin() - air_ymin
        x2 = allpolygons.get_xmax() + air_xmax
        y2 = allpolygons.get_ymax() + air_ymax

    box_tag = gmsh.model.occ.addBox(x1,y1,z1,x2-x1,y2-y1,z2-z1)
    
    # apply a boolean difference to create the "airbox minus others" shape:
    out = gmsh.model.occ.cut([(3, box_tag)], tool_tags, -1, removeTool=False)
    box_tag = out[0][0][1]
    gmsh.model.setEntityName(dim=3,tag=box_tag, name= 'airbox')
    gmsh.model.occ.synchronize()

    tags_created_3D['airbox'] = [box_tag]
 
    return tags_created_3D



def add_ports (allpolygons, metals_list, simulation_ports, meshseed = 0):
    """Add ports from special port layers to gmsh

    Args:
        allpolygons (all_polygons_list): from gds reader
        metals_list (metal_layers_list): from XML stackup reader
        simulation_ports (all_simulation_ports): all simulation ports object, provides .ports (list), .portcount (int) and portlayers (list)
        meshseed (float, optional): Mesh see at polygon edges. Defaults to 0.

    Returns:
       list of port dimtags, struct with port details
    """

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
                        pt1 = gmsh.model.occ.addPoint(xmin, ymin, zmin, meshseed, -1)
                        pt2 = gmsh.model.occ.addPoint(xmin, ymax, zmin, meshseed, -1)
                        pt3 = gmsh.model.occ.addPoint(xmax, ymax, zmin, meshseed, -1)
                        pt4 = gmsh.model.occ.addPoint(xmax, ymin, zmin, meshseed, -1)

                        # port information that we write to Palace output directory
                        if 'X' in port.direction.upper():
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
                            pt1 = gmsh.model.occ.addPoint(xmin, ymin, zmin, meshseed, -1)
                            pt2 = gmsh.model.occ.addPoint(xmin, ymax, zmin, meshseed, -1)
                            pt3 = gmsh.model.occ.addPoint(xmin, ymax, zmax, meshseed, -1)
                            pt4 = gmsh.model.occ.addPoint(xmin, ymin, zmax, meshseed, -1)
                            width = size_y
                       else: 
                            # ports are line in x direction
                            pt1 = gmsh.model.occ.addPoint(xmin, ymin, zmin, meshseed, -1)
                            pt2 = gmsh.model.occ.addPoint(xmin, ymin, zmax, meshseed, -1)
                            pt3 = gmsh.model.occ.addPoint(xmax, ymin, zmax, meshseed, -1)
                            pt4 = gmsh.model.occ.addPoint(xmax, ymin, zmin, meshseed, -1)
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
                    line1 = gmsh.model.occ.addLine(pt1,pt2,-1) 
                    line2 = gmsh.model.occ.addLine(pt2,pt3,-1) 
                    line3 = gmsh.model.occ.addLine(pt3,pt4,-1) 
                    line4 = gmsh.model.occ.addLine(pt4,pt1,-1) 
                    linetaglist = [line1, line2, line3, line4]

                    # after creating the lines, we can create a curve loop and a surface 
                    # to do so, we need the line segment numbers again
                    curvetag   = gmsh.model.occ.addCurveLoop(linetaglist, tag=-1)
                    surfacetag = gmsh.model.occ.addPlaneSurface([curvetag], tag=-1)

                    port_dimtag.append(surfacetag)
                    tags_created_2D['P'+str(portnum)]=port_dimtag

    gmsh.model.occ.synchronize()

    all_port_information_struct = {}
    all_port_information_struct['ports'] = all_port_information

    return tags_created_2D, all_port_information_struct                    




######### end of function createSimulation ()  ##########

def create_elmer (excite_ports, settings):
    """Create output file for Elmer FEM. 

    Args:
        excite_ports (list of int): list of ports that are excited (active)
        settings (dict): simulation settings

    Returns:
        config_name(string), data_dir (string): create model files here
    """
    # configure for Elmer output
    settings['elmer']=True
    # now we can run main function
    config_name, data_dir = create_model (excite_ports, settings)
    return config_name, data_dir



def create_palace (excite_ports, settings):
    """Create output file for Palace

    Args:
        excite_ports (list of int): list of ports that are excited (active)
        settings (dict): simulation settings

    Returns:
        config_name(string), data_dir (string): create config.json and Palace result dir specified there
    """
    # the default is to create Palace output, but we can override this by settings['elmer']=True
    config_name, data_dir = create_model (excite_ports, settings)
    return config_name, data_dir
    



def create_model (excite_ports, settings):
    """Create output file for Palace or Elmer

    Args:
        excite_ports (list of int): list of ports that are excited (active)
        settings (dict): simulation settings

    Returns:
        config_name(string), data_dir (string): create config.json and Palace result dir specified there
    """

    def get_optional_setting (settings, key, default):
        # get setting that might exist, but is not required
        return settings.get(key, default)    

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
    unit = get_optional_setting (settings,'unit', 1e-6) # unit defaults to micron
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

    adaptive_sweep = get_optional_setting (settings, "adaptive_sweep", True)
    
    order = int(get_optional_setting (settings, "order", 2))  # order of FEM basis functions, default 2
    if (order < 1) or (order > 3):
        print('WARNING: Order of basis function must 1, 2 or 3.\nValue changed to default value order=2.')
        order = 2

    # optional iterative solver setting for Elmer
    iterative = get_optional_setting (settings, "iterative", False)
   
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

    # optional refined cellsize override per layer
    refined_cellsize_override = get_optional_setting (settings, "refined_cellsize_override", [])
    refined_cellsize_override_dict = {}
    # dictionary of override with key=layername, value = refined cellsize override for that layer
    for item in refined_cellsize_override:
        layername = item[0]
        value = item[1]
        refined_cellsize_override_dict[layername]=value

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
    preview_only = get_optional_setting (settings,'preview_only', False)   # show unmeshed geometry only  
    no_preview   = get_optional_setting (settings,'no_preview', False)   # don't show unmeshed geometry, immediately show meshed model

    geo_name = os.path.join(sim_path, model_basename + '.geo_unrolled')
    msh_name = os.path.join(sim_path, model_basename + '.msh')
    config_name = os.path.join(sim_path, 'config' + config_suffix + '.json')
    data_dir = 'output/' + model_basename 

    # optional output for Elmer FEM
    elmer = get_optional_setting(settings, 'elmer', False)
    
    # option model for Elmer thermal solver
    elmer_thermal = get_optional_setting (settings, "elmer_thermal", False)
    if elmer_thermal:
        elmer = True
    filled_metals = elmer_thermal # solid metals for thermal
    

    # optional multithreading for Elmer FEM because it requires modifies settings in case.sif file
    # (not used for Palace where multithreading is fully defined in external runs script)
    if elmer:
        ELMER_MPI_THREADS = util_elmer.get_ELMER_MPI_THREADS(settings)
   
   
    # parameter check
    # DC simulation gives errors for now, so replace that
    if fstart is not None:
        if fstart < 0.1e6:
            fstart = fstep # start sweep from next step
            # add low frequency to list of discrete frequencies, to replace 0 Hz from user input
            f_DC = 10e6
            f_discrete_list.append (f_DC)
            f_discrete_list.append (2*f_DC)
            print('WARNING: Start frequency changed from DC to ', f_DC/1e9, ' GHz!')


    # AdaptiveTol value enables adaptive frequency sweep, 0 means regular sweep (not adaptive)
    if adaptive_sweep:
        AdaptiveTol = 2e-2
    else:    
        AdaptiveTol = 0

    print('Starting to create mesh file and config file')

    fmax = 0
    if fstop is not None: 
        fmax = max(fmax, fstop)
    if len(f_discrete_list) > 0: 
        discrete_max = max(f_discrete_list) 
        fmax = max(fmax, discrete_max)

    wavelength_air = 3e8/fmax / unit
    # max_cellsize = min((wavelength_air)/(math.sqrt(materials_list.eps_max)*cells_per_wavelength), meshsize_max)
    max_cellsize_air = wavelength_air/cells_per_wavelength

    print("---------------------------------------------------")
    print(f"Wavelength in air: {wavelength_air:.1f} units")
    print(f"  meshsize_max: {meshsize_max:.1f}  units")
    print(f"  max_cellsize_air: {max_cellsize_air:.1f} units")
    print("---------------------------------------------------")
    
    gmsh.initialize()
    gmsh.option.setNumber("General.Verbosity", 5)

    # Define tolerance so that we don't tun into numerical precision issue
    # Our unit is in microns and the smallest real structure seems to be MIM dielectric thickness at 40 nm
    gmsh.option.setNumber("Geometry.Tolerance", 1e-3) # this should be 1nm


    # Add model, initialize
    if "from_gds" in gmsh.model.list():
        gmsh.model.setCurrent("from_gds")
        gmsh.model.remove()
    gmsh.model.add("from_gds")


    # create lookup dict to quickly check if we have a metal or a dielectric, and store tags
    # create lookup dict to quickly check if we have a dielectric stackup volume (not drawn in GDSII), and store tags
    metal_volume_dict = {}
    metal_surface_dict = {}
    metal_sheet_dict = {}
    dielectric_volume_dict = {}

    for metal in metals_list.metals:
        if metal.is_via:
            metal_volume_dict[metal.name] = []
        elif metal.is_dielectric: # drawn dielectric brick    
            dielectric_volume_dict[metal.name] = []
        elif metal.is_sheet: # sheet layer for resistor etc
            metal_sheet_dict[metal.name] = []
        else: 
            if not filled_metals:
                # regular case, planar metal will be represented at surfaces of hollow volumes
                metal_surface_dict[metal.name]=[] 
            else:
                # special case for thermal etc: make planar metals as volumes, not surface 
                metal_volume_dict[metal.name] = []
                     

    for dielectric in dielectrics_list.dielectrics:
        dielectric_volume_dict[dielectric.name]=[]

    # for the airbox surface, we use a list
    airbox_surface_taglist = []    


    # add drawn geometries to gmsh model

    print('Adding metal tags ...')
    # add as volume
    metal_dimtags_created_3D, sheetlayer_dimtags = add_metal_volumes (allpolygons, metals_list)

    # add dielectric boxes (oxide, substrate, air etc) to gmsh model
    print('Adding dielectrics ...')
    dielectric_tags_created_3D = add_dielectrics (materials_list, dielectrics_list, metals_list, allpolygons, margin, air_around, refined_cellsize=refined_cellsize)
    
    # separate metal and dielectric volumes
    dielectric_volume_dimtags = []
    for key in dielectric_tags_created_3D.keys():
        tags = dielectric_tags_created_3D[key]
        for tag in tags:
            dielectric_volume_dimtags.append((3, tag))

    # 3D volumes that are not a dielectric must be a drawn metal
    metal_volume_dimtags = []
    all_volume_dimtags = gmsh.model.getEntities(3)
    for volume_dimtag in all_volume_dimtags:
        if volume_dimtag not in dielectric_volume_dimtags:
            metal_volume_dimtags.append(volume_dimtag)


    # debugging
    '''
    missing_debug_log = "missing_tags.txt"
    if len(metal_volume_dimtags) != len(metal_dimtags_created_3D):
        print(f"We have a mismatch in metal volume count, {len(metal_volume_dimtags)} vs. {len(metal_dimtags_created_3D)} !")

        with open(missing_debug_log, "w") as file:
            for dimtag in metal_volume_dimtags:
                if dimtag not in metal_dimtags_created_3D:
                    file.write(f"{dimtag}\n")
        print(f"Missing dimtags written to file: missing_tags.txt")
        exit(2)
    else:
        if os.path.exists(missing_debug_log):
            os.remove(missing_debug_log)        
    '''        

    # cut metal volumes from dielectric volumes
    outDimTags, outDimTagsMap = gmsh.model.occ.cut(dielectric_volume_dimtags, metal_volume_dimtags, -1, removeTool=False)
    dielectric_tags_unchanged = (outDimTags==dielectric_volume_dimtags)
    assert dielectric_tags_unchanged

    gmsh.model.occ.synchronize()
    
    # Now embed/fragment metal and dielectric volumes, return value geom_map keeps mapping between original tags and new tags after fragmenting

    geom_dimtags = [x for x in gmsh.model.occ.getEntities(dim=3)]
    # create dict with names for each original volume
    original_volume_names_dict ={}
    for dim, tag in geom_dimtags:
        name = gmsh.model.getEntityName(dim=3,tag=tag)
        original_volume_names_dict[tag] = name


    _, geom_map = gmsh.model.occ.fragment(geom_dimtags, [])   
    gmsh.model.occ.synchronize()


    # restore names with possibly new tag numbers
    for n, new_dimtag_list in enumerate(geom_map):
        # we get a list with one or more new dimtags for each the original dimtag
        _, original_tag = geom_dimtags[n]
        name = original_volume_names_dict[original_tag]
        for _, newdimtag in new_dimtag_list:
            gmsh.model.setEntityName(dim=3,tag=newdimtag, name=name)

    gmsh.model.occ.synchronize()

    # dielectric volume dim tags have not changed, so all other volumes after fragmenting must be metal
    metal_volume_dimtags = []
    all_volume_dimtags = gmsh.model.getEntities(3)
    for volume_dimtag in all_volume_dimtags:
        if volume_dimtag not in dielectric_volume_dimtags:
            metal_volume_dimtags.append(volume_dimtag)    

    # add ports
    print('Adding ports ...')
    port_dimtags_created_2D, all_port_information_struct = add_ports (allpolygons, metals_list, simulation_ports)
    # create flat list of port dimtags
    port_tags = []
    for key in port_dimtags_created_2D.keys():
        for tag in port_dimtags_created_2D[key]:
            port_tags.append((2,tag))


    #  sheet metal tags, this is a flat list of dimtags, information on layer/material is only in sheet itself (getEntityName)
    geom_dimtags = [x for x in gmsh.model.occ.getEntities(dim=3)]
    geom_dimtags.extend(port_tags)
    geom_dimtags.extend(sheetlayer_dimtags)


    # fragment to insert 2D sheets into 3D volumes
    _, geom_map = gmsh.model.occ.fragment(geom_dimtags, [])   
    gmsh.model.occ.synchronize()


    # Restore port and sheet tags
    # restore names with possibly new tag numbers

    # Sheet tags
    restored_sheetlayer_dimtags = []
    for n, new_dimtag_list in enumerate(geom_map):
        # we get a list with one or more new dimtags for each the original dimtag
        original_tag = geom_dimtags[n]
        if original_tag in sheetlayer_dimtags:
            #  sheetlayer_dimtags is flat list, this is all we have for now, information on layer/material is only in sheet itself (getEntityName)
            restored_sheetlayer_dimtags.append(new_dimtag_list[0])
    sheetlayer_dimtags = restored_sheetlayer_dimtags


    # Port tags
    # The port might span across multiple dielectrics, then it will fall into multiple surfaces and we need all of them,
    for key in port_dimtags_created_2D.keys():
        for tag in port_dimtags_created_2D[key]:    
            for n, new_dimtag_list in enumerate(geom_map):
                original_dimtag = geom_dimtags[n]
                if tag==original_dimtag[1]:
                    newtags = []
                    # the port might span across multiple dielectrics, then it will fall into multiple surfaces and we need all of them
                    for dimtag in new_dimtag_list:
                        tag = dimtag[1]
                        newtags.append(tag)
                    port_dimtags_created_2D[key]=newtags
                    break



    # create dict for lookup of sheet metal layers and dimtags
    for dimtag in sheetlayer_dimtags:
        dim, tag = dimtag
        layername = gmsh.model.getEntityName(dim=2,tag=tag)
        metal_sheet_dict[layername].append(tag)



    # ----------------  ITERATE OVER VOLUMES AND PORTS TO CREATE PHYSICAL GROUPS -----------------

    # MESHING: Get list of boundary line tags of all metals, used to refine mesh along the edges

    # dictionary of boundary tags (for refinement) per layer, also used for port. Key is layername or port name.
    boundary_line_tags_dict = {}
    
    geom_dimtags = [x for x in gmsh.model.occ.getEntities(dim=3)]     
    for dim, tag in geom_dimtags:
        name = gmsh.model.getEntityName(dim=3,tag=tag)
        if name in metal_volume_dict.keys():
            metal_volume_dict[name].append(tag)
        elif name in metal_surface_dict.keys():
            # get all surfaces of 3d body
            _, surfaceloops = gmsh.model.occ.getSurfaceLoops(tag)
            metal_surface_dict[name].append(surfaceloops)    
        elif name in dielectric_volume_dict.keys():
            dielectric_volume_dict[name].append(tag)
        elif name == "airbox":
            dielectric_volume_dict['airbox']=[tag]
            # get all surfaces 
            _, surfaceloops = gmsh.model.occ.getSurfaceLoops(tag)
            for surfaceloop in surfaceloops:
                airbox_surface_taglist.append(surfaceloop) 
        else:
            # this should not happen
            print(f"Found volume tag {tag} with name '{name}' which can't be assigned, abort")
            if 'unknown' not in metal_volume_dict:
                metal_volume_dict['unknown'] = []
            metal_volume_dict['unknown'].append(tag)
            # exit(2)            


    # create lists where we store dictionaries with material name, physical group tag and physical group name
    physical_groups_3D = []
    physical_groups_2D = [] 
    physical_groups_ports = [] 

    # create physical group for metal volumes
    for key in metal_volume_dict.keys():
        volume_list = metal_volume_dict[key]
        if len(volume_list)>0:
            phys_group = gmsh.model.addPhysicalGroup(3, volume_list, tag=-1)
            gmsh.model.setPhysicalName(3, phys_group, key)    
            # store, used when creating solver config file
            physical_groups_3D.append({"layername":key, "groupname":key, "grouptag":phys_group })


    # create physical group for metal surfaces
    for key in metal_surface_dict.keys():
        surfaces_list = metal_surface_dict[key]
        if len(surfaces_list)>0:

            i=0
            for surfaces in surfaces_list:
                i=i+1

                # we want to separate surfaces into planar (xy) and vertical (z) 
                new_tags_planar = []
                new_tags_vertical = []

                all_tags = surfaces[0]
                for tag in all_tags:
                    if is_vertical_surface(tag):
                        new_tags_vertical.append(tag)
                    else:
                        new_tags_planar.append(tag)     

                # we now have separate lists for xy and z surfaces

                # xy in-plane
                if len(new_tags_planar)>0:
                    phys_group = gmsh.model.addPhysicalGroup(2, new_tags_planar, tag=-1)
                    group_name = f"{key}_{i}_xy"
                    gmsh.model.setPhysicalName(2, phys_group, group_name)            
                    # store, used when creating solver config file
                    physical_groups_2D.append({"layername":key+"_xy", "groupname":group_name, "grouptag":phys_group })

                # z vertical
                if len(new_tags_vertical)>0:
                    phys_group = gmsh.model.addPhysicalGroup(2, new_tags_vertical, tag=-1)
                    group_name = f"{key}_{i}_z"
                    gmsh.model.setPhysicalName(2, phys_group, group_name)            
                    # store, used when creating solver config file
                    physical_groups_2D.append({"layername":key+"_z", "groupname":group_name, "grouptag":phys_group })

                # add for edge mesh refinement also
                if key not in boundary_line_tags_dict.keys():
                    boundary_line_tags_dict[key]=[]
                for tag in all_tags:
                    clt, ct = gmsh.model.occ.getCurveLoops(tag)
                    for curvetag in ct:
                        boundary_line_tags_dict[key].extend(curvetag)     


    # create physical group for dielectric stackup volumes
    for key in dielectric_volume_dict.keys():
        volume_list = dielectric_volume_dict[key]
        if len(volume_list)>0:
            phys_group = gmsh.model.addPhysicalGroup(3, volume_list, tag=-1)
            gmsh.model.setPhysicalName(3, phys_group, key)            
            # store, used when creating solver config file
            physical_groups_3D.append({"layername":key, "groupname":key, "grouptag":phys_group })


    # create physical groups for metal sheet layers (resistors)
    for key in metal_sheet_dict.keys():
        surface_list = metal_sheet_dict[key]
        if len(surface_list)>0:
            phys_group = gmsh.model.addPhysicalGroup(2, surface_list, tag=-1)
            gmsh.model.setPhysicalName(2, phys_group, key)            
            # store, used when creating solver config file
            physical_groups_2D.append({"layername":key, "groupname":key, "grouptag":phys_group })            


    # create physical group for port surfaces
    for key in port_dimtags_created_2D.keys():
        porttag_list = port_dimtags_created_2D[key]
        phys_group = gmsh.model.addPhysicalGroup(2, porttag_list, tag=-1)
        gmsh.model.setPhysicalName(2, phys_group, key)               
        # store, used when creating solver config file
        physical_groups_ports.append({"layername":"Port", "groupname":key, "grouptag":phys_group })
        
        # add for edge mesh refinement also
        if key not in boundary_line_tags_dict.keys():
            boundary_line_tags_dict[key]=[]
        for tag in porttag_list:
            try:
                clt, ct = gmsh.model.occ.getCurveLoops(tag)
                for curvetag in ct:
                    boundary_line_tags_dict[key].extend(curvetag)     
            except:
                print(f"Exception when assigning surface for port {key}, possible overlap of port and metal.\nCheck if port from/to/target layers are correct!")        
                exit(1)



    gmsh.model.occ.synchronize()
    # gmsh.fltk.run()

    # ----------------  PORT CONFIG METADATA JSON FILE -----------------

    # we start from all_port_information_struct metadata that was created by add_ports() above

    # add units to port information
    all_port_information_struct['unit'] = unit
    # add model name
    all_port_information_struct['name'] = model_basename

    # write JSON with port information to Palace outputmodel directory
    port_information_file = os.path.join(sim_path, 'port_information' + config_suffix + '.json')
    with open(port_information_file, 'w', encoding='utf-8') as f:
        json.dump(all_port_information_struct, f, ensure_ascii=False, indent=4)
    f.close()

   

    def get_material_from_layer_or_dielectric_name (layername):
        material = None
        layer = metals_list.getbylayername(layername)
        if layer is not None:
            material = materials_list.get_by_name(layer.material)
        if material is None:
                dielectric = dielectrics_list.get_by_name(layername)
                if dielectric is not None:
                    material = materials_list.get_by_name(dielectric.material)
        return material                    


    # ----------------  PALACE CONFIG  -----------------

    # --------- config header ----------------
    config_data = {}    # data structure to hold the config file data
 
    problem =  {
            "Type": "Driven",
            "Verbose": 3,
            "Output": data_dir
        }
    config_data['Problem'] = problem

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
        # Discrete frequencies list values for Palace must be in GHz, divide by 1e9
        f_discrete_list_GHz = [f / 1e9 for f in f_discrete_list]
        discrete = {
                    "Type": "Point",
                    "Freq": f_discrete_list_GHz,
                    "SaveStep": 0,
        }

        sweep.append(discrete)


    # add f_dump_list for frequencies where we request dump file at every sample
    if len(f_dump_list) > 0:
        # Discrete frequencies list values for Palace must be in GHz, divide by 1e9
        f_dump_list_GHz = [f / 1e9 for f in f_dump_list]
        dump = {
                    "Type": "Point",
                    "Freq": f_dump_list_GHz,
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


    # DOMAINS: iterate over physical_groups_3D 
    # keys: "layername", "groupname", "grouptag"

    Palace_materials = []

    for item in physical_groups_3D:
        # items can be from via layer or from dielectric stackup

        layername, groupname, grouptag = item.values()
        material = get_material_from_layer_or_dielectric_name(layername)

        if material is not None:
            Palace_material = {}
            Palace_material['Attributes'] = [grouptag]
            Palace_material['Permittivity'] = material.eps

            metal = metals_list.getbylayername(layername)
            if metal is not None:        
                if metal.is_via:
                    # anisotropic conductivity so that merged via array don't carry (much) xy current
                    xy_sigma = material.sigma/10
                    Palace_material['Conductivity']=[xy_sigma, xy_sigma, material.sigma]
                else:    
                    Palace_material['Conductivity']=material.sigma
            else:
                # not a metal, but we also have conductivity in stackup substrate
                Palace_material['Conductivity']=material.sigma

            Palace_materials.append(Palace_material)
        else:    
            # nothing found in XML stackup materials
            if layername == 'airbox':
                Palace_material = {}
                Palace_material['Attributes'] = [grouptag]
                Palace_material['Permittivity'] = 1.0
                Palace_materials.append(Palace_material)
            else:
                # this should not happen!
                print(f'No material found for this volume: {layername} {group_name}')



    postprocessing =  {
                "Energy": [],
                "Probe": []
            }

    domains={}
    domains['Materials']=Palace_materials
    domains['Postprocessing']=postprocessing
    config_data['Domains'] = domains


    # CONDUCTORS: iterate over physical_groups_2D 

    boundaries = {}
    Palace_conductors = []
    Palace_impedances = []

    for item in physical_groups_2D:
        # items can be from surface of metal conductor
        internal_layername, groupname, grouptag = item.values()
        is_vertical = '_z' in internal_layername

        # strip suffix _xy and _z 
        layername = internal_layername.replace('_xy','')
        layername = layername.replace('_z','')

        material = get_material_from_layer_or_dielectric_name(layername)

        if material is not None:
           
            # we also need to check metal definition
            metal = metals_list.getbylayername(layername)
            if metal is not None:   

                # check that use of conductor or sheet matches material definition
                if material.type == "CONDUCTOR" and metal.is_sheet:
                    print('Invalid material assignment: sheet layer ', metal.name, ' must use a resistor material!')
                    exit(1)

                if material.type == "RESISTOR" and not metal.is_sheet:
                    print('Invalid material assignment: resistor material mapping only valid for sheet layers, not for ', metal.name)
                    exit(1)

                if metal.is_metal:
                    # regular metal
                    Palace_conductor = {}
                    Palace_conductor['Attributes'] = [grouptag]

                    # regular conductor
                    Palace_conductor['Conductivity'] = material.sigma
                    # for regular metal, we apply an optional thickness factor to the vertical sheets
                    if is_vertical:
                        Palace_conductor['Thickness'] = metal.thickness * z_thickness_factor
                    else:
                        Palace_conductor['Thickness'] = metal.thickness 
                    Palace_conductors.append(Palace_conductor)

                elif metal.is_sheet:
                    # sheet metal for resistors etc
                    Palace_impedance = {}
                    Palace_impedance['Attributes'] = [grouptag]
                    Palace_impedance['Rs'] = material.Rs
                    Palace_impedances.append(Palace_impedance) # append to global list
                else:
                    # we should never get here
                    print(f'Invalid surface found, layer {metal}, physical group {grouptag}')
        else:    
            # this should not happen!
            print(f'No material found for this conductor: {layername} {group_name}')



    boundaries['Conductivity']= Palace_conductors
    config_data['Boundaries'] = boundaries


    # PORTS
    Palace_lumpedports = []

    for item in physical_groups_ports:
        layername, portname, grouptag = item.values()

        Palace_lumpedport = {}
        portnum = int(portname.replace('P',''))
        port = simulation_ports.get_port_by_number(portnum)

        # find in which excitation group the port is, defaults to boolean false
        excite_group = False
        for idx, group in enumerate(excite_ports):
            if portnum in group:
                excite_group = portnum

        Palace_lumpedport['Index'] = portnum
        Palace_lumpedport['R'] = port.port_Z0
        Palace_lumpedport['Direction'] = port.direction.upper()
        Palace_lumpedport['Excitation'] = excite_group
        Palace_lumpedport['Attributes']=[grouptag]
        Palace_lumpedports.append(Palace_lumpedport)

    boundaries['LumpedPort'] = Palace_lumpedports


    # AIRBOX

    # get surface tags of airbox 
    simulation_boundary = airbox_surface_taglist[0]  # assume we have air margin all around

    PEC_boundaries = []
    PML_boundaries = []
    PMC_boundaries = []
 
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
    gmsh.model.setPhysicalName(2, phys_group_PML, 'Absorbing_boundary')

    phys_group_PEC = gmsh.model.addPhysicalGroup(2, PEC_boundaries, tag=-1)
    gmsh.model.setPhysicalName(2, phys_group_PEC, 'PEC_boundary')

    phys_group_PMC = gmsh.model.addPhysicalGroup(2, PMC_boundaries, tag=-1)
    gmsh.model.setPhysicalName(2, phys_group_PMC, 'PMC_boundary')


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


    # write Palace JSON simulation config file now, so that we can verify it while geometry is open in gmsh GUI
    if not elmer: # create Palace when not Elmer solver requested
        with open(config_name, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)
        f.close()



    # ----------------  ELMER CONFIG  -----------------

    # Optional output for Elmer FEM solver
    if elmer:

        # bodies

        Elmer_materials = []
        Elmer_bodies    = []

        for item in physical_groups_3D:
            # items can be from via layer or from dielectric stackup

            layername, groupname, grouptag = item.values()
            material = get_material_from_layer_or_dielectric_name(layername)

            if (material is not None) or (layername == 'airbox'):
                Elmer_material = {}

                if layername == 'airbox':
                    Elmer_material['name']='airbox'
                    Elmer_material['permittivity']=1.0
                    Elmer_material['conductivity']=0.0
                else:
                    Elmer_material['name']=material.name
                    Elmer_material['permittivity']=material.eps
                    Elmer_material['conductivity']=material.sigma
                
                if Elmer_material != {}:
                    if Elmer_material not in Elmer_materials:
                        Elmer_materials.append(Elmer_material)

                    material_index = Elmer_materials.index(Elmer_material)
                
                    # volumes are identified by physical group name (=layername), which was already set above
                    Elmerbody = {}
                    Elmerbody['name']=layername
                    Elmerbody['material']=material_index+1
                    Elmer_bodies.append(Elmerbody)


        # surfaces
        Elmer_boundaries = []
        for item in physical_groups_2D:
            # items can be from surface of metal conductor
            internal_layername, groupname, grouptag = item.values()
            is_vertical = '_z' in internal_layername

            # strip suffix _xy and _z 
            layername = internal_layername.replace('_xy','')
            layername = layername.replace('_z','')

            material = get_material_from_layer_or_dielectric_name(layername)

            if material is not None:
            
                # we also need to check metal definition
                metal = metals_list.getbylayername(layername)
                if metal is not None:   

                    if metal.is_metal:
                        # regular metal
                        Elmer_boundary = {}
                        Elmer_boundary['name'] = gmsh.model.getPhysicalName(2,grouptag)
                        Elmer_boundary['conductivity'] = material.sigma
                        if '_z' in internal_layername:                        
                            Elmer_boundary['thickness'] = metal.thickness * z_thickness_factor
                        else:    
                            Elmer_boundary['thickness'] = metal.thickness 
                        Elmer_boundaries.append(Elmer_boundary)

                    elif metal.is_sheet:
                        # sheet metal for resistors etc
                        print('Sheet resistors not supported yet for Elmer model output!')
                        exit(1)
                    else:
                        # we should never get here
                        print(f'Invalid surface found, layer {metal}, physical group {grouptag}')
            else:    
                # this should not happen!
                print(f'No material found for this conductor: {layername} {group_name}')




        # PORTS
        Elmer_ports = []
        for item in physical_groups_ports:
            layername, portname, grouptag = item.values()

            portnum = int(portname.replace('P',''))           
            Elmer_port_boundary = {}
            Elmer_port_boundary['name'] = portname
            Elmer_port_boundary['portnum'] = portnum
            Elmer_port_boundary['Z0'] = port.port_Z0


            # convert direction to number for Elmer
            if 'X' in port.direction.upper():
                direction = 1
            elif 'Y' in port.direction.upper():
                direction = 2
            else:
                direction = 3
            # polarity
            if '-' in port.direction:
                direction = - direction
            Elmer_port_boundary['direction'] = direction
            Elmer_ports.append(Elmer_port_boundary)



        # write simulation frequencies for Elmer
        elmer_freq_file = os.path.join(sim_path, 'frequencies.dat')
        num_frequencies = util_elmer.write_elmer_frequencies (elmer_freq_file, 
                                                                fstart, 
                                                                fstop, 
                                                                fstep, 
                                                                f_discrete_list, 
                                                                f_dump_list)

        # write *.sif file for Elmer
        elmer_physics_file = os.path.join(sim_path, 'physics.sif')
        util_elmer.write_elmer_physics_file (unit,
                                                elmer_physics_file, 
                                                num_frequencies, 
                                                Elmer_materials, 
                                                Elmer_bodies,
                                                Elmer_boundaries,
                                                Elmer_ports,
                                                PEC_boundaries,
                                                PML_boundaries,
                                                PMC_boundaries)


        elmer_start_file = os.path.join(sim_path, 'ELMERSOLVER_STARTINFO')
        with open(elmer_start_file, "w") as f:  
            f.write('case.sif\n')
        f.close()  


        # write_case_and_solver_files (targetdir, order, iterative) 
        util_elmer.write_case_and_solver_files (sim_path, order, iterative, ELMER_MPI_THREADS=ELMER_MPI_THREADS)



    
    if save_gmsh_geometry:
        # write "raw" geometry with no mesh, so that we can open in gmsh
        gmsh.write(geo_name)


    # -------------- MESH REFINEMENT ------------------
    if True:

        # OPTIONAL: MESH IN SILICON
        # 
        # We can add some higher mesh density at the upper end of silicon
        # To do so, we need to get the z position of the topmost semiconductor

        z_semi = -math.inf  # maximum z position for semiconductors in stackup, default at minus infinity

        # dielectrics from stackup
        for dielectric in dielectrics_list.dielectrics:
            # get CSX material object for this dielectric layers material name
            materialname = dielectric.material
            material = materials_list.get_by_name(materialname)
            
            if material.sigma > 0:
                z_semi = max(z_semi, dielectric.zmax)



        # REFINE MESH AT CONDUCTORS (SURFACES)

        def refine_along_boundary (boundary_line_tags, refined_cellsize_value, i):
            """Create mesh field for given boundary line tags, with specified cellsize value, place extra vertices and save mesh field 


            Args:
                boundary_line_tags (list of int): line tags where to place refined cellsize
                refined_cellsize_value (float): refined cellsize in micron
                i (int): index of mesh size field for gmsh (couting upwards, returns the next index)

            Returns:
                int: next index
            """
            # resample along boundaries, i.e. place points along the boundaries
            gmsh.model.mesh.field.add("Distance", i)
            gmsh.model.mesh.field.setNumbers(i, "CurvesList", boundary_line_tags) 
            gmsh.model.mesh.field.setNumber(i, "Sampling", 200)

            i = i + 1
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
            gmsh.model.mesh.field.add("Threshold", i)
            gmsh.model.mesh.field.setNumber(i, "InField", i-1)  # number of this field definition
            gmsh.model.mesh.field.setNumber(i, "SizeMin", refined_cellsize_value)
            gmsh.model.mesh.field.setNumber(i, "SizeMax", max_cellsize_air)
            gmsh.model.mesh.field.setNumber(i, "DistMin", 0)
            gmsh.model.mesh.field.setNumber(i, "DistMax", max_cellsize_air)

            fields_list.append(i)
            i = i + 1
            return i


        # We create multiple fields and then tell gmsh to use the minimum value of all
        fields_list = []  # global edge refinement
        override_dict = {}  # used to store fields for edge refinement override, key is refined cellsize (micron), value is list of boundary linetags 

        # iterate over all entries and choose between global refined_cellsize and per-layer value
        boundary_line_tags_using_refined_cellsize = []   

        for key in boundary_line_tags_dict.keys():  # boundary_line_tags_dict is organized by layername, value is list of dimtags
            # key is layername
            if key in refined_cellsize_override_dict.keys():
                # this layer uses special override refinement
                refined_cellsize_value = refined_cellsize_override_dict[key]
                tags = boundary_line_tags_dict[key]
                
                # create if entry does not exits, otherwise add to list
                if refined_cellsize_value not in override_dict.keys():
                    override_dict[refined_cellsize_value]=tags
                else:    
                    override_dict[refined_cellsize_value].extend(tags)
            else:
                # this layer uses default refined_cellsize value
                boundary_line_tags_using_refined_cellsize.extend(boundary_line_tags_dict[key])


        # apply default refined_cellsize for all layers that have no override
        i=1
        i = refine_along_boundary (boundary_line_tags_using_refined_cellsize, refined_cellsize, i) # return next value of i

        # apply other value if layername and value was provided in override_dict
        for key in override_dict.keys():
            refined_cellsize_value=key
            tags = override_dict[key]
            i = refine_along_boundary (tags, refined_cellsize_value, i)            

    
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

            gmsh.model.mesh.field.add("Box", i)
            gmsh.model.mesh.field.setNumber(i, "VIn",  refine_value)
            gmsh.model.mesh.field.setNumber(i, "VOut", max_cellsize_local)
            gmsh.model.mesh.field.setNumber(i, "XMin", x1)
            gmsh.model.mesh.field.setNumber(i, "XMax", x2)
            gmsh.model.mesh.field.setNumber(i, "YMin", y1)
            gmsh.model.mesh.field.setNumber(i, "YMax", y2)
            gmsh.model.mesh.field.setNumber(i, "ZMin", z_semi-refine_layer_thickness)
            gmsh.model.mesh.field.setNumber(i, "ZMax", z_semi)

            fields_list.append(i)
            i = i + 1


        # Iterate over dielectric and set max_cellsize in medium according to permittivity
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

        # Set maximum cellsize for surrounding airbox also
        xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(-1, -1) 
        max_cellsize_local = min(max_cellsize_air, 2*meshsize_max)   # factor 2 compared to meshsize_max
        gmsh.model.mesh.field.add("Box", i)
        gmsh.model.mesh.field.setNumber(i, "VIn",  max_cellsize_local) # inside
        gmsh.model.mesh.field.setNumber(i, "VOut", max_cellsize_air) # outside
        gmsh.model.mesh.field.setNumber(i, "XMin", xmin)
        gmsh.model.mesh.field.setNumber(i, "XMax", xmax)
        gmsh.model.mesh.field.setNumber(i, "YMin", ymin)
        gmsh.model.mesh.field.setNumber(i, "YMax", ymax)
        gmsh.model.mesh.field.setNumber(i, "ZMin", zmin)
        gmsh.model.mesh.field.setNumber(i, "ZMax", zmax)

        fields_list.append(i)
        i = i + 1

        # Let's use the minimum of all the fields as the mesh size field:
        gmsh.model.mesh.field.add("Min", i)
        gmsh.model.mesh.field.setNumbers(i, "FieldsList", fields_list)

        gmsh.model.mesh.field.setAsBackgroundMesh(i)

        # When the element size is fully specified by a mesh size field, 
        # it is thus often desirable to set
        gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
        gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 0)
        gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)
        # This will prevent over-refinement due to small mesh sizes on the boundary.


    # Finally, while the default "Frontal-Delaunay" 2D meshing algorithm
    # (Mesh.Algorithm = 6) usually leads to the highest quality meshes, the
    # "Delaunay" algorithm (Mesh.Algorithm = 5) will handle complex mesh size fields
    # better - in particular size fields with large element size gradients:


    gmsh.option.setNumber("Mesh.Algorithm", 5)
    gmsh.option.setNumber("Mesh.Optimize", 1)
    gmsh.option.setNumber("Mesh.Smoothing", 10)
    

    # open gmsh GUI with unmeshed geometry, but all mesh settings already applied
    if not no_gui:
        if not no_preview: # display of unmeshed model can be skipped
            gmsh.fltk.run()

    if not preview_only:
        # now generate mesh
        gmsh.model.mesh.generate(3)

        # Save mesh
        gmsh.option.setNumber("Mesh.Binary", 0)
        gmsh.option.setNumber("Mesh.SaveAll", 0)  # value 1 means: save everything, no matter if in physical group or not - DON'T USE WITH V2.2
        gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)  # Palace requires mesh version 2.2!

        # write meshed geometry
        gmsh.write(msh_name)
        # show meshed model in gmsh GUI
        if not no_gui:

            if no_preview:
                # hide physical volumes in viewer
                # Step 1: Get all physical volumes
                volume_groups = [(dim, tag) for dim, tag in gmsh.model.getPhysicalGroups() if dim == 3]

                # Step 2: Collect all volume entities AND their surfaces
                entities_to_hide = []
                for dim, vol_tag in volume_groups:
                    # Get the actual volume entities
                    volumes = gmsh.model.getEntitiesForPhysicalGroup(dim, vol_tag)
                    
                    for vol in volumes:
                        entities_to_hide.append((3, vol))  # hide volume itself
                        # gmsh.model.getAdjacencies(dimFrom, tagFrom) → returns (entityDim[], entityTags[])
                        _, surface_tags = gmsh.model.getAdjacencies(3, vol)  # dimFrom=3, tag=vol
                        for s in surface_tags:
                            entities_to_hide.append((2, s))  # add surface to hide

                # Step 3: Hide everything in the viewer
                gmsh.model.setVisibility(entities_to_hide, False)        

            gmsh.fltk.run()

    
    gmsh.clear()
    gmsh.finalize()

    # Optional convert mesh file to Elmer format
    if elmer:
        util_elmer.convert_mesh_to_elmer (msh_name, ELMER_MPI_THREADS)

    return config_name, data_dir


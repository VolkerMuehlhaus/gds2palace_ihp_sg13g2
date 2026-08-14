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

"""
Load/edit/save/validate stackup XML files (see XML_stackup_format.md) at the
xml.etree.ElementTree level, independent of any GUI toolkit.

This module is deliberately kept separate from util_stackup_reader.py: the
reader turns XML into the read-only object model (stackup_material,
dielectric_layer, metal_layer, ...) used by the rest of gds2palace, while this
module is for tools that need to load a file, edit it (materials/dielectrics/
layers), and write it back out - such as a GUI stackup editor - while leaving
any parts of the file they don't understand (e.g. DerivedLayers, Tables, and
XML comments) completely untouched.
"""

__version__ = "1.0.0"

import xml.etree.ElementTree as ET

VALID_MATERIAL_TYPES = ("Conductor", "Dielectric", "Semiconductor", "Resistor")
VALID_LAYER_TYPES = ("conductor", "via", "dielectric", "sheet")
VALID_DERIVED_OPERATIONS = ("AND", "OR", "XOR", "NOT", "SIZE")


def _comment_preserving_parser():
  """XML parser that keeps <!-- comments --> as Comment nodes in the tree, instead of
     silently dropping them (the default xml.etree behavior), so a load/save round
     trip does not lose comments in sections this module never edits.
  """
  target = ET.TreeBuilder(insert_comments=True)
  return ET.XMLParser(target=target)


# -------------------- load / new / save --------------------

def load_stackup_tree(filename):
  """Load a stackup XML file into an editable ElementTree, preserving comments.
  Args:
      filename (string): path to the stackup XML file
  Returns:
      xml.etree.ElementTree.ElementTree
  """
  return ET.parse(filename, parser=_comment_preserving_parser())


def new_stackup_tree(length_unit="um", schema_version="2.0"):
  """Create a minimal empty stackup tree (empty Materials/Dielectrics/Layers), for
     starting a new stackup file from scratch in an editor.
  Returns:
      xml.etree.ElementTree.ElementTree
  """
  root = ET.Element("Stackup", {"schemaVersion": schema_version})
  ET.SubElement(root, "Materials")
  elayers = ET.SubElement(root, "ELayers", {"LengthUnit": length_unit})
  ET.SubElement(elayers, "Dielectrics")
  ET.SubElement(elayers, "Layers")
  return ET.ElementTree(root)


GENERATOR_COMMENT_PREFIX = "Created/modified using the XML Stackup Editor in"
DESCRIPTION_COMMENT_PREFIX = "File description:"
_HEADER_SEPARATOR_TEXT = "=" * 60


def _sanitize_comment_text(text):
  """XML comments may not contain '--' or end in '-'; make free-form user text
     safe to embed as a Comment node's .text without raising on write().
  """
  text = text.replace("--", "- -")
  return text.rstrip("-")


def _is_header_comment(comment_element):
  """True if this Comment node looks like one this module previously wrote as part
     of the header block (generator stamp / separator / file description), so a
     re-stamp can cleanly remove the old block before writing a fresh one.
  """
  text = (comment_element.text or "").strip()
  return (text.startswith(GENERATOR_COMMENT_PREFIX)
          or text.startswith(DESCRIPTION_COMMENT_PREFIX)
          or text == _HEADER_SEPARATOR_TEXT)


def stamp_header_comments(root, app_name, description=""):
  """Insert or update the header comment block at the very top of the stackup root:
     a fixed "created with" stamp, and - only if description is non-empty - a
     separator line followed by the user-supplied file description. Idempotent:
     replaces a previously-stamped header block instead of stacking a new one on
     every save; any other pre-existing comments/elements are left untouched.
  Args:
      root (xml.etree.ElementTree.Element): the <Stackup> root element
      app_name (string): name of the host application (e.g. "setupEM", "setupThermal")
      description (string): optional free-text description of the file
  """
  children = list(root)
  while children and children[0].tag is ET.Comment and _is_header_comment(children[0]):
    root.remove(children[0])
    children = list(root)

  nodes = [ET.Comment(f" {_sanitize_comment_text(GENERATOR_COMMENT_PREFIX + ' ' + app_name)} ")]
  description = _sanitize_comment_text((description or "").strip())
  if description:
    nodes.append(ET.Comment(f" {_HEADER_SEPARATOR_TEXT} "))
    nodes.append(ET.Comment(f" {DESCRIPTION_COMMENT_PREFIX} {description} "))

  for i, node in enumerate(nodes):
    root.insert(i, node)


def get_file_description(root):
  """Return the free-text file description previously stamped by the editor (see
     stamp_header_comments), or "" if none is present.
  Args:
      root (xml.etree.ElementTree.Element): the <Stackup> root element
  """
  for child in root:
    if child.tag is ET.Comment:
      text = (child.text or "").strip()
      if text.startswith(DESCRIPTION_COMMENT_PREFIX):
        return text[len(DESCRIPTION_COMMENT_PREFIX):].strip()
  return ""


def save_stackup_tree(tree, filename):
  """Write a stackup tree back to disk with consistent indentation.

  Note: this re-serializes the whole document, so exact original whitespace and
  attribute order may change. Comments and all element content are preserved.
  Args:
      tree (xml.etree.ElementTree.ElementTree): tree to write, as returned by
        load_stackup_tree() or new_stackup_tree()
      filename (string): path to write to
  """
  ET.indent(tree, space="  ")
  tree.write(filename, xml_declaration=True, encoding="UTF-8")


# -------------------- structural accessors --------------------

def get_materials_element(root):
  return root.find("Materials")


def get_dielectrics_element(root):
  return root.find("ELayers/Dielectrics")


def get_layers_element(root):
  return root.find("ELayers/Layers")


def get_substrate_offset_element(root):
  layers_el = get_layers_element(root)
  if layers_el is None:
    return None
  return layers_el.find("Substrate")


def get_derived_layers_element(root, create=False):
  """<DerivedLayers> is optional and, unlike Dielectrics/Layers, may not exist yet.
  Args:
      create (bool): if True and the element is missing, create (and return) it
  """
  elayers = root.find("ELayers")
  derived_layers_el = elayers.find("DerivedLayers") if elayers is not None else None
  if derived_layers_el is None and create and elayers is not None:
    derived_layers_el = ET.SubElement(elayers, "DerivedLayers")
  return derived_layers_el


# -------------------- Material --------------------

def add_material(root, **attrs):
  """Append a new <Material> element. Keyword args become attributes (None/"" skipped).
  Returns:
      xml.etree.ElementTree.Element: the new Material element
  """
  materials_el = get_materials_element(root)
  el = ET.SubElement(materials_el, "Material")
  for key, value in attrs.items():
    if value is not None and value != "":
      el.set(key, str(value))
  return el


def remove_material(root, element):
  get_materials_element(root).remove(element)


# -------------------- Dielectric --------------------

def add_dielectric(root, index=None, **attrs):
  """Insert a new <Dielectric> element. Order in <Dielectrics> is top-to-bottom and
     meaningful, so callers can pass index to control where it lands (default: end).
  Returns:
      xml.etree.ElementTree.Element: the new Dielectric element
  """
  dielectrics_el = get_dielectrics_element(root)
  el = ET.Element("Dielectric")
  for key, value in attrs.items():
    if value is not None and value != "":
      el.set(key, str(value))
  if index is None or index >= len(dielectrics_el):
    dielectrics_el.append(el)
  else:
    dielectrics_el.insert(index, el)
  return el


def remove_dielectric(root, element):
  get_dielectrics_element(root).remove(element)


def move_dielectric(root, element, direction):
  """Move a Dielectric element within its parent, to reorder the stack.
  Args:
      element (xml.etree.ElementTree.Element): the Dielectric element to move
      direction (int): -1 to move earlier (up), +1 to move later (down)
  """
  dielectrics_el = get_dielectrics_element(root)
  children = list(dielectrics_el)
  index = children.index(element)
  new_index = index + direction
  if 0 <= new_index < len(children):
    dielectrics_el.remove(element)
    dielectrics_el.insert(new_index, element)


# -------------------- Layer / Substrate offset --------------------

def add_layer(root, **attrs):
  """Append a new <Layer> element. Keyword args become attributes (None/"" skipped).
  Returns:
      xml.etree.ElementTree.Element: the new Layer element
  """
  layers_el = get_layers_element(root)
  el = ET.SubElement(layers_el, "Layer")
  for key, value in attrs.items():
    if value is not None and value != "":
      el.set(key, str(value))
  return el


def remove_layer(root, element):
  get_layers_element(root).remove(element)


def set_substrate_offset(root, value):
  """Add, update, or remove the single optional <Substrate Offset="..."/> element.
  Args:
      value: new offset (numeric or numeric string), or None/0 to remove the element
  Returns:
      xml.etree.ElementTree.Element or None: the Substrate element, or None if removed
  """
  layers_el = get_layers_element(root)
  existing = layers_el.find("Substrate")

  if value is None or value == "" or float(value) == 0:
    if existing is not None:
      layers_el.remove(existing)
    return None

  if existing is None:
    existing = ET.Element("Substrate")
    layers_el.insert(0, existing)
  existing.set("Offset", str(value))
  return existing


# -------------------- DerivedLayer --------------------

def add_derived_layer(root, **attrs):
  """Append a new <DerivedLayer> element, creating <DerivedLayers> if this is the
     first one. Keyword args become attributes (None/"" skipped); use set_operands()
     separately to add its <Operand> children.
  Returns:
      xml.etree.ElementTree.Element: the new DerivedLayer element
  """
  derived_layers_el = get_derived_layers_element(root, create=True)
  el = ET.SubElement(derived_layers_el, "DerivedLayer")
  for key, value in attrs.items():
    if value is not None and value != "":
      el.set(key, str(value))
  return el


def remove_derived_layer(root, element):
  """Remove a <DerivedLayer> element, and drop the now-empty <DerivedLayers>
  container too if that was the last one (keeps a from-scratch file clean).
  """
  derived_layers_el = get_derived_layers_element(root)
  if derived_layers_el is None:
    return
  derived_layers_el.remove(element)
  if len(derived_layers_el) == 0:
    root.find("ELayers").remove(derived_layers_el)


def get_operand_layers(element):
  """Layer numbers (as strings, in document order) of a DerivedLayer's <Operand> children."""
  return [operand.get("Layer") for operand in element.findall("Operand")]


def set_operands(element, layer_numbers):
  """Replace a DerivedLayer element's <Operand> children with one per given layer
  number, in order - order matters for Operation="NOT" (first operand minus the rest).
  Args:
      layer_numbers (list of str/int): GDSII or other-DerivedLayer layer numbers
  """
  for existing in element.findall("Operand"):
    element.remove(existing)
  for layernum in layer_numbers:
    ET.SubElement(element, "Operand", {"Layer": str(layernum)})


# -------------------- validation --------------------

def _is_float(value):
  try:
    float(value)
    return True
  except (TypeError, ValueError):
    return False


def _is_int(value):
  try:
    int(value)
    return True
  except (TypeError, ValueError):
    return False


def validate_stackup(root):
  """Validate Materials/Dielectrics/Layers/DerivedLayers against the rules in
     XML_stackup_format.md. Tables is intentionally not checked here (not editable yet).
  Args:
      root (xml.etree.ElementTree.Element): root <Stackup> element
  Returns:
      list of str: human-readable problems found, empty if the file is valid
  """
  errors = []

  materials_el = get_materials_element(root)
  material_names = []
  if materials_el is not None:
    for el in materials_el.findall("Material"):
      name = el.get("Name")
      mtype = el.get("Type")
      label = name or "<unnamed material>"

      if not name:
        errors.append("Material is missing required attribute 'Name'")
      elif name in material_names:
        errors.append(f"Duplicate material Name '{name}'")
      else:
        material_names.append(name)

      if not mtype:
        errors.append(f"Material '{label}' is missing required attribute 'Type'")
      elif mtype.upper() not in [t.upper() for t in VALID_MATERIAL_TYPES]:
        errors.append(f"Material '{label}' has invalid Type '{mtype}' (must be one of {VALID_MATERIAL_TYPES})")

      for attr in ("Permittivity", "DielectricLossTangent", "Conductivity", "Rs", "Density", "ThermalConductivity"):
        value = el.get(attr)
        if value is not None and value != "" and not _is_float(value):
          errors.append(f"Material '{label}' has non-numeric {attr}='{value}'")

  dielectrics_el = get_dielectrics_element(root)
  dielectric_names = []
  if dielectrics_el is not None:
    for el in dielectrics_el.findall("Dielectric"):
      name = el.get("Name")
      material = el.get("Material")
      label = name or "<unnamed dielectric>"

      if not name:
        errors.append("Dielectric is missing required attribute 'Name'")
      elif name in dielectric_names:
        errors.append(f"Duplicate dielectric Name '{name}'")
      else:
        dielectric_names.append(name)

      if not material:
        errors.append(f"Dielectric '{label}' is missing required attribute 'Material'")
      elif material not in material_names:
        errors.append(f"Dielectric '{label}' references undefined Material '{material}'")

      thickness = el.get("Thickness")
      zmin = el.get("Zmin")
      zmax = el.get("Zmax")
      has_thickness = thickness is not None and thickness != ""
      has_zminmax = (zmin is not None and zmin != "") and (zmax is not None and zmax != "")

      if not has_thickness and not has_zminmax:
        errors.append(f"Dielectric '{label}' needs either Thickness or both Zmin and Zmax")
      if has_thickness and not _is_float(thickness):
        errors.append(f"Dielectric '{label}' has non-numeric Thickness='{thickness}'")
      if has_zminmax:
        if not _is_float(zmin):
          errors.append(f"Dielectric '{label}' has non-numeric Zmin='{zmin}'")
        if not _is_float(zmax):
          errors.append(f"Dielectric '{label}' has non-numeric Zmax='{zmax}'")

      boundary = el.get("Boundary")
      if boundary is not None and boundary != "" and not _is_int(boundary):
        errors.append(f"Dielectric '{label}' has non-integer Boundary='{boundary}'")

  layers_el = get_layers_element(root)
  layer_numbers = set()
  if layers_el is not None:
    for el in layers_el.findall("Layer"):
      name = el.get("Name")
      ltype = el.get("Type")
      material = el.get("Material")
      zmin = el.get("Zmin")
      zmax = el.get("Zmax")
      layernum = el.get("Layer")
      label = name or "<unnamed layer>"
      if layernum is not None and _is_int(layernum):
        layer_numbers.add(int(layernum))

      if not name:
        errors.append("Layer is missing required attribute 'Name'")
      if not ltype:
        errors.append(f"Layer '{label}' is missing required attribute 'Type'")
      elif ltype.upper() not in [t.upper() for t in VALID_LAYER_TYPES]:
        errors.append(f"Layer '{label}' has invalid Type '{ltype}' (must be one of {VALID_LAYER_TYPES})")

      if not material:
        errors.append(f"Layer '{label}' is missing required attribute 'Material'")
      elif material not in material_names:
        errors.append(f"Layer '{label}' references undefined Material '{material}'")

      if zmin is None or zmin == "":
        errors.append(f"Layer '{label}' is missing required attribute 'Zmin'")
      elif not _is_float(zmin):
        errors.append(f"Layer '{label}' has non-numeric Zmin='{zmin}'")

      if zmax is None or zmax == "":
        errors.append(f"Layer '{label}' is missing required attribute 'Zmax'")
      elif not _is_float(zmax):
        errors.append(f"Layer '{label}' has non-numeric Zmax='{zmax}'")

      if layernum is None or layernum == "":
        errors.append(f"Layer '{label}' is missing required attribute 'Layer'")
      elif not _is_int(layernum):
        errors.append(f"Layer '{label}' has non-integer Layer='{layernum}'")

      if ltype and zmin is not None and zmax is not None and _is_float(zmin) and _is_float(zmax):
        is_zero_thickness = float(zmin) == float(zmax)
        if ltype.upper() == "SHEET" and not is_zero_thickness:
          errors.append(f"Layer '{label}' has Type=\"sheet\" but Zmax != Zmin (sheet layers must have zero thickness)")

  # DerivedLayers: these checks intentionally mirror util_stackup_reader.derived_layer's
  # requirements exactly (invalid Operation / wrong operand count for SIZE / fewer than
  # 2 operands otherwise / SIZE without a non-zero Oversize) - that reader class calls
  # exit(1) on any of them instead of raising, which would otherwise kill the whole GUI
  # process the moment something tries to parse this data (e.g. the live preview).
  derived_layers_el = get_derived_layers_element(root)
  derived_names = []
  if derived_layers_el is not None:
    all_derived_elements = derived_layers_el.findall("DerivedLayer")

    # a derived layer used as another derived layer's Operand is a pure
    # intermediate helper (e.g. a poly/implant/contact intersection stage) and
    # is never itself drawn, so it legitimately doesn't need a <Layer> entry -
    # only require one for a derived layer nothing else consumes
    referenced_as_operand = set()
    for el in all_derived_elements:
      for operand in el.findall("Operand"):
        operand_layer = operand.get("Layer")
        if operand_layer is not None and _is_int(operand_layer):
          referenced_as_operand.add(int(operand_layer))

    for el in all_derived_elements:
      name = el.get("Name")
      layernum = el.get("Layer")
      operation = el.get("Operation")
      oversize = el.get("Oversize")
      operands = [operand.get("Layer") for operand in el.findall("Operand")]
      label = name or "<unnamed derived layer>"

      if not name:
        errors.append("DerivedLayer is missing required attribute 'Name'")
      elif name in derived_names:
        errors.append(f"Duplicate derived layer Name '{name}'")
      else:
        derived_names.append(name)

      if not layernum:
        errors.append(f"DerivedLayer '{label}' is missing required attribute 'Layer'")
      elif not _is_int(layernum):
        errors.append(f"DerivedLayer '{label}' has non-integer Layer='{layernum}'")
      elif int(layernum) not in layer_numbers and int(layernum) not in referenced_as_operand:
        errors.append(f"DerivedLayer '{label}' target Layer={layernum} has no matching <Layer> "
                       f"entry (needed to give it a Z-position/material) and isn't used as "
                       f"another derived layer's operand either")

      op_upper = operation.upper() if operation else None
      if not operation:
        errors.append(f"DerivedLayer '{label}' is missing required attribute 'Operation'")
      elif op_upper not in VALID_DERIVED_OPERATIONS:
        errors.append(f"DerivedLayer '{label}' has invalid Operation '{operation}' "
                       f"(must be one of {VALID_DERIVED_OPERATIONS})")

      oversize_value = None
      if oversize is not None and oversize != "":
        if not _is_float(oversize):
          errors.append(f"DerivedLayer '{label}' has non-numeric Oversize='{oversize}'")
        else:
          oversize_value = float(oversize)

      for operand_layer in operands:
        if not operand_layer or not _is_int(operand_layer):
          errors.append(f"DerivedLayer '{label}' has a non-integer Operand Layer='{operand_layer}'")

      if op_upper == "SIZE":
        if len(operands) != 1:
          errors.append(f"DerivedLayer '{label}' has Operation=\"SIZE\", which needs "
                         f"exactly 1 operand, found {len(operands)}")
        if not oversize_value:
          errors.append(f"DerivedLayer '{label}' has Operation=\"SIZE\", which needs "
                         f"a non-zero Oversize value")
      elif op_upper in ("AND", "OR", "XOR", "NOT"):
        if len(operands) < 2:
          errors.append(f"DerivedLayer '{label}' needs at least 2 Operand entries, "
                         f"found {len(operands)}")

  return errors

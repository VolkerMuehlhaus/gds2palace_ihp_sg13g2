# gds2palace FEM workflow for IHP User’s Guide 

Volker Mühlhaus,volker@muehlhaus.com
---
Document version: 2026-08-17

## Contents
[What's New](#whats-new)  
[About this workflow](#about-this-workflow)  
[Workflow](#workflow)  
[Required software and Python modules](#required-software-and-python-modules)  
&ensp;[Recommended installation of gds2palace as Python module](#recommended-installation-of-gds2palace-as-python-module)  
&ensp;[Alternative, no longer recommended: local gds2palace directory](#alternative-no-longer-recommended-local-gds2palace-directory)  
&ensp;[External tools (not Python modules)](#external-tools-not-python-modules)  
[Installing AWS Palace](#installing-aws-palace)  
&ensp;[Installing the Palace solver using Apptainer](#installing-the-palace-solver-using-apptainer)  
&ensp;[Installing the Palace solver using spack package manager](#installing-the-palace-solver-using-spack-package-manager)  
&ensp;[Running Palace (after installation)](#running-palace-after-installation)  
[Quick tour](#quick-tour)  
&ensp;[Simulation model: Input files](#simulation-model-input-files)  
&ensp;[Simulation model: Simulation control](#simulation-model-simulation-control)  
&ensp;[Simulation model: Ports](#simulation-model-ports)  
&ensp;[Running the model code to create Palace input files](#running-the-model-code-to-create-palace-input-files)  
&ensp;[Running Palace FEM simulation from our input files](#running-palace-fem-simulation-from-our-input-files)  
[Simulation model file in detail](#simulation-model-file-in-detail)  
&ensp;[Input files](#input-files)  
&ensp;[settings](#settings)  
&ensp;[Port configuration](#port-configuration)  
&ensp;[Filenames and flow control](#filenames-and-flow-control)  
[Examples](#examples)  
[Conductor loss modelling](#conductor-loss-modelling)  
[Dielectric loss modelling](#dielectric-loss-modelling)  
[Advanced topics](#advanced-topics)  
&ensp;[Adaptive mesh refinement at selected frequencies only](#adaptive-mesh-refinement-at-selected-frequencies-only)  
&ensp;[Using wave ports instead of lumped ports not supported](#using-wave-ports-instead-of-lumped-ports-not-supported)  
&ensp;[Using S-Parameter output, model extraction](#using-s-parameter-output-model-extraction)  
&ensp;[Lumped circuit model extraction](#lumped-circuit-model-extraction)  
&ensp;[Mathematical "black box" vector fit](#mathematical-black-box-vector-fit)  
[Using gds2palace with Elmer FEM for EM simulation](#using-gds2palace-with-elmer-fem-for-em-simulation)  
&ensp;[Installing Elmer FEM](#installing-elmer-fem)  
&ensp;[From a Palace model to an Elmer model](#from-a-palace-model-to-an-elmer-model)  
&ensp;[Frequency sweep](#frequency-sweep)  
&ensp;[Mesh order and solver method](#mesh-order-and-solver-method)  
&ensp;[Boundary conditions and current limitations](#boundary-conditions-and-current-limitations)  
&ensp;[Running the Elmer EM simulation and getting S-parameters](#running-the-elmer-em-simulation-and-getting-s-parameters)  
[Using gds2palace with Elmer FEM for thermal simulation](#using-gds2palace-with-elmer-fem-for-thermal-simulation)  
&ensp;[Stackup XML: thermal material properties](#stackup-xml-thermal-material-properties)  
&ensp;[Heat sources and constant-temperature boundaries](#heat-sources-and-constant-temperature-boundaries)  
&ensp;[Model script settings](#model-script-settings)  
&ensp;[Running ElmerSolver and viewing results](#running-elmersolver-and-viewing-results)  
&ensp;[Using setupThermal instead of writing Python code](#using-setupthermal-instead-of-writing-python-code)  
[Appendix](#appendix)  
&ensp;[Understanding volumes and surfaces created from GDSII](#understanding-volumes-and-surfaces-created-from-gdsii)  
&ensp;[Mapping of Volumes and Surfaces to Palace materials](#mapping-of-volumes-and-surfaces-to-palace-materials)  
&ensp;[Extended XML stackup format](#extended-xml-stackup-format)  
&ensp;[Software versions used in this document](#software-versions-used-in-this-document)  
&ensp;[List of examples](#list-of-examples)  



## What's New

This chapter gives a brief overview of major features added since the previous edition of this guide. For the complete, dated change log, see [`CHANGES.md`](https://github.com/VolkerMuehlhaus/gds2palace_ihp_sg13g2/blob/main/doc/CHANGES.md) in the repository.

- **Elmer FEM as an additional solver.** gds2palace can now generate simulation input not only for AWS Palace, but also for [Elmer FEM](https://www.elmerfem.org/), an open-source multiphysics solver. This adds two new workflows, both built from the same GDSII layout + XML stackup + Python model script approach already used for Palace:
  - **Elmer EM simulation** — S-parameter simulation, see chapter "Using gds2palace with Elmer FEM for EM simulation".
  - **Elmer thermal simulation** — steady-state heat conduction (temperature) simulation from user-defined heat sources and constant-temperature boundaries, see chapter "Using gds2palace with Elmer FEM for thermal simulation".
- **Derived layers in the XML stackup.** A layer's geometry can now be computed from other layers using boolean operations (AND/OR/XOR/NOT) and resizing, instead of only being read directly from GDSII. This is used, for example, to derive SG13G2 resistor geometry from existing process layers, see the example in folder `more_examples/derived_layers_and_resistors`.
- **Reference-relative layer positioning in the XML stackup.** A `<Layer>` or `<Dielectric>` can now be positioned as an offset from the top or bottom edge of another named layer/dielectric, instead of always requiring an absolute Zmin/Zmax. This removes the need to hand-recompute every dependent layer's z-position whenever a thickness changes.
- **Simplified handling of cutouts.** Mesh generation was redesigned so that the `preprocess_gds` option is no longer required for layouts with cutouts (holes) or other self-intersecting polygon boundaries.
- **setupThermal.** The companion desktop tool `setupEM` now also includes `setupThermal`, a GUI for building Elmer thermal models without writing Python code, and a GUI-driven XML stackup editor. See <u>https://github.com/VolkerMuehlhaus/setupEM</u>

The XML stackup file format used by both Palace and Elmer models has grown to support these new features. See chapter "Extended XML stackup format" in the Appendix, and the full attribute reference in [`XML_stackup_format.md`](../XML_stackup_format/XML_stackup_format.md).

## About this workflow 
Palace, for **PA** rallel **LA** rge-scale **C** omputational **E** lectromagnetics, is an open-source, parallel finite element code for full-wave 3D electromagnetic simulations. It can be scaled from single computer to large high performance simulation clusters and cloud-based computing.  
<u>https://awslabs.github.io/palace/stable/</u>   
<u>https://aws.amazon.com/de/blogs/quantum-computing/aws-releases-open-source-softwarepalace-for-cloud-based-electromagnetics-simulations-of-quantum-computing-hardware/</u>  
The gds2palace workflow enables RFIC FEM simulation using Palace from GDSII layout files. 

## Workflow  
In this document, the status of the IHP workflow developed for AWS Palace FEM solver is documented.  
Two files must be provided by the user: the **layout in GDSII format** and a **simulation model script** in Python. This simulation script references the technology stackup file (XML format) and calls functions from the workflow code to create two output files for Palace: the **simulation mesh file** which is built from geometries and stackup, and the **simulation control file** in *.json format which defines material settings and simulation settings.  

Having these two files, the user can now run the FEM simulation in Palace. The simulation model script can start an external command to start simulation, or the user can run Palace on a platform of his choice. This way, the files for Palace can be created on any desktop computer, and the Palace simulation can be done on the same computer or on a very different system. This gives many options to scale Palace simulation power as needed, using the exact same Palace input data from our workflow.  


![](./images/gds2palace_workflow_userguide.pdf-0003-09.png)


## Required software and Python modules 

The gds2palace Python workflow creates AWS Palace model files (mesh file + config file). To actually simulate these models, you need to have AWS Palace installed. Installing Palace is described below in chapter “Installing AWS Palace”. 

It is recommended to install gds2palace into a Python virtual environment. In this document, we assume Linux environment and install to a virtual environment `palace` that is located in the user’s home directory at `~/venv/palace` 

This is how to create that virtual environment: 

```
cd ~
python3 -m venv ~/venv/palace
```

### Recommended installation of gds2palace as Python module 

The easiest method to install the gds2palace Python workflow is to use the preconfigured package which automatically installs all dependencies (gdspy, gmsh, scikit-rf). We activate the virtual environment and install to there:  

```
source ~/venv/palace/bin/activate
pip install –-upgrade gds2palace
```

That’s all we need to do for installing the gds2palace Python module. If you install gds2palace this way, you only need the gds2palace repository to download the examples and XML stackup files and documentation.  

```
source ~/venv/palace/bin/activate
```

As an alterna?ve, it would also be possible to work with a local copy of the gds2palace directory, as described below. However, this is more complicated and no longer recommended! 

### Alternative, no longer recommended: local gds2palace directory 

It is possible to use a local directory with gds2palace module code. This directory can be downloaded from the gds2palace github repository and must always be copied to the directory where the *.py simulation model is located. The simulation model must then have a code line to include that local gds2palace directory in the Python path.  

In this case, Python module dependencies must be installed manually:  

```
source ~/venv/palace/bin/activate
pip install gdspy
pip install gmsh
pip install scikit-rf
```

This virtual environment with installed dependencies can be used to run gds2palace and the scripts that postprocess the Palace simulation results. To activate this Python environment on the command line: 

```
source ~/venv/palace/bin/activate
```

### External tools (not Python modules)

Two more tools are needed for parts of the workflow, but are not installed via pip:

- [ParaView](https://www.paraview.org/) — to view field-dump output (Palace/Elmer EM) and Elmer thermal result files.
- An MPI implementation — only needed for multi-process Elmer runs (`settings['ELMER_MPI_THREADS']`, see chapter "Installing Elmer FEM"). Use OpenMPI or MPICH on Linux/macOS; on Windows, install [Microsoft MPI](https://learn.microsoft.com/en-us/message-passing-interface/microsoft-mpi).

## Installing AWS Palace 

To actually simulate the model created by gds2palace, you need to have AWS Palace installed. Different methods of installing Palace are described at <u>https://awslabs.github.io/palace/stable/install/</u>  but we have compiled the most relevant methods for gds2palace users below.  

### Installing the Palace solver using Apptainer 

For development of gds2palace, Palace was installed using the Singularity/Apptainer installation method. This was rather simple and straightforward, even with no knowledge about container usage. Some documentation on creating and using this container solution can be found here: [<u>https://github.com/VolkerMuehlhaus/gds2palace_ihp_sg13g2/blob/main/doc/Installing_Palace_using_Apptainer.pdf</u>  ](https://github.com/VolkerMuehlhaus/gds2palace_ihp_sg13g2/blob/main/doc/Installing_Palace_using_Apptainer.pdf)

Starting in March 2026, we also provide a pre-built container image for Palace. To download the palace version 0.16 container into your current directory:  

```
$ apptainer pull palace_016.sif oras://ghcr.io/volkermuehlhaus/palace_016:latest
```

### Installing the Palace solver using spack package manager 

Palace can also be created from source with a few simple commands. All tools required by the build process will be downloaded and installed automatically by spack, so you can sit and watch while your system builds the software.  
Notes on compiling Palace using the **spack package manager for Linux** : [Installing Palace <u>using spack</u> ](https://github.com/VolkerMuehlhaus/gds2palace_ihp_sg13g2/blob/main/doc/Installing_Palace_using_Spack.pdf)

### Running Palace (after installation) 

You can use any of the installation methods described on the AWS Palace web site. The gds2palace workflow does not change, it only creates the input files for Palace and does not care how you installed Palace, or on what platform you run the actual Palace simulation from these model files.  

To start Palace from setupEM, a wrapper script **run_palace** is used, and this is where you point to your actual installation (even remote copy & remote simulation is possible). This script is available in the scripts folder in gds2palace repository, and needs to be adjusted for your path settings and number of processor cores.  

## Quick tour 

This chapter will give a very brief overview of the workflow usage, without going into the details.  

To get started, we need a directory that contains:  
- GDSII layout file to be simulated  
- XML stackup file  
- Only if gds2palace is **not** installed as Python module: local copy of gds2palace directory  

In addition, we need the simulation model code in Python, which brings the workflow to life. Below are the most important code sections that need to be configured by the user.  

### Simulation model: Input files 

In this section, the user specifies the GDSII data source and the technology stackup file.  

![](./images/gds2palace_workflow_userguide.pdf-0006-09.png)


### Simulation model: Simulation control 

In this section, the user needs to specify frequency range and mesh settings.  There are additional optional settings that can be applied, as discussed later in this document.  

![](./images/gds2palace_workflow_userguide.pdf-0006-12.png)

Users who are familiar with the IHP openEMS workflow will notice many similarities, although some implementation details are different.  

One important difference is that FEM simulates one frequency after another, so frequency settings have an effect on total simulation time. However, Palace is configured to use an adaptive frequency sweep, which will EM simulate only the minimum required number of frequencies across the band, and then create all other frequency points using interpolation. This adaptive sweep is enabled by default in our workflow.  

Another important difference is the use of “refined_cellsize” to create the mesh: the gmsh meshing engine will always create a mesh based on all geometry detail, no matter how small it is, and then apply an additional mesh refinement based on “refined_cellsize” along the metal edges.  

### Simulation model: Ports 

Additional important user input are the port definitions.  

Similar to the IHP openEMS workflow, **ports are created based on polygons from the GDSII file** , located on special layers that are not part of the IHP layer table. Each port needs to use a different source layer in the GDSII file.  

The port mapping defines the port number and port impedance, and then maps the port geometry from the special GDSII input layer (usually 201 and above) to actual IHP technology layers. For the vertical ports shown here, we have from_layername and to_layername. For in-plane ports, we would have target_layername instead. Finally, the port direction is required to specify vertical ports or in-plane ports and their direction/polarity.  


![](./images/gds2palace_workflow_userguide.pdf-0007-04.png)


For this Palace workflow, the voltage parameter is not supported yet by the Palace solver. Palace only supports opposite polarity by reversing the port direction. **But here in our workflow, we use this voltage parameter to specify if a port is active: ports with voltage=0 will not be excited.**  

It must be noted that Palace behaves differently from other FEM solvers: to get the full S- matrix, we need to run all port excitations, one after another. This only happens if all port voltages are not zero. Only then, the full S-parameter output file can be created.  

**ATTENTION** : If any port excitation is zero, that “zero voltage” port will not be excited and that row in the S-parameter file will be padded with zeros. For example, if we simulate an 8-port circuit and only excite port 1, the S-parameter output will have valid results for S11, S21, … S81 but all other values will be zero. This can be useful to quickly simulate one specific path in the model.  

To get the full S-parameter file, all ports must be defined with non-zero voltage, so that all port excitations are simulated, one after another.  

**PORT SHAPE IN GDSII** : The workflow creates lumped ports in Palace, which need to be 2D sheets. This means that for vertical ports (via ports), you should draw a zero-width box in GDSII, resulting in a vertical 2D sheet with no width. If you define a vertical port from a box with finite xy area, the Palace port will be created as a vertical 2D sheet along the center line of that 2D box.  

**Composite ports** (multiple EM ports grouped into one port in the final output file) are not yet supported by this workflow. All ports with non-zero voltage are simulated one after another, resulting in n-port S-parameters.  

### Running the model code to create Palace input files 

The simulation model file (Python code) can be run on the command line. After reading and processing the input files, a 3D viewer comes up and shows the resulting 3D model. This viewer is the graphical interface of the gmsh meshing library, and provides many options for inspection of the model. At this point, the model is not meshed yet, so that we can see the raw geometries. 


![](./images/gds2palace_workflow_userguide.pdf-0008-02.png)


To see the structure of the 3D model, you can go to Tools > Visibility.  

In the screenshot, you can see that dielectric boxes (SiO2, Passive, AIR etc) have been added around the GDSII polygons, with an offset value in xy direction from the “margins” parameter in the model file. Around that, we have another layer of air on all six sides, using the same margins value.  

Metals have been created as surfaces. All polygons on each layer are merged, if possible, and then each of the resulting polygons is created as a separate surface. To be more precise, we have two surfaces for each polygon: the horizontal (xy) surfaces and the vertical (z) surfaces are assigned to different groups, for reasons explained later in this document. 

You can also see two ports P1 and P2 created as surfaces. The outer simulation boundary is this example is a surface “Absorbing boundary” that is defined as absorbing boundary in the Palace config file.  

When we are done with inspecting the model (which is optional, no user action is required!), the gmsh viewer window can be closed to proceed with meshing. After closing the gmsh geometry preview, the simulation model script will mesh these geometries, which can take a while and will show lots of status information on the command line.  

When meshing is completed, the gmsh 3D viewer will be displayed again, showing the overall mesh.  


![](./images/gds2palace_workflow_userguide.pdf-0009-02.png)


This is too complex to see anything, but we can now go to Tools > Visibility and select one or more groups to be displayed:  


![](./images/gds2palace_workflow_userguide.pdf-0009-04.png)


This shows the mesh at the conductor surfaces of Metal1, TopMetal1 and the vertical ports. We can also display the meshed oxide, which has a lot of detail because the metal layers reside inside this volume. The metals have been “cut out” from the dielectric layer, and we see the mesh refinement around the conductor edges.  


![](./images/gds2palace_workflow_userguide.pdf-0010-01.png)

When you are done with inspection of the model (which is optional, no user action is required!), the gmsh viewer window can be closed to finish model generation. The workflow code has now created the required file to start Palace: the simulation control file config.json and the mesh file.  


![](./images/gds2palace_workflow_userguide.pdf-0010-04.png)


### Running Palace FEM simulation from our input files 

To simplify running the solver, in addition to mesh file and config file, a script file was also created named *run_sim*.  


![](./images/gds2palace_workflow_userguide.pdf-0011-02.png)


This starts a script *run_palace* where you can define in detail how to run Palace. It is recommended that you place this run_palace script in your PATH, configured for the actual machine where you want to run Palace.  

For workflow development and test, Palace was installed into an apptainer container, as documented in the Palace documentation in chapter “ **<u>Build using Singularity/Apptainer</u>** ”.  

The script *run_palace* was then configured to start Palace inside the palace_014.sif container, which is located in the user’s home directory, and passes one command line argument (the config.json file). The additional parameter _-np 16_ tells palace to run using 16 threads. This will partition the simulation domain into 8 pieces, each running in a separate process, and the combine results into one output directory.  


![](./images/gds2palace_workflow_userguide.pdf-0011-06.png)


Running Palace is not very spectacular, the simulation progress is shown in the terminal window.  


![](./images/gds2palace_workflow_userguide.pdf-0011-08.png)


When *run_palace* is finished, Palace output files are created in the *output* directory below the simulation model directory. S-parameters are in *.csv file format, which we need to convert now.  


![](./images/gds2palace_workflow_userguide.pdf-0012-01.png)


To do that conversion, the run_sim script where we started simulation with “run_palace” executes another command *combine_snp*.  

*combine_snp*  is a script that searches for Palace s-parameter files (port-S.csv) and converts them to Touchstone file format. If the model was simulated for selected port excitations only, missing rows in the S-parameter file will be padded with zeros. 

It should be noted that Palace frequency domain simulation cannot go down to 0 Hz, and the workflow script will replace any 0 Hz start frequency by a low value like 1 GHz. 

If simulation results include such low frequency data, combine_snp will create an additional S-Parameter file with suffix “_dc”, with a DC value extrapolated from the EM simulated data.<sup>1</sup> Always check that DC extrapolated dataset carefully before use! 


![](./images/gds2palace_workflow_userguide.pdf-0012-06.png)


This ends our quick tour of using the gds2palace workflow. There are many additional settings available, which will be described in detail in the next chapters. 

> 1 combine_snp is a Python script created for this workflow. DC extrapolation in this script is powered by Python library scikit-rf. 

## Simulation model file in detail 

### Input files 

Typical simulation models require two input files: GDSII geometries and XML stackup. 


![](./images/gds2palace_workflow_userguide.pdf-0013-03.png)


Two settings are available to control processing of the GDSII geometries: 


![](./images/gds2palace_workflow_userguide.pdf-0013-05.png)


**pre_process_gds** must be enabled if the layout includes any cutouts (holes) or other selfintersecting polygon boundaries. This will split such polygons into smaller entities, which can be processed properly. Without that preprocessing, mesh generation of layout with holes would fail with error messages like “Exception: Curve loop is not closed” 

**merge_polygon_size** applies to layers which are declared as _Type=”via”_ in the XML stackup file. 

When enabled with a non-zero value, the code will merge polygons on these layers with the given distance. This is how it works: in the GDSII reader, polygons on this layer will be oversized by half the given value, then all overlapping polygons on that layer will be merged, then undersized by half the given value. 

For via arrays that are oriented along the xy-axis, this will give the resulting bounding box if the maximum via spacing is no larger than the given value. 

### settings ###

settings for meshing and simulation control are implemented as a Python dictionary, which is passed to the simulation_setup.create_palace function. Some settings are required, other are optional with a meaningful default value.  

These settings are always required:  

**settings['unit']:** Unit of values in mesh, typically 1E-6  
**settings['margin']:** Oversize of dielectrics from bounding box of drawing in xy plane  
**settings['fstart']:** Start frequency in Hz  
**settings['fstop']:** Stop frequency in Hz  
**settings['fstep']:** Frequency step in Hz for output, not all of them need to be EM simulated due to adaptive frequency sweep  
**settings['refined_cellsize']:** Target mesh size at polygon edges  

There are additional **optional** settings to specify fixed discrete frequencies, which you can use in addition to fstart/fstop and fstep, or instead of fstart/fstop and fstep:  

**settings['fpoint']:** Discrete frequency/frequencies, values enclosed in [ ]. Example: settings['fpoint']=[10e9, 15e9]  
**settings['fdump']:** Same as fpoint, but Palace is configured to write a field dump for Paraview at this frequency/these frequencies. Example: settings['fdump']=[10e9]  

These other settings are optional:  

**settings['cells_per_wavelength']:** Calculated at highest frequency,value must be 10 or more, default is 10  
**settings['meshsize_max']:** Maximum mesh size limit, in addition to cells, default is 70  
**settings['refined_cellsize_override']:** Optional per-layer override of refined_cellsize,example: settings['refined_cellsize_override']=[['Metal3',10],['Metal2',2]]  
**settings['boundary']:** List with 6 values for boundary at xmin,xmax,ymin,ymax,zmin,zmax. Values can be ABC/PML, PEC or PMC. Default: ['ABC','ABC','ABC','ABC','ABC','ABC']  
**settings['air_around']:** Other spacing of air around dielectrics, default is same as margin. Can be a single value or a list of 6 values [air_xmin, air_xmax, air_ymin, air_ymax, air_zmin, air_zmax]. A value of 0 is allowed on any side, placing the simulation boundary flush with the dielectric/metal stack on that side (e.g. a backside ground plane serving directly as the PEC/ABC boundary, with no wasted air layer below it).  
**settings['order']:** Order of basis function for FEM solver (order 2 is more accurate,order 1 is only for quick & dirty results). Default is 2  
**settings['substrate_refinement']:** Extra mesh refinement into substrate, usually not required, default is False  
**settings['adaptive_sweep']:** Enable adaptive frequency sweep, default is True  
**settings['adaptive_mesh_iterations']:** Iterations for adaptive mesh refinement, often not required when using fine initial mesh, default is 0  
**settings['save_adaptive_mesh']:** Save mesh file from adaptive iteration for possible re-use, default is False  
**settings['save_gmsh_unrolled']:** Also save gmsh geometry file without meshing, for later inspection, default is False  
**settings['z_thickness_factor']:** Factor for metal thickness value on conductor side walls (see footnote), default is 1  
**settings['no_gui']:** Run script without showing gmsh user interface, useful for automated processing, default is False  
**settings['no_preview']:** don't show unmeshed geometry, immediately show meshed model, default is False  

footnote on z_thickness_factor: See chapter on metal loss at low frequency, where skin depth is larger than metal thickness   

### Port configuration ###

Similar to the IHP openEMS workflow, **ports are created based on polygons from the GDSII file** , located on special layers that are not part of the IHP layer table. Each port needs to use a different source layer in the GDSII file.  

The port mapping defines the port number and port impedance, and then maps the port geometry from the special GDSII input layer (usually 201 and above) to actual IHP technology layers. For the vertical ports shown here, we have from_layername and to_layername. For in-plane ports, we would have target_layername instead. Finally, the port direction is required to specify vertical ports or in-plane ports and their direction/polarity.  


![](./images/gds2palace_workflow_userguide.pdf-0016-03.png)


For this Palace workflow, the voltage parameter is not supported yet by the Palace solver. Palace only supports opposite polarity by reversing the port direction. **But here in our workflow, we use this voltage parameter to specify if a port is active: ports with voltage=0 will not be excited.**  

It must be noted that Palace behaves differently from other FEM solvers: to get the full S- matrix, we need to run all port excitations, one after another. This only happens if all port voltages are not zero. Only then, the full S-parameter output file can be created.  

**ATTENTION** : If any port excitation is zero, that “zero voltage” port will not be excited and that row in the S-parameter file will be padded with zeros. For example, if we simulate an 8-port circuit and only excite port 1, the S-parameter output will have valid results for S11, S21, … S81 but all other values will be zero. This can be useful to quickly simulate one specific path in the model.  

To get the full S-parameter file, all ports must be defined with non-zero voltage, so that all port excitations are simulated, one after another.  

**PORT SHAPE IN GDSII** : The workflow creates lumped ports in Palace, which need to be 2D sheets. This means that for vertical ports (via ports), you should draw a zero-width box in GDSII, resulting in a vertical 2D sheet with no width. If you define a vertical port from a box with finite xy area, the Palace port will be created as a vertical 2D sheet along the center line of that 2D box.  

**Composite ports** (multiple EM ports grouped into one port in the final output file) are not yet supported by this workflow. All ports with non-zero voltage are simulated one after another, resulting in n-port S-parameters.  

**Port parasitics in results, lumped port vs. wave port:** This workflow creates lumped ports, which introduce some physical length into the simulation model, leading to extra path length (? inductance) in results. Other 3D volume meshing EM tools behave the same for lumped ports. If port size is not small compared to the device under test, one possible solution is to estimate these parasitics and remove them in postprocessing (or result use) by cascading negative inductance or negative length at each port.  

### Filenames and flow control ###

If you want to have additional control over the names of files and directories that are created by the workflow, have a look at this section at the beginning of the simulation model file: 


![](./images/gds2palace_workflow_userguide.pdf-0017-02.png)


For example, if you want the customize the model name, to reflect settings used for meshing, you can define these values as variables and append that to the model_basename variable. 


![](./images/gds2palace_workflow_userguide.pdf-0017-04.png)


If you want the script to create the Palace files without showing the mesh in gmsh 3D viewer, this is also possible. 

You can use the optional _**settings[''no_gui']_ and either set this to _False_ (always run without graphical user interface) or you can check for an optional command line parameter passed to the simulation model script. 


![](./images/gds2palace_workflow_userguide.pdf-0018-02.png)


In this case, running the model as 

```
python mymodel.py
```

would run with 3D mesh viewer, or running the model as 

```
python mymodel.py nogui
```

would run without the 3D viewer. Maybe this gives some idea what customization is possible. 

## Examples 

This chapter gives examples on configuration settings, especially mesh control, and their results. 

### Single microstrip line 

The first testcase for meshing is a microstrip line with TopMetal2 over Metal1 ground. Width is 15 µm to achieve 50 Ohm line impedance, length is 880µm.  
This model is simulated with mesh configurations that vary 2 mesh parameters:  
- **'refined_cellsize'** defines the mesh resolution along the conductor edges 
- **'order** ' defines the order of basis functions, i.e. the degrees of freedom for field variation within one cell 

By default, we want to simulate with an order=2, which is a good trade-off between accuracy and speed. However, in this simple example, we will check how these two values can be configured for accurate results, and what this does to simulation time. 

**The basic idea is this:** if we have a higher order of basis functions, the fields can be modelled more accurately within each mesh cell, so we need less mesh cells ? larger value of refined_cellsize. 

If we use first order basis functions, we need higher mesh density to accurately model the field distribution.  
Mesh on conductors at **'refined_cellsize'** = 5: 


![](./images/gds2palace_workflow_userguide.pdf-0019-11.png)


Mesh on conductors at **'refined_cellsize'** = 2:  


![](./images/gds2palace_workflow_userguide.pdf-0020-00.png)


These two mesh densities are now simulated with different order of basis function.  


![](./images/gds2palace_workflow_userguide.pdf-0020-02.png)


The clear outlier in this return loss plot is the pink curve, simulated with mesh order = 1 at 2µm refined cellsize. This result is different from the other curves obtained with higher mesh order. Our default simulation would be the blue curve, obtained with refined_cellsize = 2µm and order = 2.  
Going to a larger value of refined_cellsize = 5µm (less mesh density at the edges) at order = 2 gives slightly different results, shown by the red curve.  

If we combine the larger refined_cellsize = 5µm with higher order = 3, to give each cell more degrees of freedom, we get similar results as our baseline (default) simulation: the green and blue curve are visually identical for S11. For S21 transmission, we get a similar result: these two are almost identical.  


![](./images/gds2palace_workflow_userguide.pdf-0021-00.png)


For phase of S21 we also have similar results: the order = 1 result is a clear outlier, but all other results are very close.  


![](./images/gds2palace_workflow_userguide.pdf-0021-02.png)


Conclusion: refined_cellsize=2 at order=2 is a good starting point, and for this example we don’t need to go any further. Decreasing the mesh resolution to refined_cellsize=5 at order=2 is possible if we can accept some small change in results.  Let’s look at simulation times for these 4 different meshing approaches:  

**Simulation time total, Degrees of freedom (from log)**  
refined_cellsize=2, order=2: 733s, DOF 1640126  
refined_cellsize=2, order=1: 64s, DOF 321999  
refined_cellsize=5, order=2: 282s, DOF 699658  
refined_cellsize=5, order=3: 1967s, DOF 1982661  



All simulations were done using adaptive frequency sweep and required 10 discrete frequencies to be EM simulated. Total time in the table also includes interpolation to the specified sweep range.  It can be seen that refined_cellsize=2, order=2 is the best choice for accurate data, we get results that are visually identical to refined_cellsize=5, order=3 at less simulation time (733 s total vs. 1967 s total).  

In the next chapter, we will go from that baseline setting, and investigate the use of adaptive mesh refinement.  

### Balun 140-170 GHz 

This testcase is a balun from the phase shifter project by Rupok Das, published for the OPDK July 2025 tapeout:  

- <u>https://github.com/IHP GmbH/TO_July2025/tree/main/FMD_QNC_D_Band_Phase_Shifter</u> 


![](./images/gds2palace_workflow_userguide.pdf-0023-03.png)



![](./images/gds2palace_workflow_userguide.pdf-0023-04.png)


Line width is 7µm with TopMetal2 over Metal3 ground, gap width is 2µm. 


![](./images/gds2palace_workflow_userguide.pdf-0023-06.png)


The critical dimension in this design is the 2µm wide gap between the coupler traces, the solver needs to model the field distribution in that gap with sufficient accuracy. 


![](./images/gds2palace_workflow_userguide.pdf-0024-01.png)



![](./images/gds2palace_workflow_userguide.pdf-0024-02.png)


We will first look at results from refined_cellsize=5 and refined_cellsize=2, both with order=2, over the frequency band 100 to 200 GHz, with all 3 port excitations simulated for full S- parameter data. 


![](./images/gds2palace_workflow_userguide.pdf-0025-01.png)



![](./images/gds2palace_workflow_userguide.pdf-0025-02.png)


There is quite a difference in S11 and S21,S31 results, and we can assume that the finer mesh gives more accurate results … but how far are we off from convergence? We could now simulate with an ever smaller refined_meshsize = 1, or we can use adaptive mesh refinement now. This will run the simulation starting with an initial mesh size, and then refine the mesh in the most relevant regions.  

By default, adaptive mesh refinement in Palace uses data from all simulation frequencies and all port excitations, which means a significant increase in overall simulation time because a full simulation is used during mesh refinement. The screenshot below shows settings from the Palace configuration file for an adaptive sweep with maximum of 2 adaptive mesh refinements, with up to 2 million degrees of freedom.  


![](./images/gds2palace_workflow_userguide.pdf-0026-01.png)


Note for experts: We could decide to create an adaptive mesh refinement at one target frequency, or a few selected target frequencies, and then store that refined mesh for the final full frequency sweep. This is the approach chosen by many commercial FEM solvers, where the user needs to decide what frequencies are used for AMR.  

However, that is not implemented in this gds2gmsh workflow. The present implementation of adaptive mesh refinement in gds2gmsh workflow does each refinement step at all frequencies and for all port excitations, to provide a safe and reliable mesh refinement. In this case, the refined mesh exists in memory only and is not stored to disk.  

Below is the result from an adaptive mesh refinement with 2 refinement steps, based on an initial mesh with refined_cellsize=5. This result is very close to the results obtained with a (fixed) mesh created from refined_cellsize=2, so both models come to similar results from different (initial) mesh.  


![](./images/gds2palace_workflow_userguide.pdf-0026-05.png)



![](./images/gds2palace_workflow_userguide.pdf-0027-00.png)


Here is the overview of simulation times and mesh size for full sweep over all 3 port excitations: 

**Simulation time total, Degrees of freedom (from log)**  
refined_cellsize=2: 580s (13 freq), DOF 836878  
refined_cellsize=5: 218s (13 freq), DOF 353056  
refined_cellsize=5 + AMR 2x: 1132s (13 freq), DOF 353056, 402138,710236   

We could now spend more time to double check result with an adaptive mesh refinement starting from an initial mesh that is even finer, and to save time, that could be done at one or few frequencies only. Below is the result for 3 selected frequencies with 2 mesh refinements starting from 2µm:  


![](./images/gds2palace_workflow_userguide.pdf-0027-04.png)



![](./images/gds2palace_workflow_userguide.pdf-0028-00.png)


This gives an idea where a converged result would be located in frequency, at approximately 150 GHz resonance instead of 145 GHz calculated with coarser mesh. Here is the overview of simulation times and mesh size for 3 frequencies (not full sweep!) over all 3 port excitations: 

**Simulation time total, Degrees of freedom (from log)**  
refined_cellsize=2 + AMR 2x: 1346s (3 freq), DOF 804166, 961866, 1742956  


## Conductor loss modelling 

Many RF FEM solvers, including this gds2palace workflow, model metals as hollow bodies with surface resistance on the side walls. The advantage of this approach is that we don’t need to mesh into skin effect, which might require sub-micron mesh size inside the conductors.  


![](./images/gds2palace_workflow_userguide.pdf-0029-02.png)


The surface impedance can be calculated easily when physical metal dimensions are much larger than skin depth. However, at low frequency and in the transition between skin effect regime and low frequency, we also need to consider conductor dimensions.  

### Limits of conductor loss calculation 

The gds2palace workflow creates surface elements for planar metals, and defines them as a conductor sheet with conductivity and thickness in the Palace config.json file. Thickness in this case is the value defined for that metal in the XML stackup file, e.g. 3µm thickness for TopMetal2.  

The code in Palace does not know anything about the aspect ratio of the conductor, and uses a surface impedance calculation that is accurate for wide sheets, where we have a conductor that is much wider than the conductor height. Summing up the surface impedance mapped to top and bottom side of a thin sheet, the resulting impedance would be accurate down to DC where it is limited by physical conductor cross section.  

However, in our RFIC use case, we might have conductor aspect ratio that reaches almost square shape, and we need to account for side wall currents, not only for closely spaced coupled lines.  

Mapping the surface impedance (as calculated internally by Palace from conductor thickness) onto all surfaces, i.e. side walls as well as top and bottom, will lead to an overestimate of available conductor cross section at low frequency:  

The Palace calculation<sup>3</sup> of Zs is exact when applied to top and bottom side only. If we apply this value to all sides, the extreme case at DC will over-estimate the conductor cross section by factor (width+thickness)/width.  


![](./images/gds2palace_workflow_userguide.pdf-0029-10.png)


> 3 https://github.com/awslabs/palace/blob/main/palace/models/surfaceconductivityoperator.cpp 

The approach taken by the gds2palace workflow script is to have a **scaling factor** that **reduces** the thickness value for the side walls. This reduces the error at low frequency (where skin depth is not much smaller than physical dimensions) and we converge towards the precise result in skin effect regime. 

In the model code, you can set this value by parameter 'z_thickness_factor': 


![](./images/gds2palace_workflow_userguide.pdf-0031-02.png)


If you do not specify this option, the default value for that scaling factor is 1.0 

### Testcase L2n0 with z_thickness_factor 0.33, 0.5 and 1.0 

One testcase to check the effect of parameter z_thickness_factor is the 2nH inductor already known from IHP openEMS workflow. 

The simulated inductance in differential model is visually identical for all 3 cases as expected, but  differential resistance shows a significant difference. 


![](./images/gds2palace_workflow_userguide.pdf-0031-07.png)



![](./images/gds2palace_workflow_userguide.pdf-0031-08.png)


Of course, this change in series resistance also shows up in Q factor: 


![](./images/gds2palace_workflow_userguide.pdf-0032-01.png)


It was confirmed by single frequency simulations near peak Q that this change is not an artefact from adaptive frequency sweep. 

This is not what we expected, because conductor width is 12µm. We do not have an extreme case where side walls give a massive over-estimate of total DC cross section, and indeed the low frequency resistance at 0.1 GHz is quite close: 1.27 Ohm @ z_thickness_factor = 0.33, 1.40 Ohm @ 0.5 and 1.45 Ohm @ 1.0 

The percentage difference increases in the medium frequency range, just around frequency of maximum Q for this testcase. 

To understand this, we check the skin depth of TopMetal2 in IHP SG13 technology: 1.29 µm @ 5 GHz. The skin effect correction done in internally in Palace calculates a correction factor from skin depth and half physical thickness, and at these frequencies both values are roughly the same, so that a correction of effective surface impedance takes place. By applying a correct factor on thickness used for side walls, we change surface impedance well into the skin effect regime! 

To check losses more wideband, we now look at “loss factor” which is the relative amount of power dissipated in the simulation model. The plot below shows that the main difference between the different runs for this model is in the frequency range 2 to 10 GHz, and results converge at higher frequencies. The Q factor comparison for the L2n0 testcase falls into the range of worst error. 


![](./images/gds2palace_workflow_userguide.pdf-0032-07.png)


To verify that the difference is not caused by insufficient mesh density, adaptive mesh refinement was carried out with 3 iterations at 5 GHz: loss factor changed by no more than 0.05 dB with those 3 steps of mesh refinement. 

(See PDF version of this document for calculation)

In other words, the we do not only change low frequency losses, but we also change high frequency impedance on the side walls, especially the imaginary part. 

### Testcase microstrip line 

As another test case, we use the 50 Ohm microstrip line from a previous chapter, where the mesh density and basis functions were investigated. The line is 15µm wide on TopMetal2 over Metal1 ground, with 880µm line length. 

Below is a plot of S21 where we can see some difference between z_thickness_factor=0.33 and z_thickness_factor=1.0 in insertion loss, especially in the frequency range up to 40 GHz. 


![](./images/gds2palace_workflow_userguide.pdf-0035-03.png)


When testing a narrower line with 7µm TopMetal2 over Metal3, this is not matched to 50 Ohm very well and S21 would show some ripple, so we better look at loss factor 1 - S11<sup>2</sup> - S21<sup>2</sup> to compare the metal losses between z_thickness_factor=0.33 and z_thickness_factor=1.0 


![](./images/gds2palace_workflow_userguide.pdf-0035-05.png)


This testcases uses a shorter line length of 500µm only, for faster simulation, so the total insertion loss of the shorter line is lower. Both 15µm line and 7µm line testcase were simulated with refined_cellsize = 2 and mesh order = 2, with no adaptive mesh refinement. 

### Compare to other data 

We can also compare simulated results of the line with 15µm TopMetal2 over Metal1 to other data sources: openEMS simulation and measurement. 

Palace simulations for this line were done without the substrate below, the stackup didn’t include the silicon substrate because we expect the Metal1 ground plane to shield the substrate from the fields in the transmission line. It was verified that the difference with/without substrate below is negligible for these line models.  

For openEMS (red curve), the simulation was also done without substrate below, using metal (PEC) side walls. Mesh refinement was set to 0.5µm because openEMS needs to mesh into skin effect. The measurement (light blue) was obtained by de-embedding the line from the overall measurement data with GSG pads, so the overall ripple might be partially due to this more complex setup.  


![](./images/gds2palace_workflow_userguide.pdf-0036-05.png)



![](./images/gds2palace_workflow_userguide.pdf-0036-06.png)


Looking at the S21 plot, the blue curve (Palace with z_thickness_factor=1) is closer to the others than the pink curve with z_thickness_factor=0.33  
We can also compare data for a longer line of 2580µm, width 15µm TopMetal2 over Metal1.  


![](./images/gds2palace_workflow_userguide.pdf-0037-01.png)



![](./images/gds2palace_workflow_userguide.pdf-0037-02.png)


The pink curve (Palace with z_thickness_factor=1) is closer to measured data up to 40 GHz. Above that frequency range, z_thickness_factor has very little effect.  
It can also be seen that measured insertion increases more with frequency than simulated. One possible explanation from an earlier paper was dielectric loss in the SiO2. This dielectric was modelled here as lossless dielectric, loss tangent = 0.  
If you prefer to use another value for loss tangent, that is fully supported by the gds2palace workflow, and can be specified easily in the XML stackup file.  

### Conclusion regarding z_thickness_factor 

Reduced thickness for the side walls looked like a simple, effective correction to prevent an over-estimate of low frequency conductor cross section, but this effect spreads out into the microwave frequency range. Further investigation is needed on this topic, to see which default setting is most appropriate.  

## Dielectric loss modelling 

The transmission line examples in the metal loss chapter showed a difference between simulated and measured insertion loss which increases toward higher frequencies.  

As already mentioned in that metal loss chapter, this could indicate higher **dielectric loss** than modelled. In the supplied XML stackup files, SiO2 is modelled as a lossless dielectric. To verify if dielectric loss could be the reason for poor agreement in that frequency range, we repeat the simulation of the 2580 µm line with non-zero loss tangent for the SiO2 layer.  

Loss tangent value used in this simulation is **0.01** , which is a rough estimate based on a paper published by IHP authors for SG25H technologies back in 2007:  
_Korndörfer F, F Sischka Optimization of the Substrate Parameters for EM-simulators MOSAK/ESSDERC/ESSCIRC Workshop (Munich) 14 Sep., 2007_  
- - <u>https://www.mos ak.org/munich_2007/posters/P05_MOS AK_Korndoerfer.pdf</u> 


![](./images/gds2palace_workflow_userguide.pdf-0038-06.png)


Indeed, that simulation with SiO2 loss tangent of 0.01 (pink curve) gives increased high frequency loss and quite nice agreement with the measured data above 50 GHz, much better than the model with lossless SiO2.  


![](./images/gds2palace_workflow_userguide.pdf-0038-08.png)


For the 880µm line length, the ripple on measurement data has a larger (relative) impact, but we see the same trend: simulation results with tand=0.01 are much closer to measurement than the simulation without SiO2 losses.  


![](./images/gds2palace_workflow_userguide.pdf-0039-01.png)


### Conclusion regarding dielectric losses 

The existing data is not complete enough to create an “official” technology stackup with SiO2 losses, but it seems that some amount of dielectric loss is real. If you decide to include dielectric loss in your simulation, this can be easily specified in the XML stackup file using parameter _DielectricLossTangent_ for the SiO2 material definition.  

## Advanced topics 

### Adaptive mesh refinement at selected frequencies only 

By default, adaptive mesh refinement in Palace uses data from all simulation frequencies and all port excitations, which means a significant increase in overall simulation time because a full simulation is used during mesh refinement. To do a two-step approach where the adaptive mesh refinement used only a limited set of frequencies, you could run the gds2palace workflow with those frequencies only, and change the config.json file to **store the resulting mesh data to disk** , by setting SaveAdaptMesh to true.  


![](./images/gds2palace_workflow_userguide.pdf-0040-04.png)


Adaptive frequency sweep would be **disabled** by removing the "AdaptiveTol" line in the frequency block. 

After running Palace with this config file, you will find a refined mesh file in the output folder. Note that the final mesh refinement result is **not** located in the “iteration_nn” folder, the results of adaptive sweep can be found one level above (!) in the parent folder.  You would then create another config.json file with the full frequency range and adaptive frequency sweep enabled, with the Mesh setting pointing to that adaptive mesh file created by the AMR before.  

### Using wave ports instead of lumped ports not supported 

This gds2palace workflow creates lumped ports, which introduce some physical size and thus some parasitic series impedance. The Palace solver also supports using wave ports, but that is not implemented in the gds2gmsh workflow. 

## Using S-Parameter output, model extraction 

S-Parameters are an accurate wideband description of the simulation results, but can be difficult to use in time domain circuits simulators. In this chapter, we will look at some possible solutions. 

### Lumped circuit model extraction 

For a limited range of devices, we can use straightforward calculation of the equivalent lumped circuit model. Such a calculation is available here, based on simple narrowband calculation: 

<u>https://github.com/VolkerMuehlhaus/lumpedmodel</u>  

Currently, these devices are supported:  
- Untapped inductors (2-port)  
- MIM capacitor (2-port)  
- Transmission line model (RLGC, 2-port data)  

These tools are provided as Python scripts. The user needs to specify a target frequency, the fit result is then plotted along with the input data to show the quality of the model fit. For sure, there are other extraction tools available elsewhere that might cover more use cases.  

### Mathematical “black box” vector fit 

Another approach is to do vector fitting of arbitrary n-port data. One possible implementation is available here, using the vector fit in scikit-rf library: 
<u>https://github.com/VolkerMuehlhaus/lumpedmodel/tree/main/vector_fit</u> 


![](./images/gds2palace_workflow_userguide.pdf-0041-14.png)


## Using gds2palace with Elmer FEM for EM simulation

[Elmer FEM](https://www.elmerfem.org/) is an open-source multiphysics FEM solver. In addition to the AWS Palace output described so far in this guide, gds2palace can create input files for Elmer's electromagnetic (`VectorHelmholtz`) solver, producing S-parameters from the same layout, stackup and port model already used for Palace.

### Installing Elmer FEM

Elmer FEM is not distributed with gds2palace and must be installed separately, see <u>https://www.elmerfem.org/</u>. gds2palace needs to find two Elmer command-line tools: `ElmerGrid` (mesh conversion) and `ElmerSolver` (the solver itself).

- **Windows:** set the environment variable `ELMER_HOME` to your Elmer install directory. gds2palace looks for `%ELMER_HOME%\bin\ElmerGrid.exe`.
- **Linux/macOS:** make sure `ElmerGrid` and `ElmerSolver` are available on your `PATH`.

If you use `settings['ELMER_MPI_THREADS']` to run Elmer across multiple processes, you also need an MPI implementation installed (see "External tools (not Python modules)" above) — on Windows this is Microsoft MPI, providing the `mpiexec`/`mpirun` launcher the generated `run_elmer` script uses.

### From a Palace model to an Elmer model

An Elmer EM model uses the same **GDSII layout**, **XML stackup file**, **settings dictionary** and **port definitions** already described in chapter "Simulation model file in detail". The only change needed at the end of the model script is which output function is called:

```python
# Palace output
config_name, data_dir = simulation_setup.create_palace (excite_ports, settings)
utilities.create_run_script(sim_path)
```

becomes

```python
# Elmer FEM output
config_name, data_dir = simulation_setup.create_elmer (excite_ports, settings)
utilities.create_elmer_run_script(sim_path, settings)
```

Everything else in the model script — `gds_filename`, `XML_filename`, `settings['unit']`, `settings['margin']`, `settings['refined_cellsize']`, and port definitions via `simulation_setup.all_simulation_ports()` / `simulation_setup.simulation_port(...)` — stays exactly the same as for a Palace model.

**Important difference in how ports are excited:** Palace runs one solver pass per active port excitation (controlled by each port's `voltage` and the `excite_ports` list) to build up the full S-matrix, and ports with `voltage=0` are skipped to save simulation time. Elmer's EM solver instead uses a *constraint modes* ("scanning") analysis that solves for **all** ports defined in the model in a single run. This means:

- Every port you define in `simulation_ports` appears in the resulting Elmer S-matrix, regardless of its `voltage` setting.
- There is no equivalent to the Palace "excite only port 1" trick to save time — with Elmer, you get the full n-port S-matrix or nothing.
- Depending on port count and mesh size, a full n-port Elmer run can be faster or slower than n separate Palace excitation runs; this depends on the specific model.

### Frequency sweep

`settings['fstart']`, `settings['fstop']`, `settings['fstep']`, `settings['fpoint']` and `settings['fdump']` are read the same way as for Palace and written to a plain frequency list (`frequencies.dat`) for Elmer. Note that Palace's adaptive frequency sweep interpolation (`settings['adaptive_sweep']`) has no Elmer equivalent — Elmer solves at every frequency you list, so simulation time scales directly with the number of frequency points.

### Mesh order and solver method

```python
settings['order'] = 2          # 1 = linear, 2 = quadratic (recommended), default 2
settings['iterative'] = False  # True = iterative linear solver, False = direct solver (default)
```

- `settings['order']` selects the basis function order, same setting as used for Palace. Elmer supports order 1 (linear) and order 2 (quadratic); other values fall back to the order-1 solver recipe.
- `settings['iterative']` selects between Elmer's direct solver (MUMPS, default, robust for small/medium models) and an iterative solver, which can be more memory-efficient for large models.
- `settings['ELMER_MPI_THREADS']` (optional) enables MPI-parallel solving: gds2palace partitions the mesh with `ElmerGrid` for the given number of MPI processes, and the generated `run_elmer` script (see below) uses `mpirun` to start `ElmerSolver`.

```python
settings['ELMER_MPI_THREADS'] = 8   # partition mesh and solve using 8 MPI processes
```

### Boundary conditions and current limitations

`settings['boundary']` (the six-sided outer simulation boundary, values ABC/PML/PEC/PMC) works the same way as for Palace, including PMC.

A few other Palace features are not yet available in the Elmer EM flow:

- **Sheet resistor layers** (`Type="sheet"` metal paired with a `Resistor` material, as used for on-chip resistors) are not yet supported for Elmer EM output.
- **Composite ports** (grouping several EM ports into one output port) are not supported, same limitation as for Palace.
- Metal loss is modeled from conductivity using Elmer's built-in "good conductor" surface impedance; the explicit finite-thickness side-wall correction available for Palace (`settings['z_thickness_factor']`) does not carry over to Elmer output.

### Running the Elmer EM simulation and getting S-parameters

`utilities.create_elmer_run_script(sim_path, settings)` writes a `run_elmer` script into the model output directory, next to the generated Elmer input files (`physics.sif`, `case.sif`, `frequencies.dat`, `mesh/`, `ELMERSOLVER_STARTINFO`):

```bash
#!/bin/bash
ElmerSolver
combine_snp
```

or, if `settings['ELMER_MPI_THREADS']` is set to more than 1:

```bash
#!/bin/bash
mpirun -np 8 ElmerSolver case.sif
combine_snp
```

Run it from the model output directory:

```
cd <model>_data
./run_elmer
```

`ElmerSolver` finds `case.sif` automatically via `ELMERSOLVER_STARTINFO`. The same `combine_snp` postprocessing script already used for Palace results also recognizes Elmer's `scalar_results` output and converts it to Touchstone (`.sNp`) format, so downstream use of Elmer S-parameters is identical to Palace results.


## Using gds2palace with Elmer FEM for thermal simulation

In addition to EM simulation, gds2palace can generate input for Elmer's steady-state Heat Equation solver, producing a 3D temperature field from user-defined heat sources and constant-temperature boundaries. This shares the same GDSII + XML stackup pipeline as the EM flows, but does not use frequencies or ports.

Elmer FEM must be installed as described above (`ElmerGrid` and `ElmerSolver` on `PATH`, or `ELMER_HOME` set on Windows).

A complete, extensively documented worked example (model script, stackup XML, and GDSII layout) is available at [`more_examples/thermal_simulation_using_Elmer/Elmer_Thermal_Workflow.md`](../../more_examples/thermal_simulation_using_Elmer/Elmer_Thermal_Workflow.md) — this chapter summarizes the key points.

### Stackup XML: thermal material properties

For a thermal run, every `<Material>` needs a thermal conductivity. Only steady-state conductivity is evaluated so far; electrical parameters (used for S-parameter simulation) are not needed for a thermal-only model, though the same stackup file can be reused for both EM and thermal simulation.

```xml
<Material Name="TopMetal2" Type="Conductor" Conductivity="30300000.0"
          Density="2700" ThermalConductivity="237" Color="ff8000"/>
```

- `Density` (kg/m³) is written through to Elmer but not used by the steady-state solver.
- `ThermalConductivity` is a single value in W/(m·K), for materials whose conductivity doesn't change meaningfully with temperature.
- `ThermalConductivityTable` points to a `<Table>` instead, for temperature-dependent conductivity (e.g. silicon substrate):

```xml
<Material Name="HighResSubstrate" Type="Semiconductor" Conductivity="0.025"
          ThermalConductivityTable="SiliconThermalCond" Density="2329"/>
...
<Tables>
  <Table Name="SiliconThermalCond">
    <Point Temperature="280" Value="163.00"/>
    <Point Temperature="290" Value="155.20"/>
  </Table>
</Tables>
```

gds2palace writes this straight through as an Elmer temperature-dependent material table — no manual `.sif` editing needed. See chapter "Extended XML stackup format" in the Appendix and [`XML_stackup_format.md`](../XML_stackup_format/XML_stackup_format.md) for the full attribute reference.

### Heat sources and constant-temperature boundaries

Instead of ports, a thermal model declares where heat enters and leaves through `thermal_objects`, using ordinary marker polygons drawn on dedicated GDSII layers:

```python
thermal_objects = simulation_setup.all_thermal_objects()
thermal_objects.add_heatsource(simulation_setup.heatsource(
    power=0.65, source_layernum=201, target_layername='TFR'))
thermal_objects.add_consttemp(simulation_setup.constanttemp(
    temp=298, source_layernum=202, target_layername='BACKSIDEGND'))
```

- `source_layernum` is a GDSII layer number you draw purely as an xy footprint marker; it does not set a z-position.
- `target_layername` is the name of an existing `<Layer>` from the stackup XML — its z-range becomes the 3D volume the source/boundary is applied to.
- `heatsource(power, ...)` dissipates `power` Watts as a volumetric heat source over that volume. In the example above, 0.65 W is applied to the `TFR` resistor layer via marker layer 201.
- `constanttemp(temp, ...)` fixes that volume's temperature (Kelvin), acting as a heat sink/reference boundary. In the example above, layer 202 pins the `BACKSIDEGND` layer to 298 K (25 °C), a typical backside heatsink boundary.

The target layer for a heat source must be a volume (`Zmax` larger than `Zmin`). The target layer for a constant-temperature boundary is usually a zero-thickness sheet layer (`Zmax = Zmin`) — if it has finite thickness instead, two boundaries are created, one at each face.

### Model script settings

```python
settings['unit']              = 1e-6   # geometry is in microns
settings['margin']            = 100    # air margin around the layout, in microns
settings['refined_cellsize']  = 5      # extra-fine mesh near heat sources
settings['meshsize_max']      = 100    # coarsest mesh size, in microns
settings['elmer_thermal']     = True   # selects the thermal flow instead of EM/Palace
settings['thermal_objects']   = thermal_objects
```

`settings['no_gui'] = True` skips the interactive gmsh mesh preview, useful for unattended/batch runs. Then create the model:

```python
config_name, data_dir = simulation_setup.create_elmer_thermal (settings)
```

Note there is no `excite_ports` argument here — a thermal run has no ports.

### Running ElmerSolver and viewing results

Output goes to an `elmer_model/` folder next to the script, containing the gmsh mesh, the Elmer-native `mesh/` folder (from `ElmerGrid`), `case.sif` (materials, body/volume definitions, the heat source as a volumetric Body Force, and the constant-temperature Boundary Condition), and `ELMERSOLVER_STARTINFO`. It's worth a quick look at `case.sif` before solving, especially the first time you use a new stackup — it's plain text and easy to sanity-check.

```
cd elmer_model
ElmerSolver
```

Results appear in the same directory:

- `thermal_results.vtu` — full 3D temperature field, open in ParaView.
- `thermal_results.dat` — quick min/max temperature summary (plain text).

If `settings['ELMER_MPI_THREADS']` is set to more than 1, gds2palace also partitions the mesh for you; run `ElmerSolver_mpi` with your MPI launcher of choice instead of the single-threaded `ElmerSolver`.

### Using setupThermal instead of writing Python code

[setupThermal](https://github.com/VolkerMuehlhaus/setupEM) is a desktop GUI (part of the `setupEM` project) that drives this same flow without writing a Python model script by hand: pick the layout/stackup files, add heat sources and constant-temperature boundaries in a table (GDSII source layer, target stackup layer name, and power in W or temperature in K), then generate and run the model, or launch `ElmerSolver` directly from the app with output streamed to an on-screen log. The **Model** tab shows the generated Python code, so you can inspect or export it if you'd rather take over from there manually.


## Appendix 

### Understanding volumes and surfaces created from GDSII 

The workflow creates different types of geometry: volumes and surfaces. This depends on the mapping in the XML stackup file. 

**Geometries from GDSII layers** are defined in the “Layers” section of the XML file : 
- Type=”conductor” is used for all regular metal layers, in the mesh they are represented by **“Surface”** objects on all boundaries (top, bottom, side walls). In other words, these metals are represented by hollow shells and not by solid volumes.  
- Type=”sheet” is used for metal layers that have no physical height in the model, they are represented as one flat **“Surface** ” only.  
- Type=”via” is used for via layers, these are represented in the mesh by **“Volume”** objects.  

#### **Important: Conductor layers must never be stacked directly, they must be separated by a via layer!** 

Extract from an XML stackup file, showing layer mappings with conductor, via and sheet types: 


![](./images/gds2palace_workflow_userguide.pdf-0042-09.png)


Resulting mesh with surface and volume objects: 


![](./images/gds2palace_workflow_userguide.pdf-0043-00.png)


**Dielectrics:** There are additional materials in the stackup that are not drawn in the GDSII file, such as substrate or oxide or passivation. These are created as **“Volume”** objects in the mesh.  
Dielectrics are defined in the <Dielectrics> section of the XML file, and usually cover the entire drawing area (bounding box of GDSII drawing) plus an additional “margin” that is defined in the simulation model code.  


![](./images/gds2palace_workflow_userguide.pdf-0043-03.png)


As an option, the size of these dielectric layers can be defined by an optional parameter **Boundary** which sets the size of the dielectric from the bounding box of that layer in the GDSII file.  


![](./images/gds2palace_workflow_userguide.pdf-0044-00.png)


### Mapping of Volumes and Surfaces to Palace materials 

Palace offers a wide range of options to assign material properties to volumes and surfaces. Our workflow creates that mapping in the Palace control file (config.json), as described below:  

**Via layers** (Type=”via”) are created as volumes, and the conductivity defined in the XML stackup is assigned to these volumes.  


![](./images/gds2palace_workflow_userguide.pdf-0045-03.png)


To account for the z-directed nature of via arrays, which allows current flow predominantly in z direction, the conductivity from XML is only assigned to z-direction, and the value in xydirection is reduced by a factor of 10. This avoids issues with “unreal” currents flowing on the side walls of merged via polygons after via array merging.  

**Metal layers** (Type=”conductor”) are created as hollow elements surrounded by surfaces, with surface impedance to define metal loss. The conductivity and thickness are obtained from the XML file.  


![](./images/gds2palace_workflow_userguide.pdf-0045-06.png)


This is straightforward for top and bottom of the conductors, with the total conductor cross section being calculated properly even at low frequency where skin depth is larger than the physical conductor height.  

However, using that same surface impedance also for the side walls, we would over-estimate the total physical cross section, so the side walls get a different material mapping with a thickness value that is only 1/3 of the top/bottom values. This gives a reasonable result also in the transition from skin effect regime to low frequency.  

**Metall sheet layers** (Type=”sheet”) are created as a single, flat surface. Their position in the stackup should be defined with Zmin=Zmax for better readability, but actually the Zmax value is ignored here.  
 

![](./images/gds2palace_workflow_userguide.pdf-0046-01.png)


These sheets are typically used with a Type=”Resistor” material definition in the XML file, with fixed sheet resistance in Ohm/square. 


![](./images/gds2palace_workflow_userguide.pdf-0046-03.png)


In the Palace config file, this results in an Impedance boundary with Rs value mapped to the surface.  


![](./images/gds2palace_workflow_userguide.pdf-0046-05.png)


### Extended XML stackup format

The XML stackup format has grown beyond the basic dielectric stack and conductor/via layer mapping described above. The current major additions, all optional and backward-compatible with older stackup files, are:

- **Derived layers** — a layer's geometry can be computed from other layers via boolean operations (`AND`/`OR`/`XOR`/`NOT`) and resizing, instead of only being read directly from GDSII. Used, for example, to derive on-chip resistor geometry from existing process layers.
- **Reference-relative positioning** — a `<Layer>` or `<Dielectric>` can be positioned as an offset from the top or bottom edge of another named layer/dielectric, instead of requiring an absolute Zmin/Zmax.
- **Thermal material properties** — `Density`, `ThermalConductivity` and `ThermalConductivityTable` on `<Material>`, plus a `<Tables>` block for temperature-dependent conductivity, used by the Elmer thermal flow described in chapter "Using gds2palace with Elmer FEM for thermal simulation".

Using derived layers, reference-relative positioning, or thermal conductivity tables requires `schemaVersion="3.0"` in the `<Stackup>` root element. The stackup reader prints a warning if a file declares a newer `schemaVersion` than the installed gds2palace version supports, so an outdated installation is easier to notice.

The full attribute reference, with examples, is in [`XML_stackup_format.md`](../XML_stackup_format/XML_stackup_format.md), and derived-layer details specifically are in [`derived_layers.md`](../XML_stackup_format/derived_layers.md).

### Software versions used in this document 

Palace version used for this document: v0.14  
Palace installation method used: container for Apptainer environment, running on Ubuntu 24.04.02 LTS  
Simulation host: AMD Ryzen 9-7950X (16 cores) with 128 GB RAM  
Code base used for this test: gds2palace Python scripts as of October 13, 2025 (unless noted otherwise)  

## List of examples 

Here is an overview of model examples. 

### palace_line_viaport.py 

Microstrip line on TopMetal2 over Metal1 ground plane, with via ports on both ends. Geometry is read from GDSII. The stackup does not include bulk silicon because that is shield by the ground plane anyway. 

![](./images/gds2palace_workflow_userguide.pdf-0048-04.png)

https://github.com/VolkerMuehlhaus/gds2palace_ihp_sg13g2/blob/main/workflow/palace_line_viaport.py  


### palace_line_noGDS.py 

Similar to palace_line_viaport.py but geometry is created by code instead of reading it from GDSII. 
https://github.com/VolkerMuehlhaus/gds2palace_ihp_sg13g2/blob/main/workflow/palace_line_noGDS.py


### palace_ind_frame.py 

This is a 2-port inductor embedded into a metal frame. Geometry from GDSII. 

![](./images/gds2palace_workflow_userguide.pdf-0048-09.png)

https://github.com/VolkerMuehlhaus/gds2palace_ihp_sg13g2/blob/main/workflow/palace_ind_frame.py


### palace_L2n0.py 

2-port octagon inductor with via ports down to an artificial metal plane that sits on the surface of bulk silicon. 


![](./images/gds2palace_workflow_userguide.pdf-0049-02.png)


https://github.com/VolkerMuehlhaus/gds2palace_ihp_sg13g2/blob/main/workflow/palace_L2n0.py  

Field dump at a single frequency is enabled in this model. The Paraview screenshot below shows current density using this file:


![](./images/gds2palace_workflow_userguide.pdf-0049-04.png)


### palace_butlermatrix.py 

This is quite a big model, the Butler Matrix by Ardavan Rahimian in IHP Open PDK Tapeout - July 2025, available at https://github.com/IHP <u>GmbH/TO_July2025/tree/main/W_Band_Butler_Matrix_IC</u> 


![](./images/gds2palace_workflow_userguide.pdf-0050-02.png)

https://github.com/VolkerMuehlhaus/gds2palace_ihp_sg13g2/blob/main/workflow/palace_butlermatrix.py  

Geometry is from GDSII, the model uses a total of 8 via ports between Metal3 and TopMetal2. However, to speed up simulation, only one port excitation is active in this model, and we only get S11,S21,S31,S41,S51,S61,S71 and S81 from this simulation run. 


![](./images/gds2palace_workflow_userguide.pdf-0050-04.png)


All other port excitations are set to voltage=0 in the model. To get full 8-port S-parameters, we would need to change all port voltages to 1 and re-run the model, so that all excitations are simulated, one after another. 

### palace_butlermatrix_dump93.py 

Same as before, but a field dump setting is added in this model at 93 GHz. 


![](./images/gds2palace_workflow_userguide.pdf-0050-08.png)

https://github.com/VolkerMuehlhaus/gds2palace_ihp_sg13g2/blob/main/workflow/palace_butlermatrix_dump93.py  


### palace_core.py 

This is the 4-port “core” model of the 60 GHz medium power amplifier from IHP Analog Academy online course. There are two via ports at the input and output, and two in-plane ports on Metal2 between the common emitter polygon and base/collector coming down from the via stacks. 


![](./images/gds2palace_workflow_userguide.pdf-0051-02.png)

https://github.com/VolkerMuehlhaus/gds2palace_ihp_sg13g2/blob/main/workflow/palace_core.py  

### palace_rfcmim.py 

This is 2-port model of an rf_cmim component with some feedline length. Via ports are used at the input and output down to the Metal1 ground plane.  Via arrays are merged by this setting: merge_polygon_size = 2   


![](./images/gds2palace_workflow_userguide.pdf-0051-05.png)

https://github.com/VolkerMuehlhaus/gds2palace_ihp_sg13g2/blob/main/workflow/palace_rfcmim.py

### palace_pcb_lowpass.py 

This shows a use case of gds2palace outside the RFIC domain: the layout of a PCB lowpass on RO4003 substrate was imported to klayout and saved in GDSII format. 


![](./images/gds2palace_workflow_userguide.pdf-0052-02.png)

An XML stackup file was created for this substrate, with layout layers matching the layer numbers used in klayout. 

![](./images/gds2palace_workflow_userguide.pdf-0052-04.png)

Here, setting “margins” only controls the (small) oversize of the dielectrics from the drawing layers. The optional “air_around” setting was used in the simulation model to define the air margins independently, without adding these air layers in the XML stackup.  

![](./images/gds2palace_workflow_userguide.pdf-0052-06.png)

https://github.com/VolkerMuehlhaus/gds2palace_ihp_sg13g2/blob/main/workflow/palace_pcb_lowpass.py  


# Change list 

This is an (incomplete) list of changes and new features.

## 14-June-2026
Completely redesigned the core mesh algorithm, which previously had thrown Palace MFEM error message for certain stacked chip configurations. Now, metals are properly cut from dielectrics no matter if they cross dielectric boundaries. Handling of gmsh dimtags to material properties was completely redesigned. Some error check were added on invalid port configurations, and invalid stackup configurations where two conductor layers touch directly with no via metal between them.


## 15-Mar-2026
A pre-generated apptainer container image for Palace version 0.16 is now available here:
https://github.com/users/VolkerMuehlhaus/packages/container/package/palace_016


To download the palace version 0.16 container into your current directory:

```
$ apptainer pull ghcr.io/volkermuehlhaus/palace_016:latest
```

This will save the container file to palace_016_latest.sif to your current directory. When using this container with scripts for the gds2palace workflow, make sure that the *.sif filename in the script matches your actual filename and file location where you stored the *.sif



## 10-Jan-2026
Fixed bug in port metadata information for in-plane ports, direction was not properly evaluated in some cases (check for "X" orientation was case sensitive). This resulted in incorrect port de-embedding, with width and length swapped for in-plane ports specified as "x" or "-x" direction. 


## 9-Dec-2025
Fixed an issue that caused mesh error when stacked objects overlapped exactly. Now, stacking objects with same size (resulting in shared surface) works correct.

A Python-based user interface for gds2palace named setupEM is now available. 
You can install this using pip install:

```
    pip install setupEM
```
This is work in progress with frequent updates, which can be installed using
```
    pip install setupEM --upgrade
```

Project source and documentation: 
https://github.com/VolkerMuehlhaus/setupEM


## 1-Dec-2025
Instead of always having the gds2palace directory in your working directory, 
you can also install gds2palace module to your venv using pip install:

```
    pip install gds2palace
```

https://pypi.org/project/gds2palace/

## 23-Nov-2025
- Added optional setting: options["fdump"] = [frequency] to create Palace points list with field dump enabled. 
- New example file palace_butlermatrix_dump93.py shows usage of fdump option. 

- Updated User's guide with new options, added a chapter listing examples

## 22-Nov-2025
- Added optional setting: options["fpoint"] = [frequency] to specify single frequency or list [] of frequencies separated by comma

## 21-Nov-2025
- Calculation of maximum meshsize is now per dielectric layer, means larger mesh cells in air and oxide.
- Added check to enforce gdspy version 1.6 or later, because gdspy 1.4.2 causes issues.
- Add version information for gds2python module files.
- Palace solver setting changed to AdaptiveTol = 2e-2

## 19-Nov-2025
- Improved combine_extend_snp code (postprecessing of results Palace to SnP) to handle more than 9 ports

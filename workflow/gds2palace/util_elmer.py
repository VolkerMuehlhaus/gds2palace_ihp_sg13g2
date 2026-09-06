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

# This is additional code for the gds2palace from to implement the Elmer FEM output option
import os
import subprocess
import platform

def write_elmer_frequencies (elmer_freq_file, 
                             fstart, 
                             fstop, 
                             fstep, 
                             f_discrete_list, 
                             f_dump_list):
        
        # write simulation frequencies for Elmer
        with open(elmer_freq_file, "w") as freqfile:  
            frequency_list = []
            
            if (fstart is not None) and (fstop is not None):
                f = fstart
                if (fstop > fstart) and (fstep > 0):
                    while f <= fstop:
                        frequency_list.append(f)
                        f = f + fstep                
                # always include last value
                if fstop not in frequency_list:
                    frequency_list.append(fstop)
            
            # append f_discrete_list 
            if len(f_discrete_list) > 0:
                frequency_list.extend(f_discrete_list)

            # append f_dump_list 
            if len(f_dump_list) > 0:
                frequency_list.extend(f_dump_list)

            # sort and write to file
            frequency_list.sort()
            for n, freq in enumerate(frequency_list):
                freqfile.write(f"{n+1}  {freq:.3e}\n")

            # store number of frequencies because we need to write that to physics.sif
            num_frequencies = n+1

        freqfile.close() 
        return num_frequencies  

def write_elmer_physics_file (unit,
                              elmer_physics_file,
                              num_frequencies,
                              Elmer_materials,
                              Elmer_bodies,
                              Elmer_boundaries,
                              Elmer_ports,
                              PEC_boundaries,
                              PML_boundaries,
                              PMC_boundaries,
                              f_dump_list=None):

        with open(elmer_physics_file, "w") as f:

            # specify storage of dump files: only when fdump frequencies were requested,
            # since Elmer's "Scanning" simulation has no per-sample SaveStep like Palace -
            # this dumps fields at every solved frequency, not just the fdump-selected ones
            dump_requested = bool(f_dump_list)
            if dump_requested:
                item = '! Save vtu field dump files at every solved frequency (other options: "after timestep", "after all")\n'
            else:
                item = '! Dont save vtu files (other options: "after timestep", "after all")\n'
            item = item + f'Solver 3 :: Exec Solver = String "{"Always" if dump_requested else "never"}"\n\n'
            f.write(item + '\n')

            # frequency block that references output file frequencies.dat
            item = f'Simulation\n  timestep intervals(1) = {num_frequencies}\nend\n'
            f.write(item + '\n')

            item = 'Solver 1\n' 
            item = item + '   frequency = variable time\n'
            item = item + '     real\n'
            item = item + '       include frequencies.dat\n'
            item = item + '     end\n'
            item = item + 'End\n'
            f.write(item + '\n')


            # write Material sections
            for n,material in enumerate(Elmer_materials):
                materialname = material["name"]
                permittivity = material["permittivity"]
                conductivity = material["conductivity"]
                permeability = 1.0

                item = f'Material {n+1}\n   name = string "{materialname}"\n'
                item = item + f"   relative permittivity = {permittivity}\n"
                item = item + f"   electric conductivity = {conductivity}\n"
                item = item + f"   relative permeability = {permeability}\n"
                item = item + "End\n"
                f.write(item + "\n")

            # write Bodies sections
            for n,body in enumerate(Elmer_bodies):
                name = body["name"]
                material = body["material"]
                item = f'Body {n+1}\n   Equation = Integer 1\n'
                item = item + f'   Name = "{name}"\n'
                item = item + f"   material = {material}\n"
                item = item + "End\n"
                f.write(item + '\n')

            # write metal boundaries section
            for n,boundary in enumerate(Elmer_boundaries):
                name = boundary["name"]
                conductivity = boundary["conductivity"]
                thickness_SI = boundary["thickness"]*unit
                item = f'Boundary Condition {n+1}\n'
                item = item + f'   Name = "{name}"\n'
                item = item + f'   Layer Relative Reluctivity = Real 1.0\n'
                item = item + f'   Layer Electric Conductivity = Real {conductivity:.3f}\n'
                item = item + f"   Good Conductor BC = True\n"
                item = item +  '   ! Either use "good conductor" or give layer thickness.\n'
                item = item + f"   !Layer Thickness = {thickness_SI:.3e}\n"
                item = item + "End\n"
                f.write(item + '\n')

            # write port boundaries section
            for boundary in Elmer_ports:
                n = n+1 # continue number range started in metal boundaries
                name = boundary["name"]
                portnum = boundary["portnum"]
                portZ0 = boundary["Z0"]
                direction = boundary["direction"]
                item = f'Boundary Condition {n+1}\n'
                item = item + f'   Name = "{name}"\n'
                item = item + f'   Constraint Mode = {portnum}\n'
                item = item + f'   Port Type = String "rectangular"\n'
                item = item + f'   Port Impedance = Real {portZ0}\n'
                item = item + f'   Port Direction = Integer {direction}\n'
                item = item + "End\n"
                f.write(item + '\n')


            # write outer simulation boundary
            if len(PEC_boundaries) > 0:
                n = n+1
                name = 'PEC_boundary'
                item = f'Boundary Condition {n+1}\n'
                item = item + f'   Name = "{name}"\n'
                item = item +  '   E re {e} = Real 0\n'
                item = item +  '   E im {e} = Real 0\n'
                item = item + "End\n"
                f.write(item + '\n')


            if len(PML_boundaries) > 0:
                n = n+1
                name = 'Absorbing_boundary'
                item = f'Boundary Condition {n+1}\n'
                item = item + f'   Name = "{name}"\n'
                item = item + f'   Absorbing BC = True\n'
                item = item + "End\n"
                f.write(item + '\n')

            if len(PMC_boundaries) > 0:
                # No physics keywords needed: per the ElmerModelsManual VectorHelmholtz chapter,
                # the natural (Neumann) boundary condition of this curl-curl formulation - i.e.
                # what a boundary gets when no Robin/Dirichlet keyword is written for it at all -
                # is exactly the PMC (zero tangential H) condition. The mesh already carries a
                # physical group named 'PMC_boundary' for these faces (see util_simulation_setup.py),
                # so an explicit-but-empty block here is enough; Elmer applies the natural BC to it.
                n = n+1
                name = 'PMC_boundary'
                item = f'Boundary Condition {n+1}\n'
                item = item + f'   Name = "{name}"\n'
                item = item + "End\n"
                f.write(item + '\n')

        f.close()   


def write_case_and_solver_files (targetdir, order, iterative, ELMER_MPI_THREADS=1):
    # Elmer EM simulation: write case.sif and the solver files included there

    # set most efficient solver method 
    if order==2:
        solver_option = 'quadratic approximation = true'
        if iterative:
            solver_option = solver_option + '\n    include "quadratic-iterative.sif"'
        else:
            solver_option = solver_option + '\n    include "quadratic-direct.sif"'
    else:
        # order = 1
        solver_option = 'include "first-order.sif"'


    # extra settings for MPI parallel computing
    if ELMER_MPI_THREADS <= 6:
        increase = 0
    elif ELMER_MPI_THREADS <= 8:
        increase = 50
    elif ELMER_MPI_THREADS <= 12:
        increase = 100
    elif ELMER_MPI_THREADS <= 15:
        increase = 150
    else: 
        increase = 250


    casedata=f'''
    Check Keywords "warn"

    Header
    Mesh DB "mesh" "."
    End

    Simulation
    Coordinate Mapping(3) = Integer 1 2 3
    Coordinate Scaling = Real 1e-6
    Coordinate System = String "Cartesian"
    Simulation Type = String "Scanning"
    timestep sizes(1) = 1
    Steady State Max Iterations = Integer 1
    Steady State Min Iterations = Integer 0
    Use Mesh Names = Logical True
    output level = 10
    mesh levels = 1
    End

    Solver 1
    Procedure = File "VectorHelmholtz" "VectorHelmholtzSolver"
    Equation = String "curlcurl"
    Exec Solver = String "Always"
    
    use piola transform = true

    ! Here add option: 
    ! - quadratic approximation true
    !   - direct solver
    !   - iterative solver
    ! - quadratic approximation false
    
    {solver_option}
    
    Mumps percentage increase working space = integer {increase} ! table lookup for {ELMER_MPI_THREADS} MPI parallel runs

    constraint modes analysis = true
    Constraint Modes Matrix Results = true
    End


    Solver 2
    Equation = "calcfields"

    Procedure = "VectorHelmholtz" "VectorHelmholtzCalcFields"

    Calculate Elemental Fields = True
    Calculate Magnetic Field Strength = Logical True
    Calculate Magnetic Flux Density = Logical True
    !Calculate Poynting vector = Logical True
    !Calculate Div of Poynting Vector = Logical True
    Calculate Electric field = Logical True
    Calculate Energy Functional = Logical True

    Steady State Convergence Tolerance = 1
    Linear System Solver = "Iterative"
    Linear System Preconditioning = None
    Linear System Residual Output = 1000
    Linear System Max Iterations = 5000
    Linear System Iterative Method = CG
    Linear System Convergence Tolerance = 1.0e-9
    show angular frequency = logical true
    End

    Solver 3
    Ascii Output = Logical True
    Coordinate Scaling Revert = Logical True
    Equation = String "ResultOutput"
    Output File Name = File "fields"
    Procedure = File "ResultOutputSolve" "ResultOutputSolver"
    Vtu Format = Logical True
    Vtu Time Collection = Logical True
    save geometry ids = true
    End

    Solver 4
    Equation = "save scalars"
    procedure = "SaveData" "SaveScalars"
    Filename = scalar_results
    echo values = logical true
    parallel reduce = true
    End

    Equation 1
    Active Solvers(3) = Integer 1 2 3
    End

    Constants
    Permittivity Of Vacuum = Real 8.85419e-12
    End

    !!!!!!!!!!!

    include physics.sif
    '''


    case_filename = os.path.join(targetdir, 'case.sif')
    with open(case_filename, "w") as casefile:  
        casefile.write(casedata)
        casefile.close()    


    # -------------- first order solver recipe -------------------

    first_order = f'''
    Linear System Solver = direct
    Linear System Direct Method = zmumps
    '''

    filename = os.path.join(targetdir, 'first-order.sif')
    with open(filename, "w") as f:  
        f.write(first_order)
        f.close()    

    # -------------- quadratic solver recipe, direct -------------------

    quadratic_direct = f'''
    Quadratic Approximation = true
    second kind basis = false
    Linear System Solver = direct
    Linear System Direct Method = zmumps
    '''

    filename = os.path.join(targetdir, 'quadratic-direct.sif')
    with open(filename, "w") as f:  
        f.write(quadratic_direct)
        f.close()    

    # -------------- quadratic solver recipe, iterative -------------------
    quadratic_iterative = f'''
    Quadratic Approximation = true
    second kind basis = true

    Linear System Complex = logical True
    Linear System Symmetric = logical True
    Linear System Solver = Iterative
    Linear System Scaling = True
    Linear System Iterative Method = GCR
    Linear System Max Iterations = 50
    Linear System GCR Restart = 50
    Linear System Residual Output = 1
    Linear System Abort Not Converged = False
    Linear System Convergence Tolerance = 1.0e-6
    Linear System Preconditioning = Multigrid

    Edge Basis = True
    MG Method = p
    MG Levels = 2
    MG Smoother Relaxation Factor = $ 1/6
    MG Smoother = cjacobi
    MG Pre Smoothing iterations = 6
    MG Post Smoothing Iterations = 6
    MG Max Iterations = 1
    MG Preconditioning = none

    MG Lowest Linear Solver = Direct
    mglowest: Linear System Direct Method = zmumps
    '''
    
    filename = os.path.join(targetdir, 'quadratic-iterative.sif')
    with open(filename, "w") as f:  
        f.write(quadratic_iterative)
        f.close()  


#------------------------- Elmer thermal model -------------------------

def write_elmer_thermal_file (unit,
                                elmer_thermal_file,
                                Elmer_materials,
                                Elmer_bodies,
                                Elmer_boundaries,
                                Elmer_body_forces,
                                Elmer_thermal_boundaryconditions,
                                iterative=True):

    with open(elmer_thermal_file, "w") as f:

        vtu_file = '../thermal_results.vtu'

        if iterative:
            linear_system_block = '''Linear System Solver = Iterative
Linear System Iterative Method = BiCGStabl
Linear System Max Iterations = 100000
Linear System Convergence Tolerance = 1.0e-7
Linear System Preconditioning = ILU1'''
        else:
            # MUMPS is not available in the Windows Elmer build - UMFPACK ships
            # with Elmer on all platforms and needs no extra solver-specific options
            linear_system_block = '''Linear System Solver = Direct
Linear System Direct Method = umfpack'''

        header1=f'''
Check Keywords "warn"

Header
Mesh DB "mesh" "."
End

Simulation
Coordinate Mapping(3) = Integer 1 2 3
Simulation Type = Steady state
Steady State Max Iterations = 1
Coordinate System = String "Cartesian"
Coordinate Scaling = Real 1e-6
Use Mesh Names = Logical True
Mesh Levels = 1
Post File = {vtu_file}
End


Equation 1
Name = "ThermalPhysics"
Active Solvers(2) = 1 2
End

Solver 1
Equation = Heat Equation
Procedure = "HeatSolve" "HeatSolver"
Variable = Temperature
{linear_system_block}
Steady State Convergence Tolerance = 1.0e-5
End        

Solver 2
  Equation = SaveScalars
  Procedure = "SaveData" "SaveScalars"

  Filename = "../thermal_results.dat"

  Variable 1 = Temperature
  Operator 1 = min
  Operator 2 = max
End
'''

        f.write(header1 + "\n")


        # write Material sections
        for n,material in enumerate(Elmer_materials):
            item = f'Material {n+1}\n   Name = string "{material["name"]}"\n'
            # thermal conductivity can be single value or table passed as string here
            item = item + f"   Density = Real {material["density"]}\n"
            item = item + f"   Heat Conductivity = {material["thermalcond"]}\n"
            item = item + "End\n"
            f.write(item + "\n")

        # write Bodies sections
        for n,body in enumerate(Elmer_bodies):
            item = f'Body {n+1}\n   Equation = Integer 1\n'
            item = item + f'   Name = "{body["name"]}"\n'
            item = item + f"   Material = {body["material"]}\n"

            if "bodyforce_number" in body.keys():
                item = item + f'   Body Force = {body["bodyforce_number"]}\n'

            item = item + "End\n"
            f.write(item + '\n')

        # write thermal power for heat source
        for n,power in enumerate(Elmer_body_forces):
            item = f'Body Force {n+1}\n'
            item = item + f'   Volumetric Heat Source = -distribute {power:2e}\n'
            item = item + "End\n"
            f.write(item + '\n')

        # write thermal boundary conditions
        for n,thermal_bc in enumerate(Elmer_thermal_boundaryconditions):
            item = f'Boundary Condition {n+1}\n'
            item = item + f'   Name = "{thermal_bc['name']}"\n'
            item = item + f'   Temperature = Real {thermal_bc['temp']:2f}\n'
            item = item + "End\n"
            f.write(item + '\n')


#------------------------- mesh conversion *.msh to Elmer mesh -------------------------

def clear_directory (path):
    # clear mesh directory, but skip files if locked
    for root, dirs, files in os.walk(path, topdown=False):
        for name in files:
            try:
                os.remove(os.path.join(root, name))
            except (PermissionError, OSError):
                pass
        for name in dirs:
            try:
                os.rmdir(os.path.join(root, name))
            except (PermissionError, OSError):
                pass    


def convert_mesh_to_elmer (input_mesh, ELMER_MPI_THREADS=1):
    # convert gmsh mesh *.msh to Elmer mesh
    # mesh name is: msh_name
    # mesh directory is: sim_path
    # ElmerGrid.exe 14 2 <*.msh> -autoclean -out <meshdir>

    input_mesh_path = os.path.dirname(input_mesh)
    elmer_mesh_path = os.path.join(input_mesh_path, 'mesh' )

    # clear target mesh directory first, to remove old mesh fragments
    clear_directory(elmer_mesh_path)

    ElmerGrid = ""

    if platform.system() == "Windows":
        Elmer_home = os.environ.get("ELMER_HOME")
        if Elmer_home != '':
            ElmerGrid  = os.path.join(Elmer_home, "bin", "ElmerGrid.exe")
    else: 
        ElmerGrid = "ElmerGrid"

    
    if ElmerGrid != "":
        print ('Convert mesh to Elmer format')

        # Command as a list of arguments
        cmd = [
            ElmerGrid,
            "14",
            "2",
            input_mesh.replace('\\','/'),
            "-autoclean",
            "-out",
            elmer_mesh_path.replace('\\','/')
        ]

        # Run the command
        result = subprocess.run(cmd, capture_output=True, text=True)

        # Print output and errors
        print("STDOUT:\n", result.stdout)
        if len(result.stderr)>0:
            print("STDERR:\n", result.stderr)


        # Second step if we use multithreading: modify the mesh again
        if ELMER_MPI_THREADS>1:
            print (f'Split mesh now for MPI multithreading with {ELMER_MPI_THREADS} threads')

            # Command as a list of arguments
            # ElmerGrid 2 2 mesh -metiskway MPI_threads
            cmd = [
                ElmerGrid,
                "2",
                "2",
                elmer_mesh_path.replace('\\','/'),
                "-partdual",
                "-metiskway",
                str(int(ELMER_MPI_THREADS))
            ]

            # Run the command
            print(cmd)
            result = subprocess.run(cmd, capture_output=True, text=True)

            # Print output and errors
            print("STDOUT:\n", result.stdout)
            if len(result.stderr)>0:
                print("STDERR:\n", result.stderr)

    else:
        print('Location of ElmerGrid executable unknown, cannot run mesh conversion automatically.\n', cmd)    


def get_ELMER_MPI_THREADS (settings):
    # optional multithreading for Elmer FEM because it requires modifies settings in case.sif file
    ELMER_MPI_THREADS = settings.get('ELMER_MPI_THREADS', None)
    if ELMER_MPI_THREADS is not None:
        print(f'MPI multithreading specified in model file, ELMER_MPI_THREADS={ELMER_MPI_THREADS}')
    else:
        print(f'MPI multithreading disabled: settings["ELMER_MPI_THREADS"] not set in model code')
        ELMER_MPI_THREADS = 1
    print("ELMER_MPI_THREADS =", ELMER_MPI_THREADS)
    return ELMER_MPI_THREADS    



# convert Palace output port-S.csv to Touchstone format, 
# walk through directory and combine all excitation

# new version for new Palace output that creates multi excitations in one common output file
# updated 19-Oct-2025 Mue: support more than 9 ports
# updated 08-Nov-2025 Mue: added evaluation for optional port impedance file port_information.json that is created by new gds2palace code

import os,re, json 
import skrf as rf

def parse_input (input_filename, freq, S_dB, S_arg):
    params = []

    with open(input_filename) as input_file:
        for line in input_file:
            aline = line.rstrip()
            aline = aline.replace(",","")
            aline = aline.replace("(dB)","")
            aline = aline.replace("(deg.)","")

            dB = {}
            arg = {}

            # check if we have the header line
            if 'Hz)' in aline:
                # get unit from header line
                items = aline.split()
                freq_unit = re.sub('[()]', '', items[1])

                # find what parameters we have in this line
                # items are like this:      |S[1][1]| arg(S[1][1])

                num_ports = 0

                for item in items:
                    if '|' in item:
                        Sxx = item.replace('|S', '')
                        Sxx = Sxx.replace('|', '')
                        # Sxx is like this: [1][1]'
                        Sxx = Sxx.replace('][', ' ')
                        # Sxx is like this: [1 1]
                        Sxx = Sxx.replace('[', '')
                        Sxx = Sxx.replace(']', '')
                        # Sxx is like this: 1 1
                        params.append(str(Sxx))

                        # get port indices a and b from Sxx
                        splitted = Sxx.split()
                        a = int(splitted [0])
                        b = int(splitted [1])
                        num_ports = max(num_ports,a,b)

                print('Number of ports: ', num_ports)

            else:
                # process data line
                items = aline.split()
                f = items[0]
                for param in params:
                    dB_index = 2*params.index(param) + 1
                    arg_index = dB_index+1

                    dB[param] = items[dB_index]
                    arg[param] = items[arg_index]

                    # do we already have the frequency point?
                    if f in freq:
                        f_index = freq.index(f)
                        dB_dict = S_dB[f_index]
                        arg_dict = S_arg[f_index]

                        dB_dict[param] = items[dB_index]
                        arg_dict[param] = items[arg_index]

                    else:
                        freq.append(f)
                        S_dB.append(dB)
                        S_arg.append(arg)

    input_file.close()  
    return num_ports, freq_unit      

# ---------------------------

def traverse_directories(path, level=0):
    try:
        items_in_path = os.listdir(path)
        for item in items_in_path:
            item_path = os.path.join(path, item)

            if os.path.isdir(item_path):
                traverse_directories(item_path, level + 1)
            elif item=='port-S.csv':
                found_datafiles.append(item_path)

    except PermissionError:
        print(item +  "[Permission Denied]")
    except FileNotFoundError:
        print(item +  "[Not Found]")

# ----------------------

# extrapolate down to DC 

def extrapolate_to_DC (snp_filename):
    nw = rf.Network(snp_filename)

    # check if we have point below 1 GHz, otherwise exit
    if nw.frequency.npoints > 20:
        if nw.frequency.start <= 1e9:
            if True: # nw.frequency.npoints > 50:
                # extrapolate to DC
                extrapolated = nw.extrapolate_to_dc(points=None, dc_sparam=None,  kind='cubic', coords='polar')
                filename, file_extension = os.path.splitext(snp_filename)
                out_filename = filename + '_dc' # without extension
                extrapolated.write_touchstone(out_filename, skrf_comment='DC point added by extrapolation', form='db', write_noise=True)
                print('Created file with DC extrapolation: ', out_filename,'\n')
            else:
                print('Not enough frequency points, skipping DC extrapolation')    
        else:
            print('No data at low frequency, skipping DC extrapolation')    
    else:
        print('Skipping DC extrapolation, not enough freqency points')    


# ----------------------


workdir = os.getcwd()
found_datafiles = []

# work recursively through directories
traverse_directories(workdir)

# evaluate the found data files
for found_filename in found_datafiles:
    # print(str(f))

    # Before we evaluate S-parameters, also check if we have a file port_information.json
    port_info_available = False
    # Get the directory two levels up
    two_up_dir = os.path.abspath(os.path.join(os.path.dirname(found_filename), "..", ".."))
    # Possible full filename for port_information.json
    port_info_filename = os.path.join(two_up_dir, "port_information.json")
    # Check if it exists
    if os.path.isfile(port_info_filename):
        print(f"Found extra file with port information: {port_info_filename}")

        # Load the JSON data
        with open(port_info_filename, "r") as f:
            data = json.load(f)

        # Extract all Z0 values
        Z0_values = [port["Z0"] for port in data.get("ports", []) if "Z0" in port]
        print("Port Z0 values found:", Z0_values)

        Z0_string = str(Z0_values[0])
        for Z in Z0_values:
            if Z != Z0_values[0]:
                Z0_string = Z0_string + ' ' + str(Z)
        # If string is fillex, we have a Z0 parameter for Touchstone header line. 
        # For mixed port impedance, we have multiple values there
        port_info_available = True
        print("Port impedance for Touchstone header: ", Z0_string)
    
    else:
        Z0_string = "50"       # default 


    # data file items
    freq = []
    S_dB = []
    S_arg = []
    freq_unit = ''
    num_ports = 0

    num_ports, freq_unit = parse_input(found_filename, freq, S_dB, S_arg)

    data_lines = []
    
    for frequency in freq:
        # line = str(frequency) 

        index = freq.index(frequency)
        data_line = [frequency]

        for i in range(1,num_ports+1):
            for j in range(1, num_ports+1):

                # special case 2-port data: the output is S11 S21 S12 S22 
                if num_ports==2:
                    param = str(j) + ' ' + str(i)
                else: 
                    param = str(i) + ' ' + str(j)

                found_params = S_dB[index].keys()
                # assume that we also have phase data then
                if param in found_params:
                    Sij_dB  = S_dB[index].get(param)
                    Sij_arg = S_arg[index].get(param)
                else:
                    Sij_dB  = 0.0
                    Sij_arg = 0.0
                # write Sij data
                data_line.append (Sij_dB)
                data_line.append( Sij_arg)
        
        data_lines.append(data_line)

    # sort data_lines by frequency (first value)
    data_lines.sort(key=lambda x:float(x[0]))

    # get directory where port-S.csv file is stored
    data_path = os.path.dirname(found_filename)
    output_path = data_path

    # get name of parent diretory, so that we can use it as filename for output 
    splitpath =  os.path.split(data_path)
    parentname = splitpath[1]
    output_filename = parentname + '.s' + str(num_ports) + 'p'   

    output_filename = os.path.join(output_path, output_filename)


    output_file = open(output_filename, "w") 
    # write Touchstone header line
    output_file.write(f"#  {freq_unit.upper()} S DB R {Z0_string}\n")

    for data_line in data_lines:
        line = ''
        for value in data_line:
            line = line + ' ' + str(value)
        output_file.write(line + "\n")

    output_file.close() 
    print('Created combined S-parameter file for ', num_ports, 'ports, filename: ', output_filename)

    if not port_info_available:
        print('NOTE: Port impedance not listed in Palace file, assuming 50 Ohm!')
        print('      If required, you can change that value in Touchstone file header!\n')

    # try DC extrapolation
    extrapolate_to_DC(output_filename)

       

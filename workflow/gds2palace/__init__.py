# Utilities for gds2palace 
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

import gds2palace.util_stackup_reader as stackup_reader
import gds2palace.util_gds_reader as gds_reader
import gds2palace.util_utilities as utilities
import gds2palace.util_simulation_setup as simulation_setup

__version__ = "1.0.0"   # version of gds2palace

utilities.check_module_version("util_stackup_reader", "1.0.0")
utilities.check_module_version("util_gds_reader", "1.0.0")
utilities.check_module_version("util_utilities", "1.0.0")
utilities.check_module_version("util_simulation_setup", "1.0.0")

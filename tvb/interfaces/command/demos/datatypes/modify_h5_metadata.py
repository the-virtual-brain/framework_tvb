# -*- coding: utf-8 -*-
#
#
# TheVirtualBrain-Framework Package. This package holds all Data Management, and
# Web-UI helpful to run brain-simulations. To use it, you also need do download
# TheVirtualBrain-Scientific Package (for simulators). See content of the
# documentation-folder for more details. See also http://www.thevirtualbrain.org
#
# (c) 2012-2017, Baycrest Centre for Geriatric Care ("Baycrest") and others
#
# This program is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software Foundation,
# either version 3 of the License, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE.  See the GNU General Public License for more details.
# You should have received a copy of the GNU General Public License along with this
# program.  If not, see <http://www.gnu.org/licenses/>.
#
#
#   CITATION:
# When using The Virtual Brain for scientific publications, please cite it as follows:
#
#   Paula Sanz Leon, Stuart A. Knock, M. Marmaduke Woodman, Lia Domide,
#   Jochen Mersmann, Anthony R. McIntosh, Viktor Jirsa (2013)
#       The Virtual Brain: a simulator of primate brain network dynamics.
#   Frontiers in Neuroinformatics (7:10. doi: 10.3389/fninf.2013.00010)
#
#

"""
Demo script on how to load a TVB DataType by Id and modify metadata

.. moduleauthor:: Lia Domide <lia.domide@codemart.ro>
"""

import os
from uuid import UUID
from datetime import datetime
from tvb.basic.profile import TvbProfile
from tvb.adapters.datatypes.h5.local_connectivity_h5 import LocalConnectivityH5
from tvb.core.utils import date2string

TvbProfile.set_profile(TvbProfile.COMMAND_PROFILE)


def update_local_connectivity_metadata(file_path):
    with LocalConnectivityH5(file_path) as f:
        f.storage_manager.set_metadata({'Shape': "(16384, 16384)",
                                        'format': "csc",
                                        "dtype": "<f8"},
                                       "/matrix")
        f.storage_manager.set_metadata({'cutoff': 40.0,
                                        'state': "RAW_DATA",
                                        'subject': "John Doe",
                                        'user_tag_1': "srf_16k",
                                        'user_tag_2': "",
                                        'user_tag_3': "",
                                        'user_tag_4': "",
                                        'user_tag_5': "",
                                        'type': "",
                                        'create_date': date2string(datetime.now()),
                                        'visible': True,
                                        'is_nan': False,
                                        'gid': UUID('3e551cbd-47ca-11e4-9f21-3c075431bf56').urn,
                                        'surface': UUID('10467c4f-d487-4186-afa6-d9b1fd8383d8').urn}, )


if __name__ == "__main__":
    update_local_connectivity_metadata(
        os.path.expanduser('~/Downloads/LocalConnectivity_3e551cbd-47ca-11e4-9f21-3c075431bf56.h5'))

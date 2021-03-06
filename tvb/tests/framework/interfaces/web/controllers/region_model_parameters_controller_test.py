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
.. moduleauthor:: Mihai Andrei <mihai.andrei@codemart.ro>
.. moduleauthor:: Bogdan Neacsa <bogdan.neacsa@codemart.ro>
"""

import json
import pytest
import cherrypy
from tvb.tests.framework.interfaces.web.controllers.base_controller_test import BaseTransactionalControllerTest
from tvb.core.entities.model.model_burst import Dynamic
from tvb.core.entities.storage import dao
from tvb.interfaces.web.controllers.burst.region_model_parameters_controller import RegionsModelParametersController
from tvb.interfaces.web.controllers.burst.burst_controller import BurstController
from tvb.simulator.integrators import HeunDeterministic
from tvb.simulator.models import Generic2dOscillator, Kuramoto
from tvb.tests.framework.adapters.simulator.simulator_adapter_test import SIMULATOR_PARAMETERS
import tvb.interfaces.web.controllers.common as common


class TestRegionsModelParametersController(BaseTransactionalControllerTest):
    """ Unit tests for RegionsModelParametersController """

    @pytest.fixture(scope='module')
    def transactional_setup_fixture(self, connectivity_factory):
        """
        Sets up the environment for testing;
        creates a `RegionsModelParametersController` and a connectivity
        """
        self.init()
        self.region_m_p_c = RegionsModelParametersController()
        BurstController().index()
        stored_burst = cherrypy.session[common.KEY_BURST_CONFIG]
        _, self.connectivity = connectivity_factory
        new_params = {}
        for key, val in SIMULATOR_PARAMETERS.items():
            new_params[key] = {'value': val}
        new_params['connectivity'] = {'value': self.connectivity.gid}
        stored_burst.simulator_configuration = new_params
        self._setup_dynamic()

    def transactional_teardown_method(self):
        """ Cleans the testing environment """
        self.cleanup()


    def _setup_dynamic(self):
        dynamic_g = Dynamic("test_dyn", self.test_user.id, Generic2dOscillator.__name__,
                            '[["tau", 1.0], ["a", 5.0], ["b", -10.0], ["c", 10.0], ["I", 0.0], ["d", 0.02], '
                            '["e", 3.0], ["f", 1.0], ["g", 0.0], ["alpha", 1.0], ["beta", 5.0], ["gamma", 1.0]]',
                            HeunDeterministic.__name__, None)

        dynamic_k = Dynamic("test_dyn_kura", self.test_user.id, Kuramoto.__name__,
                            '[["omega", 1.0]]', HeunDeterministic.__name__, None)

        self.dynamic_g = dao.store_entity(dynamic_g)
        self.dynamic_k = dao.store_entity(dynamic_k)

    def test_index(self, transactional_setup_fixture):
        """
        Verifies that result dictionary has the expected keys / values after call to
        `edit_model_parameters()`
        """
        result_dict = self.region_m_p_c.index()
        assert self.connectivity.gid == result_dict['connectivity_entity'].gid
        assert result_dict['mainContent'] == 'burst/model_param_region'
        assert result_dict['submit_parameters_url'] == '/burst/modelparameters/regions/submit_model_parameters'
        assert 'dynamics' in result_dict
        assert 'dynamics_json' in result_dict
        assert 'pointsLabels' in result_dict
        assert 'positions' in result_dict

        json.loads(result_dict['dynamics_json'])

    def test_submit_model_parameters_happy(self, transactional_setup_fixture):
        """
        Verifies call to `submit_model_parameters(...)` correctly redirects to '/burst/'
        """
        self.region_m_p_c.index()

        dynamic_ids = json.dumps([self.dynamic_g.id for _ in range(self.connectivity.number_of_regions)])

        self._expect_redirect('/burst/', self.region_m_p_c.submit_model_parameters, dynamic_ids)
        

    def test_submit_model_parameters_inconsistent_models(self, transactional_setup_fixture):
        self.region_m_p_c.index()

        dynamic_ids = [self.dynamic_g.id for _ in range(self.connectivity.number_of_regions)]
        dynamic_ids[-1] = self.dynamic_k.id
        dynamic_ids = json.dumps(dynamic_ids)

        with pytest.raises(Exception):
            self.region_m_p_c.submit_model_parameters(dynamic_ids)

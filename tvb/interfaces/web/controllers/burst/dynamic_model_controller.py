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
# CITATION:
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
"""
import json
import numpy
import threading
from tvb.basic.neotraits.api import HasTraits, Attr
from tvb.adapters.visualizers.phase_plane_interactive import phase_space_d3
from tvb.core import utils
from tvb.core.adapters.abcadapter import ABCAdapter
from tvb.core.adapters.input_tree import InputTreeManager
from tvb.core.entities.storage import dao
import tvb.core.entities.model.model_burst as model_burst
#from tvb.datatypes import noise_framework
from tvb.interfaces.web.controllers import common
from tvb.interfaces.web.controllers.burst.base_controller import BurstBaseController
from tvb.interfaces.web.controllers.decorators import expose_page, expose_json, expose_fragment, using_template
from tvb.simulator import models, integrators


class Dynamic(object):
    """
    Groups a model and an integrator.
    """
    def __init__(self, model=None, integrator=None):
        if model is None:
            model = models.Generic2dOscillator()
        if integrator is None:
            integrator = integrators.HeunDeterministic()

        model.configure()
        self.model = model
        self.integrator = integrator

        # Only one instance should exist for a browser page.
        # To achieve something close to that we store it here
        self.phase_plane = phase_space_d3(model, integrator)


class SessionCache(object):
    """
    A simple cache backed by the current cherrypy session.
    It does not expire it's contents.
    """
    SESSION_KEY = 'session_cache'

    @property
    def _cache(self):
        cache = common.get_from_session(self.SESSION_KEY)
        if cache is None:
            cache = {}
            common.add2session(self.SESSION_KEY, cache)
        return cache

    def __contains__(self, key):
        return key in self._cache

    def __getitem__(self, key):
        return self._cache[key]

    def __setitem__(self, key, value):
        self._cache[key] = value


class _InputTreeFragment(HasTraits):
    dynamic_name = Attr(field_type=str,
        label = "Parameter configuration name",
        doc = """The name of this parameter configuration""")


class _IntegratorTreeFragment(HasTraits):
    """
    This trait-ed class is used to build the input tree for the integrator.
    """
    integrator = Attr(field_type=integrators.Integrator,
        label = "integrator",
        default = integrators.HeunDeterministic(),
        doc = """The integrator"""
        )


class _LeftFragmentAdapter(ABCAdapter):
    """
    This adapter is used only to generate the left input tree.
    """
    def __init__(self, available_models):
        ABCAdapter.__init__(self)
        self.available_models = available_models

    def launch(self):
        pass

    def get_output(self):
        pass

    def get_required_memory_size(self):
        return -1

    def get_required_disk_size(self):
        return 0

    def get_input_tree(self):
        from tvb.basic.traits import traited_interface

        models_sub_tree = {
            'name': 'model_type', 'type': 'select', 'required': True, 'label': 'model',
            'default' : 'Generic2dOscillator',
            'options': []
        }

        for clz_name, clz in self.available_models.items():
            models_sub_tree['options'].append({
                'name': clz._ui_name, # ui-name instaead
                'value': clz_name,
                'inline_description': self._dfun_math_directives_to_matjax(clz),
                'description' : clz.__doc__
            })

        fragment = _InputTreeFragment()
        fragment.trait.bound = traited_interface.INTERFACE_ATTRIBUTES_ONLY

        input_tree = fragment.interface[traited_interface.INTERFACE_ATTRIBUTES]
        input_tree.insert(1, models_sub_tree)
        #self.log.warn(json.dumps(input_tree, indent=2, sort_keys=1))
        return input_tree


    @staticmethod
    def _dfun_math_directives_to_matjax(model):
        """
        Looks for sphinx math directives if the docstring of the dfun function of a model.
        It converts them in html text that will be interpreted by mathjax
        The parsing is simplistic, not a full rst parser.
        """
        from tvb.basic.traits.util import multiline_math_directives_to_matjax
        def format_doc(doc):
            return multiline_math_directives_to_matjax(doc).replace('&', '&amp;').replace('.. math::','')

        try:
            doc = model.dfun.__doc__
        except AttributeError:
            doc = None

        if doc is not None:
            return format_doc(doc)

        # try the parent __doc__
        try:
            doc = model.__mro__[1].dfun.__doc__
        except (AttributeError, IndexError):
            doc = None

        if doc is not None:
            return format_doc('Documentation is missing. Copy-ed from parent\n' + doc)

        return 'Documentation is missing. '


class _IntegratorFragmentAdapter(ABCAdapter):
    def launch(self):
        pass

    def get_output(self):
        pass

    def get_required_memory_size(self):
        return -1

    def get_required_disk_size(self):
        return 0

    def get_input_tree(self):
        fragment = _IntegratorTreeFragment()
        fragment.trait.bound = traited_interface.INTERFACE_ATTRIBUTES_ONLY
        return fragment.interface[traited_interface.INTERFACE_ATTRIBUTES]


class DynamicModelController(BurstBaseController):
    KEY_CACHED_DYNAMIC_MODEL = 'cache.DynamicModelController'

    def __init__(self):
        BurstBaseController.__init__(self)
        self.available_models = models.Model.get_known_subclasses()
        self.available_integrators = integrators.Integrator.get_known_subclasses()
        self.cache = SessionCache()
        # Work around a numexpr thread safety issue. See TVB-1639.
        self.traj_lock = threading.Lock()


    def get_cached_dynamic(self, dynamic_gid):
        """
        Creating the model per request will be expensive.
        So we cache it in session.
        If there is nothing cached it returns the default dynamic.
        """
        # TODO: The cached objects expire only with the session. Invalidate the cache earlier.
        if dynamic_gid not in self.cache:
            dynamic = Dynamic()
            self.cache[dynamic_gid] = dynamic
        return self.cache[dynamic_gid]


    @expose_page
    def index(self):
        dynamic_gid = utils.generate_guid()
        adapter = _LeftFragmentAdapter(self.available_models)
        input_tree = adapter.get_input_tree()
        #WARN: If this input tree will contain data type references then to render it correctly we have to use fill_input_tree_with_options
        input_tree = InputTreeManager.prepare_param_names(input_tree)

        integrator_adapter = _IntegratorFragmentAdapter()
        integrator_input_tree = integrator_adapter.get_input_tree()
        integrator_input_tree  = InputTreeManager.prepare_param_names(integrator_input_tree)

        params = {
            'title': "Dynamic model",
            'mainContent': 'burst/dynamic',
            'input_tree': input_tree,
            'integrator_input_tree': integrator_input_tree,
            'dynamic_gid': dynamic_gid
        }
        self.fill_default_attributes(params)

        dynamic = self.get_cached_dynamic(dynamic_gid)
        self._configure_integrator_noise(dynamic.integrator, dynamic.model)
        return params


    def fill_default_attributes(self, param):
        return BurstBaseController.fill_default_attributes(self, param, subsection='phaseplane')


    @expose_json
    def model_changed(self, dynamic_gid, name):
        """
        Resets the phase plane and returns the ui model for the slider area.
        """
        dynamic = self.get_cached_dynamic(dynamic_gid)
        dynamic.model = self.available_models[name]()
        dynamic.model.configure()
        dynamic.phase_plane = phase_space_d3(dynamic.model, dynamic.integrator)
        mp_params = DynamicModelController._get_model_parameters_ui_model(dynamic.model)
        graph_params = DynamicModelController._get_graph_ui_model(dynamic)
        return {
            'params' : mp_params, 'graph_params':graph_params,
            'model_param_sliders_fragment': self._model_param_sliders_fragment(dynamic_gid),
            'axis_sliders_fragment': self._axis_sliders_fragment(dynamic_gid)
        }


    @expose_json
    def integrator_changed(self, dynamic_gid, **kwargs):
        adapter = _IntegratorFragmentAdapter()
        tree = adapter.convert_ui_inputs(kwargs, validation_required=False)
        integrator_name = tree['integrator']
        integrator_parameters = tree['integrator_parameters']

        noise_framework.build_noise(integrator_parameters)
        integrator = self.available_integrators[integrator_name](**integrator_parameters)

        dynamic = self.get_cached_dynamic(dynamic_gid)
        dynamic.integrator = integrator
        dynamic.model.integrator = integrator
        dynamic.model.configure()
        self._configure_integrator_noise(integrator, dynamic.model)

        dynamic.phase_plane = phase_space_d3(dynamic.model, dynamic.integrator)


    @staticmethod
    def _configure_integrator_noise(integrator, model):
        """
        This function has to be called after integrator construction.
        Without it the noise instance is not in a good state.

        Should the Integrator __init__ not take care of this? Or noise_framework.buildnoise?
        Should I call noise.configure() as well?
        similar to simulator.configure_integrator_noise
        """
        if isinstance(integrator, integrators.IntegratorStochastic):
            shape = (model.nvar, 1, model.number_of_modes)
            if integrator.noise.ntau > 0.0:
                integrator.noise.configure_coloured(integrator.dt, shape)
            else:
                integrator.noise.configure_white(integrator.dt, shape)


    @expose_json
    def parameters_changed(self, dynamic_gid, params):
        with self.traj_lock:
            params = json.loads(params)
            dynamic = self.get_cached_dynamic(dynamic_gid)
            model = dynamic.model
            for name, value in params.items():
                setattr(model, name, numpy.array([float(value)]))
            model.configure()
            return dynamic.phase_plane.compute_phase_plane()


    @expose_json
    def graph_changed(self, dynamic_gid, graph_state):
        with self.traj_lock:
            graph_state = json.loads(graph_state)
            dynamic = self.get_cached_dynamic(dynamic_gid)
            dynamic.phase_plane.update_axis(**graph_state)
            return dynamic.phase_plane.compute_phase_plane()


    @expose_json
    def trajectories(self, dynamic_gid, starting_points, integration_steps):
        with self.traj_lock:
            starting_points = json.loads(starting_points)
            dynamic = self.get_cached_dynamic(dynamic_gid)
            trajectories, signals = dynamic.phase_plane.trajectories(starting_points, int(integration_steps))

            for t in trajectories:
                if not numpy.isfinite(t).all():
                    self.logger.warn('Denaturated point %s on a trajectory')
                    return {'finite':False}

            return {'trajectories': trajectories, 'signals': signals, 'finite':True}


    @staticmethod
    def _get_model_parameters_ui_model(model):
        """
        For each model parameter return the representation used by the ui (template & js)
        """
        ret = []
        for name in model.ui_configurable_parameters:
            parameter_trait = model.trait[name].trait
            ranger = parameter_trait.range_interval
            default = float(parameter_trait.inits.kwd.get('default'))
            trait_kwd = parameter_trait.inits.kwd

            ret.append({
                'name': name,
                'label': trait_kwd.get('label'),
                'description': trait_kwd.get('doc'),
                'min': ranger.lo,
                'max': ranger.hi,
                'step': ranger.step,
                'default': default
            })
        return ret


    @staticmethod
    def _get_graph_ui_model(dynamic):
        model = dynamic.model
        sv_model = []
        for sv in range(model.nvar):
            name = model.state_variables[sv]
            min_val, max_val, lo, hi = dynamic.phase_plane.get_axes_ranges(name)
            sv_model.append({
                'name': name,
                'label': ':math:`%s`' % name,
                'description': 'state variable ' + name,
                'lo': lo,
                'hi': hi,
                'min': min_val,
                'max': max_val,
                'step': (hi - lo) / 1000.0,  # todo check if reasonable
                'default': (hi + lo) / 2
            })


        ret = {
            'modes': list(range(model.number_of_modes)),
            'state_variables': sv_model,
            'default_mode' : dynamic.phase_plane.mode
        }

        if model.nvar > 1:
            ret['default_sv'] = [ model.state_variables[dynamic.phase_plane.svx_ind],
                                  model.state_variables[dynamic.phase_plane.svy_ind]]
            ret['integration_steps'] = {'default': 512, 'min': 32, 'max':2048 }
        else:
            ret['default_sv'] = [ model.state_variables[0] ]
        return ret


    @using_template('burst/dynamic_axis_sliders')
    def _axis_sliders_fragment(self, dynamic_gid):
        dynamic = self.get_cached_dynamic(dynamic_gid)
        model = dynamic.model
        ps_params = self._get_graph_ui_model(dynamic)
        templ_var = ps_params
        templ_var.update({'showOnlineHelp' : True,
                          'one_dimensional':len(model.state_variables) == 1 })
        return templ_var

    @using_template('burst/dynamic_mp_sliders')
    def _model_param_sliders_fragment(self, dynamic_gid):
        dynamic = self.get_cached_dynamic(dynamic_gid)
        model = dynamic.model
        mp_params = self._get_model_parameters_ui_model(model)
        templ_var = {'parameters' : mp_params, 'showOnlineHelp' : True }
        return templ_var


    @expose_json
    def submit(self, dynamic_gid, dynamic_name):
        if dao.get_dynamic_by_name(dynamic_name):
            return {'saved': False, 'msg': 'There is another configuration with the same name'}

        dynamic = self.get_cached_dynamic(dynamic_gid)
        model = dynamic.model
        integrator = dynamic.integrator

        model_parameters = []

        for name in model.ui_configurable_parameters:
            value = getattr(model, name)[0]
            model_parameters.append((name, value))

        entity = model_burst.Dynamic(
            dynamic_name,
            common.get_logged_user().id,
            model.__class__.__name__,
            json.dumps(model_parameters),
            integrator.__class__.__name__,
            None
            # todo: serialize integrator parameters
            # json.dumps(integrator.raw_ui_integrator_parameters)
        )

        dao.store_entity(entity)
        return {'saved': True}


    @expose_fragment('burst/dynamic_minidetail')
    def dynamic_detail(self, dynamic_id):
        dynamic = dao.get_dynamic(dynamic_id)
        model_parameters = dict(json.loads(dynamic.model_parameters))
        return {'model_parameters': model_parameters}
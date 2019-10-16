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
Adapter that uses the traits module to generate interfaces to the Simulator.
Few supplementary steps are done here:

   * from submitted Monitor/Model... names, build transient entities
   * after UI parameters submit, compose transient Cortex entity to be passed to the Simulator.

.. moduleauthor:: Lia Domide <lia.domide@codemart.ro>
.. moduleauthor:: Stuart A. Knock <Stuart@tvb.invalid>

"""
import numpy
from tvb.simulator.simulator import Simulator
from tvb.adapters.simulator.coupling_forms import get_ui_name_to_coupling_dict
from tvb.adapters.datatypes.h5.simulation_state_h5 import SimulationStateH5
from tvb.adapters.datatypes.db.region_mapping import RegionMappingIndex, RegionVolumeMappingIndex
from tvb.adapters.datatypes.db.connectivity import ConnectivityIndex
from tvb.adapters.datatypes.db.simulation_state import SimulationStateIndex
from tvb.adapters.datatypes.db.time_series import TimeSeriesIndex
from tvb.core.entities.storage import dao
from tvb.core.adapters.abcadapter import ABCAsynchronous, ABCAdapterForm
from tvb.core.adapters.exceptions import LaunchException
from tvb.core.neotraits.forms import DataTypeSelectField, SimpleSelectField, FloatField, jinja_env
from tvb.core.services.simulator_service import SimulatorService
from tvb.core.neocom import h5


class SimulatorAdapterForm(ABCAdapterForm):

    def __init__(self, prefix='', project_id=None, is_copy=False):
        super(SimulatorAdapterForm, self).__init__(prefix, project_id)
        self.connectivity = DataTypeSelectField(self.get_required_datatype(), self, name=self.get_input_name(),
                                                required=True, label="Connectivity",
                                                doc=Simulator.connectivity.doc,
                                                conditions=self.get_filters())
        self.coupling_choices = get_ui_name_to_coupling_dict()
        self.coupling = SimpleSelectField(choices=self.coupling_choices, form=self, name='coupling', required=True,
                                          label="Coupling", doc=Simulator.coupling.doc)
        self.coupling.template = 'select_field.jinja2'
        self.conduction_speed = FloatField(Simulator.conduction_speed, self)
        self.ordered_fields = (self.connectivity, self.conduction_speed, self.coupling)
        self.range_params = [Simulator.connectivity, Simulator.conduction_speed]
        self.is_copy = is_copy

    def fill_from_trait(self, trait):
        # type: (Simulator) -> None
        if hasattr(trait, 'connectivity'):
            self.connectivity.data = trait.connectivity.gid.hex
        self.coupling.data = trait.coupling.__class__
        self.conduction_speed.data = trait.conduction_speed

    @staticmethod
    def get_input_name():
        return 'connectivity'

    @staticmethod
    def get_filters():
        return None

    @staticmethod
    def get_required_datatype():
        return ConnectivityIndex

    def get_traited_datatype(self):
        return Simulator()

    def __str__(self):
        # TODO: get rid of this
        return jinja_env.get_template('wizzard_form.jinja2').render(form=self, action="/burst/set_connectivity",
                                                                    is_first_fragment=True, is_last_fragment=False,
                                                                    is_copy=self.is_copy, is_load=False)



class SimulatorAdapter(ABCAsynchronous):
    """
    Interface between the Simulator and the Framework.
    """
    _ui_name = "Simulation Core"

    algorithm = None
    branch_simulation_state_gid = None

    # This is a list with the monitors that actually return multi dimensions for the state variable dimension.
    # We exclude from this for example EEG, MEG or Bold which return 
    HAVE_STATE_VARIABLES = ["GlobalAverage", "SpatialAverage", "Raw", "SubSample", "TemporalAverage"]

    def __init__(self):
        super(SimulatorAdapter, self).__init__()
        self.log.debug("%s: Initialized..." % str(self))

    def get_form_class(self):
        return SimulatorAdapterForm

    def get_output(self):
        """
        :returns: list of classes for possible results of the Simulator.
        """
        return [TimeSeriesIndex]

    def configure(self, simulator_gid):
        """
        Make preparations for the adapter launch.
        """
        self.log.debug("%s: Instantiating requested simulator..." % str(self))

        simulator_service = SimulatorService()
        self.algorithm, connectivity_gid, simulation_state_gid = simulator_service.deserialize_simulator(simulator_gid,
                                                                                                         self.storage_path)
        self.branch_simulation_state_gid = simulation_state_gid

        # for monitor in self.algorithm.monitors:
        #     if issubclass(monitor, Projection):
        #         # TODO: add a service that loads a RM with Surface and Connectivity
        #         pass

        connectivity_index = dao.get_datatype_by_gid(connectivity_gid.hex)
        connectivity = h5.load_from_index(connectivity_index)

        connectivity.gid = connectivity_gid
        self.algorithm.connectivity = connectivity
        self.simulation_length = self.algorithm.simulation_length
        self.log.debug("%s: Initializing storage..." % str(self))
        try:
            self.algorithm.preconfigure()
        except ValueError as err:
            raise LaunchException("Failed to configure simulator due to invalid Input Values. It could be because "
                                  "of an incompatibility between different version of TVB code.", err)

    def get_required_memory_size(self, **kwargs):
        """
        Return the required memory to run this algorithm.
        """
        return self.algorithm.memory_requirement()

    def get_required_disk_size(self, **kwargs):
        """
        Return the required disk size this algorithm estimates it will take. (in kB)
        """
        return self.algorithm.storage_requirement(self.simulation_length) / 2 ** 10

    def get_execution_time_approximation(self, **kwargs):
        """
        Method should approximate based on input arguments, the time it will take for the operation 
        to finish (in seconds).
        """
        # This is just a brute approx so cluster nodes won't kill operation before
        # it's finished. This should be done with a higher grade of sensitivity
        # Magic number connecting simulation length to simulation computation time
        # This number should as big as possible, as long as it is still realistic, to
        magic_number = 6.57e-06  # seconds
        approx_number_of_nodes = 500
        approx_nvar = 15
        approx_modes = 15

        simulation_length = int(float(kwargs['simulation_length']))
        approx_integrator_dt = float(kwargs['integrator_parameters']['dt'])

        if approx_integrator_dt == 0.0:
            approx_integrator_dt = 1.0

        if 'surface' in kwargs and kwargs['surface'] is not None and kwargs['surface'] != '':
            approx_number_of_nodes *= approx_number_of_nodes

        estimation = magic_number * approx_number_of_nodes * approx_nvar * approx_modes * simulation_length \
                     / approx_integrator_dt

        return max(int(estimation), 1)

    def _try_find_mapping(self, mapping_class, connectivity_gid):
        """
        Try to find a DataType instance of class "mapping_class", linked to the given Connectivity.
        Entities in the current project will have priority.

        :param mapping_class: DT class, with field "_connectivity" on it
        :param connectivity_gid: GUID
        :return: None or instance of "mapping_class"
        """

        dts_list = dao.get_generic_entity(mapping_class, connectivity_gid, 'connectivity_gid')
        if len(dts_list) < 1:
            return None

        for dt in dts_list:
            dt_operation = dao.get_operation_by_id(dt.fk_from_operation)
            if dt_operation.fk_launched_in == self.current_project_id:
                return dt
        return dts_list[0]

    def _try_load_region_mapping(self):
        region_map = None
        region_volume_map = None

        region_map_index = self._try_find_mapping(RegionMappingIndex, self.algorithm.connectivity.gid.hex)
        region_volume_map_index = self._try_find_mapping(RegionVolumeMappingIndex, self.algorithm.connectivity.gid.hex)

        if region_map_index:
            region_map = h5.load_from_index(region_map_index)

        if region_volume_map_index:
            region_volume_map = h5.load_from_index(region_volume_map_index)

        return region_map, region_volume_map

    def launch(self, simulator_gid):
        """
        Called from the GUI to launch a simulation.
          *: string class name of chosen model, etc...
          *_parameters: dictionary of parameters for chosen model, etc...
          connectivity: tvb.datatypes.connectivity.Connectivity object.
          surface: tvb.datatypes.surfaces.CorticalSurface: or None.
          stimulus: tvb.datatypes.patters.* object
        """
        result_h5 = dict()
        result_indexes = dict()
        start_time = self.algorithm.current_step * self.algorithm.integrator.dt

        self.algorithm.configure(full_configure=False)
        if self.branch_simulation_state_gid is not None:
            simulation_state_index = dao.get_datatype_by_gid(self.branch_simulation_state_gid.hex)
            self.branch_simulation_state_path = h5.path_for_stored_index(simulation_state_index)

            with SimulationStateH5(self.branch_simulation_state_path) as branch_simulation_state_h5:
                branch_simulation_state_h5.load_into(self.algorithm)

        region_map, region_volume_map = self._try_load_region_mapping()

        for monitor in self.algorithm.monitors:
            m_name = monitor.__class__.__name__
            ts = monitor.create_time_series(self.algorithm.connectivity, self.algorithm.surface, region_map,
                                            region_volume_map)
            self.log.debug("Monitor created the TS")
            ts.start_time = start_time

            ts_index_class = h5.REGISTRY.get_index_for_datatype(type(ts))
            ts_index = ts_index_class()
            ts_index.fill_from_has_traits(ts)
            ts_index.data_ndim = 4
            ts_index.state = 'INTERMEDIATE'

            # state_variable_dimension_name = ts.labels_ordering[1]
            # if ts_index.user_tag_1:
            #     ts_index.labels_dimensions[state_variable_dimension_name] = ts.user_tag_1.split(';')
            # elif m_name in self.HAVE_STATE_VARIABLES:
            #     selected_vois = [self.algorithm.model.variables_of_interest[idx] for idx in monitor.voi]
            #     ts.labels_dimensions[state_variable_dimension_name] = selected_vois

            ts_h5_class = h5.REGISTRY.get_h5file_for_datatype(type(ts))
            ts_h5_path = h5.path_for(self.storage_path, ts_h5_class, ts.gid)
            ts_h5 = ts_h5_class(ts_h5_path)
            ts_h5.store(ts, scalars_only=True, store_references=False)
            ts_h5.sample_rate.store(ts.sample_rate)
            ts_h5.nr_dimensions.store(ts_index.data_ndim)

            if self.algorithm.surface:
                ts_index.surface_gid = self.algorithm.surface.region_mapping_data.surface.gid.hex
                ts_h5.surface.store(self.algorithm.surface.gid)
            else:
                ts_index.connectivity_gid = self.algorithm.connectivity.gid.hex
                ts_h5.connectivity.store(self.algorithm.connectivity.gid)
                if region_map:
                    ts_index.region_mapping_gid = region_map.gid.hex
                    ts_h5.region_mapping.store(region_map.gid)
                if region_volume_map:
                    ts_index.region_mapping_volume_gid = region_volume_map.gid.hex
                    ts_h5.region_mapping_volume.store(region_volume_map.gid)

            result_indexes[m_name] = ts_index
            result_h5[m_name] = ts_h5

        # Run simulation
        self.log.debug("Starting simulation...")
        for result in self.algorithm(simulation_length=self.simulation_length):
            for j, monitor in enumerate(self.algorithm.monitors):
                if result[j] is not None:
                    m_name = monitor.__class__.__name__
                    ts_h5 = result_h5[m_name]
                    ts_h5.write_time_slice([result[j][0]])
                    ts_h5.write_data_slice([result[j][1]])

        self.log.debug("Completed simulation, starting to store simulation state ")
        # Populate H5 file for simulator state. This step could also be done while running sim, in background.
        if not self._is_group_launch():
            simulation_state_index = SimulationStateIndex()
            simulation_state_path = h5.path_for(self.storage_path, SimulationStateH5, self.algorithm.gid)
            with SimulationStateH5(simulation_state_path) as simulation_state_h5:
                simulation_state_h5.store(self.algorithm)
            self._capture_operation_results([simulation_state_index])

        self.log.debug("Simulation state persisted, returning results ")
        for monitor in self.algorithm.monitors:
            m_name = monitor.__class__.__name__
            ts_shape = result_h5[m_name].read_data_shape()
            result_indexes[m_name].fill_shape(ts_shape)
            result_h5[m_name].close()
        # self.log.info("%s: Adapter simulation finished!!" % str(self))
        return list(result_indexes.values())

    def _validate_model_parameters(self, model_instance, connectivity, surface):
        """
        Checks if the size of the model parameters is set correctly.
        """
        ui_configurable_params = model_instance.ui_configurable_parameters
        for param in ui_configurable_params:
            param_value = eval('model_instance.' + param)
            if isinstance(param_value, numpy.ndarray):
                if len(param_value) == 1 or connectivity is None:
                    continue
                if surface is not None:
                    if (len(param_value) != surface.number_of_vertices
                            and len(param_value) != connectivity.number_of_regions):
                        msg = str(surface.number_of_vertices) + ' or ' + str(connectivity.number_of_regions)
                        msg = self._get_exception_message(param, msg, len(param_value))
                        self.log.error(msg)
                        raise LaunchException(msg)
                elif len(param_value) != connectivity.number_of_regions:
                    msg = self._get_exception_message(param, connectivity.number_of_regions, len(param_value))
                    self.log.error(msg)
                    raise LaunchException(msg)


    @staticmethod
    def _get_exception_message(param_name, expected_size, actual_size):
        """
        Creates the message that will be displayed to the user when the size of a model parameter is incorrect.
        """
        msg = "The length of the parameter '" + param_name + "' is not correct."
        msg += " It is expected to be an array of length " + str(expected_size) + "."
        msg += " It is an array of length " + str(actual_size) + "."
        return msg

    @staticmethod
    def _is_surface_simulation(surface, surface_parameters):
        """
        Is this a surface simulation?
        """
        return surface is not None and surface_parameters is not None

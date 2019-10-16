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
Root classes for adding custom functionality to the code.

.. moduleauthor:: Lia Domide <lia.domide@codemart.ro>
.. moduleauthor:: Bogdan Neacsa <bogdan.neacsa@codemart.ro>
.. moduleauthor:: Yann Gordon <yann@tvb.invalid>
"""

import os
import json
import psutil
import numpy
import importlib
from functools import wraps
from datetime import datetime
from abc import ABCMeta, abstractmethod
from tvb.basic.profile import TvbProfile
from tvb.basic.logger.builder import get_logger
import tvb.basic.traits.traited_interface as interface
from tvb.core.adapters import input_tree
from tvb.core.adapters.input_tree import InputTreeManager
from tvb.core.entities.load import load_entity_by_gid
from tvb.core.utils import date2string, LESS_COMPLEX_TIME_FORMAT
from tvb.core.entities.storage import dao
from tvb.core.entities.file.files_helper import FilesHelper
from tvb.core.entities.transient.structure_entities import DataTypeMetaData
from tvb.core.adapters.exceptions import IntrospectionException, LaunchException, InvalidParameterException
from tvb.core.adapters.exceptions import NoMemoryAvailableException
from tvb.core.neotraits._forms import Form, DataTypeSelectField
from tvb.tests.framework.interfaces.neoforms_test import jinja_env

ATT_METHOD = "python_method"
ATT_PARAMETERS = "parameters_prefix"

KEY_EQUATION = input_tree.KEY_EQUATION
KEY_FOCAL_POINTS = input_tree.KEY_FOCAL_POINTS
KEY_SURFACE_GID = input_tree.KEY_SURFACE_GID

LOGGER = get_logger("ABCAdapter")


def nan_not_allowed():
    """
    Annotation that guides NumPy behavior in case of floating point errors.
    The NumPy default is to just print a warning to sys.stdout, this annotation will raise our custom exception.
    This annotation will enforce that an exception is thrown in case a floating point error is produced.

    e.g. If NaN is take as input and not produced inside the context covered by this annotation,
         nothing happens from this method p.o.v.

    e.g. If inside a method annotated with this method we have something like numpy.log(-1),
         then LaunchException is thrown.
    """

    def wrap(func):

        @wraps(func)
        def new_function(*args, **kw):
            old_fp_error_handling = numpy.seterr(divide='raise', invalid='raise')
            try:
                return func(*args, **kw)
            except FloatingPointError:
                raise LaunchException('NaN values were generated during launch. Stopping operation execution.')
            finally:
                numpy.seterr(**old_fp_error_handling)

        return new_function

    return wrap


def nan_allowed():
    """
    Annotation that configures NumPy not to throw an exception in case of floating points errors are computed.
    It should be used on Adapter methods where computation of NaN/ Inf/etc. is allowed.
    """

    def wrap(func):

        @wraps(func)
        def new_function(*args, **kw):
            old_fp_error_handling = numpy.seterr(all='ignore')
            try:
                return func(*args, **kw)
            finally:
                numpy.seterr(**old_fp_error_handling)

        return new_function

    return wrap


class ABCAdapterForm(Form):
    @staticmethod
    def get_required_datatype():
        raise NotImplementedError

    # TODO: This keeps filters for the required_datatype. Only to be in DB at introspection?
    @staticmethod
    def get_filters():
        raise NotImplementedError

    @staticmethod
    def get_input_name():
        raise NotImplementedError

    # TODO: This is used to fill in defaults for GET requests. Makes sense only for analyzers?
    @abstractmethod
    def get_traited_datatype(self):
        """"""

    def _get_original_field_name(self, field):
        return field.name[len(self.prefix) + 1:]

    # TODO: Used to support original flow (pass form values as kwargs). Also for the asynchronous launch
    def get_dict(self):
        attrs_dict = {}
        for field in self.fields:
            attrs_dict.update({field.name: field.data})
        return attrs_dict

    def get_form_values(self):
        attrs_dict = {}
        for field in self.fields:
            field_name = self._get_original_field_name(field)
            if isinstance(field, DataTypeSelectField):
                field_data = field.get_dt_from_db()
            else:
                field_data = field.data
            attrs_dict.update({field_name: field_data})
        return attrs_dict

    def __str__(self):
        # TODO: Keep using Jinja2?
        return jinja_env.get_template("form_field.jinja2").render(form=self)



class ABCAdapter(object):
    """
    Root Abstract class for all TVB Adapters. 
    """
    # todo this constants copy is not nice
    TYPE_SELECT = input_tree.TYPE_SELECT
    TYPE_MULTIPLE = input_tree.TYPE_MULTIPLE
    STATIC_ACCEPTED_TYPES = input_tree.STATIC_ACCEPTED_TYPES
    KEY_TYPE = input_tree.KEY_TYPE
    KEY_OPTIONS = input_tree.KEY_OPTIONS
    KEY_ATTRIBUTES = input_tree.KEY_ATTRIBUTES
    KEY_NAME = input_tree.KEY_NAME
    KEY_DESCRIPTION = input_tree.KEY_DESCRIPTION
    KEY_VALUE = input_tree.KEY_VALUE
    KEY_LABEL = input_tree.KEY_LABEL
    KEY_DEFAULT = input_tree.KEY_DEFAULT
    KEY_DATATYPE = input_tree.KEY_DATATYPE
    KEY_DTYPE = input_tree.KEY_DTYPE
    KEY_DISABLED = input_tree.KEY_DISABLED
    KEY_ALL = input_tree.KEY_ALL
    KEY_CONDITION = input_tree.KEY_CONDITION
    KEY_FILTERABLE = input_tree.KEY_FILTERABLE
    KEY_REQUIRED = input_tree.KEY_REQUIRED
    KEY_ID = input_tree.KEY_ID
    KEY_UI_HIDE = input_tree.KEY_UI_HIDE

    # TODO: move everything related to parameters PRE + POST into parameters_factory
    KEYWORD_PARAMS = input_tree.KEYWORD_PARAMS
    KEYWORD_SEPARATOR = input_tree.KEYWORD_SEPARATOR
    KEYWORD_OPTION = input_tree.KEYWORD_OPTION

    INTERFACE_ATTRIBUTES_ONLY = interface.INTERFACE_ATTRIBUTES_ONLY
    INTERFACE_ATTRIBUTES = interface.INTERFACE_ATTRIBUTES

    # model.Algorithm instance that will be set for each adapter created by in build_adapter method
    stored_adapter = None

    __metaclass__ = ABCMeta


    def __init__(self):
        # It will be populate with key from DataTypeMetaData
        self.meta_data = {DataTypeMetaData.KEY_SUBJECT: DataTypeMetaData.DEFAULT_SUBJECT}
        self.file_handler = FilesHelper()
        self.storage_path = '.'
        # Will be populate with current running operation's identifier
        self.operation_id = None
        self.user_id = None
        self.log = get_logger(self.__class__.__module__)
        self.tree_manager = InputTreeManager()

    @classmethod
    def get_group_name(cls):
        if hasattr(cls, "_ui_group") and hasattr(cls._ui_group, "name"):
            return cls._ui_group.name
        return None

    @classmethod
    def get_group_description(cls):
        if hasattr(cls, "_ui_group") and hasattr(cls._ui_group, "description"):
            return cls._ui_group.description
        return None

    @classmethod
    def get_ui_name(cls):
        if hasattr(cls, "_ui_name"):
            return cls._ui_name
        else:
            return cls.__name__

    @classmethod
    def get_ui_description(cls):
        if hasattr(cls, "_ui_description"):
            return cls._ui_description

    @classmethod
    def get_ui_subsection(cls):
        if hasattr(cls, "_ui_subsection"):
            return cls._ui_subsection

        if hasattr(cls, "_ui_group") and hasattr(cls._ui_group, "subsection"):
            return cls._ui_group.subsection

    @staticmethod
    def can_be_active():
        """
        To be overridden where needed (e.g. Matlab dependent adapters).
        :return: By default True, and False when the current Adapter can not be executed in the current env
        for various reasons (e.g. no Matlab or Octave installed)
        """
        return True

    @abstractmethod
    def get_input_tree(self):
        """
        Describes inputs and outputs of the launch method.
        """


    @abstractmethod
    def get_output(self):
        """
        Describes inputs and outputs of the launch method.
        """


    def configure(self, **kwargs):
        """
        To be implemented in each Adapter that requires any specific configurations
        before the actual launch.
        """


    @abstractmethod
    def get_required_memory_size(self, **kwargs):
        """
        Abstract method to be implemented in each adapter. Should return the required memory
        for launching the adapter.
        """


    @abstractmethod
    def get_required_disk_size(self, **kwargs):
        """
        Abstract method to be implemented in each adapter. Should return the required memory
        for launching the adapter in kilo-Bytes.
        """


    def get_execution_time_approximation(self, **kwargs):
        """
        Method should approximate based on input arguments, the time it will take for the operation 
        to finish (in seconds).
        """
        return -1


    @abstractmethod
    def launch(self):
        """
         To be implemented in each Adapter.
         Will contain the logic of the Adapter.
         Any returned DataType will be stored in DB, by the Framework.
        """


    def add_operation_additional_info(self, message):
        """
        Adds additional info on the operation to be displayed in the UI. Usually a warning message.
        """
        current_op = dao.get_operation_by_id(self.operation_id)
        current_op.additional_info = message
        dao.store_entity(current_op)


    @nan_not_allowed()
    def _prelaunch(self, operation, uid=None, available_disk_space=0, **kwargs):
        """
        Method to wrap LAUNCH.
        Will prepare data, and store results on return. 
        """
        self.meta_data.update(json.loads(operation.meta_data))
        self.storage_path = self.file_handler.get_project_folder(operation.project, str(operation.id))
        self.operation_id = operation.id
        self.current_project_id = operation.project.id
        self.user_id = operation.fk_launched_by

        self.configure(**kwargs)

        # Compare the amount of memory the current algorithms states it needs,
        # with the average between the RAM available on the OS and the free memory at the current moment.
        # We do not consider only the free memory, because some OSs are freeing late and on-demand only.
        total_free_memory = psutil.virtual_memory().free + psutil.swap_memory().free
        total_existent_memory = psutil.virtual_memory().total + psutil.swap_memory().total
        memory_reference = (total_free_memory + total_existent_memory) / 2
        adapter_required_memory = self.get_required_memory_size(**kwargs)

        if adapter_required_memory > memory_reference:
            msg = "Machine does not have enough RAM memory for the operation (expected %.2g GB, but found %.2g GB)."
            raise NoMemoryAvailableException(msg % (adapter_required_memory / 2 ** 30, memory_reference / 2 ** 30))

        # Compare the expected size of the operation results with the HDD space currently available for the user
        # TVB defines a quota per user.
        required_disk_space = self.get_required_disk_size(**kwargs)
        if available_disk_space < 0:
            msg = "You have exceeded you HDD space quota by %.2f MB Stopping execution."
            raise NoMemoryAvailableException(msg % (- available_disk_space / 2 ** 10))
        if available_disk_space < required_disk_space:
            msg = ("You only have %.2f GB of disk space available but the operation you "
                   "launched might require %.2f Stopping execution...")
            raise NoMemoryAvailableException(msg % (available_disk_space / 2 ** 20, required_disk_space / 2 ** 20))

        operation.start_now()
        operation.estimated_disk_size = required_disk_space
        dao.store_entity(operation)

        result = self.launch(**kwargs)

        if not isinstance(result, (list, tuple)):
            result = [result, ]
        # TODO: Fix this
        # self.__check_integrity(result)

        return self._capture_operation_results(result, uid)


    def _capture_operation_results(self, result, user_tag=None):
        """
        After an operation was finished, make sure the results are stored
        in DB storage and the correct meta-data,IDs are set.
        """
        results_to_store = []
        data_type_group_id = None
        operation = dao.get_operation_by_id(self.operation_id)
        if operation.user_group is None or len(operation.user_group) == 0:
            operation.user_group = date2string(datetime.now(), date_format=LESS_COMPLEX_TIME_FORMAT)
            operation = dao.store_entity(operation)
        if self._is_group_launch():
            data_type_group_id = dao.get_datatypegroup_by_op_group_id(operation.fk_operation_group).id
        # All entities will have the same subject and state
        subject = self.meta_data[DataTypeMetaData.KEY_SUBJECT]
        state = self.meta_data[DataTypeMetaData.KEY_STATE]
        burst_reference = None
        if DataTypeMetaData.KEY_BURST in self.meta_data:
            burst_reference = self.meta_data[DataTypeMetaData.KEY_BURST]
        perpetuated_identifier = None
        if DataTypeMetaData.KEY_TAG_1 in self.meta_data:
            perpetuated_identifier = self.meta_data[DataTypeMetaData.KEY_TAG_1]

        for res in result:
            if res is None:
                continue
            res.subject = str(subject)
            res.state = state
            res.fk_parent_burst = burst_reference
            res.fk_from_operation = self.operation_id
            res.framework_metadata = self.meta_data
            if not res.user_tag_1:
                res.user_tag_1 = user_tag if user_tag is not None else perpetuated_identifier
            else:
                res.user_tag_2 = user_tag if user_tag is not None else perpetuated_identifier
            res.fk_datatype_group = data_type_group_id
            ## Compute size-on disk, in case file-storage is used
            if hasattr(res, 'storage_path') and hasattr(res, 'get_storage_file_name'):
                associated_file = os.path.join(res.storage_path, res.get_storage_file_name())
                res.close_file()
                res.disk_size = self.file_handler.compute_size_on_disk(associated_file)
            res = dao.store_entity(res)
            # Write metaData
            # TODO: persistance should be done inisde launch()
            # res.persist_full_metadata()
            results_to_store.append(res)
        del result[0:len(result)]
        result.extend(results_to_store)

        if len(result) and self._is_group_launch():
            ## Update the operation group name
            operation_group = dao.get_operationgroup_by_id(operation.fk_operation_group)
            operation_group.fill_operationgroup_name(result[0].type)
            dao.store_entity(operation_group)

        return 'Operation ' + str(self.operation_id) + ' has finished.', len(results_to_store)


    def __check_integrity(self, result):
        """
         Check that the returned parameters for LAUNCH operation
        are of the type specified in the adapter's interface.
        """
        entity_id = self.__module__ + '.' + self.__class__.__name__

        for result_entity in result:
            if type(result_entity) == list and len(result_entity) > 0:
                #### Determine the first element not None
                first_item = None
                for res in result_entity:
                    if res is not None:
                        first_item = res
                        break
                if first_item is None:
                    return
                    #### All list items are None
                #### Now check if the first item has a supported type
                if not self.__is_data_in_supported_types(first_item):
                    msg = "Unexpected DataType %s"
                    raise InvalidParameterException(msg % type(first_item))

                first_item_type = type(first_item)
                for res in result_entity:
                    if not isinstance(res, first_item_type):
                        msg = '%s-Heterogeneous types (%s).Expected %s list.'
                        raise InvalidParameterException(msg % (entity_id, type(res), first_item_type))
            else:
                if not self.__is_data_in_supported_types(result_entity):
                    msg = "Unexpected DataType %s"
                    raise InvalidParameterException(msg % type(result_entity))


    def __is_data_in_supported_types(self, data):
        """
        This method checks if the provided data is one of the adapter supported return types 
        """
        if data is None:
            return True
        for supported_type in self.get_output():
            if isinstance(data, supported_type):
                return True
        ##### Data can't be mapped on any supported type !!
        return False


    def _is_group_launch(self):
        """
        Return true if this adapter is launched from a group of operations
        """
        operation = dao.get_operation_by_id(self.operation_id)
        return operation.fk_operation_group is not None


    @staticmethod
    def load_entity_by_gid(data_gid):
        """
        Load a generic DataType, specified by GID.
        """
        return load_entity_by_gid(data_gid)


    @staticmethod
    def build_adapter_from_class(adapter_class):
        """
        Having a subclass of ABCAdapter, prepare an instance for launching an operation with it.
        """
        if not issubclass(adapter_class, ABCAdapter):
            raise IntrospectionException("Invalid data type: It should extend adapters.ABCAdapter!")
        try:
            stored_adapter = dao.get_algorithm_by_module(adapter_class.__module__, adapter_class.__name__)

            adapter_instance = adapter_class()
            adapter_instance.stored_adapter = stored_adapter
            return adapter_instance
        except Exception as excep:
            LOGGER.exception(excep)
            raise IntrospectionException(str(excep))


    @staticmethod
    def build_adapter(stored_adapter):
        """
        Having a module and a class name, create an instance of ABCAdapter.
        """
        try:
            ad_module = importlib.import_module(stored_adapter.module)
            adapter_class = getattr(ad_module, stored_adapter.classname)
            adapter_instance = adapter_class()
            adapter_instance.stored_adapter = stored_adapter
            return adapter_instance

        except Exception:
            msg = "Could not load Adapter Instance for Stored row %s" % stored_adapter
            LOGGER.exception(msg)
            raise IntrospectionException(msg)


    ####### METHODS for PROCESSING PARAMETERS start here #############################

    def review_operation_inputs(self, parameters):
        """
        :returns: a list with the inputs from the parameters list that are instances of DataType,\
            and a dictionary with all parameters which are different than the declared defauts
        """
        flat_interface = self.flaten_input_interface()
        return self.tree_manager.review_operation_inputs(parameters, flat_interface)


    def prepare_ui_inputs(self, kwargs, validation_required=True):
        """
        Prepare the inputs received from a HTTP Post in a form that will be
        used by the Python adapter.
        """
        algorithm_inputs = self.get_input_tree()
        algorithm_inputs = InputTreeManager.prepare_param_names(algorithm_inputs)
        self.tree_manager.append_required_defaults(kwargs, algorithm_inputs)
        return self.convert_ui_inputs(kwargs, validation_required=validation_required)


    def convert_ui_inputs(self, kwargs, validation_required=True):
        """
        Convert HTTP POST parameters into Python parameters.
        """
        return self.tree_manager.convert_ui_inputs(self.flaten_input_interface(), kwargs, self.meta_data,
                                                   validation_required)


    def noise_configurable_parameters(self):
        return [entry[self.KEY_NAME] for entry in self.flaten_input_interface() if 'configurableNoise' in entry]


    def flaten_input_interface(self):
        # TODO: temporary condition to pass introspection on neoforms
        if self.get_input_tree() is None:
            return [{"name": self.get_form().get_input_name()}]
        """ Return a simple dictionary, instead of a Tree."""
        return self.tree_manager.flatten(self.get_input_tree())



class ABCAsynchronous(ABCAdapter):
    """
    Abstract class, for marking adapters that are prone to be executed  on Cluster.
    """
    __metaclass__ = ABCMeta

    def array_size2kb(self, size):
        """
        :param size: size in bytes
        :return: size in kB
        """
        return size * TvbProfile.current.MAGIC_NUMBER / 8 / 2 ** 10



class ABCSynchronous(ABCAdapter):
    """
    Abstract class, for marking adapters that are prone to be NOT executed on Cluster.
    """
    __metaclass__ = ABCMeta



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
.. moduleauthor:: Lia Domide <lia.domide@codemart.ro>
.. moduleauthor:: Ionel Ortelecan <ionel.ortelecan@codemart.ro>
.. moduleauthor:: Bogdan Neacsa <bogdan.neacsa@codemart.ro>
"""
from tvb.core.adapters.abcadapter import ABCAdapterForm
from tvb.core.entities.model.model_datatype import DataTypeGroup
from tvb.core.entities.model.model_operation import RANGE_MISSING_STRING, STATUS_FINISHED, RANGE_MISSING_VALUE
from tvb.core.entities.storage import dao
from tvb.core.entities.transient.pse import ContextDiscretePSE
from tvb.core.adapters.abcdisplayer import ABCDisplayer
from tvb.adapters.datatypes.db.mapped_value import DatatypeMeasureIndex
from tvb.core.entities.filters.chain import FilterChain
from tvb.core.neotraits.forms import DataTypeSelectField

MAX_NUMBER_OF_POINT_TO_SUPPORT = 512


class DiscretePSEAdapterForm(ABCAdapterForm):

    def __init__(self, prefix='', project_id=None):
        super(DiscretePSEAdapterForm, self).__init__(prefix, project_id)
        self.datatype_group = DataTypeSelectField(self.get_required_datatype(), self, name='datatype_group',
                                                  required=True, label='Datatype Group', conditions=self.get_filters())

    @staticmethod
    def get_required_datatype():
        return DataTypeGroup

    @staticmethod
    def get_input_name():
        return '_datatype_group'

    @staticmethod
    def get_filters():
        return FilterChain(fields=[FilterChain.datatype + ".no_of_ranges", FilterChain.datatype + ".no_of_ranges",
                                   FilterChain.datatype + ".count_results"],
                           operations=["<=", ">=", "<="],
                           values=[2, 1, MAX_NUMBER_OF_POINT_TO_SUPPORT])


class DiscretePSEAdapter(ABCDisplayer):
    """
    Visualization adapter for Parameter Space Exploration.
    Will be used as a generic visualizer, accessible when input entity is DataTypeGroup.
    Will also be used in Burst as a supplementary navigation layer.
    """
    _ui_name = "Discrete Parameter Space Exploration"
    _ui_subsection = "pse"


    def get_form_class(self):
        return DiscretePSEAdapterForm

    def get_required_memory_size(self, **kwargs):
        """
        Return the required memory to run this algorithm.
        """
        # Don't know how much memory is needed.
        return -1

    # TODO: migrate to neotraits
    def launch(self, datatype_group):
        """
        Launch the visualizer.
        """
        pse_context = self.prepare_parameters(datatype_group.gid, '')
        pse_context.prepare_individual_jsons()

        return self.build_display_result('pse_discrete/view', pse_context,
                                         pages=dict(controlPage="pse_discrete/controls"))

    @staticmethod
    def prepare_range_labels(operation_group, range_json):
        """
        Prepare Range labels for display in UI.
        When the current range_json is empty, returns None, [RANGE_MISSING_STRING], [RANGE_MISSING_STRING]

        :param operation_group: model.OperationGroup instance
        :param range_json: Stored JSON for for a given range
        :return: String with current range label, Array of ranged numbers, Array of labels for current range
        """
        contains_numbers, range_name, range_values = operation_group.load_range_numbers(range_json)

        if contains_numbers is None:
            return None, range_values, [RANGE_MISSING_STRING], False

        if contains_numbers:
            range_labels = range_values
        else:
            # when datatypes are in range, get the display name for those and use as labels.
            range_labels = []
            for data_gid in range_values:
                range_labels.append(dao.get_datatype_by_gid(data_gid).display_name)

        return range_name, range_values, range_labels, contains_numbers

    @staticmethod
    def get_value_on_axe(op_range, only_numbers, range_param_name, fake_numbers):
        if range_param_name is None:
            return RANGE_MISSING_VALUE
        if only_numbers:
            return op_range[range_param_name]
        return fake_numbers[op_range[range_param_name]]

    @staticmethod
    def prepare_parameters(datatype_group_gid, back_page, color_metric=None, size_metric=None):
        """
        We suppose that there are max 2 ranges and from each operation results exactly one dataType.

        :param datatype_group_gid: the group id for the `DataType` to be visualised
        :param back_page: Page where back button will direct
        :param color_metric: String referring to metric to apply on colors
        :param size_metric:  String referring to metric to apply on sizes

        :returns: `ContextDiscretePSE`
        :raises Exception: when `datatype_group_id` is invalid (not in database)
        """
        datatype_group = dao.get_datatype_group_by_gid(datatype_group_gid)
        if datatype_group is None:
            raise Exception("Selected DataTypeGroup is no longer present in the database. "
                            "It might have been remove or the specified id is not the correct one.")

        operation_group = dao.get_operationgroup_by_id(datatype_group.fk_operation_group)

        name1, values1, labels1, only_numbers1 = DiscretePSEAdapter.prepare_range_labels(operation_group,
                                                                                         operation_group.range1)
        name2, values2, labels2, only_numbers2 = DiscretePSEAdapter.prepare_range_labels(operation_group,
                                                                                         operation_group.range2)

        pse_context = ContextDiscretePSE(datatype_group_gid, color_metric, size_metric, back_page)
        pse_context.setRanges(name1, values1, labels1, name2, values2, labels2,
                              only_numbers1 and only_numbers2)
        final_dict = {}
        operations = dao.get_operations_in_group(operation_group.id)

        fake_numbers1 = dict(list(zip(values1, list(range(len(list(values1)))))))
        fake_numbers2 = dict(list(zip(values2, list(range(len(list(values2)))))))

        for operation_ in operations:
            if not operation_.has_finished:
                pse_context.has_started_ops = True
            range_values = eval(operation_.range_values)
            key_1 = DiscretePSEAdapter.get_value_on_axe(range_values, only_numbers1, name1, fake_numbers1)
            key_2 = DiscretePSEAdapter.get_value_on_axe(range_values, only_numbers2, name2, fake_numbers2)

            datatype = None
            if operation_.status == STATUS_FINISHED:
                pse_filter = FilterChain(fields=[FilterChain.datatype + '.type'], operations=['!='],
                                         values=['SimulatorIndex'])
                datatypes = dao.get_results_for_operation(operation_.id, pse_filter)
                if len(datatypes) > 0:
                    datatype = datatypes[0]
                    if datatype.type == "DatatypeMeasureIndex":
                        # Load proper entity class from DB.
                        measures = dao.get_generic_entity(DatatypeMeasureIndex, datatype.gid)
                    else:
                        measures = dao.get_generic_entity(DatatypeMeasureIndex, datatype.gid, 'source_gid')
                    pse_context.prepare_metrics_datatype(measures, datatype)

            if key_1 not in final_dict:
                final_dict[key_1] = {}

            final_dict[key_1][key_2] = pse_context.build_node_info(operation_, datatype)

        pse_context.fill_object(final_dict)
        # datatypes_dict is not actually used in the drawing of the PSE and actually
        # causes problems in case of NaN values, so just remove it before creating the json
        pse_context.datatypes_dict = {}
        if not only_numbers1:
            pse_context.values_x = list(range(len(list(values1))))
        if not only_numbers2:
            pse_context.values_y = list(range(len(list(values2))))
        return pse_context

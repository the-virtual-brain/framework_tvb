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
Adapter that uses the traits module to generate interfaces for FFT Analyzer.

.. moduleauthor:: Lia Domide <lia.domide@codemart.ro>
.. moduleauthor:: Stuart A. Knock <Stuart@tvb.invalid>

"""
import uuid
import psutil
import numpy
import math
import tvb.analyzers.fft as fft
import tvb.core.adapters.abcadapter as abcadapter
import tvb.basic.filters.chain as entities_filter
import tvb.datatypes.spectral as spectral
from tvb.basic.logger.builder import get_logger
from tvb.datatypes.time_series import TimeSeries

from tvb.core.entities.file.datatypes.spectral_h5 import FourierSpectrumH5
from tvb.interfaces.neocom.h5 import DirLoader

LOG = get_logger(__name__)


class FourierAdapter(abcadapter.ABCAsynchronous):
    """ TVB adapter for calling the FFT algorithm. """
    
    _ui_name = "Fourier Spectral Analysis"
    _ui_description = "Calculate the FFT of a TimeSeries entity."
    _ui_subsection = "fourier"
    
    def get_input_tree(self):
        """
        Return a list of lists describing the interface to the analyzer. This
        is used by the GUI to generate the menus and fields necessary for
        defining a simulation.
        """
        algorithm = fft.FFT()
        algorithm.trait.bound = self.INTERFACE_ATTRIBUTES_ONLY
        tree = algorithm.interface[self.INTERFACE_ATTRIBUTES]
        for node in tree:
            if node['name'] == 'time_series':
                node['conditions'] = entities_filter.FilterChain(
                    fields=[entities_filter.FilterChain.datatype + '._nr_dimensions'],
                    operations=["=="], values=[4])
        return tree
    
    
    def get_output(self):
        return [spectral.FourierSpectrum]


    def __init__(self):
        super(FourierAdapter, self).__init__()
        self.algorithm = fft.FFT()
        self.memory_factor = 1

    
    def configure(self, time_series, segment_length=None, window_function=None, detrend=None):
        """
        Do any configuration needed before launching.

        :param time_series: the input time series to which the fft is to be applied
        :param segment_length: the block size which determines the frequency resolution \
                               of the resulting power spectra
        :param window_function: windowing functions can be applied before the FFT is performed
        :type  window_function: None; ‘hamming’; ‘bartlett’; ‘blackman’; ‘hanning’
        :param detrend: None; specify if detrend is performed on the time series
        """
        self.loader = DirLoader(self.storage_path)

        shape = time_series.data.shape
        LOG.debug("time_series shape is %s" % str(shape))
        LOG.debug("Provided segment_length is %s" % segment_length)
        LOG.debug("Provided window_function is %s" % window_function)
        LOG.debug("Detrend is %s" % detrend)
        # -------------------- Fill Algorithm for Analysis -------------------
        # The enumerate set function isn't working well. A get around strategy is to create a new algorithm
        algorithm = fft.FFT()
        if segment_length is not None:
            algorithm.segment_length = segment_length

        algorithm.window_function = window_function
        algorithm.detrend = detrend
        self.algorithm = algorithm

        LOG.debug("Using segment_length is %s" % self.algorithm.segment_length)
        LOG.debug("Using window_function  is %s" % self.algorithm.window_function)
        LOG.debug("Using detrend  is %s" % self.algorithm.detrend)


    def get_required_memory_size(self, time_series, segment_length=None, window_function=None, detrend=None):
        """
        Returns the required memory to be able to run the adapter.
        """
        input_shape = time_series.data.shape
        input_size = numpy.prod(input_shape) * 8.0
        output_size = self.algorithm.result_size(input_shape, self.algorithm.segment_length,
                                                 time_series.sample_period.load())
        total_free_memory = psutil.virtual_memory().free + psutil.swap_memory().free
        total_required_memory = input_size + output_size
        while total_required_memory / self.memory_factor / total_free_memory > 0.8:
            self.memory_factor += 1
        return total_required_memory / self.memory_factor


    def get_required_disk_size(self, time_series, segment_length=None, window_function=None, detrend=None):
        """
        Returns the required disk size to be able to run the adapter (in kB).
        """
        input_shape = time_series.data.shape
        output_size = self.algorithm.result_size(input_shape, segment_length,
                                                 time_series.sample_period.load())
        return self.array_size2kb(output_size)


    def launch(self, time_series, segment_length=None, window_function=None, detrend=None):
        """
        Launch algorithm and build results.

        :param time_series: the input time series to which the fft is to be applied
        :param segment_length: the block size which determines the frequency resolution \
                               of the resulting power spectra
        :param window_function: windowing functions can be applied before the FFT is performed
        :type  window_function: None; ‘hamming’; ‘bartlett’; ‘blackman’; ‘hanning’
        :returns: the fourier spectrum for the specified time series
        :rtype: `FourierSpectrum`

        """
        shape = time_series.data.shape
        block_size = int(math.floor(shape[2] / self.memory_factor))
        blocks = int(math.ceil(shape[2] / block_size))

        gid = uuid.uuid4()
        dest_path = self.loader.path_for(FourierSpectrumH5, gid)

        spectra_file = FourierSpectrumH5(dest_path)
        spectra_file.gid.store(gid)
        spectra_file.source.store(time_series.gid.load())
        spectra_file.windowing_function.store(str(window_function))

        # ------------- NOTE: Assumes 4D, Simulator timeSeries. --------------
        node_slice = [slice(shape[0]), slice(shape[1]), None, slice(shape[3])]
        
        # ---------- Iterate over slices and compose final result ------------
        small_ts = TimeSeries()
        small_ts.sample_period = time_series.sample_period.load()

        for block in xrange(blocks):
            node_slice[2] = slice(block * block_size, min([(block+1) * block_size, shape[2]]), 1)
            small_ts.data = time_series.read_data_slice(tuple(node_slice))
            self.algorithm.time_series = small_ts
            partial_result = self.algorithm.evaluate()

            if blocks <= 1 and len(partial_result.array_data) == 0:
                self.add_operation_additional_info(
                    "Fourier produced empty result (most probably due to a very short input TimeSeries).")
                return None
            spectra_file.write_data_slice(partial_result)

        spectra_file.segment_length.store(self.algorithm.segment_length)
        spectra_file.close()

        LOG.debug("partial segment_length is %s" % (str(partial_result.segment_length)))

        return spectra_file


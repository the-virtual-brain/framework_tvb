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

import numpy
import pytest
from tvb.tests.framework.core.neotraits.data import FooDatatype, BarDatatype, BazDataType


@pytest.fixture()
def bazFactory():
    def build():
        return BazDataType(miu=numpy.array([0.0, 1.0, 2.0]), scalar_str='the baz')

    return build


@pytest.fixture()
def fooFactory():
    def build():
        return FooDatatype(
            array_float=numpy.linspace(0, 42, 100),
            array_int=numpy.arange(8 * 8).reshape((8, 8)),
            scalar_int=42,
            abaz=BazDataType(miu=numpy.zeros((2, 2)), scalar_str='a baz')
        )

    return build


@pytest.fixture()
def barFactory():
    def build():
        return BarDatatype(
            array_float=numpy.linspace(0, 42, 100),
            array_int=numpy.arange(8 * 8).reshape((8, 8)),
            scalar_int=42,
            array_str=numpy.array(['ana', 'are', 'mere']),
            abaz=BazDataType(miu=numpy.zeros((2, 2)), scalar_str='a baz')
        )

    return build

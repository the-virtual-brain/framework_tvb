from sqlalchemy import Column, Integer, ForeignKey, String

from tvb.core.entities.model.model_datatype import DataType


class VolumeIndex(DataType):
    id = Column(Integer, ForeignKey(DataType.id), primary_key=True)

    voxel_unit = Column(String, nullable=False)
    # voxel_size
    # origin

    def fill_from_has_traits(self, datatype):
        # self.gid = datatype.gid.hex
        self.voxel_unit = datatype.voxel_unit

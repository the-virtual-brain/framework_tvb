from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from tvb.datatypes.projections import ProjectionMatrix

from tvb.core.entities.model.datatypes.sensors import SensorsIndex
from tvb.core.entities.model.datatypes.surface import SurfaceIndex
from tvb.core.entities.model.model_datatype import DataType


class ProjectionMatrixIndex(DataType):
    id = Column(Integer, ForeignKey(DataType.id), primary_key=True)

    brain_skull_id = Column(Integer, ForeignKey(SurfaceIndex.id), nullable=not ProjectionMatrix.brain_skull.required)
    brain_skull = relationship(SurfaceIndex, foreign_keys=brain_skull_id, primaryjoin=SurfaceIndex.id == brain_skull_id)

    skull_skin_id = Column(Integer, ForeignKey(SurfaceIndex.id), nullable=not ProjectionMatrix.skull_skin.required)
    skull_skin = relationship(SurfaceIndex, foreign_keys=skull_skin_id, primaryjoin=SurfaceIndex.id == skull_skin_id)

    skin_air_id = Column(Integer, ForeignKey(SurfaceIndex.id), nullable=not ProjectionMatrix.skin_air.required)
    skin_air = relationship(SurfaceIndex, foreign_keys=skin_air_id, primaryjoin=SurfaceIndex.id == skin_air_id)

    source_id = Column(Integer, ForeignKey(SurfaceIndex.id), nullable=not ProjectionMatrix.sources.required)
    source = relationship(SurfaceIndex, foreign_keys=source_id, primaryjoin=SurfaceIndex.id == source_id)

    sensors_id = Column(Integer, ForeignKey(SensorsIndex.id), nullable=not ProjectionMatrix.sensors.required)
    sensors = relationship(SensorsIndex, foreign_keys=sensors_id, primaryjoin=SensorsIndex.id == sensors_id)

    def fill_from_has_traits(self, datatype):
        self.gid = datatype.gid.hex

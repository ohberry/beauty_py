from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database import Base


class History(Base):
    __tablename__ = "history"

    id = Column(Integer, primary_key=True)
    platform = Column(String)
    sec_uid = Column(String)
    user_id = Column(String)
    work_id = Column(String)
    work_type = Column(String)
    url = Column(String)
    index = Column(Integer)
    # 1：成功 2：失败
    status = Column(Integer)
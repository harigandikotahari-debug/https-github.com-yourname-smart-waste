"""SQLAlchemy ORM models.

Entities: Users, WasteCategories, Locations, Bins, BinSensorReadings,
WasteDetections, CollectionRecords, Routes, PredictionResults.

Design notes:
- Only portable types/constraints are used (String, Integer, Float, Boolean,
  DateTime, JSON, ForeignKey) so this schema runs unchanged on SQLite (dev)
  or PostgreSQL (production) per config/settings.yaml `database.url`.
- `is_simulated` / `data_source` columns exist wherever a value could
  plausibly come from a real sensor/GPS OR a simulation, so the UI can
  always show the user whether a number is verified, AI-predicted, or
  simulated (AI-safety requirement).
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


def utcnow() -> dt.datetime:
    return dt.datetime.utcnow()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    full_name = Column(String(128), nullable=False)
    email = Column(String(128), nullable=True)
    role = Column(String(16), nullable=False)  # admin | operator | citizen
    created_at = Column(DateTime, default=utcnow, nullable=False)

    detections = relationship("WasteDetection", back_populates="user")
    collections_handled = relationship("CollectionRecord", back_populates="operator")


class WasteCategory(Base):
    __tablename__ = "waste_categories"

    id = Column(Integer, primary_key=True)
    key = Column(String(32), unique=True, nullable=False)  # plastic, paper, ...
    label = Column(String(64), nullable=False)
    bin_stream = Column(String(128), nullable=False)
    bin_color = Column(String(32), nullable=False)
    recyclable = Column(Boolean, default=False, nullable=False)
    description = Column(String(256), nullable=True)

    bins = relationship("Bin", back_populates="waste_category")
    detections = relationship("WasteDetection", back_populates="waste_category")


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False)
    address = Column(String(256), nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    location_type = Column(String(32), nullable=False)  # hospital, market, ...
    zone = Column(String(64), nullable=True)

    bins = relationship("Bin", back_populates="location")


class Bin(Base):
    __tablename__ = "bins"

    id = Column(Integer, primary_key=True)
    bin_code = Column(String(32), unique=True, nullable=False)  # e.g. BIN-0042
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    waste_category_id = Column(Integer, ForeignKey("waste_categories.id"), nullable=False)
    capacity_liters = Column(Float, default=240.0, nullable=False)
    current_fill_level = Column(Float, default=0.0, nullable=False)  # 0-100
    status = Column(String(16), default="normal", nullable=False)
    installed_at = Column(DateTime, default=utcnow, nullable=False)
    last_collection_time = Column(DateTime, nullable=True)

    location = relationship("Location", back_populates="bins")
    waste_category = relationship("WasteCategory", back_populates="bins")
    sensor_readings = relationship("BinSensorReading", back_populates="bin", cascade="all, delete-orphan")
    collection_records = relationship("CollectionRecord", back_populates="bin")
    predictions = relationship("PredictionResult", back_populates="bin")


class BinSensorReading(Base):
    __tablename__ = "bin_sensor_readings"

    id = Column(Integer, primary_key=True)
    bin_id = Column(Integer, ForeignKey("bins.id"), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    fill_level = Column(Float, nullable=False)  # 0-100
    is_simulated = Column(Boolean, default=True, nullable=False)

    bin = relationship("Bin", back_populates="sensor_readings")


class WasteDetection(Base):
    __tablename__ = "waste_detections"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    waste_category_id = Column(Integer, ForeignKey("waste_categories.id"), nullable=True)
    detected_at = Column(DateTime, default=utcnow, nullable=False)
    image_path = Column(String(512), nullable=True)
    confidence = Column(Float, nullable=False)
    bbox_x = Column(Float, nullable=True)  # normalized 0-1, top-left
    bbox_y = Column(Float, nullable=True)
    bbox_w = Column(Float, nullable=True)
    bbox_h = Column(Float, nullable=True)
    raw_label = Column(String(64), nullable=True)  # model's raw class name pre-mapping
    manual_verification_required = Column(Boolean, default=False, nullable=False)
    source = Column(String(16), default="upload", nullable=False)  # upload | camera

    user = relationship("User", back_populates="detections")
    waste_category = relationship("WasteCategory", back_populates="detections")


class CollectionRecord(Base):
    __tablename__ = "collection_records"

    id = Column(Integer, primary_key=True)
    bin_id = Column(Integer, ForeignKey("bins.id"), nullable=False)
    route_id = Column(Integer, ForeignKey("routes.id"), nullable=True)
    operator_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    scheduled_time = Column(DateTime, nullable=True)
    collected_time = Column(DateTime, nullable=True)
    status = Column(String(16), default="scheduled", nullable=False)  # scheduled|completed|missed
    fill_level_at_collection = Column(Float, nullable=True)

    bin = relationship("Bin", back_populates="collection_records")
    route = relationship("Route", back_populates="collection_records")
    operator = relationship("User", back_populates="collections_handled")


class Route(Base):
    __tablename__ = "routes"

    id = Column(Integer, primary_key=True)
    vehicle_label = Column(String(32), nullable=False)
    planned_date = Column(DateTime, default=utcnow, nullable=False)
    bin_sequence = Column(JSON, nullable=False)  # ordered list of bin ids
    total_distance_km = Column(Float, nullable=False)
    total_duration_minutes = Column(Float, nullable=False)
    is_optimized = Column(Boolean, default=True, nullable=False)

    collection_records = relationship("CollectionRecord", back_populates="route")


class PredictionResult(Base):
    __tablename__ = "prediction_results"

    id = Column(Integer, primary_key=True)
    bin_id = Column(Integer, ForeignKey("bins.id"), nullable=False, index=True)
    predicted_at = Column(DateTime, default=utcnow, nullable=False)
    predicted_fill_level_24h = Column(Float, nullable=False)
    predicted_hours_to_full = Column(Float, nullable=True)
    overflow_probability = Column(Float, nullable=False)  # 0-1
    collection_required = Column(Boolean, nullable=False)
    priority_score = Column(Float, nullable=False)  # 0-100
    priority_band = Column(String(16), nullable=False)  # low|medium|high|critical
    model_version = Column(String(32), nullable=False)

    bin = relationship("Bin", back_populates="predictions")

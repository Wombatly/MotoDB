from datetime import datetime
from app.timeutils import utcnow
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app import db


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    last_login = db.Column(db.DateTime)
    consent_accepted_at = db.Column(db.DateTime)

    motorcycles = db.relationship('Motorcycle', backref='user', cascade='all, delete-orphan', lazy=True)
    services = db.relationship('ServiceEntry', backref='user', cascade='all, delete-orphan', lazy=True)
    technical_specs = db.relationship('TechnicalSpec', backref='user', cascade='all, delete-orphan', lazy=True)
    checklists = db.relationship('ServiceChecklist', backref='user', cascade='all, delete-orphan', lazy=True)
    documents = db.relationship('MotorcycleDocument', backref='user', cascade='all, delete-orphan', lazy=True)
    audit_logs = db.relationship('AuditLog', backref='user', cascade='all, delete-orphan', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method="pbkdf2:sha256")

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(80), nullable=False)  # CREATE, UPDATE, DELETE
    table_name = db.Column(db.String(80), nullable=False)
    record_id = db.Column(db.Integer)
    changes_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)


class Motorcycle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    marke = db.Column(db.String(120), nullable=False)
    modell = db.Column(db.String(120), nullable=False)
    baujahr = db.Column(db.Integer)
    kilometerstand = db.Column(db.Integer)
    kaufpreis = db.Column(db.Integer)
    hubraum = db.Column(db.Integer)
    ps = db.Column(db.Integer)
    farbe = db.Column(db.String(80))
    kaufdatum = db.Column(db.Date)
    kennzeichen = db.Column(db.String(40))
    vin = db.Column(db.String(80))
    erstzulassung = db.Column(db.Date)
    verkauft_am = db.Column(db.Date)
    verkaufspreis = db.Column(db.Integer)
    aktiv = db.Column(db.Boolean, default=True, nullable=False)
    notizen = db.Column(db.Text)
    bild = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    services = db.relationship(
        "ServiceEntry", backref="motorcycle", cascade="all, delete-orphan", lazy=True
    )
    technical_specs = db.relationship(
        "TechnicalSpec", backref="motorcycle", cascade="all, delete-orphan", lazy=True
    )
    checklists = db.relationship(
        "ServiceChecklist", backref="motorcycle", cascade="all, delete-orphan", lazy=True
    )
    images = db.relationship(
        "MotorcycleImage",
        backref="motorcycle",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="MotorcycleImage.position, MotorcycleImage.id",
    )
    documents = db.relationship(
        "MotorcycleDocument",
        backref="motorcycle",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="MotorcycleDocument.created_at.desc(), MotorcycleDocument.id.desc()",
    )


class MotorcycleImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    motorcycle_id = db.Column(db.Integer, db.ForeignKey("motorcycle.id"), nullable=False)
    path = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255))
    position = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)


class MotorcycleDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    motorrad_id = db.Column(db.Integer, db.ForeignKey("motorcycle.id"), nullable=False)
    titel = db.Column(db.String(160), nullable=False)
    kategorie = db.Column(db.String(80), nullable=False)
    path = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


class ServiceEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    motorrad_id = db.Column(db.Integer, db.ForeignKey("motorcycle.id"), nullable=False)
    titel = db.Column(db.String(160))
    datum = db.Column(db.Date, nullable=False)
    kilometerstand = db.Column(db.Integer)
    beschreibung = db.Column(db.Text)
    kosten = db.Column(db.Integer)
    kategorie = db.Column(db.String(80), nullable=False)
    beleg = db.Column(db.String(255))
    beleg_originalname = db.Column(db.String(255))
    naechster_service_km = db.Column(db.Integer)
    naechster_service_datum = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


class TechnicalSpec(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    motorrad_id = db.Column(db.Integer, db.ForeignKey("motorcycle.id"), nullable=False)
    name = db.Column(db.String(160), nullable=False)
    wert = db.Column(db.String(240))
    einheit = db.Column(db.String(40))
    kategorie = db.Column(db.String(80), default="Allgemein")
    quelle = db.Column(db.String(240))
    position = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


class ServiceChecklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    motorrad_id = db.Column(db.Integer, db.ForeignKey("motorcycle.id"), nullable=False)
    titel = db.Column(db.String(180), nullable=False)
    intervall_km = db.Column(db.Integer)
    intervall_monate = db.Column(db.Integer)
    datum = db.Column(db.Date)
    kilometerstand = db.Column(db.Integer)
    anmerkungen = db.Column(db.Text)
    is_template = db.Column(db.Boolean, default=True, nullable=False)
    source_template_id = db.Column(db.Integer, db.ForeignKey("service_checklist.id"))
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    items = db.relationship(
        "ServiceChecklistItem",
        backref="checklist",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="ServiceChecklistItem.position",
    )


class ServiceChecklistItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    checklist_id = db.Column(db.Integer, db.ForeignKey("service_checklist.id"), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)
    text = db.Column(db.String(240), nullable=False)
    kommentar_vorlage = db.Column(db.Text)
    erledigt = db.Column(db.Boolean, default=False, nullable=False)
    anmerkung = db.Column(db.Text)
    updated_at = db.Column(
        db.DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


class AppSetting(db.Model):
    key = db.Column(db.String(80), primary_key=True)
    value = db.Column(db.String(500))
    updated_at = db.Column(
        db.DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

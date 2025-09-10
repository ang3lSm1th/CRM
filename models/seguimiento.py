# seguimiento.py
from datetime import datetime
from zoneinfo import ZoneInfo
# ⬇️ AJUSTA este import según tu proyecto
from app import db  # p.ej. from extensions import db

class Seguimiento(db.Model):
    __tablename__ = "seguimientos"

    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=False, index=True)

    # Todos estos pueden ir NULL si no se llenan en seguimiento.html
    usuario_id = db.Column(db.Integer, nullable=True)
    fecha_seguimiento = db.Column(db.Date, nullable=True)          # “fecha del lead” si algún día decides guardarla
    proceso_id = db.Column(db.Integer, db.ForeignKey("procesos.id"), nullable=True)
    fecha_programada = db.Column(db.Date, nullable=True)
    motivo_no_venta_id = db.Column(db.Integer, db.ForeignKey("motivos_no_venta.id"), nullable=True)
    cotizacion = db.Column(db.String(50), nullable=True)
    monto = db.Column(db.Numeric(12, 2), nullable=True)
    moneda_id = db.Column(db.Integer, db.ForeignKey("monedas.id"), nullable=True)
    comentario = db.Column(db.Text, nullable=True)
    canal_emision = db.Column(db.String(50), nullable=True)

    # Siempre se guarda (hoy) en zona America/Lima
    fecha_guardado = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(ZoneInfo("America/Lima"))
    )

    # Relaciones (opcionales)
    lead = db.relationship("Lead", backref=db.backref("seguimientos", lazy="dynamic"))
    proceso = db.relationship("Proceso", lazy="joined")
    motivo = db.relationship("MotivoNoVenta", lazy="joined")
    moneda = db.relationship("Moneda", lazy="joined")

    __table_args__ = (
        db.Index("ix_seguimientos_lead_guardado", "lead_id", "fecha_guardado"),
    )

    def __repr__(self):
        return f"<Seguimiento id={self.id} lead_id={self.lead_id} proceso_id={self.proceso_id}>"

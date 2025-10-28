from . import db
from datetime import datetime

class Device(db.Model):
    __tablename__ = 'devices'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    device_type = db.Column(db.String(50), nullable=False)  # PZEM, ESP8266, etc.
    device_id = db.Column(db.String(50), unique=True, nullable=False)
    ip_address = db.Column(db.String(15))
    api_key = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)
    last_seen = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Chave estrangeira
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Relacionamentos
    energy_data = db.relationship('EnergyData', backref='device', lazy=True)
    reles = db.relationship('Rele', backref='device', lazy=True)
    
    def __repr__(self):
        return f'<Device {self.name} ({self.device_type})>'
    
    def update_last_seen(self):
        self.last_seen = datetime.utcnow()
        db.session.commit()
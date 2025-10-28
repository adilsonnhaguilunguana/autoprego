from . import db
from datetime import datetime

class EnergyData(db.Model):
    __tablename__ = 'energy_data'
    
    id = db.Column(db.Integer, primary_key=True)
    voltage = db.Column(db.Float, nullable=False)
    current = db.Column(db.Float, nullable=False)
    power = db.Column(db.Float, nullable=False)
    energy = db.Column(db.Float, nullable=False)
    frequency = db.Column(db.Float, nullable=False)
    pf = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Chaves estrangeiras
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id'), nullable=False)
    
    def __repr__(self):
        return f'<EnergyData {self.power}W @ {self.timestamp}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'voltage': self.voltage,
            'current': self.current,
            'power': self.power,
            'energy': self.energy,
            'frequency': self.frequency,
            'pf': self.pf,
            'timestamp': self.timestamp.isoformat(),
            'device_id': self.device_id
        }
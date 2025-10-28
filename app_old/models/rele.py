from . import db
from datetime import datetime

class Rele(db.Model):
    __tablename__ = 'reles'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    pin = db.Column(db.Integer, nullable=False)
    state = db.Column(db.Boolean, default=False)
    power_limit = db.Column(db.Integer, default=500)
    priority = db.Column(db.Integer, default=3)  # 1-5, 1 é mais alta prioridade
    current_consumption = db.Column(db.Float, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_state_change = db.Column(db.DateTime)
    
    # Chaves estrangeiras
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id'), nullable=False)
    
    def __repr__(self):
        return f'<Rele {self.name} (Pin {self.pin})>'
    
    def toggle(self):
        self.state = not self.state
        self.last_state_change = datetime.utcnow()
        db.session.commit()
        return self.state
    
    def set_state(self, state):
        self.state = bool(state)
        self.last_state_change = datetime.utcnow()
        db.session.commit()
        return self.state
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'pin': self.pin,
            'state': self.state,
            'power_limit': self.power_limit,
            'priority': self.priority,
            'current_consumption': self.current_consumption,
            'is_active': self.is_active,
            'device_id': self.device_id
        }
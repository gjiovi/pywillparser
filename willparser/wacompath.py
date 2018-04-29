from protobuf3.fields import SInt32Field, UInt32Field, BytesField, FloatField
from protobuf3.message import Message


class Path(Message):
    pass

Path.add_field('startParameter', FloatField(field_number=1, optional=True, default=0))
Path.add_field('endParameter', FloatField(field_number=2, optional=True, default=1))
Path.add_field('decimalPrecision', UInt32Field(field_number=3, optional=True, default=2))
Path.add_field('points', BytesField(field_number=4, required=True))
Path.add_field('strokeWidths', BytesField(field_number=5, required=True))
Path.add_field('strokeColor', BytesField(field_number=6, required=True))
Path.add_field('unknown', SInt32Field(field_number=9, optional=True))

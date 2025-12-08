from datetime import datetime


class DateConverter:
    regex = '\d\d\d\d-\d\d-\d\d'
    format = '%Y-%m-%d'

    def to_python(self, value):
        return datetime.strptime(value, self.format).date()

    def to_url(self, value):
        return value.strftime(self.format)


import locale
from datetime import datetime, timedelta
from urllib.request import urlopen
from xml.etree import ElementTree

from weasyprint import CSS, HTML


class UniqueByConference(object):
    def __new__(cls, conference, attr, *args, **kwargs):
        if getattr(cls,
                   '_instances',
                   None) is None:
            cls._instances = {}
        instance_id = (conference, attr)
        if cls._instances.get(instance_id, None) is None:
            cls._instances[instance_id] = super().__new__(cls)
        return cls._instances[instance_id]

    def __init__(self, conference, attr):
        self._conference = conference


class Conference(object):
    def __init__(self, url):
        self._url = url

    def __str__(self):
        return self._title

    @property
    def _rooms(self):
        rooms = {}
        for day in self._days.values():
            rooms.update(day._rooms.items())
        return rooms

    @property
    def _events(self):
        events = {}
        for day in self._days.values():
            events.update(day._events.items())
        return events

    @property
    def _persons(self):
        persons = {}
        for day in self._days.values():
            persons.update(day._persons.items())
        return persons

    def parse(self):
        remote = urlopen(self._url)
        tree = ElementTree.parse(remote)
        root_element = tree.getroot()
        for element in root_element.getchildren():
            if element.tag == 'conference':
                for element_details in element.getchildren():
                    setattr(self,
                            f'_{element_details.tag}',
                            element_details.text)
            elif element.tag == 'day':
                date = datetime.strptime(element.get('date'), '%Y-%m-%d')
                if getattr(self,
                           '_days',
                           None) is None:
                    self._days = {}
                self._days[date] = Day(self, date)
                self._days[date].parse(element)
            else:
                print('unknown element type')


class Day(UniqueByConference):
    def __init__(self, conference, date):
        super().__init__(conference, date)
        self._date = date

    @property
    def _persons(self):
        persons = {}
        for event in self._events.values():
            persons.update(event._persons.items())
        return persons

    def parse(self, day_element):
        for element in day_element.getchildren():
            if element.tag == 'room':
                room_name = element.get('name')
                if getattr(self,
                           '_rooms',
                           None) is None:
                    self._rooms = {}
                self._rooms[room_name] = Room(
                    self._conference,
                    room_name,
                    self)
                self._rooms[room_name].parse(element)
            elif element.tag == 'event':
                event_id = element.get('id')
                if getattr(self,
                           '_events',
                           None) is None:
                    self._events = {}
                self._events[event_id] = Event(
                    self._conference,
                    event_id,
                    self)
                self._events[event_id].parse(element)


class Room(UniqueByConference):
    def __init__(self, conference, name, day):
        super().__init__(conference, name)
        self._name = name
        if getattr(self,
                   '_days',
                   None) is None:
            self._days = {}
        self._days[day._date] = day

    def __str__(self):
        return self._name

    def get_events_by_day(self, day):
        events = {}
        for event in day._events.values():
            if event._room is not self:
                continue
            events[event._id] = event
        return events

    def get_sorted_list_by_day(self, day):
        events = list(self.get_events_by_day(day).values())
        events.sort(key=lambda e: e._start_datetime)
        return events

    def parse(self, room_element):
        pass


class Event(UniqueByConference):
    def __init__(self, conference, event_id, day):
        super().__init__(conference, event_id)
        self._id = event_id
        self._day = day

    def _str__(self):
        return self._title

    @property
    def title(self):
        return self._title

    @property
    def _start_datetime(self):
        date = self._day._date
        hours, minutes = str(self._start).split(':')
        return datetime(year=date.year,
                        month=date.month,
                        day=date.day,
                        hour=int(hours),
                        minute=int(minutes))

    @property
    def _end_datetime(self):
        hours, minutes = str(self._duration).split(':')
        return self._start_datetime + timedelta(hours=int(hours),
                                                minutes=int(minutes))

    @property
    def persons(self):
        names = [person._name for person in self._persons.values()]
        if len(names) >= 3:
            return '{} et {}'.format(', '.join(names[:-1]), names[-1])
        elif len(names) == 2:
            return '{} et {}'.format(*names)
        return names[0]

    def parse(self, event_element):
        for element in event_element.getchildren():
            if element.tag == 'person':
                person_id = element.get('id')
                if getattr(self,
                           '_persons',
                           None) is None:
                    self._persons = {}
                self._persons[person_id] = Person(
                    self._conference,
                    person_id,
                    self)
                self._persons[person_id].parse(element)
            elif element.tag == 'room':
                room_name = element.text
                self._room = Room(self._conference, room_name, self._day)
            else:
                setattr(self,
                        f'_{element.tag}',
                        element.text)


class Person(UniqueByConference):
    def __init__(self, conference, person_id, event):
        super().__init__(conference, person_id)
        self._id = person_id
        if getattr(self,
                   '_events',
                   None) is None:
            self._events = {}
        self._events[event._id] = event

    def __str__(self):
        return self._name

    def parse(self, person_element):
        self._name = person_element.text


if __name__ == "__main__":
    cdl2018 = Conference(
        url='https://participez-2018.capitoledulibre.org/schedule/xml/')
    cdl2018.parse()

    locale.setlocale(locale.LC_ALL, 'fr_FR.utf8')

    html_string = ''
    for day in cdl2018._days.values():
        day_html = ''
        for room in day._rooms.values():
            events = room.get_sorted_list_by_day(day)
            if len(events) == 0:
                continue
            room_html = f'''
            <div class="room">
                <header>
                    <div class="conf_title"><!-- Capitole du Libre 2018 --></div>
                    <div class="day_title">{day._date:%A %d %B}</div>
                    <div class="room_title">Salle {room}</div>
                </header>
                <table>
                    <thead>
                        <th>Heure</th>
                        <th>Conférence</th>
                    </thead>
                    <tbody>
            '''
            for i, event in enumerate(events):
                if i != 0 and \
                       events[i-1]._end_datetime != event._start_datetime:
                    room_html += f'''
                        <tr>
                            <td colspan="2"><!-- Pause --></td>
                        </tr>
                    '''
                room_html += f'''
                        <tr class="event_row">
                            <td class="event_date">
                                {event._start_datetime:%Hh%M}
                                à
                                {event._end_datetime:%Hh%M}
                            </td>
                            <td class="event_cell">
                                <div class="event_title">
                                    {event.title}
                                </div>
                                <div class="event_persons">
                                    {event.persons}
                                </div>
                            </td>
                        </tr>
                '''
            room_html += f'''
                    </tbody>
                </table>
            </div>
            '''
            day_html += room_html
        html_string += f'<div class="day">{day_html}</div>'

    html = HTML(string=html_string)
    css = CSS(filename='style.css')
    html.write_pdf('cdl2018.pdf', stylesheets=[css])

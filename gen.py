
import locale
import os
from datetime import datetime, timedelta
from pprint import pprint
from typing import Dict
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
            if hasattr(cls._instances[instance_id], 'init'):
                cls._instances[instance_id].init()
        return cls._instances[instance_id]

    def __init__(self, conference, attr):
        self._conference = conference


class Conference(object):
    def __init__(self, url):
        self._url = url
        self._days: Dict[datetime, Day] = {}

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
        for element in list(root_element):
            if element.tag == 'conference':
                for element_details in list(element):
                    if element_details.tag in ['title', 'venue', 'city', 'start_date', 'end_date', 'days_count']:
                        setattr(self,
                                f'_{element_details.tag}',
                                element_details.text)
            elif element.tag == 'day':
                date = datetime.strptime(element.get('date'), '%Y-%m-%d')
                self._days[date] = Day(self, date)
                self._days[date].parse(element)
            else:
                print('unknown element type')


class Day(UniqueByConference):
    def __init__(self, conference: Conference, date: datetime):
        super().__init__(conference, date)
        self._date = date

    def init(self):
        self._rooms: Dict[str, Room] = {}

    @property
    def _persons(self):
        persons = {}
        for room in self._rooms.values():
            for event in room._events.values():
                persons.update(event._persons.items())
        return persons

    def parse(self, day_element):
        for element in list(day_element):
            if element.tag == 'room':
                room_name = element.get('name')
                self._rooms[room_name] = Room(
                    self._conference,
                    room_name,
                    self)
                self._rooms[room_name].parse(element, self)


class Room(UniqueByConference):
    def __init__(self, conference: Conference, name: str, day: Day):
        super().__init__(conference, name)
        self._name = name
        self._days[day._date] = day

    def init(self):
        self._days: Dict[datetime, Day] = {}
        self._events: Dict[str, Event] = {}

    def __str__(self):
        return self._name

    def get_events_by_day(self, day):
        events = {}
        for event in self._events.values():
            if event._day is day:
                events[event._id] = event

        return events

    def get_sorted_list_by_day(self, day):
        events = list(self.get_events_by_day(day).values())
        events.sort(key=lambda e: e._start_datetime)
        return events

    def parse(self, room_element, day: Day):
        for element in list(room_element):
            if element.tag == 'event':
                event_id = element.get('id')
                self._events[event_id] = Event(
                    self._conference,
                    event_id,
                    day)
                self._events[event_id].parse(element)


class Event(UniqueByConference):
    def __init__(self, conference, event_id, day: Day):
        super().__init__(conference, event_id)
        self._id = event_id
        self._day: Day = day

    def init(self):
        self._persons: Dict[str, Person] = {}

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
        for element in list(event_element):
            if element.tag == 'persons':
                for person_element in list(element):
                    person_id = person_element.get('id')
                    self._persons[person_id] = Person(
                        self._conference,
                        person_id,
                        self)
                    self._persons[person_id].parse(person_element)
            else:
                setattr(self,
                        f'_{element.tag}',
                        element.text)


class Person(UniqueByConference):
    def __init__(self, conference: Conference, person_id, event: Event):
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
    conference = Conference(
        url='https://cfp.capitoledulibre.org/cdl-2022/schedule/export/schedule.xml')
    conference.parse()

    locale.setlocale(locale.LC_ALL, 'fr_FR.utf8')

    html_string = ''
    for day in conference._days.values():
        day_html = ''
        for room in day._rooms.values():
            events = room.get_sorted_list_by_day(day)
            if len(events) == 0:
                continue
            # Pauses
            if room._name == 'Foyer des Étudiants':
                continue

            p1 = Event(conference, 9000, day)
            p1._room = Room(conference, room._name, day)
            p1._title = 'Pause déjeuner'
            p1._start = '12:30'
            p1._duration = '01:30'
            p1._persons = {}
            p1._type = 'pause'
            room._events[p1._id] = p1
            if day._date.isoweekday() != 7:
                p2 = Event(conference, 9001, day)
                p2._room = Room(conference, room._name, day)
                p2._title = 'Pause'
                p2._start = '16:00'
                p2._duration = '00:30'
                p2._persons = {}
                p2._type = 'pause'
                room._events[p2._id] = p2

            # Refresh list
            events = room.get_sorted_list_by_day(day)
            room_html = f'''
            <div class="room">
                <header>
                    <div class="conf_title"><!-- Capitole du Libre 2019 --></div>
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
                        <tr class="event_row {event._type}">
                            <td class="event_date">
                                {event._start_datetime:%Hh%M}
                                à
                                {event._end_datetime:%Hh%M}
                            </td>
                            <td class="event_cell">
                                <div class="event_title">
                                    {event.title}
                                </div>
                '''
                if len(event._persons.values()) > 0:
                    room_html += f'''
                                    <div class="event_persons">
                                        {event.persons}
                                    </div>
                    '''
                room_html += f'''
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
    file_name = 'conference.pdf'
    try:
        os.remove(file_name)
    except FileNotFoundError:
        pass

    html.write_pdf(file_name, stylesheets=[css])

import simpy
import csv
from datetime import time, timedelta, datetime
import numpy as np
import matplotlib.pyplot as plt

N_tickets_desk = 3  # кол-во касс
T_tickets = 20  # время покупки билета (сек)

N_security = 4  # кол-во пунктов досмотра
T_security = 25  # время проверки (сек)

N_rooms = 2  # кол-во комнат проверки билетов
T_room_entrance = 10  # проверка билета (сек)

T_before_start = 30 * 60  # кол-во секунд прихода до начала (15 минут)

sessions = []
with open('sessions.csv') as file:
    reader = csv.reader(file, delimiter=';')
    for row in reader:
        sessions.append((int(row[0]), time.fromisoformat(row[1]), int(row[2])))
sessions.sort(key=lambda x: x[1])


class Cinema:
    def __init__(self, env):
        self.env = env
        self.ticketResources = simpy.Resource(env, N_tickets_desk)
        self.securityResources = simpy.Resource(env, N_security)
        self.roomResources = simpy.Resource(env, N_rooms)
        self.sessions = sessions

        self.queues = {
            'tickets': {},
            'security': {},
            'rooms': {}
        }

    def update_max_queue_length(self, current_time, key, cur_len):
        hour = int(current_time // 3600)
        minute = (current_time % 3600) // 60

        #  обновление максимальной длины очереди в пункте key в текущем 15 минутном промежутке
        if minute >= 45 and cur_len >= self.queues[key].get(f'{str(hour):02}:45', 0):
            self.queues[key][f'{str(hour):02}:45'] = cur_len
        elif minute >= 30 and cur_len >= self.queues[key].get(f'{str(hour):02}:30', 0):
            self.queues[key][f'{str(hour):02}:30'] = cur_len
        elif minute >= 15 and cur_len >= self.queues[key].get(f'{str(hour):02}:15', 0):
            self.queues[key][f'{str(hour):02}:15'] = cur_len
        elif cur_len >= self.queues[key].get(f'{str(hour):02}:00', 0):
            self.queues[key][f'{str(hour):02}:00'] = cur_len

    def simulate_processes(self, person, session_id):
        # покупка билета
        with self.ticketResources.request() as resources:
            yield resources
            # print(f'Сеанс номер {session_id}, покупает билет человек номер {person}, время: {self.env.now}')
            yield self.env.timeout(T_tickets)
            self.update_max_queue_length(self.env.now, 'tickets', len(self.ticketResources.queue))

        # безопасность
        with self.securityResources.request() as resources:
            yield resources
            # print(f'Сеанс номер {session_id}, проходит проверку человек номер {person}, время: {self.env.now}')
            yield self.env.timeout(T_security)
            self.update_max_queue_length(self.env.now, 'security', len(self.securityResources.queue))

        # проход в зал
        with self.roomResources.request() as resources:
            yield resources
            # print(f'Сеанс номер {session_id}, заходит в зал человек номер {person}, время: {self.env.now}')
            yield self.env.timeout(T_room_entrance)
            self.update_max_queue_length(self.env.now, 'rooms', len(self.roomResources.queue))

    def person_arrive(self, arrive_time, person, session_id):
        yield self.env.timeout(arrive_time)
        yield self.env.process(self.simulate_processes(person, session_id))

    def run(self):
        for session_id, start_time, cnt in self.sessions:
            seconds = start_time.hour * 3600 + start_time.minute * 60 + start_time.second  # начало сеанса
            # время приходов клиентов
            arrive_interval = np.sort(np.clip(np.random.normal(loc=seconds, scale=T_before_start / 3, size=cnt),
                                              seconds - T_before_start, seconds + T_before_start))
            print(len(arrive_interval))
            for i in range(cnt):
                self.env.process(self.person_arrive(arrive_interval[i], i, session_id))
                yield self.env.timeout(0)


# создание графика
def create_result(queues):
    y_values = { # значения длин очередей в промежутках 15 мин
        'tickets': [],
        'security': [],
        'rooms': []
    }
    x_names = []

    min_time = min(time.fromisoformat(t) for i in queues for t in queues[i].keys())
    # время, когда пришёл первый посетитель. Год, месяц, день - заглушки
    min_time = datetime(year=2020, month=1, day=1, hour=min_time.hour, minute=min_time.minute)

    max_time = max(time.fromisoformat(t) for i in queues for t in queues[i].keys())
    # время, когда в зал зашел последний посетитель. Год, месяц, день - заглушки
    max_time = datetime(year=2020, month=1, day=1, hour=max_time.hour, minute=max_time.minute)

    # кол-во 15 минутных промежутков
    need_len = (max_time.hour * 60 + max_time.minute - min_time.hour * 60 - min_time.minute) // 15 + 1

    # Заполнение данных на каждой стадии (кассы, безопасность, залы) в 15 минутных промежутках
    for i in queues:
        min_time1 = min_time
        while min_time1 <= max_time:
            t = f'{min_time1.hour:02}:{min_time1.minute:02}'
            if len(x_names) < need_len:
                x_names.append(t)
            y_values[i].append(queues[i].get(t, 0))
            min_time1 += timedelta(minutes=15)

    width = 0.25
    ind = np.arange(len(x_names))
    plt.bar(ind - width, y_values['tickets'], width, label='Кассы')
    plt.bar(ind, y_values['security'], width, label='Безопасность')
    plt.bar(ind + width, y_values['rooms'], width, label='Залы')
    plt.xlabel('Очереди в пунктах', fontsize=8)
    plt.ylabel('Длина очереди')
    plt.xticks(ind, x_names, rotation=45, fontsize=6)
    plt.legend()
    plt.show()


env = simpy.Environment()
cinema = Cinema(env)
env.process(cinema.run())
env.run()
create_result(cinema.queues)

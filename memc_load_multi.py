#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
# Импорты всегда помещаются в начале файла, сразу после комментариев к модулю
# и строк документации, и перед объявлением констант.
#
# Импорты должны быть отсортированы по алфавиту.
#
# Импорты должны быть сгруппированы в следующем порядке:
#
# - импорты из стандартной библиотеки
# - импорты сторонних библиотек
# - импорты модулей текущего проекта
# Вставляйте пустую строку между каждой группой импортов.
import gzip
import sys
import glob
import logging
import collections
import time
from optparse import OptionParser
# brew install protobuf
# protoc  --python_out=. ./appsinstalled.proto
# pip install protobuf
import appsinstalled_pb2
# pip install python-memcached
import memcache
import threading
from queue import Queue

CONNECTION_RETRY_TIMEOUT = 20
CONNECTION_TIMEOUT = 5
CHUNK_SIZE = 100
NORMAL_ERR_RATE = 0.01
# Длина строки согласно PEP8, не должна превышать 79 символов.
AppsInstalled = collections.namedtuple("AppsInstalled", ["dev_type", "dev_id", "lat", "lon", "apps"])


def dot_rename(path):
    head, fn = os.path.split(path)
    # atomic in most cases
    os.rename(path, os.path.join(head, "." + fn))


# Длина строки согласно PEP8, не должна превышать 79 символов.
# Рекомендую добавить аннотацию типов для аргументов функции.
# Код станет читабельнее.
def insert_appsinstalled(memc_addr, appsinstalled, dry_run=False, name='', line_num=0):
    # Названия должны однозначно говорить о том, зачем нужна сущность:
    # переменная, функция или что-то ещё.
    # https://dvmn.org/encyclopedia/clean_code/good_names/
    ua = appsinstalled_pb2.UserApps()
    ua.lat = appsinstalled.lat
    ua.lon = appsinstalled.lon
    # Для форматирование строк рекомендую использовать f-строки.
    key = "%s:%s" % (appsinstalled.dev_type, appsinstalled.dev_id)
    ua.apps.extend(appsinstalled.apps)
    packed = ua.SerializeToString()

    # @TODO persistent connection
    # @TODO retry and timeouts!

    if dry_run:
       # Для форматирование строк рекомендую использовать f-строки.
       logging.debug("%s - %s -> %s" % (memc_addr, key, str(ua).replace("\n", " ")))
       # Предлагаю здесь сделать `return False`, чтобы избавиться от `else`
       # и от вложенности.
    else:
        result = False
        # Длина строки согласно PEP8, не должна превышать 79 символов.
        memc = memcache.Client([memc_addr], dead_retry=CONNECTION_RETRY_TIMEOUT, socket_timeout=CONNECTION_TIMEOUT)

        if memc.servers[0]._get_socket():  # connection established
            result = memc.set(key, packed)
            if result == 0:
                # Для форматирование строк рекомендую использовать f-строки.
                logging.exception("Cannot write to memc %s: %s" % (memc_addr, e))
                result = False
        else:
            # Для форматирование строк рекомендую использовать f-строки.
            logging.exception("Error connecting to %s" % (memc_addr))
        # Закомментированный код лучше удалять из проекта.
        #print('{}: {} {} {}'.format(line_num, name, key, result))
        return result

    return False

# Рекомендую добавить аннотацию типов для аргументов функции.
# Код станет читабельнее.
# Название функций должно быть в `snake_case`, необходимо разделять каждое слово
# с помощью `_` `parse_apps_installed`
def parse_appsinstalled(line):
    line_parts = line.decode("utf-8").strip().split("\t")
    if len(line_parts) < 5:
        return
    dev_type, dev_id, lat, lon, raw_apps = line_parts
    if not dev_type or not dev_id:
        return
    try:
        apps = [int(a.strip()) for a in raw_apps.split(",")]
    except ValueError:
        apps = [int(a.strip()) for a in raw_apps.split(",") if a.isidigit()]
        # Для форматирование строк рекомендую использовать f-строки.
        logging.info("Not all user apps are digits: `%s`" % line)
    try:
        lat, lon = float(lat), float(lon)
    except ValueError:
        # Для форматирование строк рекомендую использовать f-строки.
        logging.info("Invalid geo coords: `%s`" % line)
    return AppsInstalled(dev_type, dev_id, lat, lon, apps)


# Рекомендую добавить аннотацию типов для аргументов функции.
# Код станет читабельнее.
def main(options):
    device_memc = {
        "idfa": options.idfa,
        "gaid": options.gaid,
        "adid": options.adid,
        "dvid": options.dvid,
    }

    # Init multiple workers
    queue = Queue(maxsize=3000)
    producer = Producer(queue)
    workers = []
    # Неиспользуемые переменные следует называть _ , так как это требует PEP8
    # По умолчанию range начинается с 0, поэтому не обязательно передавать 0.
    # как начало отсчета.
    for w in range(0, opts.workers):
        # Для форматирование строк рекомендую использовать f-строки.
        logging.info("Starting worker %s" % w)
        worker = Worker(queue, opts, device_memc)
        worker.start()
        workers.append(worker)
    producer.start()

    for fn in glob.iglob(options.pattern):
        # Не рекомендую такое присвоение для переменных
        # processed, errors = 0, 0 выглядит лучше
        # Или же для каждой переменной использовать новую строчку.
        processed = errors = 0
        # Для форматирование строк рекомендую использовать f-строки.
        logging.info('Processing %s' % fn)

        producer.init()
        producer.set_filename(fn)

        # Checking if parsing complete
        checking = True
        counter = 0
        last_state = 0
        while checking:
            # Для форматирование строк рекомендую использовать f-строки.
            # Длина строки согласно PEP8, не должна превышать 79 символов.
            logging.info("Unfinished tasks: {} Producer finished: {}".format(queue.unfinished_tasks, producer.task_complete))
            if producer.task_complete:
                time.sleep(3)
                if queue.unfinished_tasks > 0:
                    if queue.unfinished_tasks == last_state:
                        counter += 1
                    else:
                        logging.info("Unfinished tasks changed, counter null")
                        counter = 0

                if counter == 10 or queue.unfinished_tasks == 0:
                    logging.info("Producer and workers finished tasks")
                    for worker in workers:
                        processed += worker.processed
                        errors += worker.errors
                    logging.info("Exit ... ")
                    checking = False
            else:
                time.sleep(20)

        # Checking parsing results
        if not processed:
            dot_rename(fn)
            continue

        err_rate = float(errors) / processed
        if err_rate < NORMAL_ERR_RATE:
            # Для форматирование строк рекомендую использовать f-строки.
            logging.info("Acceptable error rate ({:.5f}). Successfull load".format(err_rate))
        else:
            # Для форматирование строк рекомендую использовать f-строки.
            logging.error("High error rate ({:.5f} > {:.5f}). Failed load".format(err_rate, NORMAL_ERR_RATE))
        dot_rename(fn)

    # Stop everything
    logging.info("Closing all")
    producer.disable()
    producer.join()
    logging.info("Producer stopped")
    for worker in workers:
        worker.disable()
        worker.join()
        # Для форматирование строк рекомендую использовать f-строки.
        logging.info("Worker {} stopped".format(worker))
    queue.join()
    logging.info("Queue stopped")

    # Обычно функция `main` ничего не возвращает. Так как результат
    # этой функци мы нигде не используем, то этот `return` можно убрать.
    return True

# Тесты лучше хранить в отдельном модуле.
def prototest():
    sample = "idfa\t1rfw452y52g2gq4g\t55.55\t42.42\t1423,43,567,3,7,23\ngaid\t7rfw452y52g2gq4g\t55.55\t42.42\t7423,424"
    for line in sample.splitlines():
        dev_type, dev_id, lat, lon, raw_apps = line.strip().split("\t")
        apps = [int(a) for a in raw_apps.split(",") if a.isdigit()]
        lat, lon = float(lat), float(lon)
        ua = appsinstalled_pb2.UserApps()
        ua.lat = lat
        ua.lon = lon
        ua.apps.extend(apps)
        packed = ua.SerializeToString()
        unpacked = appsinstalled_pb2.UserApps()
        unpacked.ParseFromString(packed)
        assert ua == unpacked


class Producer(threading.Thread):
    """
    Produces string chunks from file
    """

    # Рекомендую добавить аннотацию типов для аргументов функции.
    def __init__(self, queue):
        """
        Constructor.
        @param queue queue synchronization object
        """
        # Рекомендую использовать функцию `super()`
        # для вызова `__init__` у родительского класса.
        threading.Thread.__init__(self)
        self.queue = queue
        self.fn = None
        self.task_complete = False
        self.running = True

    # Рекомендую добавить аннотацию типов для аргументов функции.
    def set_filename(self, fn):
        self.fn = fn

    def init(self):
        self.running = True
        self.task_complete = False

    def disable(self):
        self.running = False

    def run(self):
        """
        Thread run method. Reads file line by line, accumulates lines into chunks
        and sends it to queue
        """
        while self.running:
            # Проверка на `None` должна быть через `is None` вместо `==`
            if not self.fn == None:
                try:
                    chunk = []
                    chunk_num = 0
                    fd = gzip.open(self.fn)
                    self.task_complete = False
                    for line_num, line in enumerate(fd):
                        chunk.append((line_num, line))
                        if len(chunk) == CHUNK_SIZE:
                            self.queue.put(chunk)
                            chunk = []
                            chunk_num += 1
                    self.queue.put(chunk)
                    logging.info("Producer added last chunk")
                    self.task_complete = True
                    self.set_filename(None)
                except:
                    # Для форматирование строк рекомендую использовать f-строки.
                    logging.exception("Error reading file: %s" % (self.fn))
            time.sleep(10) # Waiting for another file


class Worker(threading.Thread):

    # Рекомендую добавить аннотацию типов для аргументов функции
    def __init__(self, queue, opts, device_memc):
        """
        Constructor.
        @param queue queue synchronization object
        @param opts parsing options
        @param device_memc device map
        """
        # Рекомендую использовать функцию `super()`
        # для вызова `__init__` у родительского класса.
        threading.Thread.__init__(self)
        self.queue = queue
        self.options = opts
        self.device_memc = device_memc
        self.processed = 0
        self.errors = 0
        self.running = True

    def disable(self):
        self.running = False

    def run(self):
        """
        Thread run method. Parses chunk and loads it to Memcache.
        """
        while self.running:
            chunk = self.queue.get()
            for line_num, line in chunk:
                try:
                    line = line.strip()
                    if not line:
                        continue
                    appsinstalled = parse_appsinstalled(line)
                    if not appsinstalled:
                        self.errors += 1
                        continue
                    memc_addr = self.device_memc.get(appsinstalled.dev_type)
                    if not memc_addr:
                        self.errors += 1
                        # Для форматирование строк рекомендую использовать f-строки.
                        logging.error("Unknown device type: %s" % appsinstalled.dev_type)
                        continue
                    # Длина строки согласно PEP8, не должна превышать 79 символов.
                    ok = insert_appsinstalled(memc_addr, appsinstalled, self.options.dry, self.name, line_num)
                    if ok:
                        self.processed += 1
                    else:
                        self.errors += 1
                except:
                    # Для форматирование строк рекомендую использовать f-строки.
                    logging.error("Thread error: {} ".format(self.name))
                    self.errors += 1
            self.queue.task_done()
        # Для форматирование строк рекомендую использовать f-строки.
        logging.info("Got disable sign: {} ".format(self.name))


if __name__ == '__main__':
    op = OptionParser()
    op.add_option("--workers", action="store", default=1)
    op.add_option("-t", "--test", action="store_true", default=False)
    op.add_option("-l", "--log", action="store", default=None)
    op.add_option("--dry", action="store_true", default=False)
    # Длина строки согласно PEP8, не должна превышать 79 символов.
    op.add_option("--pattern", action="store", default="/data/appsinstalled/*.tsv.gz")
    op.add_option("--idfa", action="store", default="35.226.182.234:11211")
    op.add_option("--gaid", action="store", default="35.232.4.163:11211")
    op.add_option("--adid", action="store", default="35.226.182.234:11211")
    op.add_option("--dvid", action="store", default="35.232.4.163:11211")
    (opts, args) = op.parse_args()
    # Длина строки согласно PEP8, не должна превышать 79 символов.
    logging.basicConfig(filename=opts.log, level=logging.INFO if not opts.dry else logging.DEBUG,
                        format='[%(asctime)s] %(levelname).1s %(message)s', datefmt='%Y.%m.%d %H:%M:%S')
    if opts.test:
        prototest()
        sys.exit(0)

    # Для форматирование строк рекомендую использовать f-строки.
    logging.info("Starting Memc loader with options: %s" % opts)
    start_time = time.time()
    try:
        opts.workers = int(opts.workers)
        main(opts)
    except Exception as e:
        # Для форматирование строк рекомендую использовать f-строки.
        logging.exception("Unexpected error: %s" % e)
        sys.exit(1)
    finally:
        elapsed_time = time.time() - start_time
        # Для форматирование строк рекомендую использовать f-строки.
        logging.info("Time elapsed: %s sec" % elapsed_time)
        sys.exit(0)  # По PEP8 необходимо добавлять пустую строку в конце модуля.
# -*- coding: utf-8 -*-
import sys
import os
import time
import atexit
import signal
import syslog
import abc
import traceback
def check_pid(pid):
    """ Check For the existence of a unix pid. """
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True
def syslg(msg: str, lvl: int = 6):
    """
    syslog.LOG_ERR = 3, syslog.LOG_WARNING = 4, syslog.LOG_INFO = 6
    """
    syslog.syslog(lvl, msg)
class BaseDaemon(object):
    def __init__(self, pidfile: str, log_name: str, stdin='/dev/null', stdout='/dev/null', stderr='/dev/null'):
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.pidfile = pidfile
        self.log_name = log_name
        syslog.openlog(self.log_name)
    def daemonize(self):
        """
        производит UNIX double-form магию,
        Stevens "Advanced Programming in the UNIX Environment"
        """
        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)  # exit first parent
        except OSError as e:
            msg = f"(UNIX)fork #1 был неудачным: {e.errno} ({e.strerror})\n"
            syslg(msg, 3)
            sys.exit(msg)
        # decouple from parent environment
        os.chdir("/")
        os.setsid()
        os.umask(0)
        try:
            pid = os.fork()  # do second fork
            if pid > 0:
                sys.exit(0)  # exit from second parent
        except OSError as e:
            msg = f"(UNIX)fork #2 был неудачным: {e.errno} ({e.strerror})\n"
            syslg(msg, 3)
            sys.exit(msg)
        syslg(f'Pid файл {self.pidfile} записан')  # redirect standard file descriptors and write pidfile
        atexit.register(self.delpid)
        signal.signal(signal.SIGTERM, self.delpid)
        signal.signal(signal.SIGINT, self.delpid)
        pid = str(os.getpid())
        syslg(f'Pid процесса: {pid}')
        with open(self.pidfile, 'w+') as pid_file:
            pid_file.write(f"{pid}\n")
    def delpid(self, *args, **kwargs):  # для atexit.register следует оставлять *args, **kwargs
        if os.path.exists(self.pidfile):
            os.remove(self.pidfile)
            syslog.syslog(syslog.LOG_INFO, 'Демон остановлен. Pid файл удален...')
    def start(self):
        syslg('*' * 100)
        syslg(f'Инициализация демонизации процесса {self.log_name}')
        try:  # Check for a pidfile to see if the daemon already runs
            with open(self.pidfile, 'r') as pid_file:
                pid = int(pid_file.read().strip())
        except IOError:
            pid = None
        if pid is not None and check_pid(pid):
            msg = f'pid файл ({self.pidfile}) уже существует и процесс демона уже запущен\n'
            syslg(msg)
            sys.stderr.write(msg)
            sys.exit(1)
        syslg('Запускаем процесс демонизации.')  # Start the daemon
        self.daemonize()
        try:
            self.run()
        except BaseException as err:
            syslg('Произошла ошибка при вызове функции run демона. Traceback:', 3)
            syslg('-' * 100, 3)
            ex_type, ex, tb = sys.exc_info()
            for obj in traceback.extract_tb(tb):
                syslg(f'Файл: {obj[0]}, строка: {obj[1]}, вызов: {obj[2]}', 3)
                syslg(f'----->>>  {obj[3]}', 3)
            syslg(f'Ошибка: {err}.', 3)
            syslg('-' * 100, 3)
    def stop(self):
        try:  # Get the pid from the pidfile
            with open(self.pidfile, 'r') as pid_file:
                pid = int(pid_file.read().strip())
        except IOError:
            pid = None
        if not pid:
            msg = f"Pid файл ({self.pidfile} не найден). Возможно демон не запущен?\n"
            syslg(msg, 3)
            sys.stderr.write(msg)
            return  # not an error in a restart
        num = 0  # Try killing the daemon process
        try:
            while 1:
                os.kill(pid, signal.SIGTERM)
                time.sleep(0.1)
                num += 1
                if num == 50:  # 5 секунд (принято для linux)
                    os.kill(pid, signal.SIGKILL)
                    syslg('процесс не завершается, выполняется SIGKILL', 4)
        except OSError:
                if os.path.exists(self.pidfile):
                    os.remove(self.pidfile)
        syslg('завершение работы')
        syslog.closelog()
    def restart(self):
        syslg('Перезапускаем процесс демонизации')
        self.stop()
        self.start()
    @abc.abstractmethod
    def run(self):

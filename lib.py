# -*- coding: utf-8 -*-

import os
import sys
import abc
import time
import signal
import syslog
import traceback

def check_pid(pid):
    """ Check For the existence of a unix pid. """
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True
    
""" syslog.LOG_ERR = 3, syslog.LOG_WARNING = 4, syslog.LOG_INFO = 6 """

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
            sys.exit(0) if pid > 0 else None  # exit first parent
        except OSError as e:
            msg = f"(UNIX)fork #1 был неудачным: {e.errno} ({e.strerror})\n"
            syslog.syslog(3, msg)
            raise SystemExit(msg)
        os.chdir("/")  # decouple from parent environment
        os.setsid()
        os.umask(0)
        try:
            pid = os.fork()  # do second fork
            if pid > 0:
                sys.exit(0)  # exit from second parent
        except OSError as e:
            msg = f"(UNIX)fork #2 был неудачным: {e.errno} ({e.strerror})\n"
            syslog.syslog(3, msg)
            sys.exit(msg)
        # redirect standard file descriptors and write pidfile
        signal.signal(signal.SIGTERM, self.delpid)
        signal.signal(signal.SIGINT, self.delpid)
        pid = str(os.getpid())
        with open(self.pidfile, 'w+') as pid_file:
            pid_file.write(f"{pid}\n")
    STRSIGNAL = lambda self, n: {9: 'SIGKILL', 15: 'SIGTERM', 2: 'SIGINT'}.get(n, n)
    
    def delpid(self, signum, frame):
        syslog.syslog(6, f'завершение, сигнал {self.STRSIGNAL(signum)}')
        if os.path.exists(self.pidfile):
            os.remove(self.pidfile)
            syslog.syslog(6, 'Pid файл удален...')
        raise SystemExit()
        
    def start(self):
        syslog.syslog(6, '*' * 100)
        syslog.syslog(6, f'Инициализация процесса {self.log_name}')
        try:  # Check for a pidfile to see if the daemon already runs
            with open(self.pidfile, 'r') as pid_file:
                pid = int(pid_file.read().strip())
        except IOError:
            pid = None
        if pid is not None and check_pid(pid):
            msg = f'pid файл ({self.pidfile}) уже существует и процесс демона запущен\n'
            syslog.syslog(6, msg)
            raise SystemExit(msg)
        self.daemonize()
        try:
            self.run()
        except SystemExit:
            syslog.syslog(6, 'завершение работы')
            syslog.closelog()
        except BaseException as err:
            syslog.syslog(3, 'Произошла ошибка при вызове функции run демона. Traceback:')
            syslog.syslog(3, '-' * 100)
            ex_type, ex, tb = sys.exc_info()
            for obj in traceback.extract_tb(tb):
                syslog.syslog(3, f'Файл: {obj[0]}, строка: {obj[1]}, вызов: {obj[2]}')
                syslog.syslog(3, f'----->>>  {obj[3]}')
                syslog.syslog(3, f'Ошибка: {err}.')
            syslog.syslog(3, '-' * 100)
            
    def stop(self):
        try:  # Get the pid from the pidfile
            with open(self.pidfile, 'r') as pid_file:
                pid = int(pid_file.read().strip())
        except IOError:
            pid = None
        if pid is None:
            msg = f"Pid файл ({self.pidfile} не найден). Возможно демон не запущен?\n"
            syslog.syslog(3, msg)
            raise SystemExit(msg)
        num = 0
        while True:
            try:
                os.kill(pid, signal.SIGTERM)
                break
            except OSError as er:
                num += 1
                syslog.syslog(3, f'ошибка при выполнении SIGTERM: {str(er)}')
                os.kill(pid, signal.SIGKILL) if num == 5 else None
            time.sleep(1)
            
    @abc.abstractmethod
    def run(self):
        """
        inherited
        """

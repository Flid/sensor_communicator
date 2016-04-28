# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from threading import Thread, Lock
import socket
import logging
import select
import json

logger = logging.getLogger(__name__)


class ClientSocket(object):
    def __init__(self, conn):
        self.conn = conn
        self.initialized = False

        # Keep track of all registration, so we can clean them on removal.
        self.registrations = set()


class SocketServer(object):
    EPOLL_REG_FLAGS = select.EPOLLIN | select.EPOLLERR | select.EPOLLHUP

    def __init__(self, port):
        self._port = port

        self.active_sockets = {}
        self.server_lock = Lock()
        self.registrations = {}
        self._epoll = select.epoll()

        self._thread = Thread(target=self._listener)
        self._thread.daemon = True
        self._thread.start()
        self._messages = []

    @staticmethod
    def _set_keepalive(sock, after_idle_sec=30, interval_sec=10, max_fails=5):
        """Set TCP keepalive on an open socket.

        It activates after `after_idle_sec` second of idleness,
        then sends a keepalive ping once every `interval_sec` seconds,
        and closes the connection after `max_fails` failed pings.
        """
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, after_idle_sec)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, interval_sec)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, max_fails)

    def send_message(self, data, fno):

        logger.info('Sending data `%s` to %s', data, fno)

        self.server_lock.acquire()

        try:
            sock = self.active_sockets.get(fno)
            if not sock:
                logger.warning('Sending data to invalid socket')
                return False

            sock.conn.sendall(data)

            if not data.endswith('\n'):
                sock.conn.sendall('\n')

            return True
        except socket.error:
            self._unregister_socket(fno)
            return False

        finally:
            self.server_lock.release()

    def send_broadcast_message(self, data, sensor_name, msg_stream=''):

        if not isinstance(data, basestring):
            data = json.dumps(data)

        self.server_lock.acquire()

        sockets = self.registrations.setdefault(
            sensor_name,
            {},
        ).setdefault(
            msg_stream,
            set(),
        )

        logger.info(
            'Sending broadcast socket message `%s:%s` `%s` to %s receivers',
            sensor_name,
            msg_stream,
            data,
            len(sockets),
        )

        to_remove = []

        try:
            for fno in sockets:
                sock = self.active_sockets.get(fno)
                if not sock:
                    to_remove.append(fno)
                    continue

                try:
                    sock.conn.sendall(data)
                    if not data.endswith('\n'):
                        sock.conn.sendall('\n')

                except socket.error:
                    self._unregister_socket(fno)
                    to_remove.append(fno)

            # Cleanup
            for fno in to_remove:
                sockets.remove(fno)

        finally:
            self.server_lock.release()

    def get_messages(self):
        """
        Get all messages and remove them from the local storage.
        """
        output = self._messages
        self._messages = []
        return output

    def _unregister_socket(self, fno):
        logger.info('Unregistering socket %s', fno)
        self._epoll.unregister(fno)
        self.active_sockets[fno].conn.close()

        for sensor_name, msg_stream in self.active_sockets[fno].registrations:
            self.registrations[sensor_name][msg_stream].remove(fno)

        del self.active_sockets[fno]

    def _process_message(self, fno, raw_data):
        # NOTE: all exception will be caught and logged outside
        logger.info('Processing message %s from %s', raw_data, fno)

        data = json.loads(raw_data)
        sensor_name = data['sensor']

        if data['type'] == 'register':
            msg_stream = data.get('msg_stream', '')

            logger.info(
                'Registering socket for node %s, stream `%s`',
                sensor_name,
                msg_stream,
            )

            self.registrations.setdefault(
                sensor_name,
                {},
            ).setdefault(
                msg_stream,
                set(),
            ).add(fno)
            self.active_sockets[fno].registrations.add((sensor_name, msg_stream))
        else:
            self._messages.append((sensor_name, data, fno))

    def _process_event(self, server_socket, fno, event):
        if fno == server_socket.fileno():
            connection, address = server_socket.accept()
            logger.info('New connection from %s', address)

            connection.setblocking(0)
            self._set_keepalive(connection)

            self._epoll.register(connection.fileno(), self.EPOLL_REG_FLAGS)

            with self.server_lock:
                self.active_sockets[connection.fileno()] = ClientSocket(connection)

        elif event & select.EPOLLIN:
            data = self.active_sockets[fno].conn.recv(4096)
            if not data:
                with self.server_lock:
                    self._unregister_socket(fno)
                return

            messages = data.split('\n')

            for message in messages:
                if not message:
                    continue

                try:
                    self._process_message(fno, message)
                except Exception as ex:
                    logger.warning(
                        'Error while processing socket message:',
                        exc_info=ex,
                    )

        elif event & select.EPOLLHUP:
            with self.server_lock:
                self._unregister_socket(fno)
        else:
            logger.error('Unprocessed epoll event: %s', event)

    def _listener(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('0.0.0.0', self._port))
        server_socket.listen(10)
        server_socket.setblocking(0)

        self._epoll.register(server_socket.fileno(), self.EPOLL_REG_FLAGS)

        while True:
            events = self._epoll.poll(1)
            for fileno, event in events:
                try:
                    self._process_event(server_socket, fileno, event)
                except Exception as ex:
                    logger.error('Error while processing socket event:', exc_info=ex)


server = SocketServer(10101)


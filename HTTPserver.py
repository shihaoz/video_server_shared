import util.config as config  # must import first to use logging correctly
import util.measure as measure
import util.common as common
import util.request_filter as request_filter
import select
import socket
import sys
import re
import logging
import time

print("log file: {}, log level: {}".format(config.log_file, config.log_level))
logging.info(
	"log file: {}, log level: {}"
	.format(config.log_file, config.log_level)
)
# listening address
addr_server = ('10.0.0.1', 5000)
# apache server info
target_addr = ('10.0.0.1', 80)
fd_to_socket = {}  # fd : socket object
fd_to_tp = {}  # fd: (T_cur, last time)
server_to_client = {}  # server_fd : client_fd
client_to_server = {}  # client_fd : server_fd
bitrate = []  # list of sorted available bitrate


def readSocket(sock):
	""" read from a socket object, return entire request/response """
	buffer = b""
	print('reading from socket {}'.format(sock.fileno()))
	logging.info('reading from socket {}'.format(sock.fileno()))
	chunk = sock.recv(common.BUFFER_SIZE)
	while chunk:
		buffer += chunk
		logging.info(chunk)
		if chunk.find(b"\r\n\r\n") != -1:
			break
		chunk = sock.recv(common.BUFFER_SIZE)
	match = re.search(b"Content-Length: ([0-9]+)", buffer)
	if match:
	    content_length = int(match.group(1).decode('utf-8'))
	    print("content length: {}".format(content_length))
	    logging.info("content length: {}".format(content_length))
	    remain_length = content_length - (
		    len(buffer) - buffer.find(b"\r\n\r\n") - len(b'\r\n\r\n')
	    )
	    logging.info("remain length: {}".format(remain_length))
	    while (remain_length > 0 and len(chunk) > 0):
	            logging.info('chunk-loop, remain length {}'.format(remain_length))
	            chunk = sock.recv(common.BUFFER_SIZE)
	            remain_length -= len(chunk)
	            buffer += chunk
	""" return the buffer data """
	logging.info("returning buffer")
	return buffer


def forwardRequest(fd, sock, request):
	if fd in server_to_client:
		""" response from server """
		fd_client = server_to_client[fd]  # get client fd
		sk_client = fd_to_socket[fd_client]  # get client socket
		# time the server response on client
		measure.time2nd(fd_to_tp, fd_client, len(request))
		# send response to client
		print("sending to client sock {}".format(fd_client))
		try:
			logging.info("sending to client sock {}".format(fd_client))
			hold = time.perf_counter()
			sk_client.sendall(request)
			realtime = time.perf_counter() - hold
			logging.info(
				"REAL TP: {}bps"
				.format(len(request)/(1000*realtime))
			)

		except Exception as ex:
			print('error:{}'.format(ex), file=sys.stderr)

	else:
		""" request from client """
		request = request_filter.modifyF4M(request)
		request = request_filter.modifyBitrate(request, fd, bitrate, fd_to_tp)
		measure.time1st(fd_to_tp, fd)  # time the client request
		fd_relay = client_to_server[fd]
		sk_relay = fd_to_socket[fd_relay]
		try:
			"""relaying request"""
			logging.info(
				"forwarding request from client {} to server {}"
				.format(fd, fd_relay)
			)
			sk_relay.sendall(request)  # send request to server
		except Exception as ex:
			print("connect error:{}".format(ex), file=sys.stderr)


def cleanup_socket(sock):
	""" @param(socket object) cleanup a socket after use """
	fd = sock.fileno()
	poller.unregister(sock)  # unregister from poller
	sock.close()
	del fd_to_socket[fd]  # delete from map fd_to_socket
	if fd in fd_to_tp:  # delete from map fd_to_throughput
		del fd_to_tp[fd]
	if fd in server_to_client:
		del server_to_client[fd]
	if fd in client_to_server:
		del client_to_server[fd]


# fetching f4m file from server
request_filter.readF4M(bitrate, target_addr[0], target_addr[1])

# setup socket
sk_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sk_server.bind(addr_server)
fd_to_socket[sk_server.fileno()] = sk_server  # map the fd to socket object

# listen
print('listening on {}:{}'.format(addr_server[0], addr_server[1]))
sk_server.listen(10)

# polling
poller = select.poll()
poller.register(sk_server, select.POLLIN)  # register server with POLLIN flag

while True:
	print('event loop')
	events = poller.poll(common.TIMEOUT)  # timeout every second
	print(events)
	if len(events) == 0:
		print('timeout')
		continue
	for (fd, flag) in events:
		sock = fd_to_socket[fd]  # get the socket object
		if flag & (select.POLLIN):

			if sock is sk_server:
				""" new connection in listening socket """
				conn, addr_client = sock.accept()
				print('new connection from {}'.format(addr_client))
				logging.info("new connection from {}".format(addr_client))
				fd_to_socket[conn.fileno()] = conn  # add to map
				poller.register(conn, select.POLLIN)  # add to polling
				# creating relay socket to server
				sk_relay = socket.socket(socket.AF_INET,
				                         socket.SOCK_STREAM)
				sk_relay.connect(target_addr)  # connect to server
				# store in client_to_server
				client_to_server[conn.fileno()] = sk_relay.fileno()
				# store in fd_to_socket
				fd_to_socket[sk_relay.fileno()] = sk_relay
				# store in server_to_client
				server_to_client[sk_relay.fileno()] = conn.fileno()
				# add to polling
				poller.register(sk_relay, select.POLLIN)
			else:
				"""new request in connected socket"""
				request = readSocket(sock)
				if request:
					""" forward the request """
					forwardRequest(fd, sock, request)

				else:  # recv == 0
					""" client close """
					print("client closing from {}".format(sock.getpeername()))
					if fd in client_to_server:
						# clean up server first
						server_fd = client_to_server[fd]
						cleanup_socket(fd_to_socket[server_fd])
					cleanup_socket(sock)


		elif flag & (select.POLLHUP):
			print('client hung up from {}'.format(sock.getpeername()),
			      file=sys.stderr)
			logging.debug('client hung up from {}'.format(sock.getpeername()))
			cleanup_socket(sock)

		elif flag & (select.POLLERR):
			print('client error up from {}'.format(sock.getpeername()),
			      file=sys.stderr)
			logging.debug('client hung up from {}'.format(sock.getpeername()))
			cleanup_socket(sock)

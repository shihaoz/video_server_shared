import time
import select
import socket
import sys
import re
import logging
TIMEOUT = 1000
BUFFER_SIZE = 200
ALPHA = 0.5
logging.basicConfig(filename="proxy.log", level=logging.DEBUG)

fd_to_socket = {}  # fd : socket object
fd_to_tp = {}  # fd: (T_cur, last time)
server_to_client = {}  # server_fd : client_fd
client_to_server = {}  # client_fd : server_fd
bitrate = []  # list of available bitrate


def readF4M(request):
	""" read request from server """
	logging.info("reading f4M")
	if request.find(b"text/xml") != -1:
		""" this is a f4m """
		logging.info("this is a f4m")
		logging.info(request.decode('utf-8'))
		if len(bitrate) == 0:
			""" 1st time see f4m, read the available bitrate """
			rates = re.findall(b'bitrate="([0-9]+)"', request)
			logging.info("bitrates available: {}".format(rates))
			for rate in rates:
				bitrate.append(int(rate.decode('utf-8')))
		request = request.replace(b'big_buck_bunny.f4m',
		                          b'big_buck_bunny_nolist.f4m')
	return request


def readSocket(sock):
	""" read from a socket object, return entire request/response """
	buffer = b""
	print('reading from socket {}'.format(sock.fileno()))
	logging.info('reading from socket {}'.format(sock.fileno()))
	chunk = sock.recv(BUFFER_SIZE)
	while chunk:
		buffer += chunk
		logging.info(chunk)
		if chunk.find(b"\r\n\r\n") != -1:
			break
		chunk = sock.recv(BUFFER_SIZE)
	match = re.search(b"Content-Length: ([0-9]+)", buffer)
	if match:
	    content_length = int(match.group(1).decode('utf-8'))
	    print("content length: {}".format(content_length))
	    logging.info("content length: {}".format(content_length))
	    remain_length = content_length - (len(buffer) - buffer.find(b"\r\n\r\n") - len(b'\r\n\r\n'))
	    logging.info("remain length: {}".format(remain_length))
	    while (remain_length > 0 and len(chunk) > 0):
	            logging.info('chunk-loop, remain length {}'.format(remain_length))
	            chunk = sock.recv(BUFFER_SIZE)
	            remain_length -= len(chunk)
	            buffer += chunk
	""" return the buffer data """
	logging.info("returning buffer")
	return buffer


def modifyBitrate(request, fd):
	logging.info("modifying birate")
	if request.find(b'-Frag') != -1:
		''' this is a chunk request'''
		logging.info("this is a chunk request")
		if len(bitrate) == 0:
			logging.debug("ERROR: bitrate is not ready yet;")
			return request
		br_client = fd_to_tp[fd][0] * 2 / 3  # maximum bitrate for this client
		br_chosen = 0
		for br in bitrate:
			if br <= br_client and br > br_chosen:
				br_chosen = br
		old_chunk = re.search(b'/[0-9]+Seg', request).group()
		new_chunk = "/{}Seg".format(br_chosen).encode('utf-8')
		logging.info("from {} to {}".format(old_chunk, new_chunk))
		request = request.replace(old_chunk, new_chunk)
	return request


def time1st(fd_to_tp, fd):
	"""@param(dictionary, socket fd)  ==> @return(None)"""
	# call when received client request
	if fd in fd_to_tp:
		fd_to_tp[fd] = (fd_to_tp[fd][0], time.perf_counter())
	else:
		fd_to_tp[fd] = (0, time.perf_counter())


def time2nd(fd_to_tp, fd, size):
	"""call when recevied response from server"""
	T_cur, last_time = fd_to_tp[fd]
	now_time = time.perf_counter()
	T_new = size/(now_time - last_time)
	logging.info("chunk size: {}, time1: {}, time2: {}".format(size, last_time, now_time))
	T_cur = ALPHA*(T_new) + (1 - ALPHA) * T_cur
	logging.info("sock: {}| throughput: {}".format(fd, T_cur))


def forwardRequest(fd, sock, request):
	if fd in server_to_client:
		""" response from server """
		fd_client = server_to_client[fd]  # get client fd
		sk_client = fd_to_socket[fd_client]  # get client socket
		# time the server response on client
		time2nd(fd_to_tp, fd_client, len(request))
		# send response to client
		print("sending to client sock {}".format(fd_client))
		# check f4m
		request = readF4M(request)
		try:
			logging.info("sending to client sock {}".format(fd_client))
			sk_client.sendall(request)

		except Exception as ex:
			print('error:{}'.format(ex), file=sys.stderr)

	else:
		""" request from client """
		request = modifyBitrate(request, fd)
		time1st(fd_to_tp, fd)  # time the client request
		fd_relay = client_to_server[fd]
		sk_relay = fd_to_socket[fd_relay]
		try:
			"""relaying request"""
			logging.info("forwarding request from client {} to server {}".format(fd, fd_relay))
			sk_relay.sendall(request)  # send request to server
		except Exception as ex:
			print("connect error:{}".format(ex), file=sys.stderr)


# setup socket
sk_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
addr_server = ('10.0.0.1', 5000)
sk_server.bind(addr_server)
fd_to_socket = {sk_server.fileno(): sk_server}  # map the fd to socket object

# listen
print('listening on {}:{}'.format(addr_server[0], addr_server[1]))
sk_server.listen(10)

# polling
poller = select.poll()
poller.register(sk_server, select.POLLIN)  # register server with POLLIN flag

# apache server info 
target_addr = ('10.0.0.1', 80)


while True:
	print('event loop')
	events = poller.poll(TIMEOUT)  # timeout every second
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
					poller.unregister(sock)  # unregister from poll
					del fd_to_socket  # remove from map
					sock.close()

		elif flag & (select.POLLHUP):
			print('client hung up from {}'.format(sock.getpeername()),
			      file=sys.stderr)
			logging.debug('client hung up from {}'.format(sock.getpeername()))
			poller.unregister(sock)  # unregister from poll
			del fd_to_socket[fd]  # remove from map
			if fd in server_to_client:
				del server_to_client[fd]
			sock.close()

		elif flag & (select.POLLERR):
			print('client error up from {}'.format(sock.getpeername()),
			      file=sys.stderr)
			logging.debug('client hung up from {}'.format(sock.getpeername()))
			poller.unregister(sock)  # unregister from poll
			del fd_to_socket[fd]  # remove from map
			if fd in server_to_client:
				del server_to_client[fd]
			sock.close()

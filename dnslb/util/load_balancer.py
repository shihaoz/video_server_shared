import parser as pr
import config
from common import log_print, log_err, log_matrix
import argparse, socket, sys, logging


class DNSServer:
	def __init__(self):
		""" declare variables """
		self.sock_dns = None  # dns server socket
		self.log_file = ""  # name of the log file
		self.port = -1  # port number
		self.geo_based = False  # mode, true = geo based, false = round-robin
		self.servers = None  # rr = [ip], geo = [i][j] cost from host i to j
		self.rr_counter = 0  # round-robin counter

	def read_args(self):
		ap = argparse.ArgumentParser(description='run DNS server')
		ap.add_argument('log', type=str)
		ap.add_argument('port', type=int)
		ap.add_argument('geo_based', type=bool)
		ap.add_argument('servers', type=str)
		args = ap.parse_args()
		self.log_file = args.log
		self.port = args.port
		self.geo_based = args.geo_based
		self.servers = (
			self.parse_geo_based(args.servers) if self.geo_based
			else self.parse_round_robin(args.servers)
		)

	def parse_round_robin(self, file_name):
		""" parse the round robin input  """
		ip_list = []
		try:
			with open(file_name, 'r') as f:
				ip_list = f.readlines()
		except Exception as ex:
			log_err("server files not found {}".format(ex))
		return ip_list

	def getip_round_robin(self):
		"""return the rr ip"""
		ip_rr = self.servers[self.rr_counter]
		self.rr_counter = (self.rr_counter + 1) % len(self.servers)
		log_print("round-robin ip: {}".format(ip_rr))
		return ip_rr

	def parse_geo_based(self, file_name):
		""" parse the geo based input """
		lines = []
		try:
			with open(file_name, 'r') as f:
				lines = f.readlines()
		except Exception as ex:
			log_err("parse geo cannot open file {}, exception:{}"
			        .format(file_name, ex))
			return None
		idx = num_nodes = num_links = 0
		client_ip = {}
		server_ip = {}
		costs = []
		# read num nodes
		num_nodes = int(lines[idx].split(' ')[1])
		idx += 1
		# read nodes info
		for i in range(num_nodes):
			costs.append([1000]*num_nodes)  # build costs
			(id, node_type, ip) = lines[idx].split(' ')
			id = int(id)
			if node_type == "CLIENT":
				client_ip[id] = ip
			elif node_type == "SERVER":
				server_ip[id] = ip
			idx += 1
		print("client ip:\n{}\nserver ip:\n{}".format(client_ip, server_ip))
		# read num link
		num_links = int(lines[idx].split(' ')[1])
		idx += 1

		for i in range(num_links):
			(node1, node2, cost) = [int(n) for n in lines[idx].split(' ')]
			costs[node1][node2] = cost
			costs[node2][node1] = cost
			idx += 1
		log_matrix(costs)

		# run floyd-warshall shortest path
		for i in range(num_nodes):
			for x in range(num_nodes):
				for y in range(num_nodes):
					if (
					    x != y and
					    costs[x][y] > (costs[x][i] + costs[i][y])
					):
						costs[x][y] = costs[x][i] + costs[i][y]
						costs[y][x] = costs[x][i] + costs[i][y]

		log_matrix(costs)

		result_ip = {}  # [client ip] -> closest server ip

		for cid in client_ip:  # for each client ip
			cip = client_ip[cid]
			mincost = 1000
			for i in range(num_nodes):  # get closest server ip
				if costs[cid][i] < mincost and i in server_ip:
					mincost = costs[cid][i]  # update mincost
					result_ip[cip] = server_ip[i]  # store server ip

		# print result_ip
		for cip in result_ip:
			log_print("client {} closest to server {}".format(cip, result_ip[cip]))
		return result_ip

	def start(self):
		# read args, and setups
		self.read_args()

		# run server
		""" blocking; one request a time """
		sock_dns = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sock_dns.bind(config.server_addr)
		log_print("server listening on {}:{}".format(*config.server_addr))
		sock_dns.listen(10)
		while True:
			sock_client, client_addr = sock_dns.accept()
			log_print('connection from {} at socket {}'
			          .format(client_addr, sock_client))
			req_header = pr.DNSHeader()
			req_question = pr.DNSQuestion()
			try:
				request = sock_client.recv(4096)
				log_print("request:{}".format(request))
				# parsing
				idx = 0
				idx = req_header.getHeader(request, idx)
				idx = req_question.getQuestion(request, idx)
			except Exception as ex:
				log_err("socket exception:{}".format(ex))
				sock_client.close()
			# processing request
			res_ip = None
			if self.geo_based:
				res_ip = self.servers[client_addr[0]]
			else:
				res_ip = self.getip_round_robin()

			res_header = pr.DNSHeader()
			res_question = pr.DNSQuestion()
			res_record = pr.DNSRecord()
			res_flags = 33792  # pre-set
			res_header = res_header.buildHeader(
				req_header.ID, res_flags, 1, 1, 0, 0
			)
			res_question = res_question.buildQuestion(
				req_question.QNAME, req_question.QTYPE, req_question.QTYPE
			)
			res_record = res_record.buildRecord(req_question.QNAME, res_ip)
			response = res_header + res_question + res_record
			sock_client.sendall(response)
			sock_client.close()

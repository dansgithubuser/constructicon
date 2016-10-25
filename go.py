#!/usr/bin/python

import common
import os, webbrowser

megatron_master_path=os.path.join('megatron', 'master')
megatron_slave_path=os.path.join('megatron', 'slave')
devastator_master_path=os.path.join('devastator', 'master')
devastator_slave_path=os.path.join('devastator', 'slave')

class Cybertron:
	def __init__(self): self.contents=None

	def __getitem__(self, key):
		if not self.contents:
			with open('cybertron.py') as file: self.contents=eval(file.read())
		return self.contents[key]

cybertron=Cybertron()

def invoke(invocation, async=False):
	print('invoking async: '+invocation)
	print('in: '+os.getcwd())
	import subprocess
	return (subprocess.Popen if async else subprocess.check_call)(invocation, shell=True)

def m1(args):
	invoke('buildbot create-master {}'.format(megatron_master_path))
	invoke('buildslave create-slave {} localhost:{} megatron-slave {}'.format(
		megatron_slave_path,
		cybertron['megatron_slave_port'],
		common.password
	))
	invoke('buildbot restart {}'.format(megatron_master_path))
	invoke('buildslave restart {}'.format(megatron_slave_path))

def m0(args):
	invoke('buildbot stop {}'.format(megatron_master_path))
	invoke('buildslave stop {}'.format(megatron_slave_path))
	invoke('buildbot stop {}'.format(devastator_master_path))

def mb(args):
	webbrowser.open('http://localhost:{}'.format(cybertron['megatron_master_port']))

def mc(args):
	invoke('buildbot checkconfig {}'.format(megatron_master_path))

def d1(args):
	invoke('buildslave create-slave {} localhost:{} {} {}'.format(
		devastator_slave_path,
		cybertron['devastator_slave_port'],
		args.devastator_slave_name,
		common.password
	))
	invoke('buildslave restart {}'.format(devastator_slave_path))

def d0(args):
	invoke('buildslave stop {}'.format(devastator_slave_path))

def dr(args):
	invocation=['buildbot']
	import socket
	s=socket.socket()
	r=s.connect_ex(('localhost', cybertron['devastator_master_port']))
	s.close()
	invocation.append('reconfig' if r==0 else 'restart')
	import platform
	if platform.system()=='Windows': invocation.append('--nodaemon')
	os.chdir(os.path.join('devastator', 'master'))
	invoke(' '.join(invocation))

def df(args):
	devastator_file_server_port=cybertron['devastator_file_server_port']
	os.chdir(devastator_master_path)
	import SimpleHTTPServer, SocketServer
	SocketServer.TCPServer(
		('', devastator_file_server_port),
		SimpleHTTPServer.SimpleHTTPRequestHandler
	).serve_forever()

def db(args):
	webbrowser.open('http://localhost:{}'.format(cybertron['devastator_master_port']))

def example(args):
	global cybertron
	if os.path.exists('cybertron.py'): print('cybertron.py already exists, using it.')
	else:
		print('Creating example cybertron.py.')
		cybertron={
			'slaves': {
				'slave1': {'platform': 'linux'},
			},
			'megatron_master_port': 9120,
			'megatron_slave_port': 9121,
			'devastator_master_port': 9122,
			'devastator_slave_port': 9123,
			'devastator_file_server_port': 9124,
		}
		with open('cybertron.py', 'w') as file:
			import pprint
			file.write(pprint.pformat(cybertron))
	print("When you hit enter, I'll start a megatron and open a browser to it.")
	print("Wait for the megatron master to start.")
	print("When it has, request a build with repo URL set to https://github.com/dansgithubuser/constructicon")
	print("This will construct a constructicon for this repo.")
	print("When you're done that, hit enter again.")
	try: input=raw_input
	except: pass
	input()
	m=invoke('python go.py m1', async=True)
	webbrowser.open('http://localhost:{}/builders/megatron-builder'.format(cybertron['megatron_master_port']))
	input()
	print("Now, when you hit enter, I'll open a browser to the constructicon builder we just made.")
	print("I'll also start a devastator slave.")
	print("Wait for the devastator slave to connect.")
	print("Request a build from the constructicon builder, and it should print out this script's help.")
	print("When you're done that, hit enter again.")
	input()
	webbrowser.open('http://localhost:{}/builders/constructicon-help-linux'.format(cybertron['devastator_master_port']))
	d=invoke('python go.py d1 slave1', async=True)
	input()
	print("At the end of that build you just requested, a build result was uploaded from the devastator slave to the devastator master.")
	print("To allow users to access this file, I'll start a devastator file server.")
	print("When you're done checking that out, hit enter again to clean up and quit.")
	input()
	f=invoke('python go.py df', async=True)
	input()
	m.kill()
	d.kill()
	f.kill()
	invoke('python go.py m0')
	invoke('python go.py d0')

import argparse
parser=argparse.ArgumentParser()
subparsers=parser.add_subparsers()
subparsers.add_parser('m1', help='megatron start').set_defaults(func=m1)
subparsers.add_parser('m0', help='megatron stop' ).set_defaults(func=m0)
subparsers.add_parser('mb', help='megatron browser').set_defaults(func=mb)
subparsers.add_parser('mc', help='megatron check').set_defaults(func=mc)
parser_d1=subparsers.add_parser('d1', help='devastator start')
parser_d1.set_defaults(func=d1)
parser_d1.add_argument('devastator_slave_name')
subparsers.add_parser('d0', help='devastator stop').set_defaults(func=d0)
subparsers.add_parser('dr', help='devastator restart/reconfig -- usually called by megatron').set_defaults(func=dr)
subparsers.add_parser('df', help='devastator file server').set_defaults(func=df)
subparsers.add_parser('db', help='devastator browser').set_defaults(func=db)
subparsers.add_parser('example', help='run example').set_defaults(func=example)
args=parser.parse_args()
args.func(args)

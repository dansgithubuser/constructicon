#!/usr/bin/python

import common
import argparse, os, pprint, subprocess, time, webbrowser

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

def m1(args):
	subprocess.check_call('buildbot create-master -r {}'.format(megatron_master_path), shell=True)
	subprocess.check_call('buildslave create-slave -r {} localhost:{} megatron-slave {}'.format(
		megatron_slave_path,
		cybertron['megatron_slave_port'],
		common.password
	), shell=True)
	subprocess.check_call('buildbot restart {}'.format(megatron_master_path), shell=True)
	subprocess.check_call('buildslave restart {}'.format(megatron_slave_path), shell=True)

def m0(args):
	subprocess.check_call('buildbot stop {}'.format(megatron_master_path), shell=True)
	subprocess.check_call('buildslave stop {}'.format(megatron_slave_path), shell=True)
	subprocess.check_call('buildbot stop {}'.format(devastator_master_path), shell=True)

def mb(args):
	webbrowser.open('http://localhost:{}'.format(cybertron['megatron_master_port']))

def mc(args):
	subprocess.check_call('buildbot checkconfig {}'.format(megatron_master_path), shell=True)

def d1(args):
	subprocess.check_call('buildslave create-slave -r {} localhost:{} {} {}'.format(
		devastator_slave_path,
		cybertron['devastator_slave_port'],
		args.devastator_slave_name,
		common.password
	), shell=True)
	subprocess.check_call('buildslave restart {}'.format(devastator_slave_path), shell=True)

def d0(args):
	subprocess.check_call('buildslave stop {}'.format(devastator_slave_path), shell=True)

def db(args):
	webbrowser.open('http://localhost:{}'.format(cybertron['devastator_master_port']))

def example(args):
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
		}
		with open('cybertron.py', 'w') as file: file.write(pprint.pformat(cybertron))
	print("When you hit enter, I'll start a megatron and open a browser to it.")
	print("Wait for the megatron master to start.")
	print("When it has, request a build with repo URL set to https://github.com/dansgithubuser/constructicon")
	print("This will construct a constructicon for this repo.")
	print("When you're done that, hit enter again.")
	try: input=raw_input
	except: pass
	input()
	m=subprocess.Popen('python go.py m1', shell=True)
	webbrowser.open('http://localhost:9120/builders/megatron-builder')
	input()
	print("Now, when you hit enter, I'll open a browser to the constructicon builder we just made.")
	print("I'll also start a devastator slave.")
	print("Wait for the devastator slave to connect.")
	print("Request a build from the constructicon builder, and it should print out this script's help.")
	print("When you're done that, hit enter again to clean up and quit.")
	input()
	webbrowser.open('http://localhost:9122/builders/constructicon-help-linux')
	d=subprocess.Popen('python go.py d1 slave1', shell=True)
	input()
	m.kill()
	d.kill()
	subprocess.check_output('python go.py m0', shell=True)
	subprocess.check_output('python go.py d0', shell=True)

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
subparsers.add_parser('db', help='devastator browser').set_defaults(func=db)
subparsers.add_parser('example', help='run example').set_defaults(func=example)
args=parser.parse_args()
args.func(args)

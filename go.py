#!/usr/bin/python

#=====imports=====#
import common
import os, pprint, sys, time, webbrowser

if sys.version_info[0]==2:
	from cookielib import CookieJar
	from urllib2 import Request
	from urllib2 import build_opener
	from urllib2 import HTTPCookieProcessor
	from urllib import urlopen
	from urllib import urlencode
else:
	from http.cookiejar import CookieJar
	from urllib.request import Request
	from urllib.request import build_opener
	from urllib.request import HTTPCookieProcessor
	from urllib.request import urlopen
	from urllib.parse import urlencode

#=====globals=====#
import random, re, socket, string
stamp=''.join(random.choice(string.ascii_lowercase) for i in range(16))

try: input=raw_input
except: pass

folder=os.path.split(os.path.realpath(__file__))[0]
os.chdir(folder)

megatron_master_path=os.path.join('megatron', 'master')
megatron_slave_path=os.path.join('megatron', 'slave')
devastator_master_path=os.path.join('devastator', 'master')
devastator_slave_path=os.path.join('devastator', 'slave')

#=====cybertron=====#
class Cybertron:
	def __init__(self): self.contents=None

	def __getitem__(self, key):
		self._load()
		return self.contents[key]

	def items(self):
		self._load()
		return self.contents.items()

	def set(self, contents):
		print('writing cybertron.py')
		print(contents)
		with open(os.path.join(folder, 'cybertron.py'), 'w') as file: file.write(contents)
		self.contents=None
		self._load()

	def _load(self):
		if not self.contents: self.contents=common.cybertron(folder)

cybertron=Cybertron()

cybertron_example='''cybertron={
	'slaves': {
		'slave-1': {'platform': 'linux'},
	},
	'megatron_master_port': 9120,
	'megatron_slave_port': 9121,
	'devastator_master_port': 9122,
	'devastator_slave_port': 9123,
	'devastator_file_server_port': 9124,
}
'''

#=====helpers=====#
def devastator_slave_name(args):
	name=args.devastator_slave_name
	try:
		if args.devastator_slave_name in common.constructicon()['slaves']:
			name=os.path.split(os.getcwd())[1]+'-'+name
	except: pass
	return name

def timestamp():
	import datetime
	return '{:%Y-%m-%d %H:%M:%S.%f}'.format(datetime.datetime.now())

def invoke(invocation, async=False, path='.'):
	start=os.getcwd()
	os.chdir(path)
	print(timestamp())
	print('invoking{}: {}'.format(' async' if async else '', invocation))
	print('in: '+os.getcwd())
	import subprocess
	r=(subprocess.Popen if async else subprocess.check_call)(invocation, shell=True)
	os.chdir(start)
	return r

def retry(f):
	i=0
	while True:
		try: return f()
		except:
			i+=1
			time.sleep(2)
			if i>=15: raise

def check_port_closed(port):
	return socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect_ex(('localhost', port))

def assert_ports_clean():
	for i, j in cybertron.items():
		if i.endswith('_port'): assert(check_port_closed(j))

#=====forcer=====#
class Forcer:
	def __init__(self, server, port, builder=None, user=None, password=None, skip_get_parameters=False):
		self.master='http://{}:{}'.format(server, port)
		self.builder=builder
		if user:
			self.url_opener=build_opener(HTTPCookieProcessor(CookieJar()))
			r=str(self._request('{}/login'.format(self.master), {'username': user, 'passwd': password}).read())
			if 'The username or password you entered were not correct' in r:
				raise Exception('invalid login')
		else:
			self.url_opener=build_opener()
		self.parameters={}
		if not skip_get_parameters: self.parameters=self.get_parameters()

	def get_parameters(self, build=None):
		result={}
		#get required parameters
		response=self._request('{}/builders/{}'.format(self.master, self.builder), {})
		for line in response:
			line=str(line)
			if '<input' in line:
				m=re.search(r"type='([^']*)'.*name='([^']*)'[\s]*value='([^']*)'[\s]*((?:checked)?)", line)
				if m and (m.group(1)!='checkbox' or m.group(4)): result[m.group(2)]=m.group(3)
		#get parameters from previous build request
		if build!=None:
			root=self.json_request(build)
			for i in root['properties']:
				if i[0] in result:
					result[i[0]]=i[1]
				if i[0]=='got_revision':
					for repo, commit in i[1].items():
						result['{}_revision'.format(repo)]=commit
						result['{}_branch'.format(repo)]=''
			for i in root['sourceStamps']:
				result['{}_repository'.format(i['codebase'])]=i['repository']
		#
		return result

	def force(self, parameters={}, dry=False):
		self.parameters.update(parameters)
		self.parameters['reason']=self.parameters.get('reason', '')+'--'+stamp
		self.force_url='{}/builders/{}/force'.format(self.master, self.builder)
		print('{} forcing build, url: {}'.format(timestamp(), self.force_url))
		if dry:
			print('parameters')
			pprint.pprint(self.parameters)
		else:
			r=self._request(self.force_url, self.parameters)
			for line in r:
				line=str(line)
				if 'alert' in line:
					raise Exception('invalid arguments\n{}\n{}'.format(self.force_url, self.parameters))
				if 'Authorization Failed' in line:
					raise Exception('authorization failed')

	def wait(self, period=1):
		while(True):
			if self.get_progress()[0]: break
			time.sleep(period)

	def get_progress(self):
		if not hasattr(self, 'requested_build'):
			root=self.json_request(-1)
			if stamp in root['reason']:
				self.requested_build=root['number']
				self.url='{}/builders/{}/builds/{}'.format(self.master, self.builder, root['number'])
			else: return (False, 'not started')
		else:
			root=self.json_request(self.requested_build)
		if root['results']==None: return (False, 'started')
		return (True, root['results'])

	def get_url(self):
		if hasattr(self, 'url'): return self.url
		return 'no url, force url was: {}'.format(self.force_url)

	def json_request_generic(self, suffix):
		import json
		try:
			result=retry(lambda: json.loads(urlopen('{}/json/{}'.format(
				self.master, suffix
			)).read().decode('utf-8')))
		except:
			import pdb; pdb.set_trace()
		return result

	def json_request(self, build):
		return self.json_request_generic('builders/{}/builds/{}'.format(self.builder, build))

	def _request(self, url, data):
		headers={'Referer': '{}/builders/{}'.format(self.master, self.builder)}
		request=Request(url, urlencode(data).encode('utf-8'), headers)
		return retry(lambda: self.url_opener.open(request))

#=====subfunctions=====#
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
	if os.path.exists(os.path.join(megatron_master_path, 'buildbot.tac')):
		invoke('buildbot stop {}'.format(megatron_master_path))
	if os.path.exists(os.path.join(megatron_slave_path, 'buildbot.tac')):
		invoke('buildslave stop {}'.format(megatron_slave_path))
	if os.path.exists(os.path.join(devastator_master_path, 'buildbot.tac')):
		invoke('buildbot stop {}'.format(devastator_master_path))

def mb(args):
	webbrowser.open('http://localhost:{}'.format(cybertron['megatron_master_port']))

def mc(args):
	invoke('buildbot checkconfig {}'.format(megatron_master_path))

def d1(args):
	if not os.path.exists(devastator_slave_path): os.makedirs(devastator_slave_path)
	name=devastator_slave_name(args)
	path=os.path.join(devastator_slave_path, name)
	invoke('buildslave create-slave {} localhost:{} {} {}'.format(
		path,
		cybertron['devastator_slave_port'],
		name,
		common.password
	))
	invoke('buildslave restart {}'.format(path))

def d0(args):
	if os.path.exists(devastator_slave_path):
		os.chdir(devastator_slave_path)
		import glob
		for i in glob.glob('*'):
			invoke('buildslave stop {}'.format(i))

def dr(args):
	os.chdir(os.path.join('devastator', 'master'))
	#create if necessary
	if not os.path.exists('buildbot.tac'): invoke('buildbot create-master')
	#start making invocation
	invocation=['buildbot']
	#figure out if master is running
	s=socket.socket()
	r=s.connect_ex(('localhost', cybertron['devastator_master_port']))
	s.close()
	#restart if necessary
	invocation.append('reconfig' if r==0 else 'restart')
	#on Windows, work around daemon problems
	import platform
	if platform.system()=='Windows': invocation.append('--nodaemon')
	#
	invoke(' '.join(invocation))

def df(args):
	os.chdir(devastator_master_path)
	import SimpleHTTPServer, SocketServer
	SocketServer.TCPServer(
		('', cybertron['devastator_file_server_port']),
		SimpleHTTPServer.SimpleHTTPRequestHandler
	).serve_forever()

def db(args):
	webbrowser.open('http://localhost:{}'.format(cybertron['devastator_master_port']))

def example(args):
	global cybertron
	if os.path.exists('cybertron.py'): print('cybertron.py already exists, using it.')
	else: cybertron.set(cybertron_example)
	assert_ports_clean()
	print("When you hit enter, I'll start a megatron and open a browser to it.")
	print("Wait for the megatron master to start.")
	print("When it has, request a build with repo URL set to https://github.com/dansgithubuser/constructicon")
	print("This will construct a constructicon for this repo.")
	print("When you're done that, hit enter again.")
	input()
	invoke('python go.py m1')
	webbrowser.open('http://localhost:{}/builders/megatron-builder'.format(cybertron['megatron_master_port']))
	input()
	print("Now, when you hit enter, I'll open a browser to a constructicon builder we just made.")
	print("I'll also start a devastator slave.")
	print("Wait for the devastator slave to connect.")
	print("Request a build from the constructicon builder, and it should print out this script's help.")
	print("When you're done that, hit enter again.")
	input()
	webbrowser.open('http://localhost:{}/builders/constructicon-basic'.format(cybertron['devastator_master_port']))
	invoke('python go.py d1 slave-1')
	input()
	print("At the end of that build you just requested,")
	print("a build result was uploaded from the devastator slave to the devastator master.")
	print("To allow users to access this file, I'll start a devastator file server.")
	print("When you're done checking that out, hit enter again to clean up and quit.")
	input()
	f=invoke('python go.py df', async=True)
	input()
	f.kill()
	invoke('python go.py m0')
	invoke('python go.py d0')

def expect(condition, description):
	if not condition:
		print('condition failed: '+description)
		assert(False)

def test(args):
	#setup
	cybertron.set(cybertron_example)
	invoke('python go.py m0')
	invoke('python go.py d0')
	assert_ports_clean()
	invoke('python go.py m1')
	m_forcer=Forcer('localhost', cybertron['megatron_master_port'], 'megatron-builder')
	m_forcer.force({'constructicon_repo_url': 'https://github.com/dansgithubuser/constructicon', 'reason': 'test setup'})
	m_forcer.wait()
	r=m_forcer.json_request(-1)
	expect(stamp in r['reason'], 'setup - megatron build happened')
	expect(r['results']==0, 'setup - megatron build succeeded')
	invoke('python go.py d1 slave-1')
	d_forcer=Forcer('localhost', cybertron['devastator_master_port'], skip_get_parameters=True)
	r=d_forcer.json_request_generic('')
	expect('constructicon-sleep' in r['builders'].keys(), 'setup - constructicon-sleep builder created')
	#test
	if re.match(args.regex, 'reconfig'):
		#modify constructicon.py
		constructicon=common.constructicon()
		constructicon['builders']['sleep']['commands'].append('python -c "import time; time.sleep(1)"')
		os.chdir(os.path.join('devastator', 'constructicons', 'constructicon'))
		with open('constructicon.py', 'w') as file:
			file.write('constructicon='+pprint.pformat(constructicon))
		invoke('git add -u :/')
		invoke('git commit -m "test reconfig"')
		os.chdir(folder)
		#request original build
		d_forcer=Forcer('localhost', cybertron['devastator_master_port'], 'constructicon-sleep')
		d_forcer.force({'reason': 'test reconfig original'})
		#reconfig
		m_forcer.force({'constructicon_repo_url': '', 'reason': 'test reconfig reconfig'})
		m_forcer.wait()
		#request reconfigged build
		d_forcer.force({'reason': 'test reconfig reconfigged'})
		while d_forcer.json_request_generic('')['builders']['constructicon-sleep']['state']!='idle': time.sleep(1)
		#check stuff
		r=d_forcer.json_request(-1)
		expect(stamp in r['reason'], 'reconfig - reconfigged build happened')
		expect(r['results']==0, 'reconfig - reconfigged build succeeded')
		expect(len(r['steps'])==5, 'reconfig - reconfigged build had an extra step')
		r=d_forcer.json_request(-2)
		expect(stamp in r['reason'], 'reconfig - original build happened')
		expect(r['results']==0, 'reconfig - original build succeeded')
		expect(len(r['steps'])==4, 'reconfig - original build had normal number of steps')
	if re.match(args.regex, 'user-slave'):
		invoke('python go.py d1 user-slave-1')
		expect(d_forcer.json_request_generic('')['slaves']['constructicon-user-slave-1']['connected'], 'user-slave - user slave connected to devastator')
	#teardown
	invoke('python go.py m0')
	invoke('python go.py d0')

#=====args=====#
import argparse
parser=argparse.ArgumentParser()
subparsers=parser.add_subparsers()
subparsers.add_parser('m1', help='megatron start').set_defaults(func=m1)
subparsers.add_parser('m0', help='megatron stop' ).set_defaults(func=m0)
subparsers.add_parser('mb', help='megatron master browser').set_defaults(func=mb)
subparsers.add_parser('mc', help='megatron master check').set_defaults(func=mc)
subparser=subparsers.add_parser('d1', help='devastator slave start')
subparser.set_defaults(func=d1)
subparser.add_argument('devastator_slave_name')
subparsers.add_parser('d0', help='devastator slave stop').set_defaults(func=d0)
subparsers.add_parser('dr', help='devastator master create/restart/reconfig -- usually called by megatron').set_defaults(func=dr)
subparsers.add_parser('df', help='devastator file server').set_defaults(func=df)
subparsers.add_parser('db', help='devastator master browser').set_defaults(func=db)
subparsers.add_parser('example', help='run example').set_defaults(func=example)
subparser=subparsers.add_parser('test', help='run tests')
subparser.set_defaults(func=test)
subparser.add_argument('regex')

#=====main=====#
args=parser.parse_args()
args.func(args)

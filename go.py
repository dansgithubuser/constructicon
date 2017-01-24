#!/usr/bin/python

#=====imports=====#
import common
import os, pprint, re, socket, subprocess, sys, time, webbrowser

#=====globals=====#
import random, string
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

	def __contains__(self, key):
		self._load()
		return key in self.contents

	def items(self):
		self._load()
		return self.contents.items()

	def _load(self):
		if not self.contents: self.contents=common.cybertron(folder)

cybertron=Cybertron()

def cybertron_store_folder(cybertron_folder):
	with open(os.path.join(folder, 'cybertron.txt'), 'w') as file:
		file.write(os.path.realpath(cybertron_folder))

#=====helpers=====#
def timestamp():
	import datetime
	return '{:%Y-%m-%d %H:%M:%S.%f}'.format(datetime.datetime.now())

def invoke(invocation, async=False, path='.'):
	start=os.getcwd()
	os.chdir(path)
	print(timestamp())
	print('invoking{}: {}'.format(' async' if async else '', invocation))
	print('in: '+os.getcwd())
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
		if i.endswith('_port'):
			if not check_port_closed(j):
				raise Exception('port {} is not closed'.format(j))

#=====forcer=====#
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

class Forcer:
	def __init__(self, server, port, builder, user=None, password=None):
		self.master='http://{}:{}'.format(server, port)
		self.builder=builder
		if user:
			self.url_opener=build_opener(HTTPCookieProcessor(CookieJar()))
			r=str(self._request('{}/login'.format(self.master), {'username': user, 'passwd': password}).read())
			if 'The username or password you entered were not correct' in r:
				raise Exception('invalid login')
		else:
			self.url_opener=build_opener()
		self.parameters=self.get_parameters()

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
		self.requested_build=None
		self.url=None
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

	def wait_all(self, period=1):
		while self.json_request_generic('')['builders'][self.builder]['state']!='idle': time.sleep(period)

	def get_progress(self):
		if not self.requested_build:
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
		if not self.url: self.get_progress()
		if self.url: return self.url
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
	cybertron_store_folder(args.cybertron_folder)
	if not args.slave_only:
		invoke('buildbot --verbose create-master {}'.format(megatron_master_path))
		restart_args=[]
		if args.foreground: restart_args.append('--nodaemon')
		restart_args.append(megatron_master_path)
		invoke('buildbot --verbose restart '+' '.join(restart_args))
	if not args.master_only:
		invoke('buildslave --verbose create-slave {} localhost:{} megatron-slave {}'.format(
			megatron_slave_path,
			cybertron['megatron_slave_port'],
			common.password
		))
		invoke('buildslave --verbose restart {}'.format(megatron_slave_path))

def m0(args):
	if os.path.exists(os.path.join(megatron_master_path, 'buildbot.tac')):
		invoke('buildbot --verbose stop {}'.format(megatron_master_path))
	if os.path.exists(os.path.join(megatron_slave_path, 'buildbot.tac')):
		invoke('buildslave --verbose stop {}'.format(megatron_slave_path))
	if os.path.exists(os.path.join(devastator_master_path, 'buildbot.tac')):
		invoke('buildbot --verbose stop {}'.format(devastator_master_path))

def mb(args):
	webbrowser.open('http://localhost:{}'.format(cybertron['megatron_master_port']))

def mc(args):
	invoke('buildbot checkconfig {}'.format(megatron_master_path))

def d1(args):
	cybertron_store_folder(args.cybertron_folder)
	if not os.path.exists(devastator_slave_path): os.makedirs(devastator_slave_path)
	path=os.path.join(devastator_slave_path, args.devastator_slave_name)
	tac=os.path.join(path, 'buildbot.tac')
	if os.path.exists(tac):
		invoke('buildslave --verbose stop {}'.format(path))
		os.remove(tac)
	invoke('buildslave --verbose create-slave {} {}:{} {} {}'.format(
		path,
		cybertron['megatron_hostname'],
		cybertron['devastator_slave_port'],
		args.devastator_slave_name,
		common.password
	))
	with open(os.path.join(path, 'info', 'host'), 'w') as file:
		file.write(socket.gethostbyname(socket.gethostname()))
	invoke('buildslave --verbose restart {}'.format(path))

def d0(args):
	if os.path.exists(devastator_slave_path):
		os.chdir(devastator_slave_path)
		import glob
		for i in glob.glob('*'):
			invoke('buildslave --verbose stop {}'.format(i))

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

getmailrc_format='''
[retriever]
type = SimplePOP3SSLRetriever
server = pop.gmail.com
username = {}
port = 995
password = {}
[destination]
type = Maildir
path = email/maildir/
[options]
read_all = false
'''

def mail(args):
	def mkdir(*args):
		path=os.path.join(*args)
		if os.path.exists(path): return
		os.makedirs(path)
	mkdir('email', 'config')
	with open(os.path.join('email', 'config', 'getmailrc'), 'w') as file:
		file.write(getmailrc_format.format(
			cybertron['email_username'], cybertron['email_password'])
		)
	for i in ['new', 'tmp', 'cur']: mkdir('email', 'maildir', i)
	while True:
		try: invoke('python '+os.path.join('email', 'getmail', 'getmail')+' --getmaildir email/config')
		except Exception as e:
			print(timestamp())
			import traceback
			traceback.print_exc(file=sys.stdout)
		print(timestamp()+' sleeping')
		time.sleep(30)

def f(args):
	port=cybertron['megatron_master_port' if args.megatron else 'devastator_master_port']
	forcer=Forcer(cybertron['megatron_hostname'], port, args.builder)
	forcer.force(parameters=dict(zip(args.key, args.value)))

def example(args):
	cybertron_store_folder(folder)
	global cybertron
	assert_ports_clean()
	print("When you hit enter, I'll start a megatron and open a browser to it.")
	print("Wait for the megatron master to start.")
	print("When it has, request a build with repo URL set to https://github.com/dansgithubuser/constructicon")
	print("This will construct a constructicon for this repo.")
	print("When you're done that, hit enter again.")
	input()
	invoke('python go.py m1 {}'.format(folder))
	webbrowser.open('http://localhost:{}/builders/megatron-builder'.format(cybertron['megatron_master_port']))
	input()
	print("Now, when you hit enter, I'll open a browser to a constructicon builder we just made.")
	print("I'll also start a devastator slave.")
	print("Wait for the devastator slave to connect.")
	print("Request a build from the constructicon builder, and it should print out this script's help.")
	print("When you're done that, hit enter again.")
	input()
	webbrowser.open('http://localhost:{}/builders/constructicon-basic'.format(cybertron['devastator_master_port']))
	invoke('python go.py d1 slave-1 {}'.format(folder))
	input()
	print("At the end of that build you just requested,")
	print("a build result was uploaded from the devastator slave to the devastator master.")
	print("To allow users to access this file, I'll start a devastator file server.")
	print("When you're done checking that out, hit enter again to clean up and quit.")
	input()
	f=invoke('python go.py df'.format(folder), async=True)
	input()
	f.kill()
	invoke('python go.py m0')
	invoke('python go.py d0')

def expect(condition, description, information=None):
	if not condition:
		print('condition failed: '+description)
		if information: print(information)
		assert(False)

def test(args):
	cybertron_store_folder(folder)
	#setup
	invoke('python go.py m0')
	invoke('python go.py d0')
	assert_ports_clean()
	time.sleep(1)
	invoke('python go.py m1 {}'.format(folder))
	m_forcer=Forcer('localhost', cybertron['megatron_master_port'], 'megatron-builder')
	m_forcer.force({'constructicon_repo_url': 'https://github.com/dansgithubuser/constructicon', 'reason': 'test setup'})
	m_forcer.wait()
	r=m_forcer.json_request(-1)
	expect(r['results']==0, 'setup - megatron build succeeded')
	invoke('python go.py d1 slave-1 {}'.format(folder))
	basic_forcer=Forcer('localhost', cybertron['devastator_master_port'], 'constructicon-basic')
	#test
	if re.match(args.regex, 'reconfig'):
		#modify constructicon.py
		constructicon=common.constructicon(folder)
		constructicon['builders']['sleep']['commands'].append('python -c "import time; time.sleep(1)"')
		os.chdir(os.path.join('devastator', 'constructicons', 'constructicon'))
		with open('constructicon.py', 'w') as file:
			file.write('constructicon='+pprint.pformat(constructicon))
		invoke('git add -u :/')
		invoke('git commit -m "test reconfig"')
		os.chdir(folder)
		#request original build
		sleep_forcer=Forcer('localhost', cybertron['devastator_master_port'], 'constructicon-sleep')
		sleep_forcer.force({'reason': 'test reconfig original'})
		#reconfig
		m_forcer.force({'constructicon_repo_url': '', 'reason': 'test reconfig reconfig'})
		m_forcer.wait()
		#request reconfigged build
		sleep_forcer.force({'reason': 'test reconfig reconfigged'})
		sleep_forcer.wait_all()
		#check stuff
		r1=sleep_forcer.json_request(-1)
		r2=sleep_forcer.json_request(-2)
		expect(stamp in r1['reason'], 'reconfig - reconfigged build happened')
		expect(r1['results']==0, 'reconfig - reconfigged build succeeded')
		expect(stamp in r2['reason'], 'reconfig - original build happened')
		expect(r2['results']==0, 'reconfig - original build succeeded')
		expect(len(r1['steps'])==len(r2['steps'])+1, 'reconfig - reconfigged build had an extra step')
	if re.match(args.regex, 'user-slave'):
		invoke('python go.py d1 constructicon-user-slave-1 {}'.format(folder))
		r=basic_forcer.json_request_generic('')
		expect(r['slaves']['constructicon-user-slave-1']['connected'], 'user-slave - user slave connected to devastator', pprint.pformat(r))
	if re.match(args.regex, 'builder_base'):
		#---builder---#
		r=basic_forcer.json_request_generic('')['builders']['constructicon-basic']
		#features
		expect('slave-bad' not in r['slaves'], 'no bad slave', pprint.pformat(r))
		expect('user-slave-bad' not in r['slaves'], 'no bad user slave', pprint.pformat(r))
		#schedulers
		expect('constructicon-basic-force-cybertron' in r['schedulers'], 'builder_base force scheduler', pprint.pformat(r))
		expect('constructicon-basic-commit-cybertron' in r['schedulers'], 'builder_base commit scheduler', pprint.pformat(r))
		#---build---#
		basic_forcer.force({'reason': 'test builder_base'})
		basic_forcer.wait()
		r=basic_forcer.json_request(-1)
		#deps
		expect(any(['crangen' in i['name'] for i in r['steps']]), 'builder_base dep', pprint.pformat(r))
		#precommands
		expect(any([any(['precommand' in j for j in i['text']]) for i in r['steps']]), 'builder_base precommand', pprint.pformat(r))
		#commands
		expect(any([any(['command' in j for j in i['text']]) for i in r['steps']]), 'builder_base command', pprint.pformat(r))
		#upload
		expect(any(['upload' in i['name'] for i in r['steps']]), 'builder_base upload', pprint.pformat(r))
	#teardown
	invoke('python go.py m0')
	invoke('python go.py d0')

def c(args):
	cans={
		't': ['test', '.*'],
	}
	if args.name not in cans or args.name=='h':
		print('available cans:')
		pprint.pprint(cans)
	else: subprocess.check_call(['python', 'go.py']+cans[args.name])

#=====args=====#
import argparse
parser=argparse.ArgumentParser()
subparsers=parser.add_subparsers()

#-----megatron-----#
#start
subparser=subparsers.add_parser('m1', help='megatron start')
subparser.set_defaults(func=m1)
subparser.add_argument('cybertron_folder', help='folder containing cybertron.py')
subparser.add_argument('--foreground', '-f', action='store_true')
subparser.add_argument('--master-only', '-m', action='store_true')
subparser.add_argument('--slave-only', '-s', action='store_true')
#stop
subparsers.add_parser('m0', help='megatron stop').set_defaults(func=m0)
#browser
subparser=subparsers.add_parser('mb', help='megatron master browser')
subparser.set_defaults(func=mb)
#check config
subparsers.add_parser('mc', help='megatron master check').set_defaults(func=mc)

#-----devastator-----#
#start
subparser=subparsers.add_parser('d1', help='devastator slave start')
subparser.set_defaults(func=d1)
subparser.add_argument('devastator_slave_name')
subparser.add_argument('cybertron_folder', help='folder containing cybertron.py')
#stop
subparsers.add_parser('d0', help='devastator slave stop').set_defaults(func=d0)
#recombobulate
subparsers.add_parser('dr', help='devastator master create/restart/reconfig -- usually called by megatron').set_defaults(func=dr)
#file server
subparsers.add_parser('df', help='devastator file server').set_defaults(func=df)
#browser
subparsers.add_parser('db', help='devastator master browser').set_defaults(func=db)

#-----mail-----#
subparsers.add_parser('mail', help='get mail for email-based on-commit scheduling').set_defaults(func=mail)

#-----force-----#
subparser=subparsers.add_parser('f', help='force a build')
subparser.set_defaults(func=f)
subparser.add_argument('--megatron', '-m', action='store_true', help='force on megatron, default is devastator')
subparser.add_argument('--builder', '-b', default='megatron-builder', help='which builder to force, default is megatron-builder')
subparser.add_argument('--key'  , '-k', nargs='+', default=[], help='parameter keys, there should be an equal number of values')
subparser.add_argument('--value', '-v', nargs='+', default=[], help='parameter values, there should be an equal number of keys')

#-----example-----#
subparsers.add_parser('example', help='run example').set_defaults(func=example)

#-----test-----#
subparser=subparsers.add_parser('test', help='run tests')
subparser.set_defaults(func=test)
subparser.add_argument('regex')

#-----canned commands-----#
subparser=subparsers.add_parser('c', help='canned commands')
subparser.add_argument('name')
subparser.set_defaults(func=c)

#=====main=====#
args=parser.parse_args()
args.func(args)

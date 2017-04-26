import os; folder=os.path.realpath(os.path.dirname(__file__))
import sys; sys.path.append(os.path.join(folder, '..', '..'))

import common

from buildbot.plugins import changes, buildslave, schedulers, steps, util
from buildbot.status import html
from buildbot.status.web import authz
from buildbot.schedulers import forcesched
from twisted.python import log

import calendar, collections, pprint

ForceScheduler=schedulers.ForceScheduler
Nightly=schedulers.Nightly
AnyBranchScheduler=schedulers.AnyBranchScheduler

cybertron=common.cybertron()

parameter_prefix='parameter-'

global_constructicons={{{constructicons}}}
global_repo_urls={{{repo_urls}}}
global_git_states={{{git_states}}}

class ConfigException(Exception): pass

class Config:
	@staticmethod
	def create(x):
		if type(x)==dict: return Config({k: Config.create(v) for k, v in x.items()})
		elif type(x)==list: return [Config.create(i) for i in x]
		else: return x

	def __init__(self, dict):
		self.visited=set()
		self.dict=dict

	def __getitem__(self, k):
		self.visited.add(k)
		return self.dict[k]

	def __contains__(self, k): return k in self.dict

	def __repr__(self): return 'configuration'+str((self.visited, self.dict))

	def update(self, dict): self.dict.update(dict)

	def get(self, k, default):
		if k in self.dict: return self[k]
		else: return default

	def items(self, mark_used=False):
		if mark_used: self.visited=self.dict.keys()
		return self.dict.items()

	def keys(self): return self.dict.keys()

	def values(self): return self.dict.values()

	def unused(self, prefix=[]):
		result=[prefix+[k] for k in self.dict if k not in self.visited]
		def recurse_list(k, v, f):
			if type(v)==list:
				for i in range(len(v)): recurse_list(k+[i], v[i], f)
			else: f(k, v)
		def recurse(k, v):
			if isinstance(v, Config): result.extend(v.unused(k))
		for k, v in self.dict.items(): recurse_list(prefix+[k], v, recurse)
		return result

def repo_url_to_name(repo_url):
	r=repo_url.split('/')[-1]
	if r.endswith('.git'): r=r[:-4]
	return r

def make_full_builder_name(constructicon_name, builder_name):
	return constructicon_name+'-'+builder_name

resource_locks={}

def factory(constructicon_name, builder_name, deps, commands, upload, zip, unzip, url, resources):
	deps=sorted(deps)
	def work_dir_renderer(*suffix, **kwargs):
		@util.renderer
		def work_dir(properties):
			if kwargs.get('log', False):
				log.msg('properties are: '+pprint.pformat(properties.asDict()))
				log.msg('sourcestamps are: '+pprint.pformat([(i.repository, i.branch, i.revision) for i in properties.getBuild().getAllSourceStamps()]))
			sep='/'
			if all_slaves[properties['slavename']].get('platform', 0)=='windows': sep='\\'
			return sep.join(('..', 'constructicons', constructicon_name, constructicon_name)+suffix)
		return work_dir
	result=util.BuildFactory()
	def git_step(repo_url, work_dir):
		return common.sane_step(steps.Git,
			repourl=repo_url,
			codebase=repo_url,
			workdir=work_dir,
			mode='full',
			method='fresh',
		)
	def extract_parameters(dict):
		return {i[len(parameter_prefix):]: str(j[0]) for i, j in dict.items() if i.startswith(parameter_prefix)}
	@util.renderer
	def env(properties): return extract_parameters(properties.asDict())
	def format(command):
		@util.renderer
		def f(properties): return command.format(**extract_parameters(properties.asDict()))
		return f
	@util.renderer
	def get_command(properties):
		revisions=''
		for i in properties.getBuild().getAllSourceStamps():
			revision=None
			if i.revision: revision=i.revision
			elif i.branch: revision=i.branch
			if revision: revisions+=' -r {}:{}'.format(i.codebase, revision)
		return common.constructicon_slave_go('g {}{}'.format(
			builder_name,
			revisions,
		))
	for resource in resources:
		if resource not in resource_locks:
			resource_locks[resource]=util.MasterLock(resource)
	locks=[resource_locks[i].access('exclusive') for i in resources]
	#properties, get, compile
	result.addSteps(
		[
			common.sane_step(steps.SetProperty,
				name='devastator git state',
				property='devastator_git_state',
				value={{{devastator_git_state}}},
			),
			common.sane_step(steps.SetProperty,
				name='cybertron git state',
				property='cybertron_git_state',
				value={{{cybertron_git_state}}},
			),
			common.sane_step(steps.SetProperty,
				name='git state',
				property='git_state',
				value=global_git_states[constructicon_name],
			),
			git_step(global_repo_urls[constructicon_name], work_dir_renderer()),
			common.sane_step(steps.Compile,
				name='get',
				command=get_command,
				workdir=work_dir_renderer(log=True),
			),
		]
		+
		[common.sane_step(steps.Compile,
			name=commands[i][0],
			command=format(commands[i][1]),
			workdir=work_dir_renderer(),
			env=env,
			locks=locks,
		) for i in range(len(commands))]
	)
	#upload
	for i, j in upload.items(True):
		zip_steps=[]
		upload_steps=[]
		unzip_steps=[]
		slave_src=i
		master_dst_extension=''
		#zip
		if i in zip:
			@util.renderer
			def command(properties, i=i):
				return 'python -m zipfile -c {0}.zip {0}'.format(i)
			zip_steps.append(steps.ShellCommand(
				command=command,
				workdir=work_dir_renderer(),
			))
			slave_src+='.zip'
			master_dst_extension='.zip'
		#unzip
		def master_dst_function(properties, j=j, extension=master_dst_extension, suffix=None):
			return os.path.join(
				make_full_builder_name(constructicon_name, builder_name),
				str(properties['buildnumber'])+'-constructicon',
				suffix if suffix else j+master_dst_extension
			)
		@util.renderer
		def master_dst_renderer(properties, f=master_dst_function):
			return f(properties)
		url_trim=0
		if j in unzip:
			@util.renderer
			def command(properties, master_dst_function=master_dst_function):
				master_dst=master_dst_function(properties)
				unzipped=os.path.split(master_dst)[0] or '.'
				return 'python -m zipfile -e {} {}'.format(master_dst, unzipped)
			unzip_steps.append(steps.MasterShellCommand(command=command))
			url_trim=4
		devastator_file_server_port=cybertron['devastator_file_server_port']
		#upload
		suffix=url.get(j, None)
		@util.renderer
		def url_renderer(properties, j=j,
			suffix=suffix,
			master_dst_function=master_dst_function,
			devastator_file_server_port=devastator_file_server_port,
			url_trim=url_trim
		):
			return (
				'http://{}:{}'.format({{{devastator_host}}}, devastator_file_server_port)
				+
				'/'+master_dst_function(properties, suffix=suffix)
			)
		upload_steps.append(steps.FileUpload(
			slavesrc=slave_src,
			masterdest=master_dst_renderer,
			url=url_renderer,
			workdir=work_dir_renderer()
		))
		#append
		result.addSteps(zip_steps+upload_steps+unzip_steps)
	return result

def check_dict(x, key_type, value_type):
	return (
		(isinstance(x, Config) or type(x)!=dict)
		and
		all([type(i)==key_type and type(j)==value_type for i, j in x.items()])
	)

def check_list(x, item_type):
	return (
		type(x)==list
		and
		all([type(i)==item_type for i in x])
	)

def t_or_list_of(t, x): return type(x)==t or check_list(x, t)

def intersect(dict1, dict2):
	return set(dict1.keys())&set(dict2.keys())

def get_base(key, default):
	result=default
	if 'builder_base' in cybertron:
		if key in cybertron['builder_base']:
			result=cybertron['builder_base'][key]
	return Config.create(result)

base={
	'builder_base accept': get_base('accept', 'True'),
	'builder_base deps': get_base('deps', []),
	'builder_base precommands': get_base('precommands', []),
	'builder_base commands': get_base('commands', []),
	'builder_base upload': get_base('upload', {}),
	'builder_base zip': get_base('zip', []),
	'builder_base unzip': get_base('unzip', []),
	'builder_base url': get_base('url', {}),
	'builder_base schedulers': get_base('schedulers', {}),
	'builder_base resources': get_base('resources', []),
	'schedulers': Config.create(cybertron.get('schedulers', {})),
	'resources': Config.create(cybertron.get('resources', {})),
}

def check(spec, key, base_key, expectations):
	for expectation in expectations:
		if not expectation[0](spec, *expectation[1:-1]):
			error(key+' '+expectation[-1]); return False
		if not expectation[0](base[base_key], *expectation[1:-1]):
			error('cybertron '+key+' '+expectation[-1]); return False
	return True

def number(list, prefix):
	return [('{} {}'.format(prefix, i+1), v) for i, v in enumerate(list)]

all_repo_urls=set(global_repo_urls.values())
all_slaves=cybertron['slaves']
all_builders=[]
all_schedulers=[]
scheduler_to_builders=collections.defaultdict(list)
slave_lock=util.SlaveLock('slave-lock', maxCount=1)
errors=1
for constructicon_name, constructicon_spec in global_constructicons.items():
	constructicon_spec=Config.create(constructicon_spec)
	git_state=global_git_states[constructicon_name]
	def error(message):
		try: name=builder_name
		except NameError: name=constructicon_name
		global errors
		name+='-uniquifier-{}'.format(errors)
		errors+=1
		all_builders.append(util.BuilderConfig(
			name=name,
			description=git_state+' error: '+message,
			slavenames=['none'],
			factory=util.BuildFactory()
		))
		all_schedulers.append(ForceScheduler(
			name=name+'-force',
			builderNames=[name],
		))
		log.msg('builder {}: {}'.format(name, message))
	def full_scheduler_name(name): return constructicon_name+'-'+name
	if not isinstance(constructicon_spec, Config):
		error('constructicon is not a dict'); continue
	#slaves
	slaves=cybertron['slaves']
	if 'slaves' in constructicon_spec:
		prefix=constructicon_name+'-'
		x=constructicon_spec['slaves']
		for i, j in x.items():
			if not i.startswith(prefix): break
		else: i=None
		if i!=None:
			error("slave {} must start with {} but doesn't".format(i, prefix)); continue
		slaves.update(constructicon_spec['slaves'])
		all_slaves.update(slaves)
	#builders
	all_deps=set()
	for builder_name, builder_spec in constructicon_spec['builders'].items(True):
		#builder name
		if type(builder_name)!=str:
			error('builder name is not a str'); continue
		full_builder_name=make_full_builder_name(constructicon_name, builder_name)
		#builder spec
		if not isinstance(builder_spec, Config):
			error('builder spec is not a dict'); continue
		#get what slaves this builder accepts
		accept=builder_spec.get('accept', 'True')
		if not check(accept, 'accept', 'builder_base accept', [[str, 'is not a str']]): continue
		slave_names=[]
		for slave_name, features in slaves.items():
			try:
				if eval(accept) and eval(base['builder_base accept']):
					slave_names.append(slave_name)
			except: pass
		if not len(slave_names):
			error('no matching slaves'); continue
		#deps
		deps=builder_spec.get('deps', [])
		if not check(deps, 'deps', 'builder_base deps', [[check_list, str, 'is not a list of str']]): continue
		deps+=[i for i in base['builder_base deps'] if i not in deps]
		all_repo_urls.update(deps)
		all_deps.update(deps)
		#precommands
		precommands=builder_spec.get('precommands', [])
		if not check(precommands, 'precommands', 'builder_base precommands', [
			[lambda x: type(x)==list, 'is not a list'],
			[lambda x: all([t_or_list_of(str, i) for i in x]), 'contains a precommand that is not a str or list of str'],
		]): continue
		precommands=number(base['builder_base precommands'], 'cybertron precommand')+number(precommands, 'precommand')
		#commands
		if 'commands' not in builder_spec:
			error('no commands'); continue
		commands=builder_spec['commands']
		if not check(commands, 'commands', 'builder_base commands', [
			[lambda x: type(x)==list, 'is not a list'],
			[lambda x: all([t_or_list_of(str, i) for i in x]), 'contains a command that is not a str or list of str'],
		]): continue
		commands=number(commands, 'command')+number(base['builder_base commands'], 'cybertron command')
		#upload
		upload=builder_spec.get('upload', Config.create({}))
		if not check(upload, 'upload', 'builder_base upload', [
			[check_dict, str, str, 'is not a dict of str'],
			[lambda x: all(['..' not in j for i, j in x.items()]), 'destination may not contain ..'],
		]): continue
		if set(base['builder_base upload'].values())&set(upload.values()):
			error('upload conflicts with cybertron builder_base upload'); continue
		upload.update(base['builder_base upload'])
		zip=builder_spec.get('zip', [])+base['builder_base zip']
		unzip=builder_spec.get('unzip', [])+base['builder_base unzip']
		url=builder_spec.get('url', Config.create({}))
		if set(base['builder_base url'].values())&set(url.values()):
			error('url conflicts with cybertron builder_base url'); continue
		url.update(base['builder_base url'])
		#schedulers
		schedulers=builder_spec.get('schedulers', [])
		if not check(schedulers, 'schedulers', 'builder_base schedulers', [
			[check_list, str, 'is not a list of str']
		]): continue
		schedulers=set(schedulers+base['builder_base schedulers'])
		for i in schedulers: scheduler_to_builders[full_scheduler_name(i)].append(full_builder_name)
		#resources
		resources=builder_spec.get('resources', [])
		if not check(resources, 'resources', 'builder_base resources', [
			[check_list, str, 'is not a list of str'],
			[lambda x: all([i in base['resources'] for i in x]), 'contains a resource not on cybertron'],
		]): continue
		resources=set(resources+base['builder_base resources'])
		#get - ignore
		builder_spec.get('get', Config.create({})).items(True)
		#append
		f=factory(constructicon_name, builder_name, deps, precommands+commands, upload, zip, unzip, url, resources)
		unused=builder_spec.unused()
		if unused:
			error('unused configuration keys\n'+pprint.pformat(unused)); continue
		all_builders.append(util.BuilderConfig(
			name=full_builder_name,
			description=global_repo_urls[constructicon_name]+' '+git_state+' on cybertron '+common.cybertron_git_state()+' in devastator '+common.git_state(),
			slavenames=slave_names,
			factory=f,
			locks=[slave_lock.access('exclusive')],
		))
	#schedulers
	schedulers=constructicon_spec.get('schedulers', Config.create({}))
	if not check(schedulers, 'schedulers', 'schedulers', [
		[lambda x: isinstance(x, Config), 'is not a dict'],
		[lambda x: all([type(i)==str for i in x.keys()]), "has a key that isn't a str"],
		[lambda x: all([isinstance(j, Config) for i, j in x.items()]), "has a value that isn't a dict"],
		[lambda x: all(['type' in j.keys() for i, j in x.items()]), 'contains a scheduler that is missing a type specification'],
		[lambda x: all([j['type'] in ['force', 'time', 'commit'] for i, j in x.items()]), 'contains a scheduler that has an unknown type specification'],
	]): continue
	if intersect(schedulers, base['schedulers']):
		error('schedulers conflicts with cybertron schedulers'); continue
	schedulers.update(base['schedulers'])
	for name, spec in schedulers.items(True):
		scheduler_args={}
		#name
		scheduler_args['name']=full_scheduler_name(name)
		#builderNames
		scheduler_args['builderNames']=scheduler_to_builders[scheduler_args['name']]
		#trigger
		if spec['type']=='time':
			scheduler_args['month']=spec.get('month', '*')
			scheduler_args['dayOfMonth']=spec.get('day-of-month', '*')
			scheduler_args['dayOfWeek']=spec.get('day-of-week', '*')
			scheduler_args['hour']=spec.get('hour', 0)
			scheduler_args['minute']=spec.get('minute', 0)
			scheduler_args['branch']='master'
		elif spec['type']=='commit':
			scheduler_args['change_filter']=util.ChangeFilter(branch_re=spec.get('branch_regex', '.*'))
		#codebases
		x=[global_repo_urls[constructicon_name]]+list(all_deps)
		if spec['type']=='force':
			scheduler_args['codebases']=[forcesched.CodebaseParameter(codebase=i) for i in x]
		else:
			scheduler_args['codebases']={i: {'repository': i} for i in x}
		#parameters
		parameters=spec.get('parameters', Config.create({}))
		if spec['type']=='force':
			scheduler_args['properties']=[util.StringParameter(name=parameter_prefix+i, default=j) for i, j in parameters.items(True)]
		else:
			scheduler_args['properties']={parameter_prefix+i: str(j) for i, j in parameters.items(True)}
		#append
		all_schedulers.append({
			'force': ForceScheduler,
			'time': Nightly,
			'commit': AnyBranchScheduler
		}[spec['type']](**scheduler_args))

git_pollers=[ConstructiconGitPoller(
	repo_url=i,
	work_dir='git-poller-work-'+repo_url_to_name(i),
) for i in all_repo_urls]

class DevastatorChangeSource(changes.MaildirSource):
	name='DevastatorChangeSource'
	def parse(self, m, prefix=None):
		for i in git_pollers: i.poll()
		return None

change_sources=git_pollers
if 'email_username' in cybertron:
	maildir=os.path.join(folder, '..', '..', 'email', 'maildir')
	change_sources.append(DevastatorChangeSource(maildir))

log.msg('devastator schedulers:\n'+pprint.pformat({i.name: i.builderNames for i in all_schedulers}))

BuildmasterConfig={
	'db': {'db_url': 'sqlite:///state.sqlite'},
	'slaves': [buildslave.BuildSlave(i, common.password) for i in all_slaves.keys()+['none']],
	'protocols': {'pb': {'port': cybertron['devastator_slave_port']}},
	'builders': all_builders,
	'schedulers': all_schedulers,
	'status': [html.WebStatus(cybertron['devastator_master_port'], authz=authz.Authz(
		view=True,
		forceBuild=True,
		forceAllBuilds=True,
		pingBuilder=True,
		stopBuild=True,
		stopAllBuilds=True,
		cancelPendingBuild=True,
		cancelAllPendingBuilds=True,
		stopChange=True,
		showUsersPage=True
	))],
	'codebaseGenerator': lambda chdict: chdict['repository'],
	'change_source': change_sources,
	'mergeRequests': False,
	'debugPassword': 'sesame',
	'changeHorizon': cybertron['horizon'],
	'buildHorizon': cybertron['horizon'],
	'eventHorizon': cybertron['horizon'],
	'title': 'devastator {} on cybertron {}'.format({{{devastator_git_state}}}, {{{cybertron_git_state}}}),
}

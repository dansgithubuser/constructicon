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

	def remove(self, key):
		if key in self.dict: del self.dict[key]

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
	def git_step(repo_url, work_dir, env):
		return common.sane_step(steps.Git,
			repourl=repo_url,
			codebase=repo_url,
			workdir=work_dir,
			mode='incremental',
			env=env,
			warnOnWarnings=False,
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
			if revision: revisions+=' {}:{}'.format(i.codebase, revision)
		if revisions: revisions=' -r'+revisions
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
			git_step(global_repo_urls[constructicon_name], work_dir_renderer(), env),
			common.sane_step(steps.ShellCommand,
				name='get',
				command=get_command,
				workdir=work_dir_renderer(log=True),
				env=env,
				warnOnWarnings=False,
			),
		]
	)
	for command_i in range(len(commands)):
		kwargs={}
		meat=commands[command_i][1]
		timeout=5*60
		if type(meat)==str:
			command=meat
		else:
			command=meat['command']
			warning_pattern='(.*warning[: ])'
			if 'warnings' in meat:
				warning_pattern='({})'.format('|'.join(meat['warnings']))
			if 'suppress_warnings' in meat:
				warning_pattern=warning_pattern+'(?!{})'.format(
					'|'.join(meat['suppress_warnings'])
				)
			kwargs['warningPattern']=warning_pattern
			timeout=meat.get('timeout', timeout)
		result.addStep(common.sane_step(steps.Compile,
			name=commands[command_i][0],
			command=format(command),
			workdir=work_dir_renderer(),
			env=env,
			locks=locks,
			timeout=timeout,
			maxTime=2*60*60,
			**kwargs
		))
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
				alwaysRun=True,
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
			unzip_steps.append(steps.MasterShellCommand(command=command, alwaysRun=True))
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
			workdir=work_dir_renderer(),
			alwaysRun=True,
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

def str_or_dict(x): return any([isinstance(x, i) for i in [str, Config]])

def get_spec(spec, key, constructicon=False):
	if constructicon:
		r=spec.get(key, {
			'slaves': {},
			'schedulers': {},
			'resources': {},
		}[key])
	else:
		r=spec.get(key, {
			'accept': 'True',
			'deps': [],
			'precommands': [],
			'commands': [],
			'upload': {},
			'zip': [],
			'unzip': [],
			'url': {},
			'schedulers': [],
			'resources': [],
		}[key])
	return Config.create(r)

def get_constructicon_spec(spec, key):
	return get_spec(spec, key, True)

def get_builder_base_spec(key):
	return get_spec(cybertron.get('builder_base', {}), key)

def get_cybertron_spec(key):
	return get_spec(cybertron, key, True)

def get_scheduler_spec(spec, key):
	if key in spec: return spec[key]
	return Config.create({
		'month': '*',
		'day_of_month': '*',
		'day_of_week': '*',
		'hour': 0,
		'minute': 0,
		'branches': {},
		'branch_regex': '.*',
		'parameters': {},
	}[key])

def check(spec, key, expectations, constructicon=False):
	for expectation in expectations:
		if not expectation[0](spec, *expectation[1:-1]):
			e=key+' '+expectation[-1]+' -- '+pprint.pformat(spec)
			log.msg(e)
			error(e)
			return False
		prefix='cybertron'
		if constructicon:
			general_spec=get_constructicon_spec(cybertron, key)
		else:
			general_spec=get_builder_base_spec(key)
			prefix+=' builder_base'
		if not expectation[0](general_spec, *expectation[1:-1]):
			error(prefix+' '+key+' '+expectation[-1]+' -- '+pprint.pformat(general_spec))
			return False
	return True

def check_commands(commands, key):
	return check(commands, key, [
		[lambda x: type(x)==list,
			'is not a list'],
		[lambda x: all([ str_or_dict(i)                                   for i in x]),
			'contains a command that is not a str or dict'],
		[lambda x: all(['command' in i                                    for i in x if isinstance(i, Config)]),
			'contains a dict with no command key'],
		[lambda x: all([        type(i['command'])==str                   for i in x if isinstance(i, Config)]),
			'contains a nonstring command'],
		[lambda x: all([  check_list(i.get('warnings'         , []), str) for i in x if isinstance(i, Config)]),
			"contains a warnings spec that isn't a list of str"],
		[lambda x: all([  check_list(i.get('suppress_warnings', []), str) for i in x if isinstance(i, Config)]),
			"contains a suppress_warnings spec that isn't a list of str"],
		[lambda x: all([        type(i.get('timeout', 0))==int            for i in x if isinstance(i, Config)]),
			"contains a timeout that isn't an int"],
	])

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
		try: name=constructicon_name+'-'+builder_name
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
	slaves=get_cybertron_spec('slaves')
	prefix=constructicon_name+'-'
	x=get_constructicon_spec(constructicon_spec, 'slaves')
	for i, j in x.items():
		if not i.startswith(prefix): break
	else: i=None
	if i!=None:
		error("slave {} must start with {} but doesn't".format(i, prefix)); continue
	slaves.update(x)
	all_slaves.update(x)
	#builders
	all_deps=set()
	for builder_name, builder_spec in constructicon_spec['builders'].items(True):
		#builder name
		if type(builder_name)!=str:
			error('builder name is not a str'); continue
		full_builder_name=make_full_builder_name(constructicon_name, builder_name)
		print('processing builder '+full_builder_name)
		#builder spec
		if not isinstance(builder_spec, Config):
			error('builder spec is not a dict'); continue
		#get what slaves this builder accepts
		accept=get_spec(builder_spec, 'accept')
		if not check(accept, 'accept', [[str, 'is not a str']]): continue
		slave_names=[]
		for slave_name, features in slaves.items():
			try:
				if eval(accept) and eval(get_builder_base_spec('accept')):
					slave_names.append(slave_name)
			except: pass
		if not len(slave_names):
			error('no matching slaves -- accept="""{}"""; slaves={}'.format(
				accept, pprint.pformat(slaves),
			)); continue
		#deps
		deps=get_spec(builder_spec, 'deps')
		if not check(deps, 'deps', [
			[lambda x: all([str_or_dict(i) for i in x]), 'is not a list of (str or dict)'],
			[lambda x: all(['url' in i for i in x if isinstance(i, Config)]), 'contains a dict with no url key'],
			[lambda x: all([type(i['url'])==str for i in x if isinstance(i, Config)]), 'contains a nonstring url'],
			[lambda x: all([type(i.get('revision', ''))==str for i in x if isinstance(i, Config)]), 'contains a nonstring url'],
			[lambda x: all([type(i.get('builder', ''))==str for i in x if isinstance(i, Config)]), 'contains a nonstring url'],
		]): continue
		deps+=[i for i in get_builder_base_spec('deps') if i not in deps]
		for i in deps:#ignore
			if isinstance(i, Config):
				i.get('revision', None)
				i.get('builder', None)
		deps=[i if type(i)==str else i['url'] for i in deps]
		all_repo_urls.update(deps)
		all_deps.update(deps)
		#precommands
		precommands=get_spec(builder_spec, 'precommands')
		if not check_commands(precommands, 'precommands'): continue
		precommands=number(get_builder_base_spec('precommands'), 'cybertron precommand')+number(precommands, 'precommand')
		#commands
		if 'commands' not in builder_spec:
			error('no commands'); continue
		commands=builder_spec['commands']
		if not check_commands(commands, 'commands'): continue
		commands=number(commands, 'command')+number(get_builder_base_spec('commands'), 'cybertron command')
		#upload
		upload=get_spec(builder_spec, 'upload')#-[get_spec get_builder_base_spec] upload must point to a file
		if not check(upload, 'upload', [
			[check_dict, str, str, 'is not a dict of str'],
			[lambda x: all(['..' not in j for i, j in x.items()]), 'destination may not contain ..'],
		]): continue
		if set(get_builder_base_spec('upload').values())&set(upload.values()):
			error('upload conflicts with cybertron builder_base upload'); continue
		upload.update(get_builder_base_spec('upload'))
		zip=builder_spec.get('zip', [])+get_builder_base_spec('zip')
		unzip=builder_spec.get('unzip', [])+get_builder_base_spec('unzip')
		url=builder_spec.get('url', Config.create({}))
		if set(get_builder_base_spec('url').values())&set(url.values()):
			error('url conflicts with cybertron builder_base url'); continue
		url.update(get_builder_base_spec('url'))
		#schedulers
		schedulers=get_spec(builder_spec, 'schedulers')
		if not check(schedulers, 'schedulers', [
			[check_list, str, 'is not a list of str']
		]): continue
		schedulers=set(schedulers+get_builder_base_spec('schedulers'))
		for i in schedulers: scheduler_to_builders[full_scheduler_name(i)].append(full_builder_name)
		#resources
		resources=get_spec(builder_spec, 'resources')
		if not check(resources, 'resources', [
			[check_list, str, 'is not a list of str'],
			[lambda x: all([i in get_cybertron_spec('resources') for i in x]), 'contains a resource not on cybertron'],
		]): continue
		resources=set(resources+get_builder_base_spec('resources'))
		#get - ignore
		builder_spec.remove('get')
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
	schedulers=get_constructicon_spec(constructicon_spec, 'schedulers')
	if not check(schedulers, 'schedulers', [
		[lambda x: isinstance(x, Config), 'is not a dict'],
		[lambda x: all([type(i)==str for i in x.keys()]), "has a key that isn't a str"],
		[lambda x: all([isinstance(j, Config) for i, j in x.items()]), "has a value that isn't a dict"],
		[lambda x: all(['type' in j.keys() for i, j in x.items()]), 'contains a scheduler that is missing a type specification'],
		[lambda x: all([j['type'] in ['force', 'time', 'commit'] for i, j in x.items()]), 'contains a scheduler that has an unknown type specification'],
	], True): continue
	if set(schedulers.keys())&set(get_cybertron_spec('schedulers').keys()):
		error('schedulers conflicts with cybertron schedulers'); continue
	schedulers.update(get_cybertron_spec('schedulers'))
	for name, spec in schedulers.items(True):
		scheduler_args={}
		#name
		scheduler_args['name']=full_scheduler_name(name)
		print('processing scheduler '+scheduler_args['name'])
		#builderNames
		scheduler_args['builderNames']=scheduler_to_builders[scheduler_args['name']]
		#trigger
		if get_scheduler_spec(spec, 'type')=='time':
			scheduler_args['month']=get_scheduler_spec(spec, 'month')
			scheduler_args['dayOfMonth']=get_scheduler_spec(spec, 'day_of_month')
			scheduler_args['dayOfWeek']=get_scheduler_spec(spec, 'day_of_week')
			scheduler_args['hour']=get_scheduler_spec(spec, 'hour')
			scheduler_args['minute']=get_scheduler_spec(spec, 'minute')
			scheduler_args['branch']='master'
		elif get_scheduler_spec(spec, 'type')=='commit':
			scheduler_args['change_filter']=util.ChangeFilter(branch_re=get_scheduler_spec(spec, 'branch_regex'))
		#codebases
		x=[global_repo_urls[constructicon_name]]+list(all_deps)
		if get_scheduler_spec(spec, 'type')=='force':
			scheduler_args['codebases']=[forcesched.CodebaseParameter(codebase=i) for i in x]
		else:
			scheduler_args['codebases']={
				i: {
					'repository': i,
					'branch': get_scheduler_spec(spec, 'branches').get(i, 'master'),
				} for i in x
			}
		#parameters
		parameters=get_scheduler_spec(spec, 'parameters')
		if get_scheduler_spec(spec, 'type')=='force':
			scheduler_args['properties']=[util.StringParameter(name=parameter_prefix+i, default=j) for i, j in parameters.items(True)]
		else:
			scheduler_args['properties']={parameter_prefix+i: str(j) for i, j in parameters.items(True)}
		#append
		all_schedulers.append({
			'force': ForceScheduler,
			'time': Nightly,
			'commit': AnyBranchScheduler
		}[spec['type']](**scheduler_args))
	#resources - ignore
	constructicon_spec.remove('resources')

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

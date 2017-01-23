template=r'''#construct.py is called by megatron builder to create a devastator master.cfg

import os; folder=os.path.realpath(os.path.dirname(__file__))
import sys; sys.path.append(os.path.join(folder, '..', '..'))

import common

from buildbot.plugins import changes, buildslave, schedulers, steps, util
from buildbot.status import html
from buildbot.status.web import authz
from buildbot.schedulers import forcesched
from twisted.python import log

import calendar, pprint

ForceScheduler=schedulers.ForceScheduler
Nightly=schedulers.Nightly
AnyBranchScheduler=schedulers.AnyBranchScheduler

cybertron=common.cybertron(os.path.join(folder, '..', '..'))

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

def factory(constructicon_name, builder_name, deps, commands, upload):
	deps=sorted(deps)
	work_dir=os.path.join('..', 'constructicons', constructicon_name, constructicon_name)
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
	result.addSteps(
		[
			common.sane_step(steps.SetProperty,
				name='devastator git state',
				property='devastator_git_state',
				value='{{{devastator_git_state}}}',
			),
			common.sane_step(steps.SetProperty,
				name='constructicon git state',
				property='git_state',
				value=global_git_states[constructicon_name],
			),
			git_step(global_repo_urls[constructicon_name], work_dir),
		]
		+
		[git_step(i, os.path.join(work_dir, '..', repo_url_to_name(i))) for i in deps]
		+
		[common.sane_step(steps.ShellCommand,
			name=commands[i][0],
			command=format(commands[i][1]),
			workdir=work_dir,
			env=env,
		) for i in range(len(commands))]
	)
	for i, j in upload.items(True):
		@util.renderer
		def master_dest(properties, j=j):
			return os.path.join(builder_name, str(properties['buildnumber'])+'-constructicon', j)
		devastator_file_server_port=cybertron['devastator_file_server_port']
		@util.renderer
		def url(properties, j=j):
			return (
				'http://{{{devastator_host}}}:'+str(devastator_file_server_port)
				+
				'/'+builder_name+'/'+str(properties['buildnumber'])+'-constructicon'+'/'+j
			)
		step=steps.FileUpload(
			slavesrc=i,
			masterdest=master_dest,
			url=url,
			workdir=work_dir
		)
		result.addStep(step)
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
	'features': get_base('features', {}),
	'deps': get_base('deps', []),
	'precommands': get_base('precommands', []),
	'commands': get_base('commands', []),
	'upload': get_base('upload', {}),
	'schedulers': get_base('schedulers', {}),
}

def check(spec, key, expectations):
	for expectation in expectations:
		if not expectation[0](spec, *expectation[1:-1]):
			error(key+' '+expectation[-1]); return False
		if not expectation[0](base[key], *expectation[1:-1]):
			error('cybertron builder_base '+key+' '+expectation[-1]); return False
	return True

def number(list, prefix):
	return [('{} {}'.format(prefix, i+1), v) for i, v in enumerate(list)]

all_builders=[]
all_schedulers=[]
all_repo_urls=set(global_repo_urls.values())
all_slaves=cybertron['slaves']
errors=1
slave_lock=util.SlaveLock('slave-lock', maxCount=1)
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
	for builder_name, builder_spec in constructicon_spec['builders'].items(True):
		#builder name
		if type(builder_name)!=str:
			error('builder name is not a str'); continue
		builder_name=constructicon_name+'-'+builder_name
		#builder spec
		if not isinstance(builder_spec, Config):
			error('builder spec is not a dict'); continue
		#features
		features=builder_spec.get('features', Config.create({}))
		if not check(features, 'features', [[check_dict, str, str, 'is not a dict of str']]): continue
		for k, v in features.items():
			if k in base['features'] and v!=base['features'][k]: break
		else: k=None
		if k!=None:
			error('feature {}: {} conflicts with cybertron builder_base {}'.format(k, v, base['features'][k])); continue
		features.update(base['features'])
		slave_names=[]
		for slave_name, slave_features in slaves.items():
			for feature, value in features.items(True):
				if feature not in slave_features: break
				if slave_features[feature]!=value: break
			else: slave_names.append(slave_name)
		if not len(slave_names):
			error('no matching slaves'); continue
		#deps
		deps=builder_spec.get('deps', [])
		if not check(deps, 'deps', [[check_list, str, 'is not a list of str']]): continue
		deps+=[i for i in base['deps'] if i not in deps]
		all_repo_urls.update(deps)
		#precommands
		precommands=builder_spec.get('precommands', [])
		if not check(precommands, 'precommands', [
			[lambda x: type(x)==list, 'is not a list'],
			[lambda x: all([t_or_list_of(str, i) for i in x]), 'contains a precommand that is not a str or list of str'],
		]): continue
		precommands=number(base['precommands'], 'cybertron precommand')+number(precommands, 'precommand')
		#commands
		if 'commands' not in builder_spec:
			error('no commands'); continue
		commands=builder_spec['commands']
		if not check(commands, 'commands', [
			[lambda x: type(x)==list, 'is not a list'],
			[lambda x: all([t_or_list_of(str, i) for i in x]), 'contains a command that is not a str or list of str'],
		]): continue
		commands=number(commands, 'command')+number(base['commands'], 'cybertron command')
		#upload
		upload=builder_spec.get('upload', Config.create({}))
		if not check(upload, 'upload', [
			[check_dict, str, str, 'is not a dict of str'],
			[lambda x: all(['..' not in j for i, j in x.items()]), 'destination may not contain ..'],
		]): continue
		if set(base['upload'].values())&set(upload.values()):
			error('upload conflicts with cybertron builder_base upload'); continue
		upload.update(base['upload'])
		#schedulers
		schedulers=builder_spec.get('schedulers', Config.create({}))
		if not check(schedulers, 'schedulers', [
			[lambda x: isinstance(x, Config), 'is not a dict'],
			[lambda x: all([type(i)==str for i in x.keys()]), "has a key that isn't a str"],
			[lambda x: all([isinstance(j, Config) for i, j in x.items()]), "has a value that isn't a dict"],
			[lambda x: all(['type' in j.keys() for i, j in x.items()]), 'contains a scheduler that is missing a type specification'],
			[lambda x: all([j['type'] in ['force', 'time', 'commit'] for i, j in x.items()]), 'contains a scheduler that has an unknown type specification'],
		]): continue
		if intersect(schedulers, base['schedulers']):
			error('schedulers conflicts with cybertron builder_base schedulers'); continue
		schedulers.update(base['schedulers'])
		builder_schedulers=[]
		for name, spec in schedulers.items(True):
			scheduler_args={}
			#name
			scheduler_args['name']=builder_name+'-'+name
			#builderNames
			scheduler_args['builderNames']=[builder_name]
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
			x=[global_repo_urls[constructicon_name]]+deps
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
			builder_schedulers.append({
				'force': ForceScheduler,
				'time': Nightly,
				'commit': AnyBranchScheduler
			}[spec['type']](**scheduler_args))
		#append
		f=factory(constructicon_name, builder_name, deps, precommands+commands, upload)
		unused=builder_spec.unused()
		if unused:
			error('unused configuration keys\n'+pprint.pformat(unused)); continue
		all_builders.append(util.BuilderConfig(
			name=builder_name,
			description=global_repo_urls[constructicon_name]+' '+git_state,
			slavenames=slave_names,
			factory=f,
			locks=[slave_lock.access('exclusive')],
		))
		all_schedulers.extend(builder_schedulers)

git_pollers=[changes.GitPoller(
	repourl=i,
	branches=True,
	workdir='gitpoller-work-'+repo_url_to_name(i)
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
	'title': 'devastator {{{devastator_git_state}}}',
}
'''

import os; folder=os.path.realpath(os.path.dirname(__file__))
import sys; sys.path.append(os.path.join(folder, '..'))

import common

import glob, os, socket, subprocess

def render(template, **kwargs):
	for i, j in kwargs.items(): template=template.replace('{{{'+i+'}}}', str(j))
	return template

def run(constructicons_override={}):
	#collect information
	start=os.getcwd()
	os.chdir(os.path.join(folder, 'constructicons'))
	constructicons={}
	repo_urls={}
	git_states={}
	g=glob.glob(os.path.join('*', 'constructicon.py'))
	assert len(g)
	for i in g:
		name=os.path.split(i)[0]
		constructicons[name]=common.constructicon(name)
		os.chdir(name)
		repo_urls[name]=subprocess.check_output('git config --get remote.origin.url', shell=True).strip()
		git_states[name]=common.git_state()
		print('constructing constructicon - commit: {}, repo: {} '.format(git_states[name], name))
		os.chdir('..')
	constructicons.update(constructicons_override)
	os.chdir('..')
	#make master
	if not os.path.exists('master'): os.makedirs('master')
	os.chdir('master')
	with open('master.cfg', 'w') as file: file.write(render(template,
		constructicons=constructicons,
		repo_urls=repo_urls,
		git_states=git_states,
		devastator_git_state=common.git_state(),
		devastator_host=socket.gethostbyname(socket.gethostname()),
	))
	#reset
	os.chdir(start)

if __name__=='__main__': run()

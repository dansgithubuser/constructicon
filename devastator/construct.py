template=r'''#construct.py is called by megatron builder to create a devastator master.cfg

import os; folder=os.path.realpath(os.path.dirname(__file__))
import sys; sys.path.append(os.path.join(folder, '..', '..'))

import common

from buildbot.plugins import changes, buildslave, schedulers, steps, util
from buildbot.status import html
from buildbot.status.web import authz
from buildbot.schedulers import forcesched

import calendar, pprint

ForceScheduler=schedulers.ForceScheduler
Nightly=schedulers.Nightly
AnyBranchScheduler=schedulers.AnyBranchScheduler

with open(os.path.join(folder, '..', '..', 'cybertron.py')) as file: cybertron=eval(file.read())

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

	def __init__(self, dictionary):
		self.visited=set()
		self.dictionary=dictionary

	def __getitem__(self, k):
		self.visited.add(k)
		return self.dictionary[k]

	def __contains__(self, k): return k in self.dictionary

	def __repr__(self): return 'configuration'+str((self.visited, self.dictionary))

	def get(self, k, default):
		if k in self.dictionary: return self[k]
		else: return default

	def items(self, mark_used=True):
		if mark_used: self.visited=self.dictionary.keys()
		return self.dictionary.items()

	def unused(self, prefix=[]):
		result=[prefix+[k] for k in self.dictionary if k not in self.visited]
		def recurse_list(k, v, f):
			if type(v)==list:
				for i in range(len(v)): recurse_list(k+[i], v[i], f)
			else: f(k, v)
		def recurse(k, v):
			if isinstance(v, Config): result.extend(v.unused(k))
		for k, v in self.dictionary.items(): recurse_list(prefix+[k], v, recurse)
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
	def extract_parameters(d):
		return {i[len(parameter_prefix):]: str(j[0]) for i, j in d.items() if i.startswith(parameter_prefix)}
	@util.renderer
	def env(properties): return extract_parameters(properties.asDict())
	def format(command):
		@util.renderer
		def f(properties): return command.format(**extract_parameters(properties.asDict()))
		return f
	result.addSteps(
		[
			common.sane_step(steps.SetProperty,
				property='devastator_git_state',
				value='{{{devastator_git_state}}}',
			),
			common.sane_step(steps.SetProperty,
				property='git_state',
				value=global_git_states[constructicon_name],
			),
			git_step(global_repo_urls[constructicon_name], work_dir),
		]
		+
		[git_step(i, os.path.join(work_dir, '..', repo_url_to_name(i))) for i in deps]
		+
		[common.sane_step(steps.ShellCommand,
			command=format(commands[i]),
			workdir=work_dir,
			env=env,
		) for i in range(len(commands))]
	)
	for i, j in upload.items():
		@util.renderer
		def master_dest(properties):
			return os.path.join(builder_name, str(properties['buildnumber'])+'-constructicon', j)
		devastator_file_server_port=cybertron['devastator_file_server_port']
		@util.renderer
		def url(properties):
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

all_builders=[]
all_schedulers=[]
all_repo_urls=set(global_repo_urls.values())
all_slaves=cybertron['slaves']
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
	if not isinstance(constructicon_spec, Config):
		error('constructicon is not a dict'); continue
	slaves=cybertron['slaves']
	if 'slaves' in constructicon_spec:
		x={constructicon_name+'-'+i: j for i, j in constructicon_spec['slaves'].items()}
		slaves.update(x)
		all_slaves.update(x)
	for builder_name, builder_spec in constructicon_spec['builders'].items():
		#builder name
		if type(builder_name)!=str:
			error('builder name is not a str'); continue
		builder_name=constructicon_name+'-'+builder_name
		#builder spec
		if not isinstance(builder_spec, Config):
			error('builder spec is not a dict'); continue
		#slave features
		features=builder_spec.get('features', Config.create({}))
		if not isinstance(features, Config):
			error('features is not a dict'); continue
		slave_names=[]
		for slave_name, slave_features in slaves.items():
			for feature, value in features.items():
				if feature not in slave_features: break
				if slave_features[feature]!=value: break
			else: slave_names.append(slave_name)
		if not len(slave_names):
			error('no matching slaves'); continue
		#deps
		deps=builder_spec.get('deps', [])
		if any(type(i)!=str for i in deps):
			error('deps is not a list of str'); continue
		all_repo_urls.update(deps)
		#commands
		if 'commands' not in builder_spec:
			error('no commands'); continue
		commands=builder_spec['commands']
		def t_or_list_of(t, x): return type(x)==t or type(x)==list and all([type(i)==t for i in x])
		if any(not t_or_list_of(str, i) for i in commands):
			error('command is not a str or list of str'); continue
		#upload
		upload=builder_spec.get('upload', Config.create({}))
		if not isinstance(upload, Config) or any([type(i)!=str or type(j)!=str for i, j in upload.items(False)]):
			error('upload is not a dict of str'); continue
		if any(['..' in j for i, j in upload.items()]):
			error('upload destination may not contain ..'); continue
		#schedulers
		schedulers=builder_spec.get('schedulers', Config.create({'force': {'type': 'force'}}))
		if not isinstance(schedulers, Config):
			error('schedulers is not a dict'); continue
		if any([type(i)!=str for i, j in schedulers.items(False)]):
			error("schedulers has a key that isn't a str"); continue
		if any([not isinstance(j, Config) for i, j in schedulers.items(False)]):
			error("schedulers has a value that isn't a dict"); continue
		if any(['type' not in j for i, j in schedulers.items(False)]):
			error('a scheduler is missing a type specification'); continue
		if any([j['type'] not in ['force', 'time', 'commit'] for i, j in schedulers.items(False)]):
			error('a scheduler has an unknown type specification'); continue
		for name, spec in schedulers.items():
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
				scheduler_args['change_filter']=util.ChangeFilter(branch_re=spec.get('branch-regex', '.*'))
			#codebases
			x=[global_repo_urls[constructicon_name]]+deps
			if spec['type']=='force':
				scheduler_args['codebases']=[forcesched.CodebaseParameter(codebase=i) for i in x]
			else:
				scheduler_args['codebases']={i: {'repository': i} for i in x}
			#parameters
			parameters=spec.get('parameters', Config.create({}))
			if spec['type']=='force':
				scheduler_args['properties']=[util.StringParameter(name=parameter_prefix+i, default=j) for i, j in parameters.items()]
			else:
				scheduler_args['properties']={parameter_prefix+i: str(j) for i, j in parameters.items()}
			#append
			all_schedulers.append({
				'force': ForceScheduler,
				'time': Nightly,
				'commit': AnyBranchScheduler
			}[spec['type']](**scheduler_args))
		#append
		all_builders.append(util.BuilderConfig(
			name=builder_name,
			description=global_repo_urls[constructicon_name]+' '+git_state,
			slavenames=slave_names,
			factory=factory(constructicon_name, builder_name, deps, commands, upload),
		))
		unused=builder_spec.unused()
		if unused:
			error('unused configuration keys\n'+pprint.pformat(unused)); continue

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
	'change_source': [changes.GitPoller(repourl=i, branches=True, pollInterval=30) for i in all_repo_urls],
	'mergeRequests': False,
	'debugPassword': 'sesame',
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

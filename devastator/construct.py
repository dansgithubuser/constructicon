template='''#construct.py is called by megatron builder to create a devastator master.cfg

import os; folder=os.path.realpath(os.path.dirname(__file__))
import sys; sys.path.append(os.path.join(folder, '..', '..'))

import common

from buildbot.plugins import buildslave, schedulers, steps, util
from buildbot.status import html
from buildbot.status.web import authz
from buildbot.schedulers import forcesched

import pprint

with open(os.path.join(folder, '..', '..', 'cybertron.py')) as file: cybertron=eval(file.read())

global_constructicons={constructicons}
global_urls={urls}
global_git_states={git_states}

class ConfigException(Exception): pass

class Config:
	@staticmethod
	def create(x):
		if type(x)==dict: return Config({{k: Config.create(v) for k, v in x.items()}})
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

def error(builders, scheds, name, git_state, message):
	builders.append(util.BuilderConfig(
		name=name,
		description=git_state+' error: '+message,
		slavenames=['none'],
		factory=util.BuildFactory()
	))
	scheds.append(schedulers.ForceScheduler(
		name=name+'-force',
		builderNames=[name],
	))

def factory(name, builder_name, deps, commands, upload):
	deps=sorted(deps)
	work_dir=os.path.join('..', 'constructicons', name, name)
	result=util.BuildFactory()
	def git_step(repo_url, work_dir):
		return steps.Git(repourl=repo_url, codebase=repo_url, workdir=work_dir, mode='full', method='fresh')
	result.addSteps(
		[
			steps.SetProperty(property='devastator_git_state', value='{devastator_git_state}'),
			steps.SetProperty(property='git_state', value=global_git_states[name]),
			git_step(global_urls[name], work_dir),
		]
		+
		[git_step(i, os.path.join(work_dir, '..', i.split('/')[-1])) for i in deps]
		+
		[steps.ShellCommand(command=i, workdir=work_dir) for i in commands]
	)
	for i, j in upload.items():
		@util.renderer
		def master_dest(properties):
			return os.path.join(builder_name, str(properties['buildnumber'])+'-constructicon', j)
		devastator_file_server_port=cybertron['devastator_file_server_port']
		@util.renderer
		def url(properties):
			return (
				'http://{devastator_host}:'+str(devastator_file_server_port)
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

builders=[]
scheds=[]
for constructicon_name, constructicon_spec in global_constructicons.items():
	git_state=global_git_states[constructicon_name]
	if type(constructicon_spec)!=dict:
		error(builders, scheds, constructicon_name, git_state, 'constructicon.py is not a dict')
		continue
	for builder_name, builder_spec in constructicon_spec.items():
		#builder name
		if type(builder_name)!=str:
			error(builders, scheds, constructicon_name, git_state, 'builder name is not a str')
			continue
		builder_name=constructicon_name+'-'+builder_name
		#builder spec
		if type(builder_spec)!=dict:
			error(builders, scheds, builder_name, git_state, 'builder spec is not a dict')
			continue
		builder_spec=Config.create(builder_spec)
		#slave features
		features=builder_spec.get('features', Config.create({{}}))
		if not isinstance(features, Config):
			error(builders, scheds, builder_name, git_state, 'features is not a dict')
			continue
		slave_names=[]
		for slave_name, slave_features in cybertron['slaves'].items():
			for feature, value in features.items():
				if feature not in slave_features: break
				if slave_features[feature]!=value: break
			else: slave_names.append(slave_name)
		if not len(slave_names):
			error(builders, scheds, builder_name, git_state, 'no matching slaves')
			continue
		#deps
		deps=builder_spec.get('deps', [])
		if any(type(i)!=str for i in deps):
			error(builders, scheds, builder_name, git_state, 'deps is not a list of str')
			continue
		#commands
		if 'commands' not in builder_spec:
			error(builders, scheds, builder_name, git_state, 'no commands')
			continue
		commands=builder_spec['commands']
		def t_or_list_of(t, x): return type(x)==t or type(x)==list and all([type(i)==t for i in x])
		if any(not t_or_list_of(str, i) for i in commands):
			error(builders, scheds, builder_name, git_state, 'command is not a str or list of str')
			continue
		#upload
		upload=builder_spec.get('upload', Config.create({{}}))
		if not isinstance(upload, Config) or any([type(i)!=str or type(j)!=str for i, j in upload.items(False)]):
			error(builders, scheds, builder_name, git_state, 'upload is not a dict of str')
			continue
		if any(['..' in j for i, j in upload.items()]):
			error(builders, scheds, builder_name, git_state, 'upload destination may not contain ..')
			continue
		#append
		builders.append(util.BuilderConfig(
			name=builder_name,
			description=global_urls[constructicon_name]+' '+git_state,
			slavenames=slave_names,
			factory=factory(constructicon_name, builder_name, deps, commands, upload),
		))
		codebases =[forcesched.CodebaseParameter(codebase=global_urls[constructicon_name])]
		codebases+=[forcesched.CodebaseParameter(codebase=i) for i in deps]
		scheds.append(schedulers.ForceScheduler(
			name=builder_name+'-force',
			builderNames=[builder_name],
			codebases=codebases,
		))
		unused=builder_spec.unused()
		if unused:
			error(builders, scheds, builder_name, git_state, 'unused configuration keys\\n'+pprint.pformat(unused))
			continue

BuildmasterConfig={{
	'db': {{'db_url': 'sqlite:///state.sqlite'}},
	'slaves': [buildslave.BuildSlave(i, common.password) for i in cybertron['slaves'].keys()+['none']],
	'protocols': {{'pb': {{'port': cybertron['devastator_slave_port']}}}},
	'builders': builders,
	'schedulers': scheds,
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
	'title': 'devastator {devastator_git_state}',
}}
'''

import os; folder=os.path.realpath(os.path.dirname(__file__))
import sys; sys.path.append(os.path.join(folder, '..'))

import common

import glob, os, socket, subprocess

def run(constructicons_override={}):
	#collect information
	start=os.getcwd()
	os.chdir(os.path.join(folder, 'constructicons'))
	constructicons={}
	urls={}
	git_states={}
	g=glob.glob(os.path.join('*', 'constructicon.py'))
	assert len(g)
	for i in g:
		name=os.path.split(i)[0]
		with open(i) as file:
			locals={'constructicon': None}
			exec(file.read(), None, locals)
			constructicons[name]=locals['constructicon']
		os.chdir(name)
		urls[name]=subprocess.check_output('git config --get remote.origin.url', shell=True).strip()
		git_states[name]=common.git_state()
		print('constructing constructicon - commit: {}, repo: {} '.format(git_states[name], name))
		os.chdir('..')
	constructicons.update(constructicons_override)
	os.chdir('..')
	#make master
	if not os.path.exists('master'): os.makedirs('master')
	os.chdir('master')
	with open('master.cfg', 'w') as file: file.write(template.format(
		constructicons=constructicons,
		urls=urls,
		git_states=git_states,
		devastator_git_state=common.git_state(),
		devastator_host=socket.gethostbyname(socket.gethostname()),
	))
	#reset
	os.chdir(start)

if __name__=='__main__': run()

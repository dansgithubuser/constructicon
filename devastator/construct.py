template='''#construct.py is called by megatron builder to create a devastator master.cfg

import os; folder=os.path.realpath(os.path.dirname(__file__))
import sys; sys.path.append(os.path.join(folder, '..', '..'))

import common

from buildbot.plugins import buildslave, schedulers, steps, util
from buildbot.status import html
from buildbot.status.web import authz
from buildbot.schedulers import forcesched

with open(os.path.join(folder, '..', '..', 'cybertron.py')) as file: cybertron=eval(file.read())

constructicons={constructicons}
urls={urls}
git_states={git_states}

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
			steps.SetProperty(property='git_state', value='{git_state}'),
			git_step(urls[name], work_dir),
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
for constructicon_name, constructicon_spec in constructicons.items():
	git_state=git_states[constructicon_name]
	if type(constructicon_spec)!=dict:
		error(builders, scheds, constructicon_name, git_state, 'constructicon.py is not a dict')
		continue
	for builder_name, builder_spec in constructicon_spec.items():
		if type(builder_name)!=str:
			error(builders, scheds, constructicon_name, git_state, 'builder name is not a str')
			continue
		builder_name=constructicon_name+'-'+builder_name
		if type(builder_spec)!=dict:
			error(builders, scheds, builder_name, git_state, 'builder spec is not a dict')
			continue
		features=builder_spec.get('features', {{}})
		if type(features)!=dict:
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
		if 'deps' not in builder_spec: builder_spec['deps']=[]
		if any(type(i)!=str for i in builder_spec['deps']):
			error(builders, scheds, builder_name, git_state, 'deps is not a list of str')
			continue
		if 'commands' not in builder_spec:
			error(builders, scheds, builder_name, git_state, 'no commands')
			continue
		commands=builder_spec['commands']
		def t_or_list_of(t, x): return type(x)==t or type(x)==list and all([type(i)==t for i in x])
		if any(not t_or_list_of(str, i) for i in commands):
			error(builders, scheds, builder_name, git_state, 'command is not a str or list of str')
			continue
		if 'upload' not in builder_spec: builder_spec['upload']={{}}
		if type(builder_spec['upload'])!=dict or any([type(i)!=str or type(j)!=str for i, j in builder_spec['upload'].items()]):
			error(builders, scheds, builder_name, git_state, 'upload is not a dict of str')
			continue
		if any(['..' in j for i, j in builder_spec['upload'].items()]):
			error(builders, scheds, builder_name, git_state, 'upload destination may not contain ..')
			continue
		builders.append(util.BuilderConfig(
			name=builder_name,
			description=git_state,
			slavenames=slave_names,
			factory=factory(constructicon_name, builder_name, builder_spec['deps'], commands, builder_spec['upload']),
		))
		codebases =[forcesched.CodebaseParameter(codebase=urls[constructicon_name])]
		codebases+=[forcesched.CodebaseParameter(codebase=i) for i in builder_spec['deps']]
		scheds.append(schedulers.ForceScheduler(
			name=builder_name+'-force',
			builderNames=[builder_name],
			codebases=codebases,
		))

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
	'title': 'devastator {git_state}',
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
		with open(i) as file: constructicons[name]=eval(file.read())
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
		git_state=common.git_state(),
		devastator_host=socket.gethostbyname(socket.gethostname()),
	))
	#reset
	os.chdir(start)

if __name__=='__main__': run()

template='''
import os; folder=os.path.realpath(os.path.dirname(__file__))
import sys; sys.path.append(os.path.join(folder, '..', '..'))

import common

from buildbot.plugins import buildslave, schedulers, steps, util
from buildbot.status import html
from buildbot.status.web import authz

with open(os.path.join(folder, '..', '..', 'cybertron.py')) as file: cybertron=eval(file.read())

constructicons={constructicons}
urls={urls}

def factory(name, command):
	work_dir=os.path.join('..', 'constructicons', name)
	result=util.BuildFactory()
	result.addStep(steps.Git(repourl=urls[name], workdir=work_dir))
	result.addStep(steps.ShellCommand(command=command, workdir=work_dir))
	return result

builders=[]
scheds=[]
for i, j in constructicons.items():
	for platform in j['platforms']:
		builder_name=i+'-'+platform
		builders.append(util.BuilderConfig(
			name=builder_name,
			slavenames=[k[0] for k in cybertron['slaves'].items() if k[1]['platform']==platform],
			factory=factory(i, j['command']),
		))
		scheds.append(schedulers.ForceScheduler(
			name=builder_name+'-force',
			builderNames=[builder_name],
		))

BuildmasterConfig={{
	'db': {{'db_url': 'sqlite:///state.sqlite'}},
	'slaves': [buildslave.BuildSlave(i, common.password) for i in cybertron['slaves'].keys()],
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
	'title': 'devastator',
}}
'''

import glob, os, subprocess

os.chdir('constructicons')
constructicons={}
urls={}
for i in glob.glob(os.path.join('*', 'constructicon.py')):
	name=os.path.split(i)[0]
	with open(i) as file: constructicons[name]=eval(file.read())
	os.chdir(name)
	urls[name]=subprocess.check_output('git config --get remote.origin.url').strip()
	os.chdir('..')
os.chdir('..')

if not os.path.exists('master'): os.makedirs('master')
os.chdir('master')

with open('master.cfg', 'w') as file: file.write(template.format(constructicons=constructicons, urls=urls))

subprocess.check_call('buildbot create-master', shell=True)

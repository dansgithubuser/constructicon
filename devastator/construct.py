#construct.py is called by megatron builder to create a devastator master.cfg

import os; folder=os.path.realpath(os.path.dirname(__file__))
import sys; sys.path.append(os.path.join(folder, '..'))

import common

import glob, os, socket, subprocess

def render(template, **kwargs):
	for i, j in kwargs.items(): template=template.replace('{{{'+i+'}}}', str(j))
	return template

def run(constructicons_override={}):
	cybertron=common.cybertron(os.path.join(folder, '..'))
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
	def read(subtemplate):
		with open(os.path.join(folder, 'template', subtemplate)) as file:
			return file.read()
	template=read('git_poller.py')+read('main.py')
	if not os.path.exists('master'): os.makedirs('master')
	os.chdir('master')
	with open('master.cfg', 'w') as file: file.write(render(template,
		constructicons=constructicons,
		repo_urls=repo_urls,
		git_states=git_states,
		devastator_git_state=common.git_state(),
		devastator_host=cybertron['megatron_hostname'],
	))
	#reset
	os.chdir(start)

if __name__=='__main__': run()

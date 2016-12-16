import os, subprocess

password='uuvdj_ksdjcls2dnwzxo'

def repo_url_to_name(repo_url):
	name=repo_url.split('/')[-1]
	if name.endswith('.git'): name=name[:-4]
	return name

def git_state():
	result=subprocess.check_output('git rev-parse HEAD', shell=True).strip()
	if(
		subprocess.check_output('git diff'         , shell=True).strip()
		or
		subprocess.check_output('git diff --cached', shell=True).strip()
	): result+=' with diff'
	return result

def sane_step(Step, **kwargs):
	if 'haltOnFailure' not in kwargs: kwargs['haltOnFailure']=True
	if 'warnOnWarnings' not in kwargs: kwargs['warnOnWarnings']=True
	return Step(**kwargs)

def execute(file_name, var):
	with open(file_name) as file:
		locals={var: None}
		exec(file.read(), None, locals)
		return locals[var]

def constructicon(folder):
	return execute(os.path.join(folder, 'constructicon.py'), 'constructicon')

def cybertron(folder):
	with open(os.path.join(folder, 'cybertron.txt')) as file:
		cybertron_folder=file.read()
	return execute(os.path.join(cybertron_folder, 'cybertron.py'), 'cybertron')
